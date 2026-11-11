# framework/api/__init__.py
"""Bridge to AI Governance Suite Unified API."""

try:
    from shared.unified_api import get_unified_api, ModelConfig, ModelResponse
    from shared.unified_api.base import ModelType
    
    # Re-export for framework use
    __all__ = ['get_unified_api', 'ModelConfig', 'ModelResponse', 'ModelType']
    
except ImportError as e:
    # Fallback for testing or development
    print(f"Warning: Could not import unified API: {e}")
    
    # Provide mock implementations
    def get_unified_api():
        return None
    
    ModelConfig = None
    ModelResponse = None
    ModelType = None
    
    __all__ = ['get_unified_api', 'ModelConfig', 'ModelResponse', 'ModelType']
