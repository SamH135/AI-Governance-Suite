"""API Key Management Service for LLM Provider Keys."""

import asyncio
import secrets
import hashlib
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from enum import Enum
import structlog
from cryptography.fernet import Fernet
import base64

from .database import db_manager
from .redis_client import redis_client
from .exceptions import ValidationError, NotFoundError, SecurityError

logger = structlog.get_logger()

class APIKeyProvider(Enum):
    """Supported API key providers."""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    AZURE = "azure"
    HUGGINGFACE = "huggingface"
    COHERE = "cohere"
    CUSTOM = "custom"

class APIKeyStatus(Enum):
    """API key status."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    EXPIRED = "expired"
    REVOKED = "revoked"

class APIKeyManager:
    """Manages user-specific API keys for LLM providers."""
    
    def __init__(self):
        self.initialized = False
        self.encryption_key = None
        self.fernet = None
        
    async def initialize(self):
        """Initialize the API key manager."""
        if self.initialized:
            return
            
        try:
            # Generate or load encryption key
            await self._setup_encryption()
            
            # Create API keys table if not exists
            await self._create_tables()
            
            self.initialized = True
            logger.info("API Key Manager initialized successfully")
            
        except Exception as e:
            logger.error("API Key Manager initialization failed", error=str(e))
            raise SecurityError(f"API Key Manager initialization failed: {str(e)}")
    
    async def create_api_key(
        self,
        user_id: int,
        provider: APIKeyProvider,
        key_value: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        expires_at: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Create a new API key for a user."""
        
        if not self.initialized:
            await self.initialize()
            
        try:
            # Validate key format
            self._validate_api_key(provider, key_value)
            
            # Encrypt the key
            encrypted_key = self._encrypt_key(key_value)
            
            # Generate key ID
            key_id = secrets.token_urlsafe(16)
            
            # Create key record
            async with db_manager.get_session() as session:
                # Check if user already has a key for this provider
                existing_query = """
                    SELECT id FROM user_api_keys 
                    WHERE user_id = :user_id AND provider = :provider AND status = 'active'
                """
                
                result = await session.execute(
                    existing_query,
                    {"user_id": user_id, "provider": provider.value}
                )
                
                existing_key = result.fetchone()
                if existing_key:
                    # Deactivate existing key
                    await session.execute(
                        "UPDATE user_api_keys SET status = 'inactive', updated_at = NOW() WHERE id = :id",
                        {"id": existing_key[0]}
                    )
                
                # Insert new key
                insert_query = """
                    INSERT INTO user_api_keys 
                    (id, user_id, provider, encrypted_key, name, description, status, expires_at, created_at, updated_at)
                    VALUES (:id, :user_id, :provider, :encrypted_key, :name, :description, :status, :expires_at, NOW(), NOW())
                """
                
                await session.execute(insert_query, {
                    "id": key_id,
                    "user_id": user_id,
                    "provider": provider.value,
                    "encrypted_key": encrypted_key,
                    "name": name or f"{provider.value.title()} API Key",
                    "description": description,
                    "status": APIKeyStatus.ACTIVE.value,
                    "expires_at": expires_at
                })
                
                await session.commit()
            
            # Cache key for quick access
            await self._cache_api_key(user_id, provider, key_value)
            
            logger.info(
                "API key created",
                user_id=user_id,
                provider=provider.value,
                key_id=key_id
            )
            
            return {
                "key_id": key_id,
                "provider": provider.value,
                "name": name or f"{provider.value.title()} API Key",
                "status": APIKeyStatus.ACTIVE.value,
                "created_at": datetime.utcnow().isoformat(),
                "expires_at": expires_at.isoformat() if expires_at else None
            }
            
        except Exception as e:
            logger.error("API key creation failed", user_id=user_id, provider=provider.value, error=str(e))
            raise ValidationError(f"API key creation failed: {str(e)}")
    
    async def get_user_api_keys(self, user_id: int) -> List[Dict[str, Any]]:
        """Get all API keys for a user (without decrypted values)."""
        
        if not self.initialized:
            await self.initialize()
            
        try:
            async with db_manager.get_session() as session:
                query = """
                    SELECT id, provider, name, description, status, expires_at, created_at, updated_at
                    FROM user_api_keys 
                    WHERE user_id = :user_id 
                    ORDER BY created_at DESC
                """
                
                result = await session.execute(query, {"user_id": user_id})
                rows = result.fetchall()
                
                keys = []
                for row in rows:
                    key_data = {
                        "key_id": row[0],
                        "provider": row[1],
                        "name": row[2],
                        "description": row[3],
                        "status": row[4],
                        "expires_at": row[5].isoformat() if row[5] else None,
                        "created_at": row[6].isoformat(),
                        "updated_at": row[7].isoformat(),
                        "is_expired": row[5] and row[5] < datetime.utcnow() if row[5] else False
                    }
                    keys.append(key_data)
                
                return keys
                
        except Exception as e:
            logger.error("Failed to get user API keys", user_id=user_id, error=str(e))
            raise ValidationError(f"Failed to get API keys: {str(e)}")
    
    async def get_api_key(self, user_id: int, provider: APIKeyProvider) -> Optional[str]:
        """Get decrypted API key for a user and provider."""
        
        if not self.initialized:
            await self.initialize()
            
        try:
            # Try cache first
            cached_key = await redis_client.get(f"api_key:{user_id}:{provider.value}")
            if cached_key:
                return cached_key
            
            # Get from database
            async with db_manager.get_session() as session:
                query = """
                    SELECT encrypted_key, expires_at 
                    FROM user_api_keys 
                    WHERE user_id = :user_id AND provider = :provider AND status = 'active'
                    ORDER BY created_at DESC LIMIT 1
                """
                
                result = await session.execute(query, {
                    "user_id": user_id,
                    "provider": provider.value
                })
                
                row = result.fetchone()
                if not row:
                    return None
                
                encrypted_key, expires_at = row
                
                # Check expiration
                if expires_at and expires_at < datetime.utcnow():
                    await self._mark_key_expired(user_id, provider)
                    return None
                
                # Decrypt key
                decrypted_key = self._decrypt_key(encrypted_key)
                
                # Cache for quick access
                await self._cache_api_key(user_id, provider, decrypted_key)
                
                return decrypted_key
                
        except Exception as e:
            logger.error("Failed to get API key", user_id=user_id, provider=provider.value, error=str(e))
            return None
    
    async def update_api_key(
        self,
        user_id: int,
        key_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        status: Optional[APIKeyStatus] = None
    ) -> Dict[str, Any]:
        """Update API key metadata."""
        
        if not self.initialized:
            await self.initialize()
            
        try:
            async with db_manager.get_session() as session:
                # Verify ownership
                verify_query = "SELECT provider FROM user_api_keys WHERE id = :key_id AND user_id = :user_id"
                result = await session.execute(verify_query, {"key_id": key_id, "user_id": user_id})
                row = result.fetchone()
                
                if not row:
                    raise NotFoundError("API Key", key_id)
                
                provider = row[0]
                
                # Build update query
                updates = []
                params = {"key_id": key_id, "user_id": user_id}
                
                if name is not None:
                    updates.append("name = :name")
                    params["name"] = name
                
                if description is not None:
                    updates.append("description = :description")
                    params["description"] = description
                
                if status is not None:
                    updates.append("status = :status")
                    params["status"] = status.value
                    
                    # Clear cache if deactivating
                    if status != APIKeyStatus.ACTIVE:
                        await redis_client.delete(f"api_key:{user_id}:{provider}")
                
                if updates:
                    updates.append("updated_at = NOW()")
                    update_query = f"UPDATE user_api_keys SET {', '.join(updates)} WHERE id = :key_id AND user_id = :user_id"
                    await session.execute(update_query, params)
                    await session.commit()
                
                logger.info("API key updated", user_id=user_id, key_id=key_id)
                
                return {"success": True, "message": "API key updated successfully"}
                
        except Exception as e:
            logger.error("API key update failed", user_id=user_id, key_id=key_id, error=str(e))
            raise ValidationError(f"API key update failed: {str(e)}")
    
    async def delete_api_key(self, user_id: int, key_id: str) -> Dict[str, Any]:
        """Delete an API key."""
        
        if not self.initialized:
            await self.initialize()
            
        try:
            async with db_manager.get_session() as session:
                # Get provider before deletion for cache cleanup
                verify_query = "SELECT provider FROM user_api_keys WHERE id = :key_id AND user_id = :user_id"
                result = await session.execute(verify_query, {"key_id": key_id, "user_id": user_id})
                row = result.fetchone()
                
                if not row:
                    raise NotFoundError("API Key", key_id)
                
                provider = row[0]
                
                # Mark as revoked instead of hard delete for audit trail
                delete_query = """
                    UPDATE user_api_keys 
                    SET status = 'revoked', updated_at = NOW() 
                    WHERE id = :key_id AND user_id = :user_id
                """
                
                await session.execute(delete_query, {"key_id": key_id, "user_id": user_id})
                await session.commit()
                
                # Clear cache
                await redis_client.delete(f"api_key:{user_id}:{provider}")
                
                logger.info("API key deleted", user_id=user_id, key_id=key_id)
                
                return {"success": True, "message": "API key deleted successfully"}
                
        except Exception as e:
            logger.error("API key deletion failed", user_id=user_id, key_id=key_id, error=str(e))
            raise ValidationError(f"API key deletion failed: {str(e)}")
    
    async def validate_api_key(self, user_id: int, provider: APIKeyProvider) -> bool:
        """Validate that a user has a valid API key for a provider."""
        
        key = await self.get_api_key(user_id, provider)
        return key is not None
    
    def _validate_api_key(self, provider: APIKeyProvider, key_value: str):
        """Validate API key format."""
        
        if not key_value or len(key_value.strip()) == 0:
            raise ValidationError("API key cannot be empty")
        
        # Provider-specific validation
        if provider == APIKeyProvider.OPENAI:
            if not key_value.startswith("sk-"):
                raise ValidationError("OpenAI API key must start with 'sk-'")
        
        elif provider == APIKeyProvider.ANTHROPIC:
            if not key_value.startswith("sk-ant-"):
                raise ValidationError("Anthropic API key must start with 'sk-ant-'")
        
        elif provider == APIKeyProvider.GOOGLE:
            if len(key_value) < 20:
                raise ValidationError("Google API key appears to be too short")
        
        # General length check
        if len(key_value) < 10:
            raise ValidationError("API key appears to be too short")
    
    def _encrypt_key(self, key_value: str) -> str:
        """Encrypt API key."""
        return self.fernet.encrypt(key_value.encode()).decode()
    
    def _decrypt_key(self, encrypted_key: str) -> str:
        """Decrypt API key."""
        return self.fernet.decrypt(encrypted_key.encode()).decode()
    
    async def _cache_api_key(self, user_id: int, provider: APIKeyProvider, key_value: str):
        """Cache API key for quick access."""
        cache_key = f"api_key:{user_id}:{provider.value}"
        await redis_client.setex(cache_key, 3600, key_value)  # Cache for 1 hour
    
    async def _mark_key_expired(self, user_id: int, provider: APIKeyProvider):
        """Mark expired keys as expired."""
        async with db_manager.get_session() as session:
            query = """
                UPDATE user_api_keys 
                SET status = 'expired', updated_at = NOW() 
                WHERE user_id = :user_id AND provider = :provider AND expires_at < NOW()
            """
            await session.execute(query, {"user_id": user_id, "provider": provider.value})
            await session.commit()
    
    async def _setup_encryption(self):
        """Setup encryption for API keys."""
        # In production, this should be loaded from secure key management
        encryption_key = base64.urlsafe_b64encode(b"your-32-byte-encryption-key-here!!")
        self.fernet = Fernet(encryption_key)
    
    async def _create_tables(self):
        """Create API keys table if not exists."""
        async with db_manager.get_session() as session:
            create_table_query = """
                CREATE TABLE IF NOT EXISTS user_api_keys (
                    id VARCHAR(64) PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    provider VARCHAR(50) NOT NULL,
                    encrypted_key TEXT NOT NULL,
                    name VARCHAR(255),
                    description TEXT,
                    status VARCHAR(20) DEFAULT 'active',
                    expires_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
                    UNIQUE(user_id, provider, status) 
                );
                
                CREATE INDEX IF NOT EXISTS idx_user_api_keys_user_provider 
                ON user_api_keys(user_id, provider);
                
                CREATE INDEX IF NOT EXISTS idx_user_api_keys_status 
                ON user_api_keys(status);
            """
            
            await session.execute(create_table_query)
            await session.commit()

# Global instance
api_key_manager = APIKeyManager()