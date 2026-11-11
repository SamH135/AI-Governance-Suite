"""Simple API Key Service for Gateway"""

import secrets
import logging
import os
from typing import List, Dict, Any, Optional
from datetime import datetime
from cryptography.fernet import Fernet
import base64
from enum import Enum

logger = logging.getLogger(__name__)

class APIKeyProvider(str, Enum):
    """Supported API key providers."""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    AZURE = "azure"
    HUGGINGFACE = "huggingface"
    COHERE = "cohere"
    CUSTOM = "custom"

class SimpleAPIKeyService:
    """Simplified API key service for the gateway."""
    
    def __init__(self, db_pool):
        self.db_pool = db_pool
        # Encryption key from environment variable
        encryption_key_str = os.getenv("API_KEY_ENCRYPTION_KEY")
        if not encryption_key_str:
            raise ValueError("API_KEY_ENCRYPTION_KEY environment variable must be set")
        # Ensure the key is properly base64-encoded for Fernet
        try:
            encryption_key = base64.urlsafe_b64encode(encryption_key_str.encode()) if len(encryption_key_str) != 44 else encryption_key_str
            self.fernet = Fernet(encryption_key)
        except Exception as e:
            raise ValueError(f"Invalid API_KEY_ENCRYPTION_KEY: {e}")
    
    def _encrypt_key(self, key_value: str) -> str:
        """Encrypt API key."""
        return self.fernet.encrypt(key_value.encode()).decode()
    
    def _decrypt_key(self, encrypted_key: str) -> str:
        """Decrypt API key."""
        return self.fernet.decrypt(encrypted_key.encode()).decode()
    
    def _validate_api_key(self, provider: str, key_value: str):
        """Validate API key format."""
        if not key_value or len(key_value.strip()) == 0:
            raise ValueError("API key cannot be empty")
        
        # Provider-specific validation
        if provider == "openai":
            if not key_value.startswith("sk-"):
                raise ValueError("OpenAI API key must start with 'sk-'")
        elif provider == "anthropic":
            if not key_value.startswith("sk-ant-"):
                raise ValueError("Anthropic API key must start with 'sk-ant-'")
        elif provider == "google":
            if len(key_value) < 20:
                raise ValueError("Google API key appears to be too short")
        
        # General length check
        if len(key_value) < 10:
            raise ValueError("API key appears to be too short")

    async def get_user_api_keys(self, user_id: int) -> List[Dict[str, Any]]:
        """Get all API keys for a user (without decrypted values)."""
        try:
            async with self.db_pool.acquire() as conn:
                query = """
                    SELECT id, provider, name, description, status, expires_at, created_at, updated_at
                    FROM user_api_keys 
                    WHERE user_id = $1 
                    ORDER BY created_at DESC
                """
                
                rows = await conn.fetch(query, user_id)
                
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
            logger.error(f"Failed to get user API keys for user {user_id}: {e}")
            raise

    async def create_user_api_key(
        self, 
        user_id: int, 
        provider: str, 
        key_value: str, 
        name: Optional[str] = None,
        description: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a new API key for a user."""
        try:
            # Validate key format
            self._validate_api_key(provider, key_value)
            
            # Encrypt the key
            encrypted_key = self._encrypt_key(key_value)
            
            # Generate key ID
            key_id = secrets.token_urlsafe(16)
            
            async with self.db_pool.acquire() as conn:
                # Check if user already has a key for this provider
                existing_query = """
                    SELECT id FROM user_api_keys 
                    WHERE user_id = $1 AND provider = $2 AND status = 'active'
                """
                
                result = await conn.fetchrow(existing_query, user_id, provider)
                if result:
                    # Deactivate existing key
                    await conn.execute(
                        "UPDATE user_api_keys SET status = 'inactive', updated_at = CURRENT_TIMESTAMP WHERE id = $1",
                        result[0]
                    )
                
                # Insert new key
                insert_query = """
                    INSERT INTO user_api_keys 
                    (id, user_id, provider, encrypted_key, name, description, status, created_at, updated_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """
                
                await conn.execute(insert_query,
                    key_id,
                    user_id,
                    provider,
                    encrypted_key,
                    name or f"{provider.title()} API Key",
                    description,
                    'active'
                )
            
            logger.info(f"API key created for user {user_id}, provider {provider}")
            
            return {
                "key_id": key_id,
                "provider": provider,
                "name": name or f"{provider.title()} API Key",
                "status": "active",
                "created_at": datetime.utcnow().isoformat()
            }
            
        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Failed to create user API key for user {user_id}: {e}")
            raise

    async def update_user_api_key(
        self, 
        user_id: int, 
        key_id: str, 
        name: Optional[str] = None,
        description: Optional[str] = None
    ) -> Dict[str, Any]:
        """Update an API key's metadata."""
        try:
            async with self.db_pool.acquire() as conn:
                # Verify ownership
                verify_query = "SELECT provider FROM user_api_keys WHERE id = $1 AND user_id = $2"
                result = await conn.fetchrow(verify_query, key_id, user_id)
                
                if not result:
                    raise ValueError("API Key not found")
                
                # Build update query
                updates = []
                params = [user_id, key_id]
                param_count = 3
                
                if name is not None:
                    updates.append(f"name = ${param_count}")
                    params.insert(-1, name)  # Insert before key_id
                    param_count += 1
                
                if description is not None:
                    updates.append(f"description = ${param_count}")
                    params.insert(-1, description)  # Insert before key_id
                    param_count += 1
                
                if updates:
                    updates.append("updated_at = CURRENT_TIMESTAMP")
                    update_query = f"UPDATE user_api_keys SET {', '.join(updates)} WHERE user_id = $1 AND id = $2"
                    await conn.execute(update_query, *params)
                
                logger.info(f"API key updated: {key_id} for user {user_id}")
                
                return {"success": True, "message": "API key updated successfully"}
                
        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Failed to update user API key {key_id} for user {user_id}: {e}")
            raise

    async def delete_user_api_key(self, user_id: int, key_id: str) -> Dict[str, Any]:
        """Delete an API key."""
        try:
            async with self.db_pool.acquire() as conn:
                # Verify ownership and mark as revoked
                result = await conn.execute(
                    "UPDATE user_api_keys SET status = 'revoked', updated_at = CURRENT_TIMESTAMP WHERE id = $1 AND user_id = $2",
                    key_id, user_id
                )
                
                # Check if any row was actually updated
                if result == 'UPDATE 0':
                    raise ValueError("API Key not found")
                
                logger.info(f"API key deleted: {key_id} for user {user_id}")
                
                return {"success": True, "message": "API key deleted successfully"}
                
        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Failed to delete user API key {key_id} for user {user_id}: {e}")
            raise

    async def get_api_key_value(self, user_id: int, key_id: str) -> Optional[str]:
        """Get decrypted API key value for a specific key ID."""
        try:
            async with self.db_pool.acquire() as conn:
                # Get the encrypted key, verifying user ownership and active status
                query = """
                    SELECT encrypted_key FROM user_api_keys 
                    WHERE id = $1 AND user_id = $2 AND status = 'active'
                """
                
                row = await conn.fetchrow(query, key_id, user_id)
                if not row:
                    return None
                
                encrypted_key = row[0]
                
                # Decrypt and return the key
                decrypted_key = self._decrypt_key(encrypted_key)
                logger.info(f"Retrieved decrypted API key for user {user_id}, key {key_id}")
                
                return decrypted_key
                
        except Exception as e:
            logger.error(f"Failed to get API key value {key_id} for user {user_id}: {e}")
            raise