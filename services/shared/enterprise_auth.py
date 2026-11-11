"""
Enterprise Authentication and Authorization Service
Provides SSO integration, advanced RBAC, and enterprise security features
"""

import os
import jwt
import json
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Union, Set
from enum import Enum
import structlog
from dataclasses import dataclass
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
import httpx

try:
    from saml2 import BINDING_HTTP_POST, BINDING_HTTP_REDIRECT
    from saml2.client import Saml2Client
    from saml2.config import Config
    SAML_AVAILABLE = True
except ImportError:
    SAML_AVAILABLE = False

try:
    import ldap3
    LDAP_AVAILABLE = True
except ImportError:
    LDAP_AVAILABLE = False
    ldap3 = None

from .database import db_manager
from .models import User
from .exceptions import ValidationError, AuthenticationError, AuthorizationError

logger = structlog.get_logger()

class PermissionAction(str, Enum):
    """Standard permission actions."""
    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    EXECUTE = "execute"
    APPROVE = "approve"
    ADMIN = "admin"

class ResourceType(str, Enum):
    """Resource types for permission management."""
    SYSTEM = "system"
    DOCUMENT = "document"
    TEST = "test"
    PROMPT = "prompt"
    EVALUATION = "evaluation"
    USER = "user"
    ROLE = "role"
    REPORT = "report"
    WORKFLOW = "workflow"

class SSOProvider(str, Enum):
    """Supported SSO providers."""
    SAML = "saml"
    OAUTH2 = "oauth2"
    LDAP = "ldap"
    AZURE_AD = "azure_ad"
    OKTA = "okta"
    GOOGLE = "google"

@dataclass
class Permission:
    """Represents a permission."""
    resource_type: ResourceType
    action: PermissionAction
    resource_id: Optional[str] = None
    conditions: Optional[Dict[str, Any]] = None

@dataclass
class Role:
    """Represents a role with permissions."""
    role_id: str
    name: str
    description: str
    permissions: List[Permission]
    inherits_from: Optional[List[str]] = None
    is_system_role: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

@dataclass
class UserSession:
    """Represents a user session."""
    session_id: str
    user_id: int
    roles: List[str]
    permissions: Set[str]
    sso_provider: Optional[str] = None
    sso_session_id: Optional[str] = None
    created_at: datetime = None
    expires_at: datetime = None
    last_activity: datetime = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None

