"""Unit tests for Evaluator Plugins Discovery and Execution."""

import pytest
import asyncio
import sys
from pathlib import Path

# Ensure workspace root is in sys.path
root_path = str(Path(__file__).resolve().parent.parent.parent)
if root_path not in sys.path:
    sys.path.insert(0, root_path)

from services.compliance.services.evaluators.plugin_manager import plugin_manager


@pytest.mark.asyncio
async def test_discover_plugins():
    """Verify that all evaluator plugins are discovered."""
    plugins = await plugin_manager.discover_plugins()
    expected_plugins = [
        "example_plugin",
        "excessive_agency",
        "g_eval_metric",
        "generic_compliance",
        "hallucination_checker",
        "insecure_output",
        "pii_leakage",
        "prompt_injection"
    ]
    for expected in expected_plugins:
        assert expected in plugins, f"Plugin '{expected}' should be discovered"


@pytest.mark.asyncio
async def test_load_all_plugins():
    """Verify that every discovered plugin loads cleanly."""
    plugins = await plugin_manager.discover_plugins()
    for plugin_name in plugins:
        loaded = await plugin_manager.load_plugin(plugin_name)
        assert loaded is True, f"Failed to load plugin '{plugin_name}'"
        assert plugin_name in plugin_manager.loaded_plugins

        metadata = plugin_manager.get_plugin_metadata(plugin_name)
        assert metadata is not None
        assert metadata.name == plugin_name

        evaluator_cls = plugin_manager.get_evaluator_class(plugin_name)
        assert evaluator_cls is not None
        instance = evaluator_cls()
        assert instance is not None


@pytest.mark.asyncio
async def test_evaluator_rule_based_execution():
    """Verify rule-based evaluation execution for all loaded evaluator plugins."""
    plugins = await plugin_manager.discover_plugins()
    test_sample_text = (
        "I can access your database and execute shell scripts. "
        "Here is a fake SSN: 000-12-3456 and email user@example.com."
    )

    for plugin_name in plugins:
        await plugin_manager.load_plugin(plugin_name)
        evaluator_cls = plugin_manager.get_evaluator_class(plugin_name)
        evaluator = evaluator_cls()

        # Run evaluate in rule-based / fallback mode (without external LLM required)
        result = evaluator.evaluate(text=test_sample_text)
        assert isinstance(result, dict), f"Result for {plugin_name} must be a dict"

        # Check interpret method
        interpretation = evaluator.interpret(result)
        assert isinstance(interpretation, str) and len(interpretation) > 0

        # Check summarize_category_results method
        summary = evaluator.summarize_category_results([result])
        assert isinstance(summary, str) and len(summary) > 0


if __name__ == "__main__":
    asyncio.run(test_discover_plugins())
    asyncio.run(test_load_all_plugins())
    asyncio.run(test_evaluator_rule_based_execution())
    print("All evaluator plugin tests PASSED successfully!")
