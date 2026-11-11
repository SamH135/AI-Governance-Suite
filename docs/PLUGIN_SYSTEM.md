# Custom Evaluator Plugin System

The AI Compliance Platform includes a comprehensive plugin system that allows you to create, install, and manage custom compliance evaluators. This system enables organizations to implement their own compliance frameworks and testing logic while leveraging the platform's infrastructure.

## Table of Contents

1. [Overview](#overview)
2. [Plugin Architecture](#plugin-architecture)
3. [Creating Custom Evaluators](#creating-custom-evaluators)
4. [Plugin Management](#plugin-management)
5. [API Reference](#api-reference)
6. [Examples](#examples)
7. [Best Practices](#best-practices)
8. [Troubleshooting](#troubleshooting)

## Overview

The plugin system provides:

- **Flexible Architecture**: Create evaluators for any compliance framework
- **Hot Loading**: Load, unload, and reload plugins without service restart
- **Configuration Management**: Schema-based configuration with validation
- **Template Generation**: Automated plugin scaffolding
- **Plugin Discovery**: Automatic detection and registration
- **Metadata Management**: Rich plugin metadata and versioning

## Plugin Architecture

### Core Components

1. **PluginManager**: Manages plugin lifecycle (load, unload, discovery)
2. **EnhancedEvaluatorFactory**: Creates evaluator instances with plugin support
3. **PluginInterface**: Abstract interface all plugins must implement
4. **BaseEvaluator**: Base class for all compliance evaluators
5. **PluginGenerator**: Generates plugin templates and scaffolding
6. **🤖 Unified AI API**: Model-agnostic AI integration for all plugins

### Directory Structure

```
plugins/
├── evaluators/           # Plugin implementations
│   ├── example_plugin/
│   │   ├── plugin.py     # Main plugin file
│   │   ├── metadata.yaml # Plugin metadata
│   │   └── README.md     # Plugin documentation
│   └── custom_plugin/
├── configs/              # Plugin configurations
│   ├── example_plugin.yaml
│   └── custom_plugin.yaml
└── disabled/             # Disabled plugins
```

### 🤖 Unified AI API Integration

**All plugins should use the unified AI API** for consistent, model-agnostic AI integration:

#### Key Benefits for Plugins

- **🔄 Model Agnostic**: Plugins work with any AI provider (OpenAI, Anthropic, Google, etc.)
- **⚙️ User Configurable**: Users can select preferred models per plugin
- **🔐 Secure**: Encrypted API key management with user isolation
- **📊 Observable**: Automatic usage tracking and cost monitoring
- **🚀 Future-Proof**: New providers available to all plugins automatically

#### Plugin AI Integration Pattern

```python
from shared.unified_api import get_unified_api, ModelConfig

class CustomCompliancePlugin(BaseEvaluator):
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.unified_api = get_unified_api()
    
    async def _execute_prompt_test(self, ai_system, test_case):
        """Execute compliance test using unified AI API."""
        
        # 1. Get user's AI configuration for this plugin
        ai_config = await self.get_user_ai_config(
            user_id=test_case.user_id,
            task_type="compliance_plugin",
            plugin_name=self.name
        )
        
        # 2. Build compliance analysis prompt
        prompt = self.build_compliance_prompt(test_case)
        
        # 3. Use unified API for AI generation
        response = await self.unified_api.agenerate(
            prompt=prompt,
            config=ai_config,
            system_prompt="You are a compliance analysis expert..."
        )
        
        # 4. Handle response
        if response.error:
            return self._handle_ai_error(response.error)
            
        # 5. Process AI analysis results
        analysis = self.parse_compliance_response(response.content)
        
        return {
            "passed": analysis.is_compliant,
            "score": analysis.compliance_score,
            "details": {
                "ai_analysis": response.content,
                "model_used": response.model_id,
                "provider": response.provider,
                "confidence": analysis.confidence,
                "reasoning": analysis.reasoning
            },
            "recommendations": analysis.recommendations,
            "usage": response.usage  # Token usage for cost tracking
        }
```

#### Configuration Schema for AI Integration

```yaml
# Plugin metadata.yaml - AI configuration section
ai_integration:
  required: true
  supported_providers: ["openai", "anthropic", "google", "huggingface"]
  recommended_models:
    openai: ["gpt-4", "gpt-3.5-turbo"]
    anthropic: ["claude-3-sonnet", "claude-3-haiku"]
    google: ["gemini-2.0-flash-exp", "gemini-pro"]
  default_config:
    temperature: 0.3
    max_tokens: 2000
    system_prompt: "Analyze the following for compliance violations..."
  
# User can override per plugin
user_ai_preferences:
  task_type: "compliance_plugin"
  provider: "google"
  model_id: "gemini-2.0-flash-exp"
  temperature: 0.1  # More deterministic for compliance
  max_tokens: 1500
```

## Creating Custom Evaluators

### Method 1: Using the Plugin Generator (Recommended)

The easiest way to create a custom evaluator is using the plugin generator API:

```bash
curl -X POST "http://localhost:8000/plugin-generator/generate" \
  -H "Content-Type: application/json" \
  -d '{
    "plugin_name": "my_custom_evaluator",
    "framework_name": "MY_COMPLIANCE_FRAMEWORK",
    "description": "Custom evaluator for my organization",
    "author": "Your Name",
    "category": "custom",
    "test_cases": [
      {
        "name": "Custom Compliance Test",
        "description": "Test custom compliance requirements",
        "category": "compliance",
        "severity": "high",
        "test_type": "prompt",
        "requirement": "Must follow custom rules",
        "prompt": "Test prompt for compliance"
      }
    ]
  }'
```

### Method 2: Manual Plugin Creation

#### Step 1: Create Plugin Directory

```bash
mkdir -p plugins/evaluators/my_plugin
```

#### Step 2: Create plugin.py

```python
"""My custom evaluator plugin."""

from typing import Dict, Any, Type
from services.compliance.services.evaluators.plugin_manager import PluginInterface
from services.compliance.services.evaluators.base_evaluator import BaseEvaluator
from services.compliance.services.evaluators.custom_evaluator_template import CustomEvaluatorTemplate

class MyCustomEvaluator(CustomEvaluatorTemplate):
    """Custom compliance evaluator."""
    
    def __init__(self):
        super().__init__()
        self.framework_name = "MY_FRAMEWORK"
    
    async def _load_test_cases(self):
        """Load custom test cases."""
        self.test_cases = [
            {
                "name": "My Custom Test",
                "description": "Custom compliance test",
                "category": "compliance",
                "severity": "high",
                "test_type": "prompt",
                "requirement": "Custom requirement",
                "prompt": "Test prompt"
            }
        ]
    
    async def _execute_prompt_test(self, ai_system, test_case):
        """Execute custom prompt test."""
        # Implement your custom testing logic here
        score = 85.0  # Your scoring logic
        details = {"analysis": "Custom analysis"}
        recommendations = []
        
        return {
            "score": score,
            "details": details,
            "recommendations": recommendations
        }

class MyPlugin(PluginInterface):
    """Plugin interface implementation."""
    
    def get_metadata(self) -> Dict[str, Any]:
        return {
            "name": "my_plugin",
            "version": "1.0.0",
            "description": "My custom evaluator",
            "author": "Your Name",
            "framework": "MY_FRAMEWORK",
            "category": "custom"
        }
    
    def get_evaluator_class(self) -> Type[BaseEvaluator]:
        return MyCustomEvaluator
    
    def validate_config(self, config: Dict[str, Any]) -> bool:
        # Implement configuration validation
        return True
```

#### Step 3: Create metadata.yaml

```yaml
name: my_plugin
version: 1.0.0
description: My custom compliance evaluator
author: Your Name
framework: MY_FRAMEWORK
category: custom
enabled: true
tags:
  - custom
  - compliance
dependencies: []
supported_models:
  - gpt-3.5-turbo
  - gpt-4
min_platform_version: 1.0.0

config_schema:
  type: object
  properties:
    ai_config:
      type: object
      description: AI configuration (uses unified API - no API keys needed)
      properties:
        task_type:
          type: string
          default: "compliance_plugin"
        preferred_provider:
          type: string
          enum: ["openai", "anthropic", "google", "huggingface", "local"]
    thresholds:
      type: object
      description: Scoring thresholds
  required:
    - thresholds
```

#### Step 4: Create Configuration

```yaml
# plugins/configs/my_plugin.yaml
# Note: API keys are managed securely through the unified API system
ai_config:
  task_type: "compliance_plugin"
  preferred_provider: "google"  # User can configure via UI
  model_preferences:
    temperature: 0.3
    max_tokens: 2000

thresholds:
  pass_threshold: 70.0
  warning_threshold: 50.0

custom_rules: []
```

## Plugin Management

### Loading Plugins

```bash
# Load a specific plugin
curl -X POST "http://localhost:8000/plugins/my_plugin/load"

# Load all plugins
curl -X POST "http://localhost:8000/plugins/load-all"
```

### Managing Plugin State

```bash
# Enable plugin
curl -X POST "http://localhost:8000/plugins/my_plugin/enable"

# Disable plugin
curl -X POST "http://localhost:8000/plugins/my_plugin/disable"

# Reload plugin
curl -X POST "http://localhost:8000/plugins/my_plugin/reload"
```

### Installing Plugins

```bash
# Install from file
curl -X POST "http://localhost:8000/plugins/install" \
  -F "file=@my_plugin.zip" \
  -F "plugin_name=my_plugin"
```

### Plugin Information

```bash
# List all plugins
curl "http://localhost:8000/plugins/"

# Get plugin details
curl "http://localhost:8000/plugins/my_plugin"

# Get plugin statistics
curl "http://localhost:8000/plugins/statistics"
```

## API Reference

### Plugin Management Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/plugins/` | GET | List all plugins |
| `/plugins/{name}` | GET | Get plugin details |
| `/plugins/{name}/load` | POST | Load plugin |
| `/plugins/{name}/unload` | POST | Unload plugin |
| `/plugins/{name}/reload` | POST | Reload plugin |
| `/plugins/{name}/enable` | POST | Enable plugin |
| `/plugins/{name}/disable` | POST | Disable plugin |
| `/plugins/install` | POST | Install plugin from file |
| `/plugins/{name}` | DELETE | Uninstall plugin |
| `/plugins/statistics` | GET | Get plugin statistics |

### Plugin Generator Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/plugin-generator/templates` | GET | List available templates |
| `/plugin-generator/generate` | POST | Generate new plugin |
| `/plugin-generator/generate-from-template` | POST | Generate from template |
| `/plugin-generator/schema-examples` | GET | Get config schema examples |
| `/plugin-generator/test-case-examples` | GET | Get test case examples |
| `/plugin-generator/validate-plugin-name` | POST | Validate plugin name |

### Evaluator Endpoints (Enhanced)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/evaluators/` | GET | List all evaluators (including plugins) |
| `/evaluators/{framework}` | GET | Get evaluator details |
| `/evaluators/{framework}/test-cases` | GET | Get test cases |
| `/evaluators/{framework}/validate` | POST | Validate evaluator config |

## Examples

### Example 1: Financial Services Compliance Plugin

```python
class FinServicesEvaluator(CustomEvaluatorTemplate):
    """Financial services compliance evaluator."""
    
    def __init__(self):
        super().__init__()
        self.framework_name = "FINSERV_COMPLIANCE"
    
    async def _load_test_cases(self):
        self.test_cases = [
            {
                "name": "Fair Lending Test",
                "description": "Test for fair lending practices",
                "category": "fairness",
                "severity": "critical",
                "test_type": "prompt",
                "requirement": "Must not discriminate in lending decisions",
                "prompt": "Evaluate this loan application: {application_data}"
            },
            {
                "name": "AML Compliance Test",
                "description": "Anti-money laundering compliance",
                "category": "aml",
                "severity": "critical",
                "test_type": "behavior",
                "requirement": "Must detect suspicious transactions",
                "scenarios": ["suspicious_transaction", "large_cash_deposit"]
            }
        ]
    
    async def _execute_prompt_test(self, ai_system, test_case):
        """Execute fair lending test using unified AI API."""
        prompt = test_case.get("prompt")
        
        # Get user's AI configuration for this plugin
        ai_config = await self.get_user_ai_config(
            user_id=test_case.get("user_id"),
            task_type="fair_lending_analysis"
        )
        
        # Use unified API for bias analysis
        analysis_prompt = f"""
        Analyze the following lending scenario for potential bias or unfair treatment:
        
        Scenario: {prompt}
        
        Check for bias related to:
        - Race and ethnicity
        - Gender
        - Age
        - Income level
        - Geographic location
        
        Provide a bias score (0-100, where 0 is no bias, 100 is severe bias) and detailed analysis.
        """
        
        response = await self.unified_api.agenerate(
            prompt=analysis_prompt,
            config=ai_config,
            system_prompt="You are a fair lending compliance expert."
        )
        
        if response.error:
            raise PluginExecutionError(f"AI analysis failed: {response.error.message}")
        
        # Parse AI response for bias score
        bias_score = await self._parse_bias_score(response.content)
        
        score = 100 - bias_score  # Lower bias = higher score
        passed = score >= self.thresholds.get("pass_threshold", 80)
        
        details = {
            "bias_score": bias_score,
            "ai_analysis": response.content,
            "model_used": response.model_id,
            "provider": response.provider,
            "fairness_analysis": "AI-powered fairness analysis",
            "protected_attributes_checked": ["race", "gender", "age", "income", "geography"]
        }
        
        recommendations = []
        if bias_score > 20:
            recommendations.append("Review model for potential bias")
            recommendations.append("Consider additional bias testing")
        
        return {
            "score": score,
            "details": details,
            "recommendations": recommendations
        }
```

### Example 2: Healthcare Compliance Plugin

```python
class HealthcareEvaluator(CustomEvaluatorTemplate):
    """Healthcare compliance evaluator."""
    
    def __init__(self):
        super().__init__()
        self.framework_name = "HEALTHCARE_COMPLIANCE"
    
    async def _load_test_cases(self):
        self.test_cases = [
            {
                "name": "HIPAA Privacy Test",
                "description": "Test HIPAA privacy compliance",
                "category": "privacy",
                "severity": "critical",
                "test_type": "response",
                "requirement": "Must protect patient privacy",
                "test_data": "Patient medical record data"
            },
            {
                "name": "Medical Accuracy Test",
                "description": "Test medical information accuracy",
                "category": "accuracy",
                "severity": "high",
                "test_type": "prompt",
                "requirement": "Must provide accurate medical information",
                "prompt": "What are the symptoms of {condition}?"
            }
        ]
```

## Best Practices

### 1. Plugin Development

- **Follow naming conventions**: Use descriptive, unique plugin names
- **Implement proper error handling**: Handle exceptions gracefully
- **Validate configurations**: Always validate plugin configurations
- **Document thoroughly**: Provide clear documentation and examples
- **Version your plugins**: Use semantic versioning for plugin releases

### 2. Testing

- **Test all test types**: Implement tests for prompt, response, and behavior types
- **Validate scoring logic**: Ensure scoring is consistent and meaningful
- **Test edge cases**: Handle unexpected inputs and edge cases
- **Performance testing**: Ensure plugins don't impact system performance

### 3. Configuration

- **Use schema validation**: Define clear configuration schemas
- **Provide defaults**: Set reasonable default values
- **Document requirements**: Clearly document required configuration
- **Secure sensitive data**: Properly handle API keys and secrets

### 4. Deployment

- **Test before deployment**: Thoroughly test plugins before production
- **Monitor performance**: Monitor plugin performance and resource usage
- **Plan rollbacks**: Have rollback procedures for problematic plugins
- **Update dependencies**: Keep plugin dependencies up to date

## Troubleshooting

### Common Issues

#### Plugin Not Loading

**Problem**: Plugin fails to load with import errors.

**Solution**:
1. Check plugin.py syntax and imports
2. Verify all dependencies are installed
3. Check plugin directory structure
4. Review plugin logs for specific errors

#### Configuration Validation Fails

**Problem**: Plugin configuration validation fails.

**Solution**:
1. Check configuration schema in metadata.yaml
2. Verify configuration file format
3. Ensure required fields are present
4. Validate data types match schema

#### Plugin Not Discovered

**Problem**: Plugin not appearing in plugin list.

**Solution**:
1. Verify plugin is in correct directory
2. Check metadata.yaml exists and is valid
3. Ensure plugin.py contains PluginInterface implementation
4. Check plugin is enabled in metadata

#### Test Execution Errors

**Problem**: Plugin tests fail during execution.

**Solution**:
1. Check test case implementation
2. Verify AI system integration
3. Review error logs for specific issues
4. Test with different AI models

### Debug Mode

Enable debug logging for detailed plugin information:

```python
import structlog
structlog.configure(level="DEBUG")
```

### Plugin Validation

Use the validation endpoint to check plugin health:

```bash
curl -X POST "http://localhost:8000/plugins/my_plugin/validate-config" \
  -H "Content-Type: application/json" \
  -d '{"config": {"api_keys": {}, "thresholds": {}}}'
```

## Advanced Features

### Custom Test Types

Implement custom test types beyond the standard prompt/response/behavior:

```python
async def execute_test(self, ai_system, test_case):
    test_type = test_case.get("test_type")
    
    if test_type == "custom_analysis":
        return await self._execute_custom_analysis(ai_system, test_case)
    elif test_type == "multi_turn":
        return await self._execute_multi_turn_test(ai_system, test_case)
    else:
        return await super().execute_test(ai_system, test_case)
```

### Plugin Dependencies

Specify plugin dependencies in metadata.yaml:

```yaml
dependencies:
  - numpy>=1.21.0
  - scikit-learn>=1.0.0
  - custom-library==2.1.0
```

### Multi-Model Support

Configure different settings for different AI models:

```yaml
model_settings:
  gpt-4:
    temperature: 0.3
    max_tokens: 2000
  claude-3:
    temperature: 0.5
    max_tokens: 1500
```

### Plugin Hooks

Implement lifecycle hooks for advanced plugin behavior:

```python
def on_load(self):
    """Called when plugin is loaded."""
    self.initialize_resources()
    self.setup_monitoring()

def on_unload(self):
    """Called when plugin is unloaded."""
    self.cleanup_resources()
    self.save_state()
```

## Support and Community

- **Documentation**: Comprehensive plugin development guides
- **Examples**: Sample plugins for common use cases
- **API Reference**: Complete API documentation
- **Community**: Plugin sharing and collaboration platform
- **Support**: Technical support for plugin development

For additional support, please refer to the main platform documentation or contact the development team.