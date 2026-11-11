# framework/core/registry.py
import importlib
import inspect
import logging
import pkgutil
import re
import traceback
from pathlib import Path
from types import ModuleType
from typing import Any, Type

try:
    from .base import BaseEvaluator
except ImportError:
    BaseEvaluator = Any

logger = logging.getLogger(__name__)


class Registry:
    """Central registry for evaluators with auto-discovery."""

    _evaluators: dict[str, Type[BaseEvaluator]] = {}

    @classmethod
    def discover_evaluators(cls) -> None:
        """Automatically discover and register all evaluators in the evaluators directory."""
        evaluators_path = Path(__file__).parent.parent / 'evaluators'
        failed_evaluators = []

        if not evaluators_path.exists():
            logger.warning(f"Evaluators directory not found: {evaluators_path}")
            return

        # Get all subdirectories in the evaluators directory
        for module_info in pkgutil.iter_modules([str(evaluators_path)]):
            if not module_info.ispkg:
                continue

            module_name = f"services.compliance.framework.evaluators.{module_info.name}.evaluator"
            try:
                module = cls._safe_import_module(module_name)
                if not module:
                    continue

                # Find all classes that inherit from BaseEvaluator
                for name, obj in inspect.getmembers(module):
                    if (inspect.isclass(obj) and
                            issubclass(obj, BaseEvaluator) and
                            obj != BaseEvaluator):
                        try:
                            # Try to create an instance to verify initialization works
                            evaluator_instance = obj()
                            cls.register_evaluator(obj, alias=module_info.name)
                            logger.info(f"Successfully registered evaluator: {obj.get_metadata().name}")
                        except Exception as init_error:
                            error_msg = f"Failed to initialize evaluator {name}: {str(init_error)}"
                            logger.warning(error_msg)
                            failed_evaluators.append({
                                "name": name,
                                "error": str(init_error)
                            })

            except Exception as e:
                error_msg = f"Failed to load evaluator module {module_info.name}: {str(e)}"
                logger.warning(error_msg)
                failed_evaluators.append({
                    "name": module_info.name,
                    "error": str(e)
                })

        if failed_evaluators:
            logger.warning("Failed evaluators summary:")
            for failure in failed_evaluators:
                logger.warning(f"- {failure['name']}: {failure['error']}")

        # Discover and register active custom evaluator plugins
        try:
            from ...services.evaluators.plugin_manager import plugin_manager
            for plugin_name, plugin_inst in plugin_manager.loaded_plugins.items():
                try:
                    eval_cls = plugin_inst.get_evaluator_class()
                    if eval_cls:
                        cls.register_evaluator(eval_cls, alias=plugin_name)
                except Exception as e:
                    logger.warning(f"Failed to register plugin evaluator {plugin_name}: {e}")
        except Exception as plugin_err:
            logger.debug(f"Plugin auto-discovery check skipped: {plugin_err}")

    @classmethod
    def _safe_import_module(cls, module_name: str) -> ModuleType | None:
        """Safely import a module with error handling."""
        try:
            return importlib.import_module(module_name)
        except ModuleNotFoundError as e:
            logger.error(f"Module {module_name} not found: {e}")
            return None
        except ImportError as e:
            logger.error(f"Error importing {module_name}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error importing {module_name}: {e}")
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(traceback.format_exc())
            return None

    @staticmethod
    def _slug(name: str) -> str:
        """Normalize an evaluator name for lookup: 'Prompt Injection Evaluator' -> 'prompt_injection'."""
        slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
        return slug.removesuffix("_evaluator")

    @classmethod
    def register_evaluator(cls, evaluator_class: Type[BaseEvaluator], alias: str | None = None) -> None:
        """Register an evaluator class under its display name and, optionally, its directory name."""
        metadata = evaluator_class.get_metadata()
        cls._evaluators[metadata.name] = evaluator_class
        if alias and alias != metadata.name:
            cls._evaluators[alias] = evaluator_class

    @classmethod
    def get_evaluator(cls, name: str, **kwargs) -> BaseEvaluator:
        """Get an instance of a registered evaluator.

        Accepts the display name ('Prompt Injection Evaluator'), the plugin
        directory name ('prompt_injection'), or the framework tag
        ('PROMPT_INJECTION') — all normalize through _slug.
        """
        evaluator_class = cls._evaluators.get(name)
        if evaluator_class is None:
            wanted = cls._slug(name)
            for registered, klass in cls._evaluators.items():
                if cls._slug(registered) == wanted:
                    evaluator_class = klass
                    break
        if evaluator_class is None:
            available_evaluators = ", ".join(cls._evaluators.keys()) or "none"
            raise ValueError(f"Unknown evaluator: '{name}'. Available evaluators: {available_evaluators}")

        try:
            return evaluator_class(**kwargs)
        except Exception as e:
            raise RuntimeError(f"Failed to instantiate evaluator '{name}'") from e

    @classmethod
    def list_evaluators(cls) -> list[str]:
        """Get list of registered evaluators."""
        return list(cls._evaluators.keys())
