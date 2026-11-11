"""Multi-tenancy manager for tenant isolation and management."""

import asyncio
import json
from typing import Dict, List, Any, Optional
from datetime import datetime
from enum import Enum
import structlog

from .database import db_manager
from .redis_client import redis_client
from .exceptions import ValidationError, NotFoundError, SecurityError

logger = structlog.get_logger()

class TenantStatus(Enum):
    """Tenant status options."""
    ACTIVE = "active"
    SUSPENDED = "suspended"
    INACTIVE = "inactive"
    PENDING = "pending"

class TenantPlan(Enum):
    """Tenant subscription plans."""
    FREE = "free"
    BASIC = "basic"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"

class MultiTenantManager:
    """Multi-tenancy manager for complete tenant isolation."""
    
    def __init__(self):
        self.initialized = False
        self.tenant_cache = {}
        
    async def initialize(self):
        """Initialize the multi-tenant manager."""
        if self.initialized:
            return
            
        try:
            # Create tenant tables
            await self._create_tables()
            
            # Load tenant configurations
            await self._load_tenant_cache()
            
            self.initialized = True
            logger.info("Multi-Tenant Manager initialized successfully")
            
        except Exception as e:
            logger.error("Multi-Tenant Manager initialization failed", error=str(e))
            raise SecurityError(f"Multi-Tenant Manager initialization failed: {str(e)}")
    
    async def create_tenant(
        self,
        name: str,
        domain: str,
        plan: TenantPlan = TenantPlan.FREE,
        admin_email: str = None,
        settings: Optional[Dict[str, Any]] = None,
        created_by: Optional[int] = None
    ) -> Dict[str, Any]:
        """Create a new tenant."""
        
        if not self.initialized:
            await self.initialize()
            
        try:
            # Validate domain uniqueness
            if await self._domain_exists(domain):
                raise ValidationError(f"Domain '{domain}' already exists")
            
            async with db_manager.get_session() as session:
                # Create tenant
                tenant_query = """
                    INSERT INTO tenants 
                    (name, domain, plan, status, admin_email, settings, created_by, created_at, updated_at)
                    VALUES (:name, :domain, :plan, :status, :admin_email, :settings, :created_by, NOW(), NOW())
                    RETURNING id
                """
                
                result = await session.execute(tenant_query, {
                    "name": name,
                    "domain": domain,
                    "plan": plan.value,
                    "status": TenantStatus.ACTIVE.value,
                    "admin_email": admin_email,
                    "settings": json.dumps(settings or {}),
                    "created_by": created_by
                })
                
                tenant_id = result.fetchone()[0]
                
                # Create tenant-specific database schema
                await self._create_tenant_schema(tenant_id)
                
                # Initialize tenant settings
                await self._initialize_tenant_settings(tenant_id, plan)
                
                await session.commit()
                
                # Update cache
                tenant_info = {
                    "id": tenant_id,
                    "name": name,
                    "domain": domain,
                    "plan": plan.value,
                    "status": TenantStatus.ACTIVE.value,
                    "settings": settings or {}
                }
                
                self.tenant_cache[domain] = tenant_info
                await self._cache_tenant_info(domain, tenant_info)
                
                logger.info("Tenant created", tenant_id=tenant_id, domain=domain, plan=plan.value)
                
                return {
                    "tenant_id": tenant_id,
                    "name": name,
                    "domain": domain,
                    "plan": plan.value,
                    "status": TenantStatus.ACTIVE.value,
                    "created_at": datetime.utcnow().isoformat()
                }
                
        except Exception as e:
            logger.error("Tenant creation failed", domain=domain, error=str(e))
            raise ValidationError(f"Tenant creation failed: {str(e)}")
    
    async def get_tenant_by_domain(self, domain: str) -> Optional[Dict[str, Any]]:
        """Get tenant information by domain."""
        
        if not self.initialized:
            await self.initialize()
            
        try:
            # Check cache first
            if domain in self.tenant_cache:
                return self.tenant_cache[domain]
            
            # Check Redis cache
            cached_info = await redis_client.get(f"tenant:{domain}")
            if cached_info:
                tenant_info = json.loads(cached_info)
                self.tenant_cache[domain] = tenant_info
                return tenant_info
            
            # Query database
            async with db_manager.get_session() as session:
                query = """
                    SELECT id, name, domain, plan, status, admin_email, settings, created_at, updated_at
                    FROM tenants 
                    WHERE domain = :domain AND status != 'inactive'
                """
                
                result = await session.execute(query, {"domain": domain})
                row = result.fetchone()
                
                if not row:
                    return None
                
                tenant_info = {
                    "id": row[0],
                    "name": row[1],
                    "domain": row[2],
                    "plan": row[3],
                    "status": row[4],
                    "admin_email": row[5],
                    "settings": json.loads(row[6]) if row[6] else {},
                    "created_at": row[7].isoformat(),
                    "updated_at": row[8].isoformat()
                }
                
                # Cache the result
                self.tenant_cache[domain] = tenant_info
                await self._cache_tenant_info(domain, tenant_info)
                
                return tenant_info
                
        except Exception as e:
            logger.error("Failed to get tenant by domain", domain=domain, error=str(e))
            return None
    
    async def get_tenant_by_id(self, tenant_id: int) -> Optional[Dict[str, Any]]:
        """Get tenant information by ID."""
        
        if not self.initialized:
            await self.initialize()
            
        try:
            async with db_manager.get_session() as session:
                query = """
                    SELECT id, name, domain, plan, status, admin_email, settings, created_at, updated_at
                    FROM tenants 
                    WHERE id = :tenant_id
                """
                
                result = await session.execute(query, {"tenant_id": tenant_id})
                row = result.fetchone()
                
                if not row:
                    return None
                
                return {
                    "id": row[0],
                    "name": row[1],
                    "domain": row[2],
                    "plan": row[3],
                    "status": row[4],
                    "admin_email": row[5],
                    "settings": json.loads(row[6]) if row[6] else {},
                    "created_at": row[7].isoformat(),
                    "updated_at": row[8].isoformat()
                }
                
        except Exception as e:
            logger.error("Failed to get tenant by ID", tenant_id=tenant_id, error=str(e))
            return None
    
    async def update_tenant(
        self,
        tenant_id: int,
        updates: Dict[str, Any],
        updated_by: Optional[int] = None
    ) -> Dict[str, Any]:
        """Update tenant information."""
        
        if not self.initialized:
            await self.initialize()
            
        try:
            async with db_manager.get_session() as session:
                # Build update query
                update_fields = []
                params = {"tenant_id": tenant_id, "updated_by": updated_by}
                
                allowed_fields = ["name", "plan", "status", "admin_email", "settings"]
                
                for field, value in updates.items():
                    if field in allowed_fields:
                        if field == "settings":
                            update_fields.append(f"{field} = :settings")
                            params["settings"] = json.dumps(value)
                        else:
                            update_fields.append(f"{field} = :{field}")
                            params[field] = value
                
                if not update_fields:
                    raise ValidationError("No valid fields to update")
                
                update_fields.append("updated_at = NOW()")
                
                update_query = f"""
                    UPDATE tenants 
                    SET {', '.join(update_fields)}
                    WHERE id = :tenant_id
                    RETURNING domain
                """
                
                result = await session.execute(update_query, params)
                domain_row = result.fetchone()
                
                if not domain_row:
                    raise NotFoundError("Tenant", tenant_id)
                
                domain = domain_row[0]
                
                await session.commit()
                
                # Clear cache
                if domain in self.tenant_cache:
                    del self.tenant_cache[domain]
                
                await redis_client.delete(f"tenant:{domain}")
                
                logger.info("Tenant updated", tenant_id=tenant_id, updates=list(updates.keys()))
                
                return {"success": True, "message": "Tenant updated successfully"}
                
        except Exception as e:
            logger.error("Tenant update failed", tenant_id=tenant_id, error=str(e))
            raise ValidationError(f"Tenant update failed: {str(e)}")
    
    async def suspend_tenant(
        self,
        tenant_id: int,
        reason: str,
        suspended_by: int
    ) -> Dict[str, Any]:
        """Suspend a tenant."""
        
        return await self.update_tenant(
            tenant_id,
            {
                "status": TenantStatus.SUSPENDED.value,
                "suspension_reason": reason
            },
            suspended_by
        )
    
    async def activate_tenant(
        self,
        tenant_id: int,
        activated_by: int
    ) -> Dict[str, Any]:
        """Activate a suspended tenant."""
        
        return await self.update_tenant(
            tenant_id,
            {"status": TenantStatus.ACTIVE.value},
            activated_by
        )
    
    async def get_tenant_users(self, tenant_id: int) -> List[Dict[str, Any]]:
        """Get all users for a tenant."""
        
        if not self.initialized:
            await self.initialize()
            
        try:
            async with db_manager.get_session() as session:
                query = """
                    SELECT u.id, u.email, u.name, u.is_active, u.created_at, tu.role
                    FROM users u
                    JOIN tenant_users tu ON u.id = tu.user_id
                    WHERE tu.tenant_id = :tenant_id AND tu.is_active = true
                    ORDER BY u.created_at DESC
                """
                
                result = await session.execute(query, {"tenant_id": tenant_id})
                users = []
                
                for row in result.fetchall():
                    users.append({
                        "user_id": row[0],
                        "email": row[1],
                        "name": row[2],
                        "is_active": row[3],
                        "created_at": row[4].isoformat(),
                        "tenant_role": row[5]
                    })
                
                return users
                
        except Exception as e:
            logger.error("Failed to get tenant users", tenant_id=tenant_id, error=str(e))
            return []
    
    async def add_user_to_tenant(
        self,
        tenant_id: int,
        user_id: int,
        role: str = "user",
        added_by: Optional[int] = None
    ) -> Dict[str, Any]:
        """Add a user to a tenant."""
        
        if not self.initialized:
            await self.initialize()
            
        try:
            async with db_manager.get_session() as session:
                # Check if user is already in tenant
                check_query = """
                    SELECT id FROM tenant_users 
                    WHERE tenant_id = :tenant_id AND user_id = :user_id AND is_active = true
                """
                
                result = await session.execute(check_query, {
                    "tenant_id": tenant_id,
                    "user_id": user_id
                })
                
                if result.fetchone():
                    raise ValidationError("User is already a member of this tenant")
                
                # Add user to tenant
                insert_query = """
                    INSERT INTO tenant_users (tenant_id, user_id, role, added_by, is_active, created_at, updated_at)
                    VALUES (:tenant_id, :user_id, :role, :added_by, true, NOW(), NOW())
                """
                
                await session.execute(insert_query, {
                    "tenant_id": tenant_id,
                    "user_id": user_id,
                    "role": role,
                    "added_by": added_by
                })
                
                await session.commit()
                
                logger.info("User added to tenant", tenant_id=tenant_id, user_id=user_id, role=role)
                
                return {"success": True, "message": "User added to tenant successfully"}
                
        except Exception as e:
            logger.error("Failed to add user to tenant", 
                        tenant_id=tenant_id, user_id=user_id, error=str(e))
            raise ValidationError(f"Failed to add user to tenant: {str(e)}")
    
    async def remove_user_from_tenant(
        self,
        tenant_id: int,
        user_id: int,
        removed_by: Optional[int] = None
    ) -> Dict[str, Any]:
        """Remove a user from a tenant."""
        
        if not self.initialized:
            await self.initialize()
            
        try:
            async with db_manager.get_session() as session:
                # Soft delete - mark as inactive
                update_query = """
                    UPDATE tenant_users 
                    SET is_active = false, removed_by = :removed_by, updated_at = NOW()
                    WHERE tenant_id = :tenant_id AND user_id = :user_id AND is_active = true
                """
                
                result = await session.execute(update_query, {
                    "tenant_id": tenant_id,
                    "user_id": user_id,
                    "removed_by": removed_by
                })
                
                if result.rowcount == 0:
                    raise ValidationError("User is not a member of this tenant")
                
                await session.commit()
                
                logger.info("User removed from tenant", tenant_id=tenant_id, user_id=user_id)
                
                return {"success": True, "message": "User removed from tenant successfully"}
                
        except Exception as e:
            logger.error("Failed to remove user from tenant", 
                        tenant_id=tenant_id, user_id=user_id, error=str(e))
            raise ValidationError(f"Failed to remove user from tenant: {str(e)}")
    
    async def get_user_tenants(self, user_id: int) -> List[Dict[str, Any]]:
        """Get all tenants for a user."""
        
        if not self.initialized:
            await self.initialize()
            
        try:
            async with db_manager.get_session() as session:
                query = """
                    SELECT t.id, t.name, t.domain, t.plan, t.status, tu.role, tu.created_at
                    FROM tenants t
                    JOIN tenant_users tu ON t.id = tu.tenant_id
                    WHERE tu.user_id = :user_id AND tu.is_active = true AND t.status = 'active'
                    ORDER BY tu.created_at DESC
                """
                
                result = await session.execute(query, {"user_id": user_id})
                tenants = []
                
                for row in result.fetchall():
                    tenants.append({
                        "tenant_id": row[0],
                        "name": row[1],
                        "domain": row[2],
                        "plan": row[3],
                        "status": row[4],
                        "role": row[5],
                        "joined_at": row[6].isoformat()
                    })
                
                return tenants
                
        except Exception as e:
            logger.error("Failed to get user tenants", user_id=user_id, error=str(e))
            return []
    
    async def check_tenant_access(
        self,
        user_id: int,
        tenant_id: int,
        required_role: Optional[str] = None
    ) -> bool:
        """Check if user has access to tenant with optional role requirement."""
        
        if not self.initialized:
            await self.initialize()
            
        try:
            async with db_manager.get_session() as session:
                query = """
                    SELECT tu.role
                    FROM tenant_users tu
                    JOIN tenants t ON tu.tenant_id = t.id
                    WHERE tu.user_id = :user_id AND tu.tenant_id = :tenant_id 
                    AND tu.is_active = true AND t.status = 'active'
                """
                
                result = await session.execute(query, {
                    "user_id": user_id,
                    "tenant_id": tenant_id
                })
                
                row = result.fetchone()
                if not row:
                    return False
                
                user_role = row[0]
                
                # Check role requirement
                if required_role:
                    role_hierarchy = ["user", "admin", "owner"]
                    
                    if required_role in role_hierarchy and user_role in role_hierarchy:
                        required_level = role_hierarchy.index(required_role)
                        user_level = role_hierarchy.index(user_role)
                        return user_level >= required_level
                    else:
                        return user_role == required_role
                
                return True
                
        except Exception as e:
            logger.error("Failed to check tenant access", 
                        user_id=user_id, tenant_id=tenant_id, error=str(e))
            return False
    
    async def get_tenant_statistics(self, tenant_id: int) -> Dict[str, Any]:
        """Get statistics for a tenant."""
        
        if not self.initialized:
            await self.initialize()
            
        try:
            async with db_manager.get_session() as session:
                # Get user count
                user_count_query = """
                    SELECT COUNT(*) FROM tenant_users 
                    WHERE tenant_id = :tenant_id AND is_active = true
                """
                
                result = await session.execute(user_count_query, {"tenant_id": tenant_id})
                user_count = result.scalar()
                
                # Get AI systems count (assuming tenant-specific systems)
                systems_count_query = """
                    SELECT COUNT(*) FROM ai_systems s
                    JOIN users u ON s.user_id = u.id
                    JOIN tenant_users tu ON u.id = tu.user_id
                    WHERE tu.tenant_id = :tenant_id AND tu.is_active = true
                """
                
                result = await session.execute(systems_count_query, {"tenant_id": tenant_id})
                systems_count = result.scalar()
                
                # Get test results count
                tests_count_query = """
                    SELECT COUNT(*) FROM test_results tr
                    JOIN models m ON tr.model_id = m.id
                    JOIN ai_systems s ON m.system_id = s.id
                    JOIN users u ON s.user_id = u.id
                    JOIN tenant_users tu ON u.id = tu.user_id
                    WHERE tu.tenant_id = :tenant_id AND tu.is_active = true
                """
                
                result = await session.execute(tests_count_query, {"tenant_id": tenant_id})
                tests_count = result.scalar()
                
                return {
                    "tenant_id": tenant_id,
                    "user_count": user_count,
                    "ai_systems_count": systems_count,
                    "tests_count": tests_count,
                    "generated_at": datetime.utcnow().isoformat()
                }
                
        except Exception as e:
            logger.error("Failed to get tenant statistics", tenant_id=tenant_id, error=str(e))
            return {"error": str(e)}
    
    async def _domain_exists(self, domain: str) -> bool:
        """Check if domain already exists."""
        
        async with db_manager.get_session() as session:
            query = "SELECT id FROM tenants WHERE domain = :domain"
            result = await session.execute(query, {"domain": domain})
            return result.fetchone() is not None
    
    async def _create_tenant_schema(self, tenant_id: int):
        """Create tenant-specific database schema (if needed)."""
        
        # For now, we use shared tables with tenant_id filtering
        # In a more advanced implementation, you might create separate schemas
        logger.info("Tenant schema initialized", tenant_id=tenant_id)
    
    async def _initialize_tenant_settings(self, tenant_id: int, plan: TenantPlan):
        """Initialize tenant settings based on plan."""
        
        plan_limits = {
            TenantPlan.FREE: {
                "max_users": 5,
                "max_ai_systems": 3,
                "max_tests_per_month": 100,
                "storage_limit_gb": 1
            },
            TenantPlan.BASIC: {
                "max_users": 25,
                "max_ai_systems": 10,
                "max_tests_per_month": 1000,
                "storage_limit_gb": 10
            },
            TenantPlan.PROFESSIONAL: {
                "max_users": 100,
                "max_ai_systems": 50,
                "max_tests_per_month": 10000,
                "storage_limit_gb": 100
            },
            TenantPlan.ENTERPRISE: {
                "max_users": -1,  # Unlimited
                "max_ai_systems": -1,
                "max_tests_per_month": -1,
                "storage_limit_gb": -1
            }
        }
        
        limits = plan_limits.get(plan, plan_limits[TenantPlan.FREE])
        
        async with db_manager.get_session() as session:
            settings_query = """
                UPDATE tenants 
                SET settings = :settings, updated_at = NOW()
                WHERE id = :tenant_id
            """
            
            await session.execute(settings_query, {
                "tenant_id": tenant_id,
                "settings": json.dumps(limits)
            })
            
            await session.commit()
    
    async def _cache_tenant_info(self, domain: str, tenant_info: Dict[str, Any]):
        """Cache tenant information in Redis."""
        
        try:
            await redis_client.setex(
                f"tenant:{domain}",
                3600,  # 1 hour
                json.dumps(tenant_info, default=str)
            )
        except Exception as e:
            logger.warning("Failed to cache tenant info", domain=domain, error=str(e))
    
    async def _load_tenant_cache(self):
        """Load tenant cache from database."""
        
        try:
            async with db_manager.get_session() as session:
                query = """
                    SELECT id, name, domain, plan, status, settings
                    FROM tenants 
                    WHERE status = 'active'
                """
                
                result = await session.execute(query)
                
                for row in result.fetchall():
                    tenant_info = {
                        "id": row[0],
                        "name": row[1],
                        "domain": row[2],
                        "plan": row[3],
                        "status": row[4],
                        "settings": json.loads(row[5]) if row[5] else {}
                    }
                    
                    self.tenant_cache[row[2]] = tenant_info
                
                logger.info("Tenant cache loaded", count=len(self.tenant_cache))
                
        except Exception as e:
            logger.error("Failed to load tenant cache", error=str(e))
    
    async def _create_tables(self):
        """Create multi-tenancy tables."""
        
        async with db_manager.get_session() as session:
            create_tables_query = """
                -- Tenants table
                CREATE TABLE IF NOT EXISTS tenants (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(255) NOT NULL,
                    domain VARCHAR(255) UNIQUE NOT NULL,
                    plan VARCHAR(50) DEFAULT 'free',
                    status VARCHAR(50) DEFAULT 'active',
                    admin_email VARCHAR(255),
                    settings JSONB,
                    created_by INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                
                -- Tenant users relationship table
                CREATE TABLE IF NOT EXISTS tenant_users (
                    id SERIAL PRIMARY KEY,
                    tenant_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    role VARCHAR(50) DEFAULT 'user',
                    added_by INTEGER,
                    removed_by INTEGER,
                    is_active BOOLEAN DEFAULT true,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                    UNIQUE(tenant_id, user_id, is_active)
                );
                
                -- Add tenant_id to existing tables for isolation
                DO $$ 
                BEGIN
                    -- Add tenant_id to users table if not exists
                    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                                  WHERE table_name='users' AND column_name='tenant_id') THEN
                        ALTER TABLE users ADD COLUMN tenant_id INTEGER;
                        ALTER TABLE users ADD CONSTRAINT fk_users_tenant 
                            FOREIGN KEY (tenant_id) REFERENCES tenants(id);
                    END IF;
                    
                    -- Add tenant_id to ai_systems table if not exists
                    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                                  WHERE table_name='ai_systems' AND column_name='tenant_id') THEN
                        ALTER TABLE ai_systems ADD COLUMN tenant_id INTEGER;
                        ALTER TABLE ai_systems ADD CONSTRAINT fk_ai_systems_tenant 
                            FOREIGN KEY (tenant_id) REFERENCES tenants(id);
                    END IF;
                END $$;
                
                -- Indexes
                CREATE INDEX IF NOT EXISTS idx_tenants_domain ON tenants(domain);
                CREATE INDEX IF NOT EXISTS idx_tenants_status ON tenants(status);
                CREATE INDEX IF NOT EXISTS idx_tenant_users_tenant_id ON tenant_users(tenant_id);
                CREATE INDEX IF NOT EXISTS idx_tenant_users_user_id ON tenant_users(user_id);
                CREATE INDEX IF NOT EXISTS idx_tenant_users_active ON tenant_users(tenant_id, user_id, is_active);
            """
            
            await session.execute(create_tables_query)
            await session.commit()

# Global instance
multi_tenant_manager = MultiTenantManager()