"""Plugin management endpoints."""

from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
import structlog

from ...shared.auth import get_current_active_user, require_admin
from ...shared.schemas import UserResponse, ApiResponse
from ..framework.core.registry import Registry
from ..services.evaluators.plugin_manager import plugin_manager
from ..services.evaluators.enhanced_evaluator_factory import enhanced_evaluator_factory

logger = structlog.get_logger()
router = APIRouter()

class PluginConfigRequest(BaseModel):
    config: Dict[str, Any]

class PluginStatusRequest(BaseModel):
    enabled: bool

@router.get("/", response_model=ApiResponse[List[Dict[str, Any]]])
async def get_plugins(
    category: Optional[str] = None,
    enabled_only: bool = False,
    current_user: UserResponse = Depends(get_current_active_user)
):
    """Get list of available plugins."""
    
    try:
        # Discover all plugins
        discovered_plugins = await plugin_manager.discover_plugins()
        loaded_plugins = plugin_manager.get_loaded_plugins()
        
        plugins_info = []
        
        for plugin_name in discovered_plugins:
            metadata = plugin_manager.get_plugin_metadata(plugin_name)
            is_loaded = plugin_name in loaded_plugins
            
            # Apply filters
            if enabled_only and not is_loaded:
                continue
            
            if category and metadata and metadata.category.lower() != category.lower():
                continue
            
            plugin_info = {
                "name": plugin_name,
                "loaded": is_loaded,
                "enabled": metadata.enabled if metadata else False,
                "version": metadata.version if metadata else "unknown",
                "description": metadata.description if metadata else "",
                "author": metadata.author if metadata else "",
                "framework": metadata.framework if metadata else plugin_name.upper(),
                "category": metadata.category if metadata else "custom",
                "tags": metadata.tags if metadata else [],
                "dependencies": metadata.dependencies if metadata else [],
                "supported_models": metadata.supported_models if metadata else [],
                "min_platform_version": metadata.min_platform_version if metadata else "1.0.0"
            }
            
            plugins_info.append(plugin_info)
        
        return ApiResponse(
            success=True,
            data=plugins_info,
            message=f"Found {len(plugins_info)} plugins"
        )
        
    except Exception as e:
        logger.error("Failed to get plugins", error=str(e))
        return ApiResponse(
            success=False,
            message=f"Failed to get plugins: {str(e)}"
        )

