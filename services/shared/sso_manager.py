"""Single Sign-On (SSO) Integration Manager."""

import asyncio
import jwt
import json
import base64
import os
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from enum import Enum
import structlog
import httpx
from urllib.parse import urlencode, parse_qs
import xml.etree.ElementTree as ET

from .database import db_manager
from .redis_client import redis_client
from .exceptions import ValidationError, AuthenticationError, SecurityError

logger = structlog.get_logger()

class SSOProvider(Enum):
    """Supported SSO providers."""
    SAML = "saml"
    OAUTH2 = "oauth2"
    OIDC = "oidc"
    AZURE_AD = "azure_ad"
    GOOGLE = "google"
    OKTA = "okta"
    AUTH0 = "auth0"

class SSOManager:
    """Single Sign-On integration manager."""
    
    def __init__(self):
        self.initialized = False
        self.providers = {}
        self.http_client = None
        
    async def initialize(self):
        """Initialize the SSO manager."""
        if self.initialized:
            return
            
        try:
            # Initialize HTTP client
            self.http_client = httpx.AsyncClient(timeout=30.0)
            
            # Create SSO tables
            await self._create_tables()
            
            # Load configured providers
            await self._load_providers()
            
            self.initialized = True
            logger.info("SSO Manager initialized successfully")
            
        except Exception as e:
            logger.error("SSO Manager initialization failed", error=str(e))
            raise SecurityError(f"SSO Manager initialization failed: {str(e)}")
    
    async def configure_provider(
        self,
        provider_type: SSOProvider,
        name: str,
        config: Dict[str, Any],
        created_by: int
    ) -> Dict[str, Any]:
        """Configure a new SSO provider."""
        
        if not self.initialized:
            await self.initialize()
            
        try:
            # Validate configuration
            self._validate_provider_config(provider_type, config)
            
            # Encrypt sensitive data
            encrypted_config = await self._encrypt_config(config)
            
            async with db_manager.get_session() as session:
                # Check if provider already exists
                check_query = "SELECT id FROM sso_providers WHERE name = :name"
                result = await session.execute(check_query, {"name": name})
                
                if result.fetchone():
                    raise ValidationError(f"SSO provider '{name}' already exists")
                
                # Insert provider
                insert_query = """
                    INSERT INTO sso_providers 
                    (name, provider_type, config, is_active, created_by, created_at, updated_at)
                    VALUES (:name, :provider_type, :config, true, :created_by, NOW(), NOW())
                    RETURNING id
                """
                
                result = await session.execute(insert_query, {
                    "name": name,
                    "provider_type": provider_type.value,
                    "config": json.dumps(encrypted_config),
                    "created_by": created_by
                })
                
                provider_id = result.fetchone()[0]
                await session.commit()
                
                # Cache provider
                self.providers[name] = {
                    "id": provider_id,
                    "type": provider_type,
                    "config": config,
                    "is_active": True
                }
                
                logger.info("SSO provider configured", name=name, type=provider_type.value)
                
                return {
                    "provider_id": provider_id,
                    "name": name,
                    "provider_type": provider_type.value,
                    "is_active": True,
                    "created_at": datetime.utcnow().isoformat()
                }
                
        except Exception as e:
            logger.error("SSO provider configuration failed", name=name, error=str(e))
            raise ValidationError(f"SSO provider configuration failed: {str(e)}")
    
    async def initiate_sso_login(
        self,
        provider_name: str,
        redirect_uri: str,
        state: Optional[str] = None
    ) -> Dict[str, Any]:
        """Initiate SSO login flow."""
        
        if not self.initialized:
            await self.initialize()
            
        try:
            if provider_name not in self.providers:
                raise ValidationError(f"SSO provider '{provider_name}' not found")
            
            provider = self.providers[provider_name]
            
            if not provider["is_active"]:
                raise ValidationError(f"SSO provider '{provider_name}' is not active")
            
            provider_type = provider["type"]
            config = provider["config"]
            
            # Generate state if not provided
            if not state:
                state = base64.urlsafe_b64encode(json.dumps({
                    "provider": provider_name,
                    "timestamp": datetime.utcnow().isoformat(),
                    "redirect_uri": redirect_uri
                }).encode()).decode()
            
            # Store state in Redis for validation
            await redis_client.setex(f"sso_state:{state}", 600, provider_name)  # 10 minutes
            
            if provider_type == SSOProvider.SAML:
                return await self._initiate_saml_login(config, redirect_uri, state)
            
            elif provider_type in [SSOProvider.OAUTH2, SSOProvider.OIDC, SSOProvider.AZURE_AD, SSOProvider.GOOGLE]:
                return await self._initiate_oauth_login(config, redirect_uri, state)
            
            else:
                raise ValidationError(f"Unsupported SSO provider type: {provider_type.value}")
                
        except Exception as e:
            logger.error("SSO login initiation failed", provider=provider_name, error=str(e))
            raise AuthenticationError(f"SSO login initiation failed: {str(e)}")
    
    async def handle_sso_callback(
        self,
        provider_name: str,
        callback_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle SSO callback and authenticate user."""
        
        if not self.initialized:
            await self.initialize()
            
        try:
            if provider_name not in self.providers:
                raise ValidationError(f"SSO provider '{provider_name}' not found")
            
            provider = self.providers[provider_name]
            provider_type = provider["type"]
            config = provider["config"]
            
            # Validate state
            state = callback_data.get("state")
            if state:
                cached_provider = await redis_client.get(f"sso_state:{state}")
                if not cached_provider or cached_provider != provider_name:
                    raise AuthenticationError("Invalid SSO state")
                
                # Clean up state
                await redis_client.delete(f"sso_state:{state}")
            
            # Handle callback based on provider type
            if provider_type == SSOProvider.SAML:
                user_info = await self._handle_saml_callback(config, callback_data)
            
            elif provider_type in [SSOProvider.OAUTH2, SSOProvider.OIDC, SSOProvider.AZURE_AD, SSOProvider.GOOGLE]:
                user_info = await self._handle_oauth_callback(config, callback_data)
            
            else:
                raise ValidationError(f"Unsupported SSO provider type: {provider_type.value}")
            
            # Create or update user
            user = await self._create_or_update_sso_user(provider_name, user_info)
            
            # Generate platform JWT token
            platform_token = await self._generate_platform_token(user)
            
            logger.info("SSO authentication successful", 
                       provider=provider_name, 
                       user_id=user["id"])
            
            return {
                "success": True,
                "user": user,
                "token": platform_token,
                "provider": provider_name
            }
            
        except Exception as e:
            logger.error("SSO callback handling failed", provider=provider_name, error=str(e))
            raise AuthenticationError(f"SSO authentication failed: {str(e)}")
    
    async def get_sso_providers(self) -> List[Dict[str, Any]]:
        """Get list of configured SSO providers."""
        
        if not self.initialized:
            await self.initialize()
            
        try:
            async with db_manager.get_session() as session:
                query = """
                    SELECT id, name, provider_type, is_active, created_at, updated_at
                    FROM sso_providers
                    ORDER BY name
                """
                
                result = await session.execute(query)
                providers = []
                
                for row in result.fetchall():
                    providers.append({
                        "id": row[0],
                        "name": row[1],
                        "provider_type": row[2],
                        "is_active": row[3],
                        "created_at": row[4].isoformat(),
                        "updated_at": row[5].isoformat()
                    })
                
                return providers
                
        except Exception as e:
            logger.error("Failed to get SSO providers", error=str(e))
            return []
    
    async def _initiate_saml_login(
        self,
        config: Dict[str, Any],
        redirect_uri: str,
        state: str
    ) -> Dict[str, Any]:
        """Initiate SAML login flow."""
        
        # Create SAML AuthnRequest
        authn_request = self._create_saml_authn_request(config, redirect_uri, state)
        
        # Encode and redirect
        encoded_request = base64.b64encode(authn_request.encode()).decode()
        
        sso_url = config["sso_url"]
        login_url = f"{sso_url}?SAMLRequest={encoded_request}&RelayState={state}"
        
        return {
            "login_url": login_url,
            "method": "redirect"
        }
    
    async def _initiate_oauth_login(
        self,
        config: Dict[str, Any],
        redirect_uri: str,
        state: str
    ) -> Dict[str, Any]:
        """Initiate OAuth/OIDC login flow."""
        
        auth_params = {
            "client_id": config["client_id"],
            "response_type": "code",
            "redirect_uri": redirect_uri,
            "state": state,
            "scope": config.get("scope", "openid profile email")
        }
        
        auth_url = config["authorization_endpoint"]
        login_url = f"{auth_url}?{urlencode(auth_params)}"
        
        return {
            "login_url": login_url,
            "method": "redirect"
        }
    
    async def _handle_saml_callback(
        self,
        config: Dict[str, Any],
        callback_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle SAML callback and extract user info."""
        
        saml_response = callback_data.get("SAMLResponse")
        if not saml_response:
            raise AuthenticationError("Missing SAML response")
        
        # Decode SAML response
        decoded_response = base64.b64decode(saml_response).decode()
        
        # Parse XML
        root = ET.fromstring(decoded_response)
        
        # Extract user attributes (simplified)
        user_info = {
            "email": self._extract_saml_attribute(root, "email"),
            "name": self._extract_saml_attribute(root, "name"),
            "first_name": self._extract_saml_attribute(root, "first_name"),
            "last_name": self._extract_saml_attribute(root, "last_name"),
            "groups": self._extract_saml_attribute(root, "groups", multiple=True)
        }
        
        return user_info
    
    async def _handle_oauth_callback(
        self,
        config: Dict[str, Any],
        callback_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Handle OAuth/OIDC callback and extract user info."""
        
        code = callback_data.get("code")
        if not code:
            raise AuthenticationError("Missing authorization code")
        
        # Exchange code for token
        token_data = {
            "grant_type": "authorization_code",
            "code": code,
            "client_id": config["client_id"],
            "client_secret": config["client_secret"],
            "redirect_uri": callback_data.get("redirect_uri")
        }
        
        token_response = await self.http_client.post(
            config["token_endpoint"],
            data=token_data
        )
        
        if token_response.status_code != 200:
            raise AuthenticationError("Failed to exchange authorization code")
        
        tokens = token_response.json()
        access_token = tokens.get("access_token")
        id_token = tokens.get("id_token")
        
        # Get user info
        if id_token:
            # Decode JWT (simplified - should verify signature in production)
            user_info = jwt.decode(id_token, options={"verify_signature": False})
        else:
            # Use userinfo endpoint
            userinfo_response = await self.http_client.get(
                config["userinfo_endpoint"],
                headers={"Authorization": f"Bearer {access_token}"}
            )
            
            if userinfo_response.status_code != 200:
                raise AuthenticationError("Failed to get user info")
            
            user_info = userinfo_response.json()
        
        return {
            "email": user_info.get("email"),
            "name": user_info.get("name"),
            "first_name": user_info.get("given_name"),
            "last_name": user_info.get("family_name"),
            "groups": user_info.get("groups", [])
        }
    
    async def _create_or_update_sso_user(
        self,
        provider_name: str,
        user_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create or update user from SSO information."""
        
        email = user_info.get("email")
        if not email:
            raise AuthenticationError("Email not provided by SSO provider")
        
        async with db_manager.get_session() as session:
            # Check if user exists
            user_query = "SELECT id, email, name FROM users WHERE email = :email"
            result = await session.execute(user_query, {"email": email})
            user_row = result.fetchone()
            
            if user_row:
                # Update existing user
                user_id = user_row[0]
                
                update_query = """
                    UPDATE users 
                    SET name = :name, updated_at = NOW()
                    WHERE id = :user_id
                """
                
                await session.execute(update_query, {
                    "user_id": user_id,
                    "name": user_info.get("name") or f"{user_info.get('first_name', '')} {user_info.get('last_name', '')}".strip()
                })
                
            else:
                # Create new user
                insert_query = """
                    INSERT INTO users (email, name, is_sso_user, created_at, updated_at)
                    VALUES (:email, :name, true, NOW(), NOW())
                    RETURNING id
                """
                
                result = await session.execute(insert_query, {
                    "email": email,
                    "name": user_info.get("name") or f"{user_info.get('first_name', '')} {user_info.get('last_name', '')}".strip()
                })
                
                user_id = result.fetchone()[0]
            
            # Record SSO login
            sso_login_query = """
                INSERT INTO sso_logins (user_id, provider_name, provider_user_info, created_at)
                VALUES (:user_id, :provider_name, :user_info, NOW())
            """
            
            await session.execute(sso_login_query, {
                "user_id": user_id,
                "provider_name": provider_name,
                "user_info": json.dumps(user_info)
            })
            
            await session.commit()
            
            return {
                "id": user_id,
                "email": email,
                "name": user_info.get("name"),
                "is_sso_user": True
            }
    
    def _validate_provider_config(self, provider_type: SSOProvider, config: Dict[str, Any]):
        """Validate SSO provider configuration."""
        
        if provider_type == SSOProvider.SAML:
            required_fields = ["sso_url", "entity_id", "certificate"]
            
        elif provider_type in [SSOProvider.OAUTH2, SSOProvider.OIDC]:
            required_fields = ["client_id", "client_secret", "authorization_endpoint", "token_endpoint"]
            
        elif provider_type == SSOProvider.AZURE_AD:
            required_fields = ["client_id", "client_secret", "tenant_id"]
            
        elif provider_type == SSOProvider.GOOGLE:
            required_fields = ["client_id", "client_secret"]
            
        else:
            required_fields = ["client_id", "client_secret"]
        
        missing_fields = [field for field in required_fields if field not in config]
        
        if missing_fields:
            raise ValidationError(f"Missing required configuration fields: {', '.join(missing_fields)}")
    
    async def _encrypt_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Encrypt sensitive configuration data."""
        # In production, use proper encryption
        # For now, just return as-is
        return config
    
    def _create_saml_authn_request(
        self,
        config: Dict[str, Any],
        redirect_uri: str,
        state: str
    ) -> str:
        """Create SAML AuthnRequest."""
        
        # Simplified SAML AuthnRequest
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<samlp:AuthnRequest xmlns:samlp="urn:oasis:names:tc:SAML:2.0:protocol"
                    xmlns:saml="urn:oasis:names:tc:SAML:2.0:assertion"
                    ID="_{state}"
                    Version="2.0"
                    IssueInstant="{datetime.utcnow().isoformat()}Z"
                    Destination="{config['sso_url']}"
                    AssertionConsumerServiceURL="{redirect_uri}">
    <saml:Issuer>{config['entity_id']}</saml:Issuer>
</samlp:AuthnRequest>"""
    
    def _extract_saml_attribute(
        self,
        root: ET.Element,
        attribute_name: str,
        multiple: bool = False
    ) -> Any:
        """Extract attribute from SAML response."""
        
        # Simplified attribute extraction
        # In production, use proper SAML parsing library
        
        namespaces = {
            'saml': 'urn:oasis:names:tc:SAML:2.0:assertion',
            'samlp': 'urn:oasis:names:tc:SAML:2.0:protocol'
        }
        
        # Find attribute elements
        attributes = root.findall(f".//saml:Attribute[@Name='{attribute_name}']", namespaces)
        
        if not attributes:
            return [] if multiple else None
        
        values = []
        for attr in attributes:
            attr_values = attr.findall("saml:AttributeValue", namespaces)
            for value in attr_values:
                if value.text:
                    values.append(value.text)
        
        return values if multiple else (values[0] if values else None)
    
    async def _generate_platform_token(self, user: Dict[str, Any]) -> str:
        """Generate platform JWT token for SSO user."""
        
        payload = {
            "user_id": user["id"],
            "email": user["email"],
            "name": user["name"],
            "is_sso_user": True,
            "iat": datetime.utcnow(),
            "exp": datetime.utcnow() + timedelta(hours=24)
        }
        
        # In production, use proper JWT signing
        secret_key = os.getenv("JWT_SECRET")
        if not secret_key:
            raise ValueError("JWT_SECRET environment variable must be set")
        token = jwt.encode(payload, secret_key, algorithm="HS256")
        
        return token
    
    async def _load_providers(self):
        """Load configured SSO providers from database."""
        
        try:
            async with db_manager.get_session() as session:
                query = "SELECT name, provider_type, config, is_active FROM sso_providers WHERE is_active = true"
                result = await session.execute(query)
                
                for row in result.fetchall():
                    name, provider_type, config_json, is_active = row
                    
                    try:
                        config = json.loads(config_json)
                        self.providers[name] = {
                            "type": SSOProvider(provider_type),
                            "config": config,
                            "is_active": is_active
                        }
                    except Exception as e:
                        logger.error("Failed to load SSO provider", name=name, error=str(e))
                
                logger.info("SSO providers loaded", count=len(self.providers))
                
        except Exception as e:
            logger.error("Failed to load SSO providers", error=str(e))
    
    async def _create_tables(self):
        """Create SSO tables."""
        
        async with db_manager.get_session() as session:
            create_tables_query = """
                -- SSO providers table
                CREATE TABLE IF NOT EXISTS sso_providers (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(100) UNIQUE NOT NULL,
                    provider_type VARCHAR(50) NOT NULL,
                    config JSONB NOT NULL,
                    is_active BOOLEAN DEFAULT true,
                    created_by INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                
                -- SSO logins table
                CREATE TABLE IF NOT EXISTS sso_logins (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    provider_name VARCHAR(100) NOT NULL,
                    provider_user_info JSONB,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                );
                
                -- Add SSO flag to users table if not exists
                DO $$ 
                BEGIN
                    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                                  WHERE table_name='users' AND column_name='is_sso_user') THEN
                        ALTER TABLE users ADD COLUMN is_sso_user BOOLEAN DEFAULT false;
                    END IF;
                END $$;
                
                -- Indexes
                CREATE INDEX IF NOT EXISTS idx_sso_providers_active ON sso_providers(is_active);
                CREATE INDEX IF NOT EXISTS idx_sso_logins_user_id ON sso_logins(user_id);
                CREATE INDEX IF NOT EXISTS idx_sso_logins_provider ON sso_logins(provider_name);
            """
            
            await session.execute(create_tables_query)
            await session.commit()
    
    async def close(self):
        """Close SSO manager resources."""
        
        if self.http_client:
            await self.http_client.aclose()
        
        logger.info("SSO Manager closed")

# Global instance
sso_manager = SSOManager()