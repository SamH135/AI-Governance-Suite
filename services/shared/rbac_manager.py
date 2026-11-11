"""Role-Based Access Control (RBAC) Manager."""

import asyncio
from typing import Dict, List, Any, Optional, Set
from datetime import datetime
from enum import Enum
import structlog

from .database import db_manager
from .redis_client import redis_client
from .exceptions import ValidationError, NotFoundError, SecurityError

logger = structlog.get_logger()

class Permission(Enum):
    """System permissions."""
    # System management
    CREATE_SYSTEM = "create_system"
    READ_SYSTEM = "read_system"
    UPDATE_SYSTEM = "update_system"
    DELETE_SYSTEM = "delete_system"
    
    # Model management
    CREATE_MODEL = "create_model"
    READ_MODEL = "read_model"
    UPDATE_MODEL = "update_model"
    DELETE_MODEL = "delete_model"
    
    # Test management
    CREATE_TEST = "create_test"
    READ_TEST = "read_test"
    UPDATE_TEST = "update_test"
    DELETE_TEST = "delete_test"
    EXECUTE_TEST = "execute_test"
    
    # Document management
    CREATE_DOCUMENT = "create_document"
    READ_DOCUMENT = "read_document"
    UPDATE_DOCUMENT = "update_document"
    DELETE_DOCUMENT = "delete_document"
    GENERATE_DOCUMENT = "generate_document"
    
    # Analytics and reporting
    VIEW_ANALYTICS = "view_analytics"
    EXPORT_DATA = "export_data"
    VIEW_REPORTS = "view_reports"
    
    # User management
    CREATE_USER = "create_user"
    READ_USER = "read_user"
    UPDATE_USER = "update_user"
    DELETE_USER = "delete_user"
    MANAGE_ROLES = "manage_roles"
    
    # API key management
    MANAGE_API_KEYS = "manage_api_keys"
    VIEW_API_KEYS = "view_api_keys"
    
    # System administration
    SYSTEM_ADMIN = "system_admin"
    VIEW_AUDIT_LOGS = "view_audit_logs"
    MANAGE_SETTINGS = "manage_settings"

class Role(Enum):
    """Predefined system roles."""
    SUPER_ADMIN = "super_admin"
    ADMIN = "admin"
    MANAGER = "manager"
    ANALYST = "analyst"
    USER = "user"
    VIEWER = "viewer"