@router.get("/{plugin_name}", response_model=ApiResponse[Dict[str, Any]])
async def get_plugin_details(
    plugin_name: str,
    current_user: UserResponse = Depends(get_current_active_user)
):
    """Get detailed information about a specific plugin."""
    
    try:
        metadata = plugin_manager.get_plugin_metadata(plugin_name)
        config = plugin_manager.get_plugin_config(plugin_name)
        is_loaded = plugin_name in plugin_manager.get_loaded_plugins()
        
        if not metadata:
            # Try to load metadata from disk
            discovered = await plugin_manager.discover_plugins()
            if plugin_name not in discovered:
                raise HTTPException(status_code=404, detail=f"Plugin not found: {plugin_name}")
            
            # Load plugin to get metadata
            await plugin_manager.load_plugin(plugin_name)
            metadata = plugin_manager.get_plugin_metadata(plugin_name)
            config = plugin_manager.get_plugin_config(plugin_name)
            is_loaded = True
        
        plugin_details = {
            "name": plugin_name,
            "loaded": is_loaded,
            "enabled": metadata.enabled if metadata else False,
            "version": metadata.version if metadata else "unknown",
            "description": metadata.description if metadata else "",
            "author": metadata.author if metadata else "",
            "framework": metadata.framework if metadata else plugin_name.upper(),
            "category": metadata.category if metadata else "custom",
            "tags": metadata.tags if metadata else [],
            "dependencies": metadata.dependencies if metadata else [],
            "supported_models": metadata.supported_models if metadata else [],
            "min_platform_version": metadata.min_platform_version if metadata else "1.0.0",
            "config_schema": metadata.config_schema if metadata else {},
            "current_config": config or {}
        }
        
        # If loaded, get evaluator information
        if is_loaded:
            evaluator_class = plugin_manager.get_evaluator_class(plugin_name)
            if evaluator_class:
                plugin_details["evaluator_class"] = evaluator_class.__name__
                plugin_details["evaluator_module"] = evaluator_class.__module__
        
        return ApiResponse(
            success=True,
            data=plugin_details,
            message=f"Plugin details for {plugin_name}"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get plugin details", plugin=plugin_name, error=str(e))
        return ApiResponse(
            success=False,
            message=f"Failed to get plugin details: {str(e)}"
        )

@router.post("/{plugin_name}/load", response_model=ApiResponse[Dict[str, Any]])
async def load_plugin(
    plugin_name: str,
    current_user: UserResponse = Depends(require_admin)
):
    """Load a specific plugin."""
    
    try:
        success = await plugin_manager.load_plugin(plugin_name)
        
        if success:
            # Update enhanced factory
            await enhanced_evaluator_factory.reload_plugins()
            
            return ApiResponse(
                success=True,
                data={"plugin": plugin_name, "loaded": True},
                message=f"Plugin {plugin_name} loaded successfully"
            )
        else:
            return ApiResponse(
                success=False,
                message=f"Failed to load plugin {plugin_name}"
            )
            
    except Exception as e:
        logger.error("Failed to load plugin", plugin=plugin_name, error=str(e))
        return ApiResponse(
            success=False,
            message=f"Failed to load plugin: {str(e)}"
        )

@router.post("/{plugin_name}/unload", response_model=ApiResponse[Dict[str, Any]])
async def unload_plugin(
    plugin_name: str,
    current_user: UserResponse = Depends(require_admin)
):
    """Unload a specific plugin."""
    
    try:
        success = await plugin_manager.unload_plugin(plugin_name)
        
        if success:
            # Update enhanced factory
            await enhanced_evaluator_factory.reload_plugins()
            
            return ApiResponse(
                success=True,
                data={"plugin": plugin_name, "loaded": False},
                message=f"Plugin {plugin_name} unloaded successfully"
            )
        else:
            return ApiResponse(
                success=False,
                message=f"Failed to unload plugin {plugin_name}"
            )
            
    except Exception as e:
        logger.error("Failed to unload plugin", plugin=plugin_name, error=str(e))
        return ApiResponse(
            success=False,
            message=f"Failed to unload plugin: {str(e)}"
        )

@router.post("/{plugin_name}/reload", response_model=ApiResponse[Dict[str, Any]])
async def reload_plugin(
    plugin_name: str,
    current_user: UserResponse = Depends(require_admin)
):
    """Reload a specific plugin."""
    
    try:
        success = await plugin_manager.reload_plugin(plugin_name)
        
        if success:
            # Update enhanced factory
            await enhanced_evaluator_factory.reload_plugins()
            
            return ApiResponse(
                success=True,
                data={"plugin": plugin_name, "reloaded": True},
                message=f"Plugin {plugin_name} reloaded successfully"
            )
        else:
            return ApiResponse(
                success=False,
                message=f"Failed to reload plugin {plugin_name}"
            )
            
    except Exception as e:
        logger.error("Failed to reload plugin", plugin=plugin_name, error=str(e))
        return ApiResponse(
            success=False,
            message=f"Failed to reload plugin: {str(e)}"
        )

@router.post("/{plugin_name}/enable", response_model=ApiResponse[Dict[str, Any]])
async def enable_plugin(
    plugin_name: str,
    current_user: UserResponse = Depends(require_admin)
):
    """Enable a plugin."""
    
    try:
        success = await plugin_manager.enable_plugin(plugin_name)
        
        if success:
            return ApiResponse(
                success=True,
                data={"plugin": plugin_name, "enabled": True},
                message=f"Plugin {plugin_name} enabled successfully"
            )
        else:
            return ApiResponse(
                success=False,
                message=f"Failed to enable plugin {plugin_name}"
            )
            
    except Exception as e:
        logger.error("Failed to enable plugin", plugin=plugin_name, error=str(e))
        return ApiResponse(
            success=False,
            message=f"Failed to enable plugin: {str(e)}"
        )

@router.post("/{plugin_name}/disable", response_model=ApiResponse[Dict[str, Any]])
async def disable_plugin(
    plugin_name: str,
    current_user: UserResponse = Depends(require_admin)
):
    """Disable a plugin."""
    
    try:
        success = await plugin_manager.disable_plugin(plugin_name)
        
        if success:
            return ApiResponse(
                success=True,
                data={"plugin": plugin_name, "enabled": False},
                message=f"Plugin {plugin_name} disabled successfully"
            )
        else:
            return ApiResponse(
                success=False,
                message=f"Failed to disable plugin {plugin_name}"
            )
            
    except Exception as e:
        logger.error("Failed to disable plugin", plugin=plugin_name, error=str(e))
        return ApiResponse(
            success=False,
            message=f"Failed to disable plugin: {str(e)}"
        )

@router.get("/{plugin_name}/config", response_model=ApiResponse[Dict[str, Any]])
async def get_plugin_config(
    plugin_name: str,
    current_user: UserResponse = Depends(get_current_active_user)
):
    """Get plugin configuration."""
    
    try:
        config = plugin_manager.get_plugin_config(plugin_name)
        metadata = plugin_manager.get_plugin_metadata(plugin_name)
        
        return ApiResponse(
            success=True,
            data={
                "plugin": plugin_name,
                "config": config or {},
                "schema": metadata.config_schema if metadata else {}
            },
            message=f"Configuration for plugin {plugin_name}"
        )
        
    except Exception as e:
        logger.error("Failed to get plugin config", plugin=plugin_name, error=str(e))
        return ApiResponse(
            success=False,
            message=f"Failed to get plugin config: {str(e)}"
        )

@router.put("/{plugin_name}/config", response_model=ApiResponse[Dict[str, Any]])
async def update_plugin_config(
    plugin_name: str,
    config_request: PluginConfigRequest,
    current_user: UserResponse = Depends(require_admin)
):
    """Update plugin configuration."""
    
    try:
        # Validate configuration if plugin is loaded
        if plugin_name in plugin_manager.get_loaded_plugins():
            plugin_interface = plugin_manager.loaded_plugins[plugin_name]
            if not plugin_interface.validate_config(config_request.config):
                return ApiResponse(
                    success=False,
                    message="Invalid plugin configuration"
                )
        
        # Save configuration
        import yaml
        from pathlib import Path
        
        config_file = Path(plugin_manager.plugins_dir) / "configs" / f"{plugin_name}.yaml"
        config_file.parent.mkdir(exist_ok=True)
        
        with open(config_file, 'w', encoding='utf-8') as f:
            yaml.dump(config_request.config, f, default_flow_style=False)
        
        # Update in-memory config
        plugin_manager.plugin_configs[plugin_name] = config_request.config
        
        return ApiResponse(
            success=True,
            data={
                "plugin": plugin_name,
                "config": config_request.config
            },
            message=f"Configuration updated for plugin {plugin_name}"
        )
        
    except Exception as e:
        logger.error("Failed to update plugin config", plugin=plugin_name, error=str(e))
        return ApiResponse(
            success=False,
            message=f"Failed to update plugin config: {str(e)}"
        )

@router.post("/{plugin_name}/validate-config", response_model=ApiResponse[Dict[str, Any]])
async def validate_plugin_config(
    plugin_name: str,
    config_request: PluginConfigRequest,
    current_user: UserResponse = Depends(get_current_active_user)
):
    """Validate plugin configuration."""
    
    try:
        # Check if plugin exists
        if plugin_name not in await plugin_manager.discover_plugins():
            raise HTTPException(status_code=404, detail=f"Plugin not found: {plugin_name}")
        
        # Load plugin if not loaded
        if plugin_name not in plugin_manager.get_loaded_plugins():
            await plugin_manager.load_plugin(plugin_name)
        
        # Validate configuration
        plugin_interface = plugin_manager.loaded_plugins.get(plugin_name)
        if not plugin_interface:
            return ApiResponse(
                success=False,
                message=f"Plugin {plugin_name} not loaded"
            )
        
        is_valid = plugin_interface.validate_config(config_request.config)
        
        return ApiResponse(
            success=True,
            data={
                "plugin": plugin_name,
                "valid": is_valid,
                "config": config_request.config
            },
            message=f"Configuration validation result for {plugin_name}"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to validate plugin config", plugin=plugin_name, error=str(e))
        return ApiResponse(
            success=False,
            message=f"Failed to validate plugin config: {str(e)}"
        )

@router.get("/statistics", response_model=ApiResponse[Dict[str, Any]])
async def get_plugin_statistics(
    current_user: UserResponse = Depends(get_current_active_user)
):
    """Get plugin system statistics."""
    
    try:
        discovered = await plugin_manager.discover_plugins()
        loaded = plugin_manager.get_loaded_plugins()
        
        # Get category distribution
        categories = {}
        for plugin_name in discovered:
            metadata = plugin_manager.get_plugin_metadata(plugin_name)
            if metadata:
                category = metadata.category
                categories[category] = categories.get(category, 0) + 1
        
        # Get framework statistics
        framework_stats = enhanced_evaluator_factory.get_framework_statistics()
        
        statistics = {
            "plugins": {
                "total_discovered": len(discovered),
                "loaded": len(loaded),
                "enabled": len([p for p in discovered if plugin_manager.get_plugin_metadata(p) and plugin_manager.get_plugin_metadata(p).enabled]),
                "categories": categories
            },
            "frameworks": framework_stats,
            "system": {
                "plugins_directory": str(plugin_manager.plugins_dir),
                "plugin_manager_initialized": True
            }
        }
        
        return ApiResponse(
            success=True,
            data=statistics,
            message="Plugin system statistics"
        )
        
    except Exception as e:
        logger.error("Failed to get plugin statistics", error=str(e))
        return ApiResponse(
            success=False,
            message=f"Failed to get plugin statistics: {str(e)}"
        )