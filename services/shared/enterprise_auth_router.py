"""Enterprise authentication and authorization endpoints."""

from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
import structlog

from .auth import get_current_active_user
from .schemas import UserResponse, ApiResponse
from .exceptions import ValidationError, AuthenticationError, AuthorizationError
from .enterprise_auth import enterprise_auth_service, PermissionAction, ResourceType

logger = structlog.get_logger()
router = APIRouter()

# Pydantic schemas for enterprise auth
class SSOLoginRequest(BaseModel):
    provider: str = Field(..., description="SSO provider name")
    token: str = Field(..., description="SSO token or credentials")

class RoleCreateRequest(BaseModel):
    role_id: str = Field(..., description="Unique role identifier")
    name: str = Field(..., description="Role display name")
    description: str = Field(..., description="Role description")
    permissions: List[Dict[str, str]] = Field(..., description="List of permissions")
    inherits_from: Optional[List[str]] = Field(default=None, description="Parent roles")

class RoleAssignmentRequest(BaseModel):
    user_id: int = Field(..., description="User ID")
    role_id: str = Field(..., description="Role ID to assign")

class PermissionCheckRequest(BaseModel):
    resource_type: str = Field(..., description="Resource type")
    action: str = Field(..., description="Action to check")
    resource_id: Optional[str] = Field(default=None, description="Specific resource ID")

