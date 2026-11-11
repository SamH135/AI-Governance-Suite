// Enhanced API error handling utilities
import logger from './logger.js';

/**
 * Extract user-friendly error message from API response
 */
export const extractErrorMessage = (error, context = '') => {
  // Network errors
  if (!error.response) {
    if (error.code === 'NETWORK_ERROR' || error.message.includes('Network Error')) {
      return 'Unable to connect to the server. Please check your internet connection.';
    }
    if (error.code === 'ECONNABORTED' || error.message.includes('timeout')) {
      return 'Request timed out. The server may be busy, please try again.';
    }
    return 'Connection failed. Please check your internet connection and try again.';
  }

  // HTTP errors
  const status = error.response?.status;
  const data = error.response?.data;

  // Extract message from different response formats
  let message = 'An unexpected error occurred';
  
  if (data?.detail) {
    message = data.detail;
  } else if (data?.message) {
    message = data.message;
  } else if (data?.error?.message) {
    message = data.error.message;
  } else if (data?.errors && Array.isArray(data.errors)) {
    message = data.errors.map(err => err.message || err).join('. ');
  }

  // Status-specific messages
  switch (status) {
    case 400:
      return message.includes('validation') ? 
        `Validation error: ${message}` : 
        `Invalid request: ${message}`;
    
    case 401:
      return 'Authentication required. Please log in and try again.';
    
    case 403:
      return 'Access denied. You don\'t have permission to perform this action.';
    
    case 404:
      return context ? 
        `${context} not found. It may have been deleted or moved.` : 
        'The requested resource was not found.';
    
    case 409:
      return `Conflict: ${message}`;
    
    case 422:
      return `Validation failed: ${message}`;
    
    case 429:
      return 'Too many requests. Please wait a moment before trying again.';
    
    case 500:
      return 'Server error occurred. Our team has been notified. Please try again later.';
    
    case 502:
    case 503:
    case 504:
      return 'Service temporarily unavailable. Please try again in a few minutes.';
    
    default:
      return message;
  }
};

/**
 * Categorize errors for different handling strategies
 */
export const categorizeError = (error) => {
  const status = error.response?.status;
  
  if (!error.response) {
    return {
      category: 'network',
      retryable: true,
      severity: 'medium'
    };
  }
  
  if (status >= 500) {
    return {
      category: 'server',
      retryable: true,
      severity: 'high'
    };
  }
  
  if (status === 429) {
    return {
      category: 'rate_limit',
      retryable: true,
      severity: 'medium'
    };
  }
  
  if (status === 401) {
    return {
      category: 'auth',
      retryable: false,
      severity: 'high',
      requiresReauth: true
    };
  }
  
  if (status >= 400 && status < 500) {
    return {
      category: 'client',
      retryable: false,
      severity: 'low'
    };
  }
  
  return {
    category: 'unknown',
    retryable: false,
    severity: 'medium'
  };
};

/**
 * Enhanced API call wrapper with better error handling
 */
export const safeApiCall = async (apiCall, options = {}) => {
  const {
    context = '',
    showToast = true,
    retries = 2,
    retryDelay = 1000,
    toast = null,
    onRetry = null,
    fallbackData = null,
    timeout = 30000
  } = options;

  let lastError;
  const startTime = Date.now();

  for (let attempt = 1; attempt <= retries + 1; attempt++) {
    try {
      logger.debug(`API call attempt ${attempt}/${retries + 1}`, 'apiErrorHandler', context);
      
      // Add timeout to the API call
      const timeoutPromise = new Promise((_, reject) =>
        setTimeout(() => reject(new Error('Request timeout')), timeout)
      );
      
      const result = await Promise.race([apiCall(), timeoutPromise]);
      
      const duration = Date.now() - startTime;
      logger.debug(`API call successful after ${attempt} attempts (${duration}ms)`, 'apiErrorHandler', context);
      
      return result;
      
    } catch (error) {
      lastError = error;
      const errorCategory = categorizeError(error);
      const errorMessage = extractErrorMessage(error, context);
      
      logger.warn(`API call attempt ${attempt} failed: ${errorMessage}`, 'apiErrorHandler', {
        context,
        status: error.response?.status,
        category: errorCategory.category
      });
      
      // Don't retry if not retryable or if this is the last attempt
      if (!errorCategory.retryable || attempt === retries + 1) {
        break;
      }
      
      // Call retry callback if provided
      if (onRetry) {
        await onRetry(attempt, error);
      }
      
      // Wait before retrying
      if (attempt <= retries) {
        await new Promise(resolve => setTimeout(resolve, retryDelay * attempt));
      }
    }
  }

  // All retries failed
  const errorCategory = categorizeError(lastError);
  const userMessage = extractErrorMessage(lastError, context);
  
  logger.error(`API call failed after ${retries + 1} attempts`, 'apiErrorHandler', {
    context,
    error: lastError.message,
    status: lastError.response?.status,
    category: errorCategory.category
  });

  // Show toast notification if requested
  if (showToast && toast) {
    toast.error(userMessage, {
      title: context ? `${context} Failed` : 'Operation Failed',
      duration: errorCategory.severity === 'high' ? 10000 : 5000
    });
  }

  // Handle authentication errors
  if (errorCategory.requiresReauth && window.location.pathname !== '/auth/login') {
    if (toast) {
      toast.warning('Please log in again to continue', {
        title: 'Session Expired',
        duration: 5000
      });
    }
    setTimeout(() => {
      window.location.href = '/auth/login';
    }, 1000);
  }

  // Return fallback data if provided
  if (fallbackData !== null) {
    logger.info('Using fallback data due to API failure', 'apiErrorHandler', context);
    return fallbackData;
  }

  // Re-throw with enhanced error
  const enhancedError = new Error(userMessage);
  enhancedError.originalError = lastError;
  enhancedError.category = errorCategory;
  enhancedError.context = context;
  throw enhancedError;
};

/**
 * Utility for handling form submission errors
 */
export const handleFormError = (error, setFieldErrors, toast) => {
  const errorCategory = categorizeError(error);
  
  // Handle validation errors with field-specific messages
  if (error.response?.status === 422 && error.response?.data?.errors) {
    const fieldErrors = {};
    const errors = error.response.data.errors;
    
    if (Array.isArray(errors)) {
      errors.forEach(err => {
        if (err.field) {
          fieldErrors[err.field] = err.message;
        }
      });
    } else if (typeof errors === 'object') {
      Object.entries(errors).forEach(([field, messages]) => {
        fieldErrors[field] = Array.isArray(messages) ? messages[0] : messages;
      });
    }
    
    setFieldErrors(fieldErrors);
    
    if (toast) {
      toast.error('Please correct the highlighted fields', {
        title: 'Validation Error'
      });
    }
  } else {
    // General error handling
    const message = extractErrorMessage(error);
    if (toast) {
      toast.error(message, {
        title: 'Error',
        duration: errorCategory.severity === 'high' ? 8000 : 5000
      });
    }
  }
};

export default {
  extractErrorMessage,
  categorizeError,
  safeApiCall,
  handleFormError
};