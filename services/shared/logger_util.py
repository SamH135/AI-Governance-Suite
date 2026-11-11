"""
Logger utility for consistent logging across all services
"""

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

try:
    from logger import logger
except ImportError:
    # Fallback to standard logging with compatible wrapper
    import logging
    
    class CompatibleLogger:
        """Wrapper for standard Python logger to be compatible with custom logger interface."""
        
        def __init__(self):
            logging.basicConfig(
                level=logging.INFO,
                format='%(asctime)s [%(levelname)s] [%(filename)s::%(funcName)s] %(message)s'
            )
            self._logger = logging.getLogger(__name__)
        
        def _log(self, level_method, message, filename='', function_name='', **kwargs):
            """Internal logging method that handles both custom and standard parameters."""
            # Format message with location info if provided
            if filename and function_name:
                formatted_message = f"[{filename}::{function_name}] {message}"
            elif function_name:
                formatted_message = f"[{function_name}] {message}"
            else:
                formatted_message = message
            
            # Add any additional keyword arguments to the message
            if kwargs:
                extra_info = " ".join(f"{k}={v}" for k, v in kwargs.items())
                formatted_message = f"{formatted_message} {extra_info}"
            
            level_method(formatted_message)
        
        def info(self, message, filename='', function='', **kwargs):
            """Log info message with optional location parameters."""
            self._log(self._logger.info, message, filename, function, **kwargs)
        
        def warn(self, message, filename='', function='', **kwargs):
            """Log warning message with optional location parameters."""
            self._log(self._logger.warning, message, filename, function, **kwargs)
        
        def warning(self, message, filename='', function='', **kwargs):
            """Log warning message with optional location parameters."""
            self._log(self._logger.warning, message, filename, function, **kwargs)
        
        def error(self, message, filename='', function='', **kwargs):
            """Log error message with optional location parameters."""
            self._log(self._logger.error, message, filename, function, **kwargs)
        
        def debug(self, message, filename='', function='', **kwargs):
            """Log debug message with optional location parameters."""
            self._log(self._logger.debug, message, filename, function, **kwargs)
    
    logger = CompatibleLogger()

# Re-export logger for easy access
__all__ = ['logger']