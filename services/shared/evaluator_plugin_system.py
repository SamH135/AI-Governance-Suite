"""
Custom Evaluator Plugin System
Allows dynamic loading and execution of custom evaluation logic
"""

import os
import sys
import json
import uuid
import asyncio
import importlib
import importlib.util
from datetime import datetime
from typing import Dict, List, Any, Optional, Callable, Union
from enum import Enum
from dataclasses import dataclass, asdict
from abc import ABC, abstractmethod
import structlog
from pathlib import Path

try:
    import docker
    DOCKER_AVAILABLE = True
except ImportError:
    DOCKER_AVAILABLE = False
    docker = None

from .database import db_manager
from .exceptions import ValidationError, ExternalServiceError
from .audit_logging_service import audit_logging_service, AuditEventType, AuditSeverity, AuditStatus

logger = structlog.get_logger()

class PluginType(str, Enum):
    """Types of evaluator plugins."""
    COMPLIANCE_CHECKER = "compliance_checker"
    SECURITY_ANALYZER = "security_analyzer"
    QUALITY_ASSESSOR = "quality_assessor"
    BIAS_DETECTOR = "bias_detector"
    PERFORMANCE_EVALUATOR = "performance_evaluator"
    CUSTOM_LOGIC = "custom_logic"

class PluginStatus(str, Enum):
    """Plugin status states."""
    PENDING = "pending"
    ACTIVE = "active"
    DISABLED = "disabled"
    ERROR = "error"
    DEPRECATED = "deprecated"

class ExecutionMode(str, Enum):
    """Plugin execution modes."""
    SYNCHRONOUS = "synchronous"
    ASYNCHRONOUS = "asynchronous"
    BATCH = "batch"
    STREAMING = "streaming"

@dataclass
class PluginConfig:
    """Configuration for a plugin."""
    plugin_id: str
    name: str
    description: str
    version: str
    plugin_type: PluginType
    execution_mode: ExecutionMode
    author: str
    created_at: datetime
    parameters: Dict[str, Any]
    requirements: List[str]
    permissions: List[str]
    timeout_seconds: int = 300
    memory_limit_mb: int = 512
    cpu_limit: float = 1.0

@dataclass
class PluginResult:
    """Result from plugin execution."""
    plugin_id: str
    execution_id: str
    status: str
    result: Any
    metadata: Dict[str, Any]
    execution_time_seconds: float
    error_message: Optional[str] = None
    warnings: List[str] = None

