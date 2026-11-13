/**
 * Browser-compatible logger utility for frontend
 * Provides logging functionality that works in web browsers
 */

class BrowserLogger {
  constructor() {
    this.isDevelopment = import.meta.env.MODE === 'development';
  }

  _formatMessage(level, message, filename = '', functionName = '') {
    const timestamp = new Date().toISOString();
    const location = filename ? `[${filename}${functionName ? `::${functionName}` : ''}]` : '';
    return `${timestamp} [${level}] ${location} ${message}`;
  }

  _log(level, method, message, filename = '', functionName = '') {
    const formattedMessage = this._formatMessage(level, message, filename, functionName);
    
    // Always log to console
    console[method](formattedMessage);
    
    // In development, also try to send to backend logger if available
    /* if (this.isDevelopment) {
      this._sendToBackend(level, message, filename, functionName);
    } */
  }

  _sendToBackend(_level, _message, _filename, _functionName) {
    // Optional: send logs to backend in development mode
    // This is a fire-and-forget operation that shouldn't block the UI
    /*
    try {
      fetch('/api/logs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          level,
          message,
          filename,
          functionName,
          timestamp: new Date().toISOString(),
          source: 'frontend'
        })
      }).catch(() => {
        // Silently ignore network errors for logging
      });
    } catch (error) {
      // Silently ignore any errors in logging
    }
    */
  }

  info(message, filename = '', functionName = '') {
    this._log('INFO', 'log', message, filename, functionName);
  }

  warn(message, filename = '', functionName = '') {
    this._log('WARN', 'warn', message, filename, functionName);
  }

  warning(message, filename = '', functionName = '') {
    this._log('WARN', 'warn', message, filename, functionName);
  }

  error(message, filename = '', functionName = '') {
    this._log('ERROR', 'error', message, filename, functionName);
  }

  debug(message, filename = '', functionName = '') {
    this._log('DEBUG', 'debug', message, filename, functionName);
  }
}

// Create and export logger instance
const logger = new BrowserLogger();
export default logger;