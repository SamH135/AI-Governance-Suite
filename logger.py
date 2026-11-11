import logging
import os
from datetime import datetime

class CustomLogger:
    def __init__(self):
        self.log_file = os.path.join(os.path.dirname(__file__), 'application.log')
        self.setup_logger()
    
    def setup_logger(self):
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s [%(levelname)s] [%(filename)s::%(funcName)s] %(message)s',
            handlers=[
                logging.FileHandler(self.log_file, mode='a'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def info(self, message, filename='', function_name='', function='', **kwargs):
        # Support both 'function' and 'function_name' for compatibility
        func_name = function or function_name
        location = f"[{filename}::{func_name}]" if filename and func_name else ""
        extra_info = " ".join(f"{k}={v}" for k, v in kwargs.items()) if kwargs else ""
        full_message = f"{location} {message} {extra_info}".strip()
        self.logger.info(full_message)
    
    def warn(self, message, filename='', function_name='', function='', **kwargs):
        # Support both 'function' and 'function_name' for compatibility
        func_name = function or function_name
        location = f"[{filename}::{func_name}]" if filename and func_name else ""
        extra_info = " ".join(f"{k}={v}" for k, v in kwargs.items()) if kwargs else ""
        full_message = f"{location} {message} {extra_info}".strip()
        self.logger.warning(full_message)
    
    def warning(self, message, filename='', function_name='', function='', **kwargs):
        # Alias for warn
        self.warn(message, filename, function_name, function, **kwargs)
    
    def error(self, message, filename='', function_name='', function='', **kwargs):
        # Support both 'function' and 'function_name' for compatibility
        func_name = function or function_name
        location = f"[{filename}::{func_name}]" if filename and func_name else ""
        extra_info = " ".join(f"{k}={v}" for k, v in kwargs.items()) if kwargs else ""
        full_message = f"{location} {message} {extra_info}".strip()
        self.logger.error(full_message)
    
    def debug(self, message, filename='', function_name='', function='', **kwargs):
        # Support both 'function' and 'function_name' for compatibility
        func_name = function or function_name
        location = f"[{filename}::{func_name}]" if filename and func_name else ""
        extra_info = " ".join(f"{k}={v}" for k, v in kwargs.items()) if kwargs else ""
        full_message = f"{location} {message} {extra_info}".strip()
        self.logger.debug(full_message)

logger = CustomLogger()