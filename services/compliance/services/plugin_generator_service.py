"""Scaffolds evaluator plugin directories for the /plugin-generator routes.

Generates a plugin.py + metadata.yaml pair modeled on
plugins/evaluators/example_plugin/. The router is admin-only, but the
plugin name still crosses a trust boundary into the filesystem — it is
slug-validated and existing directories are never overwritten.
"""

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import structlog

from ...shared.exceptions import ValidationError

logger = structlog.get_logger()

SLUG_RE = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")

TEMPLATES = ["custom_evaluator"]

_DEFAULT_TEST_CASES = [
    {
        "name": "Example check",
        "description": "Placeholder test case — replace with real checks",
        "category": "custom",
        "severity": "medium",
        "test_type": "prompt",
        "requirement": "Describe the compliance requirement here",
        "prompt": "Sample prompt for the AI system",
    }
]

_PLUGIN_PY_TEMPLATE = '''"""Generated custom evaluator plugin: {plugin_name}."""

from typing import Dict, Any, Type
import structlog

from services.compliance.services.evaluators.plugin_manager import PluginInterface
from services.compliance.services.evaluators.base_evaluator import BaseEvaluator
from services.compliance.services.evaluators.custom_evaluator_template import CustomEvaluatorTemplate

logger = structlog.get_logger()


class {class_name}Evaluator(CustomEvaluatorTemplate):
    """{description}"""

    def __init__(self):
        super().__init__()
        self.framework_name = "{framework_name}"

    async def _load_test_cases(self):
        """Load the generated test cases."""
        self.test_cases = {test_cases}


class {class_name}Plugin(PluginInterface):
    """Plugin interface for {plugin_name}."""

    def get_metadata(self) -> Dict[str, Any]:
        """Return plugin metadata."""
        return {{
            "name": "{plugin_name}",
            "version": "1.0.0",
            "description": "{description}",
            "author": "{author}",
            "framework": "{framework_name}",
            "category": "{category}",
            "tags": ["custom", "generated"],
            "dependencies": [],
            "supported_models": [],
            "min_platform_version": "1.0.0"
        }}

    def get_evaluator_class(self) -> Type[BaseEvaluator]:
        """Return the evaluator class."""
        return {class_name}Evaluator

    def validate_config(self, config: Dict[str, Any]) -> bool:
        """Validate plugin configuration."""
        return True

    def on_load(self) -> None:
        """Called when plugin is loaded."""
        logger.info("Plugin loaded", plugin="{plugin_name}")

    def on_unload(self) -> None:
        """Called when plugin is unloaded."""
        logger.info("Plugin unloaded", plugin="{plugin_name}")
'''

_METADATA_YAML_TEMPLATE = """name: {plugin_name}
version: 1.0.0
description: {description}
author: {author}
framework: {framework_name}
category: {category}
enabled: true
tags: [custom, generated]
dependencies: []
supported_models: []
min_platform_version: 1.0.0
config_schema: {config_schema}
"""


class PluginGenerator:
    """Generates evaluator plugin scaffold directories."""

    def __init__(self, base_dir: str = "plugins/evaluators"):
        self.base_dir = Path(base_dir)

    def list_available_templates(self) -> List[str]:
        """Return the scaffold templates supported by generate_from_template."""
        return list(TEMPLATES)

    def _slugify(self, plugin_name: str) -> str:
        """Validate a plugin name for safe use as a directory name."""
        slug = plugin_name.strip().lower()
        if not SLUG_RE.match(slug):
            raise ValidationError(
                f"Invalid plugin name '{plugin_name}': use letters, digits, "
                "'-' and '_', starting with a letter"
            )
        return slug

    @staticmethod
    def _class_name(slug: str) -> str:
        return "".join(part.title() for part in re.split(r"[-_]", slug))

    def generate_plugin(
        self,
        plugin_name: str,
        framework_name: str,
        description: str,
        author: str = "Unknown",
        category: str = "custom",
        test_cases: Optional[List[Dict[str, Any]]] = None,
        config_schema: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Write a new plugin scaffold. Raises on bad names or conflicts."""
        slug = self._slugify(plugin_name)
        plugin_dir = self.base_dir / slug
        if plugin_dir.exists():
            raise ValidationError(f"Plugin already exists: {slug}")

        plugin_dir.mkdir(parents=True)

        # json.dumps strings embed safely into Python code and YAML; repr()
        # keeps test_cases a Python literal.
        (plugin_dir / "plugin.py").write_text(
            _PLUGIN_PY_TEMPLATE.format(
                plugin_name=slug,
                class_name=self._class_name(slug),
                framework_name=framework_name,
                description=description.replace('"', "'").replace("\n", " "),
                author=author.replace('"', "'").replace("\n", " "),
                category=category,
                test_cases=repr(test_cases or _DEFAULT_TEST_CASES),
            ),
            encoding="utf-8",
        )

        schema = config_schema or {"type": "object", "properties": {}}
        (plugin_dir / "metadata.yaml").write_text(
            _METADATA_YAML_TEMPLATE.format(
                plugin_name=slug,
                framework_name=framework_name,
                description=json.dumps(description),
                author=json.dumps(author),
                category=json.dumps(category),
                config_schema=json.dumps(schema),
            ),
            encoding="utf-8",
        )

        logger.info("Plugin scaffold generated", plugin=slug, path=str(plugin_dir))
        return True

    def generate_from_template(
        self,
        template_name: str,
        plugin_name: str,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Generate a plugin from a named scaffold template."""
        if template_name not in self.list_available_templates():
            raise ValidationError(f"Unknown template: {template_name}")
        return self.generate_plugin(plugin_name=plugin_name, **(parameters or {}))


plugin_generator = PluginGenerator()