class RBACManager:
    """Role-Based Access Control Manager."""
    
    def __init__(self):
        self.initialized = False
        self.role_permissions = {}
        self.user_permissions_cache = {}
        
    async def initialize(self):
        """Initialize the RBAC manager."""
        if self.initialized:
            return
            
        try:
            # Create RBAC tables
            await self._create_tables()
            
            # Setup default roles and permissions
            await self._setup_default_roles()
            
            self.initialized = True
            logger.info("RBAC Manager initialized successfully")
            
        except Exception as e:
            logger.error("RBAC Manager initialization failed", error=str(e))
            raise SecurityError(f"RBAC Manager initialization failed: {str(e)}")
    
    async def create_role(
        self,
        role_name: str,
        description: str,
        permissions: List[Permission],
        created_by: int
    ) -> Dict[str, Any]:
        """Create a new custom role."""
        
        if not self.initialized:
            await self.initialize()
            
        try:
            async with db_manager.get_session() as session:
                # Check if role already exists
                check_query = "SELECT id FROM roles WHERE name = :role_name"
                result = await session.execute(check_query, {"role_name": role_name})
                
                if result.fetchone():
                    raise ValidationError(f"Role '{role_name}' already exists")
                
                # Create role
                role_query = """
                    INSERT INTO roles (name, description, is_custom, created_by, created_at, updated_at)
                    VALUES (:name, :description, true, :created_by, NOW(), NOW())
                    RETURNING id
                """
                
                result = await session.execute(role_query, {
                    "name": role_name,
                    "description": description,
                    "created_by": created_by
                })
                
                role_id = result.fetchone()[0]
                
                # Add permissions
                for permission in permissions:
                    perm_query = """
                        INSERT INTO role_permissions (role_id, permission, created_at)
                        VALUES (:role_id, :permission, NOW())
                    """
                    await session.execute(perm_query, {
                        "role_id": role_id,
                        "permission": permission.value
                    })
                
                await session.commit()
                
                # Clear cache
                await self._clear_permissions_cache()
                
                logger.info("Custom role created", role_name=role_name, role_id=role_id)
                
                return {
                    "role_id": role_id,
                    "name": role_name,
                    "description": description,
                    "permissions": [p.value for p in permissions],
                    "is_custom": True,
                    "created_at": datetime.utcnow().isoformat()
                }
                
        except Exception as e:
            logger.error("Role creation failed", role_name=role_name, error=str(e))
            raise ValidationError(f"Role creation failed: {str(e)}")
    
    async def assign_role_to_user(
        self,
        user_id: int,
        role_name: str,
        assigned_by: int,
        organization_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """Assign a role to a user."""
        
        if not self.initialized:
            await self.initialize()
            
        try:
            async with db_manager.get_session() as session:
                # Get role ID
                role_query = "SELECT id FROM roles WHERE name = :role_name"
                result = await session.execute(role_query, {"role_name": role_name})
                role_row = result.fetchone()
                
                if not role_row:
                    raise NotFoundError("Role", role_name)
                
                role_id = role_row[0]
                
                # Check if user already has this role
                check_query = """
                    SELECT id FROM user_roles 
                    WHERE user_id = :user_id AND role_id = :role_id AND is_active = true
                """
                result = await session.execute(check_query, {
                    "user_id": user_id,
                    "role_id": role_id
                })
                
                if result.fetchone():
                    raise ValidationError(f"User already has role '{role_name}'")
                
                # Assign role
                assign_query = """
                    INSERT INTO user_roles (user_id, role_id, organization_id, assigned_by, is_active, created_at, updated_at)
                    VALUES (:user_id, :role_id, :organization_id, :assigned_by, true, NOW(), NOW())
                """
                
                await session.execute(assign_query, {
                    "user_id": user_id,
                    "role_id": role_id,
                    "organization_id": organization_id,
                    "assigned_by": assigned_by
                })
                
                await session.commit()
                
                # Clear user permissions cache
                await self._clear_user_permissions_cache(user_id)
                
                logger.info("Role assigned to user", user_id=user_id, role_name=role_name)
                
                return {
                    "success": True,
                    "message": f"Role '{role_name}' assigned to user successfully"
                }
                
        except Exception as e:
            logger.error("Role assignment failed", user_id=user_id, role_name=role_name, error=str(e))
            raise ValidationError(f"Role assignment failed: {str(e)}")
    
    async def remove_role_from_user(
        self,
        user_id: int,
        role_name: str,
        removed_by: int
    ) -> Dict[str, Any]:
        """Remove a role from a user."""
        
        if not self.initialized:
            await self.initialize()
            
        try:
            async with db_manager.get_session() as session:
                # Get role ID
                role_query = "SELECT id FROM roles WHERE name = :role_name"
                result = await session.execute(role_query, {"role_name": role_name})
                role_row = result.fetchone()
                
                if not role_row:
                    raise NotFoundError("Role", role_name)
                
                role_id = role_row[0]
                
                # Remove role (soft delete)
                remove_query = """
                    UPDATE user_roles 
                    SET is_active = false, removed_by = :removed_by, updated_at = NOW()
                    WHERE user_id = :user_id AND role_id = :role_id AND is_active = true
                """
                
                result = await session.execute(remove_query, {
                    "user_id": user_id,
                    "role_id": role_id,
                    "removed_by": removed_by
                })
                
                if result.rowcount == 0:
                    raise ValidationError(f"User does not have role '{role_name}'")
                
                await session.commit()
                
                # Clear user permissions cache
                await self._clear_user_permissions_cache(user_id)
                
                logger.info("Role removed from user", user_id=user_id, role_name=role_name)
                
                return {
                    "success": True,
                    "message": f"Role '{role_name}' removed from user successfully"
                }
                
        except Exception as e:
            logger.error("Role removal failed", user_id=user_id, role_name=role_name, error=str(e))
            raise ValidationError(f"Role removal failed: {str(e)}")
    
    async def get_user_permissions(self, user_id: int) -> Set[str]:
        """Get all permissions for a user."""
        
        if not self.initialized:
            await self.initialize()
            
        try:
            # Check cache first
            cache_key = f"user_permissions:{user_id}"
            cached_permissions = await redis_client.get(cache_key)
            
            if cached_permissions:
                return set(cached_permissions.split(","))
            
            # Get from database
            async with db_manager.get_session() as session:
                query = """
                    SELECT DISTINCT rp.permission
                    FROM user_roles ur
                    JOIN roles r ON ur.role_id = r.id
                    JOIN role_permissions rp ON r.id = rp.role_id
                    WHERE ur.user_id = :user_id AND ur.is_active = true
                """
                
                result = await session.execute(query, {"user_id": user_id})
                permissions = {row[0] for row in result.fetchall()}
                
                # Cache permissions
                if permissions:
                    await redis_client.setex(cache_key, 3600, ",".join(permissions))
                
                return permissions
                
        except Exception as e:
            logger.error("Failed to get user permissions", user_id=user_id, error=str(e))
            return set()
    
    async def check_permission(self, user_id: int, permission: Permission) -> bool:
        """Check if a user has a specific permission."""
        
        user_permissions = await self.get_user_permissions(user_id)
        return permission.value in user_permissions or Permission.SYSTEM_ADMIN.value in user_permissions
    
    async def get_user_roles(self, user_id: int) -> List[Dict[str, Any]]:
        """Get all roles for a user."""
        
        if not self.initialized:
            await self.initialize()
            
        try:
            async with db_manager.get_session() as session:
                query = """
                    SELECT r.id, r.name, r.description, r.is_custom, ur.organization_id, ur.created_at
                    FROM user_roles ur
                    JOIN roles r ON ur.role_id = r.id
                    WHERE ur.user_id = :user_id AND ur.is_active = true
                    ORDER BY ur.created_at DESC
                """
                
                result = await session.execute(query, {"user_id": user_id})
                roles = []
                
                for row in result.fetchall():
                    roles.append({
                        "role_id": row[0],
                        "name": row[1],
                        "description": row[2],
                        "is_custom": row[3],
                        "organization_id": row[4],
                        "assigned_at": row[5].isoformat()
                    })
                
                return roles
                
        except Exception as e:
            logger.error("Failed to get user roles", user_id=user_id, error=str(e))
            return []
    
    async def get_all_roles(self) -> List[Dict[str, Any]]:
        """Get all available roles."""
        
        if not self.initialized:
            await self.initialize()
            
        try:
            async with db_manager.get_session() as session:
                query = """
                    SELECT r.id, r.name, r.description, r.is_custom, r.created_at,
                           COUNT(ur.user_id) as user_count
                    FROM roles r
                    LEFT JOIN user_roles ur ON r.id = ur.role_id AND ur.is_active = true
                    GROUP BY r.id, r.name, r.description, r.is_custom, r.created_at
                    ORDER BY r.is_custom, r.name
                """
                
                result = await session.execute(query)
                roles = []
                
                for row in result.fetchall():
                    # Get permissions for this role
                    perm_query = "SELECT permission FROM role_permissions WHERE role_id = :role_id"
                    perm_result = await session.execute(perm_query, {"role_id": row[0]})
                    permissions = [perm_row[0] for perm_row in perm_result.fetchall()]
                    
                    roles.append({
                        "role_id": row[0],
                        "name": row[1],
                        "description": row[2],
                        "is_custom": row[3],
                        "created_at": row[4].isoformat(),
                        "user_count": row[5],
                        "permissions": permissions
                    })
                
                return roles
                
        except Exception as e:
            logger.error("Failed to get all roles", error=str(e))
            return []
    
    async def _setup_default_roles(self):
        """Setup default system roles."""
        
        default_roles = {
            Role.SUPER_ADMIN: {
                "description": "Super administrator with all permissions",
                "permissions": list(Permission)
            },
            Role.ADMIN: {
                "description": "Administrator with most permissions",
                "permissions": [
                    Permission.CREATE_SYSTEM, Permission.READ_SYSTEM, Permission.UPDATE_SYSTEM, Permission.DELETE_SYSTEM,
                    Permission.CREATE_MODEL, Permission.READ_MODEL, Permission.UPDATE_MODEL, Permission.DELETE_MODEL,
                    Permission.CREATE_TEST, Permission.READ_TEST, Permission.UPDATE_TEST, Permission.DELETE_TEST, Permission.EXECUTE_TEST,
                    Permission.CREATE_DOCUMENT, Permission.READ_DOCUMENT, Permission.UPDATE_DOCUMENT, Permission.DELETE_DOCUMENT, Permission.GENERATE_DOCUMENT,
                    Permission.VIEW_ANALYTICS, Permission.EXPORT_DATA, Permission.VIEW_REPORTS,
                    Permission.READ_USER, Permission.UPDATE_USER,
                    Permission.MANAGE_API_KEYS, Permission.VIEW_API_KEYS,
                    Permission.VIEW_AUDIT_LOGS
                ]
            },
            Role.MANAGER: {
                "description": "Manager with team oversight permissions",
                "permissions": [
                    Permission.CREATE_SYSTEM, Permission.READ_SYSTEM, Permission.UPDATE_SYSTEM,
                    Permission.CREATE_MODEL, Permission.READ_MODEL, Permission.UPDATE_MODEL,
                    Permission.CREATE_TEST, Permission.READ_TEST, Permission.UPDATE_TEST, Permission.EXECUTE_TEST,
                    Permission.CREATE_DOCUMENT, Permission.READ_DOCUMENT, Permission.UPDATE_DOCUMENT, Permission.GENERATE_DOCUMENT,
                    Permission.VIEW_ANALYTICS, Permission.VIEW_REPORTS,
                    Permission.READ_USER,
                    Permission.VIEW_API_KEYS
                ]
            },
            Role.ANALYST: {
                "description": "Analyst with testing and reporting permissions",
                "permissions": [
                    Permission.READ_SYSTEM, Permission.READ_MODEL,
                    Permission.CREATE_TEST, Permission.READ_TEST, Permission.UPDATE_TEST, Permission.EXECUTE_TEST,
                    Permission.READ_DOCUMENT, Permission.GENERATE_DOCUMENT,
                    Permission.VIEW_ANALYTICS, Permission.VIEW_REPORTS,
                    Permission.VIEW_API_KEYS
                ]
            },
            Role.USER: {
                "description": "Regular user with basic permissions",
                "permissions": [
                    Permission.READ_SYSTEM, Permission.READ_MODEL,
                    Permission.READ_TEST, Permission.EXECUTE_TEST,
                    Permission.READ_DOCUMENT,
                    Permission.VIEW_ANALYTICS,
                    Permission.VIEW_API_KEYS
                ]
            },
            Role.VIEWER: {
                "description": "Read-only access to most resources",
                "permissions": [
                    Permission.READ_SYSTEM, Permission.READ_MODEL,
                    Permission.READ_TEST, Permission.READ_DOCUMENT,
                    Permission.VIEW_ANALYTICS
                ]
            }
        }
        
        async with db_manager.get_session() as session:
            for role, config in default_roles.items():
                # Check if role exists
                check_query = "SELECT id FROM roles WHERE name = :role_name"
                result = await session.execute(check_query, {"role_name": role.value})
                
                if result.fetchone():
                    continue  # Role already exists
                
                # Create role
                role_query = """
                    INSERT INTO roles (name, description, is_custom, created_at, updated_at)
                    VALUES (:name, :description, false, NOW(), NOW())
                    RETURNING id
                """
                
                result = await session.execute(role_query, {
                    "name": role.value,
                    "description": config["description"]
                })
                
                role_id = result.fetchone()[0]
                
                # Add permissions
                for permission in config["permissions"]:
                    perm_query = """
                        INSERT INTO role_permissions (role_id, permission, created_at)
                        VALUES (:role_id, :permission, NOW())
                    """
                    await session.execute(perm_query, {
                        "role_id": role_id,
                        "permission": permission.value
                    })
            
            await session.commit()
    
    async def _create_tables(self):
        """Create RBAC tables."""
        
        async with db_manager.get_session() as session:
            create_tables_query = """
                -- Roles table
                CREATE TABLE IF NOT EXISTS roles (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(100) UNIQUE NOT NULL,
                    description TEXT,
                    is_custom BOOLEAN DEFAULT false,
                    created_by INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                
                -- Role permissions table
                CREATE TABLE IF NOT EXISTS role_permissions (
                    id SERIAL PRIMARY KEY,
                    role_id INTEGER NOT NULL,
                    permission VARCHAR(100) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (role_id) REFERENCES roles(id) ON DELETE CASCADE,
                    UNIQUE(role_id, permission)
                );
                
                -- User roles table
                CREATE TABLE IF NOT EXISTS user_roles (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    role_id INTEGER NOT NULL,
                    organization_id INTEGER,
                    assigned_by INTEGER,
                    removed_by INTEGER,
                    is_active BOOLEAN DEFAULT true,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                    FOREIGN KEY (role_id) REFERENCES roles(id) ON DELETE CASCADE
                );
                
                -- Indexes
                CREATE INDEX IF NOT EXISTS idx_role_permissions_role_id ON role_permissions(role_id);
                CREATE INDEX IF NOT EXISTS idx_user_roles_user_id ON user_roles(user_id);
                CREATE INDEX IF NOT EXISTS idx_user_roles_active ON user_roles(user_id, is_active);
            """
            
            await session.execute(create_tables_query)
            await session.commit()
    
    async def _clear_permissions_cache(self):
        """Clear all permissions cache."""
        pattern = "user_permissions:*"
        keys = await redis_client.keys(pattern)
        if keys:
            await redis_client.delete(*keys)
    
    async def _clear_user_permissions_cache(self, user_id: int):
        """Clear permissions cache for a specific user."""
        cache_key = f"user_permissions:{user_id}"
        await redis_client.delete(cache_key)

# Global instance
rbac_manager = RBACManager()