class EnterpriseAuthService:
    """Enterprise authentication and authorization service."""
    
    def __init__(self):
        self.initialized = False
        self.roles: Dict[str, Role] = {}
        self.role_hierarchy: Dict[str, List[str]] = {}
        self.active_sessions: Dict[str, UserSession] = {}
        self.sso_providers: Dict[str, Dict[str, Any]] = {}
        self.http_client: Optional[httpx.AsyncClient] = None
        
        # Built-in system roles
        self.system_roles = {
            "super_admin": Role(
                role_id="super_admin",
                name="Super Administrator",
                description="Full system access",
                permissions=self._get_all_permissions(),
                is_system_role=True
            ),
            "admin": Role(
                role_id="admin",
                name="Administrator",
                description="Administrative access",
                permissions=[
                    Permission(ResourceType.SYSTEM, PermissionAction.READ),
                    Permission(ResourceType.USER, PermissionAction.CREATE),
                    Permission(ResourceType.USER, PermissionAction.READ),
                    Permission(ResourceType.USER, PermissionAction.UPDATE),
                    Permission(ResourceType.ROLE, PermissionAction.READ),
                    Permission(ResourceType.DOCUMENT, PermissionAction.ADMIN),
                    Permission(ResourceType.TEST, PermissionAction.ADMIN),
                    Permission(ResourceType.EVALUATION, PermissionAction.ADMIN),
                    Permission(ResourceType.WORKFLOW, PermissionAction.ADMIN)
                ],
                is_system_role=True
            ),
            "compliance_officer": Role(
                role_id="compliance_officer",
                name="Compliance Officer",
                description="Compliance management access",
                permissions=[
                    Permission(ResourceType.EVALUATION, PermissionAction.CREATE),
                    Permission(ResourceType.EVALUATION, PermissionAction.READ),
                    Permission(ResourceType.EVALUATION, PermissionAction.UPDATE),
                    Permission(ResourceType.EVALUATION, PermissionAction.APPROVE),
                    Permission(ResourceType.DOCUMENT, PermissionAction.CREATE),
                    Permission(ResourceType.DOCUMENT, PermissionAction.READ),
                    Permission(ResourceType.DOCUMENT, PermissionAction.APPROVE),
                    Permission(ResourceType.WORKFLOW, PermissionAction.READ),
                    Permission(ResourceType.WORKFLOW, PermissionAction.APPROVE),
                    Permission(ResourceType.REPORT, PermissionAction.READ)
                ],
                is_system_role=True
            ),
            "developer": Role(
                role_id="developer",
                name="Developer",
                description="Development and testing access",
                permissions=[
                    Permission(ResourceType.SYSTEM, PermissionAction.CREATE),
                    Permission(ResourceType.SYSTEM, PermissionAction.READ),
                    Permission(ResourceType.SYSTEM, PermissionAction.UPDATE),
                    Permission(ResourceType.TEST, PermissionAction.CREATE),
                    Permission(ResourceType.TEST, PermissionAction.READ),
                    Permission(ResourceType.TEST, PermissionAction.EXECUTE),
                    Permission(ResourceType.PROMPT, PermissionAction.CREATE),
                    Permission(ResourceType.PROMPT, PermissionAction.READ),
                    Permission(ResourceType.PROMPT, PermissionAction.UPDATE),
                    Permission(ResourceType.EVALUATION, PermissionAction.READ),
                    Permission(ResourceType.DOCUMENT, PermissionAction.READ)
                ],
                is_system_role=True
            ),
            "analyst": Role(
                role_id="analyst",
                name="Analyst",
                description="Analysis and reporting access",
                permissions=[
                    Permission(ResourceType.SYSTEM, PermissionAction.READ),
                    Permission(ResourceType.TEST, PermissionAction.READ),
                    Permission(ResourceType.EVALUATION, PermissionAction.READ),
                    Permission(ResourceType.DOCUMENT, PermissionAction.READ),
                    Permission(ResourceType.REPORT, PermissionAction.CREATE),
                    Permission(ResourceType.REPORT, PermissionAction.READ)
                ],
                is_system_role=True
            ),
            "viewer": Role(
                role_id="viewer",
                name="Viewer",
                description="Read-only access",
                permissions=[
                    Permission(ResourceType.SYSTEM, PermissionAction.READ),
                    Permission(ResourceType.TEST, PermissionAction.READ),
                    Permission(ResourceType.EVALUATION, PermissionAction.READ),
                    Permission(ResourceType.DOCUMENT, PermissionAction.READ),
                    Permission(ResourceType.REPORT, PermissionAction.READ)
                ],
                is_system_role=True
            )
        }
    
    async def initialize(self):
        """Initialize the enterprise auth service."""
        if self.initialized:
            return
        
        try:
            # Initialize HTTP client
            self.http_client = httpx.AsyncClient(timeout=30.0)
            
            # Load system roles
            self.roles.update(self.system_roles)
            
            # Setup role hierarchy
            self.role_hierarchy = {
                "super_admin": [],
                "admin": ["compliance_officer", "developer", "analyst", "viewer"],
                "compliance_officer": ["analyst", "viewer"],
                "developer": ["viewer"],
                "analyst": ["viewer"],
                "viewer": []
            }
            
            # Initialize SSO providers
            await self._initialize_sso_providers()
            
            # Start session cleanup task
            asyncio.create_task(self._session_cleanup_task())
            
            self.initialized = True
            logger.info("Enterprise auth service initialized")
            
        except Exception as e:
            logger.error("Failed to initialize enterprise auth service", error=str(e))
            raise ValidationError(f"Enterprise auth initialization failed: {str(e)}")
    
    async def create_role(
        self,
        role_id: str,
        name: str,
        description: str,
        permissions: List[Permission],
        inherits_from: Optional[List[str]] = None
    ) -> Role:
        """Create a custom role."""
        if not self.initialized:
            await self.initialize()
        
        if role_id in self.roles:
            raise ValidationError(f"Role {role_id} already exists")
        
        # Validate inherited roles
        if inherits_from:
            for parent_role in inherits_from:
                if parent_role not in self.roles:
                    raise ValidationError(f"Parent role {parent_role} does not exist")
        
        role = Role(
            role_id=role_id,
            name=name,
            description=description,
            permissions=permissions,
            inherits_from=inherits_from,
            is_system_role=False,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        self.roles[role_id] = role
        
        logger.info("Custom role created", role_id=role_id, name=name)
        return role
    
    async def assign_role_to_user(self, user_id: int, role_id: str) -> bool:
        """Assign a role to a user."""
        if not self.initialized:
            await self.initialize()
        
        if role_id not in self.roles:
            raise ValidationError(f"Role {role_id} does not exist")
        
        try:
            async with db_manager.get_session() as db:
                # Get user
                user_result = await db.execute(
                    select(User).where(User.user_id == user_id)
                )
                user = user_result.scalar_one_or_none()
                
                if not user:
                    raise ValidationError(f"User {user_id} does not exist")
                
                # Update user role
                user.role = role_id
                await db.commit()
                
                logger.info("Role assigned to user", user_id=user_id, role_id=role_id)
                return True
                
        except Exception as e:
            logger.error("Failed to assign role to user", 
                        user_id=user_id, role_id=role_id, error=str(e))
            raise ValidationError(f"Failed to assign role: {str(e)}")
    
    async def check_permission(
        self,
        user_id: int,
        resource_type: ResourceType,
        action: PermissionAction,
        resource_id: Optional[str] = None
    ) -> bool:
        """Check if user has permission for an action."""
        if not self.initialized:
            await self.initialize()
        
        try:
            # Get user roles and permissions
            user_permissions = await self.get_user_permissions(user_id)
            
            # Check if user has the required permission
            permission_key = f"{resource_type.value}:{action.value}"
            if resource_id:
                permission_key += f":{resource_id}"
            
            # Check direct permission
            if permission_key in user_permissions:
                return True
            
            # Check wildcard permissions
            wildcard_key = f"{resource_type.value}:{action.value}:*"
            if wildcard_key in user_permissions:
                return True
            
            # Check admin permissions
            admin_key = f"{resource_type.value}:admin"
            if admin_key in user_permissions:
                return True
            
            # Check super admin
            if "system:admin" in user_permissions:
                return True
            
            return False
            
        except Exception as e:
            logger.error("Permission check failed", 
                        user_id=user_id, error=str(e))
            return False
    
    async def get_user_permissions(self, user_id: int) -> Set[str]:
        """Get all permissions for a user."""
        if not self.initialized:
            await self.initialize()
        
        try:
            async with db_manager.get_session() as db:
                # Get user
                user_result = await db.execute(
                    select(User).where(User.user_id == user_id)
                )
                user = user_result.scalar_one_or_none()
                
                if not user:
                    return set()
                
                # Get user roles (including inherited)
                user_roles = await self._get_user_roles_with_inheritance(user.role)
                
                # Collect all permissions
                permissions = set()
                for role_id in user_roles:
                    if role_id in self.roles:
                        role = self.roles[role_id]
                        for permission in role.permissions:
                            perm_key = f"{permission.resource_type.value}:{permission.action.value}"
                            if permission.resource_id:
                                perm_key += f":{permission.resource_id}"
                            permissions.add(perm_key)
                
                return permissions
                
        except Exception as e:
            logger.error("Failed to get user permissions", user_id=user_id, error=str(e))
            return set()
    
    async def authenticate_sso_user(
        self,
        provider: str,
        sso_token: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> Dict[str, Any]:
        """Authenticate user via SSO provider."""
        if not self.initialized:
            await self.initialize()
        
        if provider not in self.sso_providers:
            raise ValidationError(f"SSO provider {provider} not configured")
        
        try:
            # Validate SSO token with provider
            user_info = await self._validate_sso_token(provider, sso_token)
            
            if not user_info:
                raise AuthenticationError("Invalid SSO token")
            
            # Get or create user
            user = await self._get_or_create_sso_user(user_info, provider)
            
            # Create session
            session = await self._create_user_session(
                user.user_id, 
                provider, 
                sso_token,
                ip_address,
                user_agent
            )
            
            # Generate JWT token
            jwt_token = await self._generate_jwt_token(user, session)
            
            logger.info("SSO authentication successful", 
                       user_id=user.user_id,
                       provider=provider,
                       session_id=session.session_id)
            
            return {
                "user": {
                    "user_id": user.user_id,
                    "username": user.username,
                    "full_name": user.full_name,
                    "email": user.email,
                    "role": user.role
                },
                "session": {
                    "session_id": session.session_id,
                    "expires_at": session.expires_at.isoformat()
                },
                "token": jwt_token,
                "sso_provider": provider
            }
            
        except Exception as e:
            logger.error("SSO authentication failed", provider=provider, error=str(e))
            raise AuthenticationError(f"SSO authentication failed: {str(e)}")
    
    async def validate_session(self, session_id: str) -> Optional[UserSession]:
        """Validate and return user session."""
        if session_id not in self.active_sessions:
            return None
        
        session = self.active_sessions[session_id]
        
        # Check if session is expired
        if datetime.utcnow() > session.expires_at:
            await self._invalidate_session(session_id)
            return None
        
        # Update last activity
        session.last_activity = datetime.utcnow()
        
        return session
    
    async def invalidate_session(self, session_id: str) -> bool:
        """Invalidate a user session."""
        return await self._invalidate_session(session_id)
    
    async def get_user_sessions(self, user_id: int) -> List[UserSession]:
        """Get all active sessions for a user."""
        sessions = []
        for session in self.active_sessions.values():
            if session.user_id == user_id:
                sessions.append(session)
        
        return sessions
    
    async def invalidate_user_sessions(self, user_id: int) -> int:
        """Invalidate all sessions for a user."""
        sessions_to_remove = []
        
        for session_id, session in self.active_sessions.items():
            if session.user_id == user_id:
                sessions_to_remove.append(session_id)
        
        for session_id in sessions_to_remove:
            await self._invalidate_session(session_id)
        
        return len(sessions_to_remove)
    
    async def get_role_hierarchy(self) -> Dict[str, List[str]]:
        """Get the complete role hierarchy."""
        return self.role_hierarchy
    
    async def get_available_roles(self) -> List[Dict[str, Any]]:
        """Get all available roles."""
        roles = []
        for role in self.roles.values():
            roles.append({
                "role_id": role.role_id,
                "name": role.name,
                "description": role.description,
                "is_system_role": role.is_system_role,
                "permission_count": len(role.permissions),
                "inherits_from": role.inherits_from
            })
        
        return roles
    
    async def audit_user_activity(
        self,
        user_id: int,
        action: str,
        resource_type: str,
        resource_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        """Log user activity for audit purposes."""
        audit_entry = {
            "user_id": user_id,
            "action": action,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "details": details,
            "timestamp": datetime.utcnow().isoformat(),
            "ip_address": details.get("ip_address") if details else None,
            "user_agent": details.get("user_agent") if details else None
        }
        
        # Store audit log (would typically go to a separate audit database)
        logger.info("User activity audited", **audit_entry)
    
    # Private helper methods
    def _get_all_permissions(self) -> List[Permission]:
        """Get all possible permissions for super admin."""
        permissions = []
        
        for resource_type in ResourceType:
            for action in PermissionAction:
                permissions.append(Permission(resource_type, action))
        
        return permissions
    
    async def _get_user_roles_with_inheritance(self, primary_role: str) -> List[str]:
        """Get user roles including inherited roles."""
        roles = [primary_role]
        
        # Add inherited roles
        if primary_role in self.role_hierarchy:
            inherited_roles = self.role_hierarchy[primary_role]
            roles.extend(inherited_roles)
        
        return roles
    
    async def _initialize_sso_providers(self):
        """Initialize SSO providers."""
        try:
            # Azure AD configuration
            azure_config = {
                "client_id": os.getenv("AZURE_CLIENT_ID"),
                "client_secret": os.getenv("AZURE_CLIENT_SECRET"),
                "tenant_id": os.getenv("AZURE_TENANT_ID"),
                "redirect_uri": os.getenv("AZURE_REDIRECT_URI")
            }
            
            if all(azure_config.values()):
                self.sso_providers["azure_ad"] = {
                    "type": SSOProvider.AZURE_AD,
                    "config": azure_config,
                    "enabled": True
                }
                logger.info("Azure AD SSO provider configured")
            
            # SAML configuration
            if SAML_AVAILABLE:
                saml_config_file = os.getenv("SAML_CONFIG_FILE")
                if saml_config_file and os.path.exists(saml_config_file):
                    self.sso_providers["saml"] = {
                        "type": SSOProvider.SAML,
                        "config_file": saml_config_file,
                        "enabled": True
                    }
                    logger.info("SAML SSO provider configured")
            
            # LDAP configuration
            if LDAP_AVAILABLE:
                ldap_config = {
                    "server": os.getenv("LDAP_SERVER"),
                    "base_dn": os.getenv("LDAP_BASE_DN"),
                    "bind_dn": os.getenv("LDAP_BIND_DN"),
                    "bind_password": os.getenv("LDAP_BIND_PASSWORD")
                }
                
                if all(ldap_config.values()):
                    self.sso_providers["ldap"] = {
                        "type": SSOProvider.LDAP,
                        "config": ldap_config,
                        "enabled": True
                    }
                    logger.info("LDAP provider configured")
            
        except Exception as e:
            logger.error("Failed to initialize SSO providers", error=str(e))
    
    async def _validate_sso_token(self, provider: str, token: str) -> Optional[Dict[str, Any]]:
        """Validate SSO token with provider."""
        provider_config = self.sso_providers.get(provider)
        if not provider_config:
            return None
        
        try:
            if provider == "azure_ad":
                return await self._validate_azure_ad_token(token, provider_config["config"])
            elif provider == "saml":
                return await self._validate_saml_token(token, provider_config)
            elif provider == "ldap":
                return await self._validate_ldap_credentials(token, provider_config["config"])
            
        except Exception as e:
            logger.error("SSO token validation failed", provider=provider, error=str(e))
            return None
    
    async def _validate_azure_ad_token(self, token: str, config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Validate Azure AD token."""
        try:
            # Validate token with Microsoft Graph API
            headers = {"Authorization": f"Bearer {token}"}
            response = await self.http_client.get(
                "https://graph.microsoft.com/v1.0/me",
                headers=headers
            )
            
            if response.status_code == 200:
                user_data = response.json()
                return {
                    "external_id": user_data.get("id"),
                    "username": user_data.get("userPrincipalName"),
                    "email": user_data.get("mail") or user_data.get("userPrincipalName"),
                    "full_name": user_data.get("displayName"),
                    "provider": "azure_ad"
                }
            
        except Exception as e:
            logger.error("Azure AD token validation failed", error=str(e))
        
        return None
    
    async def _validate_saml_token(self, token: str, config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Validate SAML token."""
        if not SAML_AVAILABLE:
            return None
        
        try:
            # This is a simplified SAML validation
            # In practice, you would parse and validate the SAML assertion
            
            # Placeholder for SAML token validation
            return {
                "external_id": "saml_user_id",
                "username": "saml_username",
                "email": "user@company.com",
                "full_name": "SAML User",
                "provider": "saml"
            }
            
        except Exception as e:
            logger.error("SAML token validation failed", error=str(e))
        
        return None
    
    async def _validate_ldap_credentials(self, credentials: str, config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Validate LDAP credentials."""
        if not LDAP_AVAILABLE:
            return None
        
        try:
            # Parse credentials (typically username:password)
            if ":" not in credentials:
                return None
            
            username, password = credentials.split(":", 1)
            
            # Connect to LDAP server
            server = ldap3.Server(config["server"])
            connection = ldap3.Connection(
                server,
                user=f"cn={username},{config['base_dn']}",
                password=password,
                auto_bind=True
            )
            
            # If we get here, authentication was successful
            # Get user attributes
            connection.search(
                config["base_dn"],
                f"(cn={username})",
                attributes=["cn", "mail", "displayName"]
            )
            
            if connection.entries:
                entry = connection.entries[0]
                return {
                    "external_id": str(entry.cn),
                    "username": str(entry.cn),
                    "email": str(entry.mail) if hasattr(entry, 'mail') else f"{username}@company.com",
                    "full_name": str(entry.displayName) if hasattr(entry, 'displayName') else username,
                    "provider": "ldap"
                }
            
        except Exception as e:
            logger.error("LDAP authentication failed", error=str(e))
        
        return None
    
    async def _get_or_create_sso_user(self, user_info: Dict[str, Any], provider: str) -> User:
        """Get or create user from SSO information."""
        async with db_manager.get_session() as db:
            # Try to find existing user by email
            user_result = await db.execute(
                select(User).where(User.email == user_info["email"])
            )
            user = user_result.scalar_one_or_none()
            
            if not user:
                # Create new user
                user = User(
                    username=user_info["username"],
                    full_name=user_info["full_name"],
                    email=user_info["email"],
                    role="viewer",  # Default role for SSO users
                    is_active=True,
                    sso_provider=provider,
                    sso_external_id=user_info["external_id"]
                )
                db.add(user)
                await db.commit()
                await db.refresh(user)
                
                logger.info("New SSO user created", 
                           user_id=user.user_id,
                           provider=provider,
                           email=user_info["email"])
            else:
                # Update SSO information
                user.sso_provider = provider
                user.sso_external_id = user_info["external_id"]
                user.last_login = datetime.utcnow()
                await db.commit()
            
            return user
    
    async def _create_user_session(
        self,
        user_id: int,
        sso_provider: Optional[str] = None,
        sso_session_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> UserSession:
        """Create a new user session."""
        import uuid
        
        session_id = str(uuid.uuid4())
        expires_at = datetime.utcnow() + timedelta(hours=8)  # 8-hour session
        
        # Get user permissions
        permissions = await self.get_user_permissions(user_id)
        
        # Get user role
        async with db_manager.get_session() as db:
            user_result = await db.execute(
                select(User).where(User.user_id == user_id)
            )
            user = user_result.scalar_one_or_none()
            roles = [user.role] if user else []
        
        session = UserSession(
            session_id=session_id,
            user_id=user_id,
            roles=roles,
            permissions=permissions,
            sso_provider=sso_provider,
            sso_session_id=sso_session_id,
            created_at=datetime.utcnow(),
            expires_at=expires_at,
            last_activity=datetime.utcnow(),
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        self.active_sessions[session_id] = session
        
        return session
    
    async def _generate_jwt_token(self, user: User, session: UserSession) -> str:
        """Generate JWT token for user session."""
        payload = {
            "user_id": user.user_id,
            "username": user.username,
            "session_id": session.session_id,
            "role": user.role,
            "sso_provider": session.sso_provider,
            "iat": datetime.utcnow(),
            "exp": session.expires_at
        }
        
        secret_key = os.getenv("JWT_SECRET")
        if not secret_key:
            raise ValueError("JWT_SECRET environment variable must be set")
        token = jwt.encode(payload, secret_key, algorithm="HS256")
        
        return token
    
    async def _invalidate_session(self, session_id: str) -> bool:
        """Invalidate a session."""
        if session_id in self.active_sessions:
            del self.active_sessions[session_id]
            logger.info("Session invalidated", session_id=session_id)
            return True
        return False
    
    async def _session_cleanup_task(self):
        """Background task to clean up expired sessions."""
        while True:
            try:
                await asyncio.sleep(300)  # Run every 5 minutes
                
                current_time = datetime.utcnow()
                expired_sessions = []
                
                for session_id, session in self.active_sessions.items():
                    if current_time > session.expires_at:
                        expired_sessions.append(session_id)
                
                for session_id in expired_sessions:
                    await self._invalidate_session(session_id)
                
                if expired_sessions:
                    logger.info("Expired sessions cleaned up", count=len(expired_sessions))
                
            except Exception as e:
                logger.error("Session cleanup task error", error=str(e))

# Global enterprise auth service instance
enterprise_auth_service = EnterpriseAuthService()