class BaseEvaluatorPlugin(ABC):
    """Base class for all evaluator plugins."""
    
    def __init__(self, config: PluginConfig):
        self.config = config
        self.logger = structlog.get_logger().bind(plugin_id=config.plugin_id)
    
    @abstractmethod
    async def evaluate(self, input_data: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Evaluate input data and return results.
        
        Args:
            input_data: The data to evaluate
            context: Additional context (user info, system state, etc.)
            
        Returns:
            Dict containing evaluation results
        """
        pass
    
    def validate_input(self, input_data: Dict[str, Any]) -> bool:
        """Validate input data format."""
        return True
    
    def get_schema(self) -> Dict[str, Any]:
        """Return JSON schema for expected input data."""
        return {}

class PluginManager:
    """Manages custom evaluator plugins."""
    
    def __init__(self):
        self.initialized = False
        self.plugins: Dict[str, BaseEvaluatorPlugin] = {}
        self.plugin_configs: Dict[str, PluginConfig] = {}
        self.plugin_directory = Path("plugins")
        self.sandboxed_execution = True
        self.docker_client = None
        
    async def initialize(self):
        """Initialize the plugin system."""
        if self.initialized:
            return
        
        try:
            # Create plugin directory
            self.plugin_directory.mkdir(exist_ok=True)
            
            # Initialize Docker client if available
            if DOCKER_AVAILABLE and self.sandboxed_execution:
                try:
                    self.docker_client = docker.from_env()
                    logger.info("Docker client initialized for sandboxed plugin execution")
                except Exception as e:
                    logger.warning("Failed to initialize Docker client", error=str(e))
                    self.sandboxed_execution = False
            
            # Load existing plugins
            await self._load_plugins()
            
            # Start monitoring task
            asyncio.create_task(self._plugin_monitoring_task())
            
            self.initialized = True
            logger.info("Plugin system initialized", plugin_count=len(self.plugins))
            
        except Exception as e:
            logger.error("Failed to initialize plugin system", error=str(e))
            raise ExternalServiceError("PluginSystem", f"Initialization failed: {str(e)}")
    
    async def register_plugin(
        self,
        plugin_code: str,
        config: PluginConfig,
        user_id: int,
        validate_only: bool = False
    ) -> Dict[str, Any]:
        """Register a new custom plugin."""
        if not self.initialized:
            await self.initialize()
        
        try:
            # Validate plugin code
            validation_result = await self._validate_plugin_code(plugin_code, config)
            
            if not validation_result["valid"]:
                raise ValidationError(f"Plugin validation failed: {validation_result['errors']}")
            
            if validate_only:
                return validation_result
            
            # Save plugin to filesystem
            plugin_path = self.plugin_directory / f"{config.plugin_id}.py"
            plugin_path.write_text(plugin_code)
            
            # Save plugin config
            config_path = self.plugin_directory / f"{config.plugin_id}.json"
            config_path.write_text(json.dumps(asdict(config), default=str, indent=2))
            
            # Load and instantiate plugin
            plugin_instance = await self._load_plugin(config.plugin_id, plugin_code, config)
            
            # Store in memory
            self.plugins[config.plugin_id] = plugin_instance
            self.plugin_configs[config.plugin_id] = config
            
            # Log audit event
            await audit_logging_service.log_event(
                event_type=AuditEventType.SYSTEM_CONFIG_CHANGE,
                user_id=user_id,
                action=f"Registered custom evaluator plugin: {config.name}",
                status=AuditStatus.SUCCESS,
                severity=AuditSeverity.MEDIUM,
                resource_type="plugin",
                resource_id=config.plugin_id,
                details={
                    "plugin_name": config.name,
                    "plugin_type": config.plugin_type,
                    "version": config.version
                }
            )
            
            logger.info("Plugin registered successfully", 
                       plugin_id=config.plugin_id,
                       plugin_name=config.name,
                       user_id=user_id)
            
            return {
                "plugin_id": config.plugin_id,
                "status": "registered",
                "validation": validation_result
            }
            
        except Exception as e:
            logger.error("Failed to register plugin", 
                        plugin_id=config.plugin_id, error=str(e))
            raise ValidationError(f"Failed to register plugin: {str(e)}")
    
    async def execute_plugin(
        self,
        plugin_id: str,
        input_data: Dict[str, Any],
        context: Dict[str, Any],
        user_id: int
    ) -> PluginResult:
        """Execute a plugin with given input data."""
        if not self.initialized:
            await self.initialize()
        
        if plugin_id not in self.plugins:
            raise ValidationError(f"Plugin {plugin_id} not found")
        
        execution_id = str(uuid.uuid4())
        start_time = datetime.utcnow()
        
        try:
            plugin = self.plugins[plugin_id]
            config = self.plugin_configs[plugin_id]
            
            # Validate input
            if not plugin.validate_input(input_data):
                raise ValidationError("Invalid input data for plugin")
            
            # Add execution context
            execution_context = {
                **context,
                "execution_id": execution_id,
                "user_id": user_id,
                "plugin_id": plugin_id,
                "timestamp": start_time.isoformat()
            }
            
            # Execute plugin with timeout
            if config.execution_mode == ExecutionMode.SYNCHRONOUS:
                result = await asyncio.wait_for(
                    plugin.evaluate(input_data, execution_context),
                    timeout=config.timeout_seconds
                )
            else:
                # For async/batch/streaming modes, start execution and return immediately
                asyncio.create_task(self._execute_plugin_async(
                    plugin, input_data, execution_context, execution_id
                ))
                result = {"status": "started", "execution_id": execution_id}
            
            execution_time = (datetime.utcnow() - start_time).total_seconds()
            
            # Create result object
            plugin_result = PluginResult(
                plugin_id=plugin_id,
                execution_id=execution_id,
                status="success",
                result=result,
                metadata={
                    "plugin_name": config.name,
                    "plugin_version": config.version,
                    "execution_mode": config.execution_mode,
                    "input_size": len(str(input_data))
                },
                execution_time_seconds=execution_time
            )
            
            # Log audit event
            await audit_logging_service.log_event(
                event_type=AuditEventType.TEST_EXECUTE,
                user_id=user_id,
                action=f"Executed plugin: {config.name}",
                status=AuditStatus.SUCCESS,
                severity=AuditSeverity.LOW,
                resource_type="plugin",
                resource_id=plugin_id,
                details={
                    "execution_id": execution_id,
                    "execution_time": execution_time,
                    "plugin_type": config.plugin_type
                }
            )
            
            logger.info("Plugin executed successfully", 
                       plugin_id=plugin_id,
                       execution_id=execution_id,
                       execution_time=execution_time)
            
            return plugin_result
            
        except asyncio.TimeoutError:
            execution_time = (datetime.utcnow() - start_time).total_seconds()
            
            await audit_logging_service.log_event(
                event_type=AuditEventType.TEST_EXECUTE,
                user_id=user_id,
                action=f"Plugin execution timeout: {config.name}",
                status=AuditStatus.ERROR,
                severity=AuditSeverity.HIGH,
                resource_type="plugin",
                resource_id=plugin_id,
                details={"execution_id": execution_id, "timeout": config.timeout_seconds}
            )
            
            return PluginResult(
                plugin_id=plugin_id,
                execution_id=execution_id,
                status="timeout",
                result=None,
                metadata={"timeout_seconds": config.timeout_seconds},
                execution_time_seconds=execution_time,
                error_message=f"Plugin execution timed out after {config.timeout_seconds} seconds"
            )
            
        except Exception as e:
            execution_time = (datetime.utcnow() - start_time).total_seconds()
            
            await audit_logging_service.log_event(
                event_type=AuditEventType.TEST_EXECUTE,
                user_id=user_id,
                action=f"Plugin execution failed: {config.name}",
                status=AuditStatus.ERROR,
                severity=AuditSeverity.MEDIUM,
                resource_type="plugin",
                resource_id=plugin_id,
                details={"execution_id": execution_id, "error": str(e)}
            )
            
            logger.error("Plugin execution failed", 
                        plugin_id=plugin_id,
                        execution_id=execution_id,
                        error=str(e))
            
            return PluginResult(
                plugin_id=plugin_id,
                execution_id=execution_id,
                status="error",
                result=None,
                metadata={},
                execution_time_seconds=execution_time,
                error_message=str(e)
            )
    
    async def get_plugin_list(self) -> List[Dict[str, Any]]:
        """Get list of all registered plugins."""
        if not self.initialized:
            await self.initialize()
        
        plugin_list = []
        for plugin_id, config in self.plugin_configs.items():
            plugin_info = {
                "plugin_id": plugin_id,
                "name": config.name,
                "description": config.description,
                "version": config.version,
                "plugin_type": config.plugin_type,
                "execution_mode": config.execution_mode,
                "author": config.author,
                "created_at": config.created_at.isoformat(),
                "status": "active" if plugin_id in self.plugins else "error",
                "schema": self.plugins[plugin_id].get_schema() if plugin_id in self.plugins else {}
            }
            plugin_list.append(plugin_info)
        
        return plugin_list
    
    async def get_plugin_details(self, plugin_id: str) -> Dict[str, Any]:
        """Get detailed information about a specific plugin."""
        if plugin_id not in self.plugin_configs:
            raise ValidationError(f"Plugin {plugin_id} not found")
        
        config = self.plugin_configs[plugin_id]
        plugin = self.plugins.get(plugin_id)
        
        details = {
            "config": asdict(config),
            "status": "active" if plugin else "error",
            "schema": plugin.get_schema() if plugin else {},
            "last_execution": None,  # Would be stored in database
            "execution_count": 0,    # Would be stored in database
            "average_execution_time": 0.0  # Would be calculated from history
        }
        
        return details
    
    async def disable_plugin(self, plugin_id: str, user_id: int) -> bool:
        """Disable a plugin."""
        if plugin_id not in self.plugins:
            raise ValidationError(f"Plugin {plugin_id} not found")
        
        try:
            # Remove from active plugins
            plugin_name = self.plugin_configs[plugin_id].name
            del self.plugins[plugin_id]
            
            # Update config status
            self.plugin_configs[plugin_id].status = PluginStatus.DISABLED
            
            # Log audit event
            await audit_logging_service.log_event(
                event_type=AuditEventType.SYSTEM_CONFIG_CHANGE,
                user_id=user_id,
                action=f"Disabled plugin: {plugin_name}",
                status=AuditStatus.SUCCESS,
                severity=AuditSeverity.MEDIUM,
                resource_type="plugin",
                resource_id=plugin_id
            )
            
            logger.info("Plugin disabled", plugin_id=plugin_id, user_id=user_id)
            return True
            
        except Exception as e:
            logger.error("Failed to disable plugin", plugin_id=plugin_id, error=str(e))
            return False
    
    async def remove_plugin(self, plugin_id: str, user_id: int) -> bool:
        """Remove a plugin completely."""
        if plugin_id not in self.plugin_configs:
            raise ValidationError(f"Plugin {plugin_id} not found")
        
        try:
            plugin_name = self.plugin_configs[plugin_id].name
            
            # Remove from memory
            if plugin_id in self.plugins:
                del self.plugins[plugin_id]
            del self.plugin_configs[plugin_id]
            
            # Remove from filesystem
            plugin_path = self.plugin_directory / f"{plugin_id}.py"
            config_path = self.plugin_directory / f"{plugin_id}.json"
            
            if plugin_path.exists():
                plugin_path.unlink()
            if config_path.exists():
                config_path.unlink()
            
            # Log audit event
            await audit_logging_service.log_event(
                event_type=AuditEventType.SYSTEM_CONFIG_CHANGE,
                user_id=user_id,
                action=f"Removed plugin: {plugin_name}",
                status=AuditStatus.SUCCESS,
                severity=AuditSeverity.HIGH,
                resource_type="plugin",
                resource_id=plugin_id
            )
            
            logger.info("Plugin removed", plugin_id=plugin_id, user_id=user_id)
            return True
            
        except Exception as e:
            logger.error("Failed to remove plugin", plugin_id=plugin_id, error=str(e))
            return False
    
    # Private helper methods
    async def _load_plugins(self):
        """Load all plugins from the plugin directory."""
        try:
            for config_file in self.plugin_directory.glob("*.json"):
                plugin_id = config_file.stem
                
                try:
                    # Load config
                    config_data = json.loads(config_file.read_text())
                    config = PluginConfig(**config_data)
                    
                    # Load plugin code
                    plugin_file = self.plugin_directory / f"{plugin_id}.py"
                    if plugin_file.exists():
                        plugin_code = plugin_file.read_text()
                        
                        # Load plugin instance
                        plugin_instance = await self._load_plugin(plugin_id, plugin_code, config)
                        
                        self.plugins[plugin_id] = plugin_instance
                        self.plugin_configs[plugin_id] = config
                        
                        logger.info("Plugin loaded", plugin_id=plugin_id, name=config.name)
                    
                except Exception as e:
                    logger.error("Failed to load plugin", plugin_id=plugin_id, error=str(e))
                    
        except Exception as e:
            logger.error("Failed to load plugins", error=str(e))
    
    async def _load_plugin(
        self,
        plugin_id: str,
        plugin_code: str,
        config: PluginConfig
    ) -> BaseEvaluatorPlugin:
        """Load a plugin from code string."""
        try:
            # Create module spec
            spec = importlib.util.spec_from_loader(
                f"plugin_{plugin_id}",
                loader=None,
                origin="dynamic"
            )
            
            # Create module
            module = importlib.util.module_from_spec(spec)
            
            # Add to sys.modules to allow imports
            sys.modules[f"plugin_{plugin_id}"] = module
            
            # Execute code in module namespace
            exec(plugin_code, module.__dict__)
            
            # Find plugin class (should inherit from BaseEvaluatorPlugin)
            plugin_class = None
            for name, obj in module.__dict__.items():
                if (isinstance(obj, type) and 
                    issubclass(obj, BaseEvaluatorPlugin) and 
                    obj != BaseEvaluatorPlugin):
                    plugin_class = obj
                    break
            
            if not plugin_class:
                raise ValidationError("Plugin must contain a class inheriting from BaseEvaluatorPlugin")
            
            # Instantiate plugin
            plugin_instance = plugin_class(config)
            
            return plugin_instance
            
        except Exception as e:
            logger.error("Failed to load plugin instance", plugin_id=plugin_id, error=str(e))
            raise ValidationError(f"Failed to load plugin: {str(e)}")
    
    async def _validate_plugin_code(
        self,
        plugin_code: str,
        config: PluginConfig
    ) -> Dict[str, Any]:
        """Validate plugin code for security and correctness."""
        validation_result = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "security_score": 100
        }
        
        try:
            # Security checks
            forbidden_imports = [
                "subprocess", "os.system", "eval", "exec", "open",
                "file", "__import__", "compile", "globals", "locals"
            ]
            
            for forbidden in forbidden_imports:
                if forbidden in plugin_code:
                    validation_result["errors"].append(f"Forbidden function/import: {forbidden}")
                    validation_result["security_score"] -= 20
            
            # Check for file system access
            file_operations = ["open(", "file(", "with open", "pathlib", "shutil"]
            for operation in file_operations:
                if operation in plugin_code:
                    validation_result["warnings"].append(f"File system operation detected: {operation}")
                    validation_result["security_score"] -= 10
            
            # Check for network access
            network_imports = ["requests", "urllib", "socket", "http", "asyncio.open_connection"]
            for network in network_imports:
                if network in plugin_code:
                    validation_result["warnings"].append(f"Network access detected: {network}")
                    validation_result["security_score"] -= 15
            
            # Syntax validation
            try:
                compile(plugin_code, f"plugin_{config.plugin_id}", "exec")
            except SyntaxError as e:
                validation_result["errors"].append(f"Syntax error: {str(e)}")
            
            # Structure validation
            if "class" not in plugin_code or "BaseEvaluatorPlugin" not in plugin_code:
                validation_result["errors"].append("Plugin must contain a class inheriting from BaseEvaluatorPlugin")
            
            if "async def evaluate" not in plugin_code:
                validation_result["errors"].append("Plugin must implement async def evaluate method")
            
            # Set final validation status
            if validation_result["errors"]:
                validation_result["valid"] = False
            
            if validation_result["security_score"] < 50:
                validation_result["errors"].append("Security score too low - plugin rejected")
                validation_result["valid"] = False
            
        except Exception as e:
            validation_result["valid"] = False
            validation_result["errors"].append(f"Validation error: {str(e)}")
        
        return validation_result
    
    async def _execute_plugin_async(
        self,
        plugin: BaseEvaluatorPlugin,
        input_data: Dict[str, Any],
        context: Dict[str, Any],
        execution_id: str
    ):
        """Execute plugin asynchronously and store results."""
        try:
            result = await plugin.evaluate(input_data, context)
            
            # Store result in database or cache
            # Implementation would depend on your storage preferences
            logger.info("Async plugin execution completed", execution_id=execution_id)
            
        except Exception as e:
            logger.error("Async plugin execution failed", 
                        execution_id=execution_id, error=str(e))
    
    async def _plugin_monitoring_task(self):
        """Background task to monitor plugin health and performance."""
        while True:
            try:
                await asyncio.sleep(300)  # Run every 5 minutes
                
                # Check plugin status
                failed_plugins = []
                for plugin_id, plugin in self.plugins.items():
                    try:
                        # Simple health check
                        if hasattr(plugin, 'health_check'):
                            await plugin.health_check()
                    except Exception as e:
                        logger.warning("Plugin health check failed", 
                                     plugin_id=plugin_id, error=str(e))
                        failed_plugins.append(plugin_id)
                
                # Handle failed plugins
                for plugin_id in failed_plugins:
                    config = self.plugin_configs[plugin_id]
                    logger.error("Plugin marked as unhealthy", 
                               plugin_id=plugin_id, name=config.name)
                
            except Exception as e:
                logger.error("Plugin monitoring task error", error=str(e))

# Global plugin manager instance
plugin_manager = PluginManager()