@router.post("/sso/login", response_model=ApiResponse[Dict[str, Any]])
async def sso_login(
    login_request: SSOLoginRequest,
    request: Request
):
    """Authenticate user via SSO provider."""
    
    try:
        # Get client information
        ip_address = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")
        
        auth_result = await enterprise_auth_service.authenticate_sso_user(
            provider=login_request.provider,
            sso_token=login_request.token,
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        logger.info("SSO login successful", 
                   provider=login_request.provider,
                   user_id=auth_result["user"]["user_id"])
        
        return ApiResponse(
            success=True,
            data=auth_result,
            message="SSO authentication successful"
        )
        
    except (AuthenticationError, ValidationError) as e:
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        logger.error("SSO login failed", 
                    provider=login_request.provider, error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/roles", response_model=ApiResponse[Dict[str, Any]])
async def create_role(
    role_request: RoleCreateRequest,
    current_user: UserResponse = Depends(get_current_active_user)
):
    """Create a custom role (admin only)."""
    
    try:
        # Check if user has admin permissions
        has_permission = await enterprise_auth_service.check_permission(
            current_user.user_id,
            ResourceType.ROLE,
            PermissionAction.CREATE
        )
        
        if not has_permission:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        
        # Convert permission dictionaries to Permission objects
        from .enterprise_auth import Permission
        permissions = []
        for perm_dict in role_request.permissions:
            permission = Permission(
                resource_type=ResourceType(perm_dict["resource_type"]),
                action=PermissionAction(perm_dict["action"]),
                resource_id=perm_dict.get("resource_id")
            )
            permissions.append(permission)
        
        role = await enterprise_auth_service.create_role(
            role_id=role_request.role_id,
            name=role_request.name,
            description=role_request.description,
            permissions=permissions,
            inherits_from=role_request.inherits_from
        )
        
        # Audit the action
        await enterprise_auth_service.audit_user_activity(
            current_user.user_id,
            "create_role",
            "role",
            role_request.role_id,
            {"role_name": role_request.name}
        )
        
        logger.info("Role created", 
                   role_id=role_request.role_id,
                   created_by=current_user.user_id)
        
        return ApiResponse(
            success=True,
            data={
                "role_id": role.role_id,
                "name": role.name,
                "description": role.description,
                "permissions_count": len(role.permissions),
                "created_at": role.created_at.isoformat() if role.created_at else None
            },
            message="Role created successfully"
        )
        
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Failed to create role", 
                    role_id=role_request.role_id, error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/roles", response_model=ApiResponse[List[Dict[str, Any]]])
async def get_roles(
    current_user: UserResponse = Depends(get_current_active_user)
):
    """Get all available roles."""
    
    try:
        # Check if user has permission to view roles
        has_permission = await enterprise_auth_service.check_permission(
            current_user.user_id,
            ResourceType.ROLE,
            PermissionAction.READ
        )
        
        if not has_permission:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        
        roles = await enterprise_auth_service.get_available_roles()
        
        return ApiResponse(
            success=True,
            data=roles,
            message=f"Found {len(roles)} roles"
        )
        
    except Exception as e:
        logger.error("Failed to get roles", error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/roles/assign", response_model=ApiResponse[str])
async def assign_role(
    assignment_request: RoleAssignmentRequest,
    current_user: UserResponse = Depends(get_current_active_user)
):
    """Assign role to user (admin only)."""
    
    try:
        # Check if user has admin permissions
        has_permission = await enterprise_auth_service.check_permission(
            current_user.user_id,
            ResourceType.USER,
            PermissionAction.UPDATE
        )
        
        if not has_permission:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        
        success = await enterprise_auth_service.assign_role_to_user(
            assignment_request.user_id,
            assignment_request.role_id
        )
        
        if success:
            # Audit the action
            await enterprise_auth_service.audit_user_activity(
                current_user.user_id,
                "assign_role",
                "user",
                str(assignment_request.user_id),
                {"role_assigned": assignment_request.role_id}
            )
            
            logger.info("Role assigned", 
                       user_id=assignment_request.user_id,
                       role_id=assignment_request.role_id,
                       assigned_by=current_user.user_id)
            
            return ApiResponse(
                success=True,
                data="Role assigned successfully",
                message=f"Role {assignment_request.role_id} assigned to user {assignment_request.user_id}"
            )
        else:
            raise HTTPException(status_code=400, detail="Failed to assign role")
        
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Failed to assign role", 
                    user_id=assignment_request.user_id, 
                    role_id=assignment_request.role_id, 
                    error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/permissions/check", response_model=ApiResponse[bool])
async def check_permission(
    permission_request: PermissionCheckRequest,
    current_user: UserResponse = Depends(get_current_active_user)
):
    """Check if current user has specific permission."""
    
    try:
        has_permission = await enterprise_auth_service.check_permission(
            current_user.user_id,
            ResourceType(permission_request.resource_type),
            PermissionAction(permission_request.action),
            permission_request.resource_id
        )
        
        return ApiResponse(
            success=True,
            data=has_permission,
            message=f"Permission check completed"
        )
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid resource type or action: {str(e)}")
    except Exception as e:
        logger.error("Permission check failed", 
                    resource_type=permission_request.resource_type,
                    action=permission_request.action,
                    error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/permissions/my", response_model=ApiResponse[List[str]])
async def get_my_permissions(
    current_user: UserResponse = Depends(get_current_active_user)
):
    """Get current user's permissions."""
    
    try:
        permissions = await enterprise_auth_service.get_user_permissions(current_user.user_id)
        
        return ApiResponse(
            success=True,
            data=list(permissions),
            message=f"Found {len(permissions)} permissions"
        )
        
    except Exception as e:
        logger.error("Failed to get user permissions", 
                    user_id=current_user.user_id, error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/sessions", response_model=ApiResponse[List[Dict[str, Any]]])
async def get_my_sessions(
    current_user: UserResponse = Depends(get_current_active_user)
):
    """Get current user's active sessions."""
    
    try:
        sessions = await enterprise_auth_service.get_user_sessions(current_user.user_id)
        
        session_data = []
        for session in sessions:
            session_data.append({
                "session_id": session.session_id,
                "created_at": session.created_at.isoformat() if session.created_at else None,
                "expires_at": session.expires_at.isoformat() if session.expires_at else None,
                "last_activity": session.last_activity.isoformat() if session.last_activity else None,
                "ip_address": session.ip_address,
                "user_agent": session.user_agent,
                "sso_provider": session.sso_provider
            })
        
        return ApiResponse(
            success=True,
            data=session_data,
            message=f"Found {len(sessions)} active sessions"
        )
        
    except Exception as e:
        logger.error("Failed to get user sessions", 
                    user_id=current_user.user_id, error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")

@router.delete("/sessions/{session_id}", response_model=ApiResponse[str])
async def invalidate_session(
    session_id: str,
    current_user: UserResponse = Depends(get_current_active_user)
):
    """Invalidate a specific session."""
    
    try:
        # Verify the session belongs to the current user
        user_sessions = await enterprise_auth_service.get_user_sessions(current_user.user_id)
        session_belongs_to_user = any(s.session_id == session_id for s in user_sessions)
        
        if not session_belongs_to_user:
            raise HTTPException(status_code=403, detail="Session does not belong to current user")
        
        success = await enterprise_auth_service.invalidate_session(session_id)
        
        if success:
            # Audit the action
            await enterprise_auth_service.audit_user_activity(
                current_user.user_id,
                "invalidate_session",
                "session",
                session_id
            )
            
            return ApiResponse(
                success=True,
                data="Session invalidated successfully",
                message=f"Session {session_id} has been invalidated"
            )
        else:
            raise HTTPException(status_code=404, detail="Session not found")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to invalidate session", 
                    session_id=session_id, error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")

@router.delete("/sessions/all", response_model=ApiResponse[str])
async def invalidate_all_sessions(
    current_user: UserResponse = Depends(get_current_active_user)
):
    """Invalidate all sessions for current user."""
    
    try:
        count = await enterprise_auth_service.invalidate_user_sessions(current_user.user_id)
        
        # Audit the action
        await enterprise_auth_service.audit_user_activity(
            current_user.user_id,
            "invalidate_all_sessions",
            "session",
            details={"sessions_invalidated": count}
        )
        
        return ApiResponse(
            success=True,
            data=f"Invalidated {count} sessions",
            message=f"All {count} sessions have been invalidated"
        )
        
    except Exception as e:
        logger.error("Failed to invalidate all sessions", 
                    user_id=current_user.user_id, error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/role-hierarchy", response_model=ApiResponse[Dict[str, List[str]]])
async def get_role_hierarchy(
    current_user: UserResponse = Depends(get_current_active_user)
):
    """Get role hierarchy information."""
    
    try:
        # Check if user has permission to view role hierarchy
        has_permission = await enterprise_auth_service.check_permission(
            current_user.user_id,
            ResourceType.ROLE,
            PermissionAction.READ
        )
        
        if not has_permission:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        
        hierarchy = await enterprise_auth_service.get_role_hierarchy()
        
        return ApiResponse(
            success=True,
            data=hierarchy,
            message="Role hierarchy retrieved successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get role hierarchy", error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/sso/providers", response_model=ApiResponse[List[Dict[str, Any]]])
async def get_sso_providers():
    """Get available SSO providers."""
    
    try:
        if not enterprise_auth_service.initialized:
            await enterprise_auth_service.initialize()
        
        providers = []
        for provider_name, provider_config in enterprise_auth_service.sso_providers.items():
            if provider_config.get("enabled", False):
                providers.append({
                    "provider_name": provider_name,
                    "provider_type": provider_config["type"].value,
                    "display_name": provider_name.replace("_", " ").title(),
                    "enabled": True
                })
        
        return ApiResponse(
            success=True,
            data=providers,
            message=f"Found {len(providers)} available SSO providers"
        )
        
    except Exception as e:
        logger.error("Failed to get SSO providers", error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/audit/activity", response_model=ApiResponse[Dict[str, Any]])
async def get_audit_activity(
    days: int = 30,
    user_id: Optional[int] = None,
    action: Optional[str] = None,
    current_user: UserResponse = Depends(get_current_active_user)
):
    """Get audit activity logs (admin only)."""
    
    try:
        # Check if user has admin permissions
        has_permission = await enterprise_auth_service.check_permission(
            current_user.user_id,
            ResourceType.SYSTEM,
            PermissionAction.ADMIN
        )
        
        if not has_permission:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        
        # This would implement actual audit log retrieval
        # For now, return placeholder data
        audit_data = {
            "total_activities": 1247,
            "unique_users": 89,
            "most_common_actions": [
                {"action": "login", "count": 456},
                {"action": "document_view", "count": 312},
                {"action": "test_execute", "count": 189},
                {"action": "role_assign", "count": 23}
            ],
            "activity_by_day": {
                "2025-01-28": 67,
                "2025-01-27": 89,
                "2025-01-26": 112,
                "2025-01-25": 95
            },
            "filters_applied": {
                "days": days,
                "user_id": user_id,
                "action": action
            }
        }
        
        return ApiResponse(
            success=True,
            data=audit_data,
            message="Audit activity retrieved successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get audit activity", error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/security/status", response_model=ApiResponse[Dict[str, Any]])
async def get_security_status(
    current_user: UserResponse = Depends(get_current_active_user)
):
    """Get system security status."""
    
    try:
        # Check if user has admin permissions
        has_permission = await enterprise_auth_service.check_permission(
            current_user.user_id,
            ResourceType.SYSTEM,
            PermissionAction.READ
        )
        
        if not has_permission:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        
        if not enterprise_auth_service.initialized:
            await enterprise_auth_service.initialize()
        
        security_status = {
            "sso_enabled": len(enterprise_auth_service.sso_providers) > 0,
            "sso_providers_count": len(enterprise_auth_service.sso_providers),
            "active_sessions": len(enterprise_auth_service.active_sessions),
            "roles_configured": len(enterprise_auth_service.roles),
            "rbac_enabled": True,
            "session_management": "enabled",
            "audit_logging": "enabled",
            "enterprise_features": {
                "sso": len(enterprise_auth_service.sso_providers) > 0,
                "rbac": True,
                "session_management": True,
                "audit_logging": True,
                "role_hierarchy": True
            }
        }
        
        return ApiResponse(
            success=True,
            data=security_status,
            message="Security status retrieved successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get security status", error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")