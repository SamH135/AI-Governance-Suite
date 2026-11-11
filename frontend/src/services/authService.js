import axios from 'axios';
import logger from '../utils/logger.js';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
logger.info(`Auth service initialized with API URL: ${API_URL}`, 'authService.js', 'init');

const api = axios.create({
  baseURL: `${API_URL}/api`,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add token to requests
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
    logger.debug(`Request authenticated for ${config.method?.toUpperCase()} ${config.url}`, 'authService.js', 'interceptor');
  } else {
    logger.debug(`Unauthenticated request to ${config.method?.toUpperCase()} ${config.url}`, 'authService.js', 'interceptor');
  }
  logger.debug(`Outgoing request: ${JSON.stringify(config, null, 2)}`, 'authService.js', 'requestInterceptor');
  return config;
});

// Handle token expiration
api.interceptors.response.use(
  (response) => {
    logger.debug(`API response received: ${response.status} ${response.config?.method?.toUpperCase()} ${response.config?.url}`, 'authService.js', 'interceptor');
    return response;
  },
  (error) => {
    const status = error.response?.status;
    const method = error.config?.method?.toUpperCase();
    const url = error.config?.url;
    
    logger.error(`API error: ${status} ${method} ${url} - ${error.message}`, 'authService.js', 'interceptor');
    logger.error(`Error response data:`, error.response?.data, 'authService.js', 'interceptor');
    
    // Only redirect on 401 if it's not a login/register attempt
    if (status === 401 && !url?.includes('/auth/login') && !url?.includes('/auth/register')) {
      logger.warn('Token expired, redirecting to login', 'authService.js', 'interceptor');
      localStorage.removeItem('token');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

export const authService = {
  async login(credentials) {
    logger.info(`Login attempt for user: ${credentials.username || credentials.email}`, 'authService.js', 'login');
    try {
      const response = await api.post('/auth/login', credentials);
      logger.info('Login API call successful', 'authService.js', 'login');
      return response.data;
    } catch (error) {
      logger.error(`Login API call failed: ${error.message}`, 'authService.js', 'login');
      logger.error(`Login error details:`, error.response?.data, 'authService.js', 'login');
      
      // Extract meaningful error message from backend response
      let errorMessage = 'Login failed';
      
      if (error.response?.status === 422) {
        // Handle validation errors
        const validationErrors = error.response?.data?.detail;
        if (Array.isArray(validationErrors) && validationErrors.length > 0) {
          errorMessage = validationErrors.map(err => `${err.loc?.join('.')}: ${err.msg}`).join(', ');
        } else {
          errorMessage = 'Invalid input data';
        }
      } else if (error.response?.data?.detail?.message) {
        errorMessage = error.response.data.detail.message;
      } else if (error.response?.data?.message) {
        errorMessage = error.response.data.message;
      } else if (error.response?.data?.detail) {
        errorMessage = typeof error.response.data.detail === 'string' 
          ? error.response.data.detail 
          : 'Authentication failed';
      } else if (error.message) {
        errorMessage = error.message;
      }
      
      const newError = new Error(errorMessage);
      newError.status = error.response?.status;
      newError.code = error.response?.data?.detail?.code;
      throw newError;
    }
  },

  async register(userData) {
    logger.info(`Registration attempt for user: ${userData.username || userData.email}`, 'authService.js', 'register');
    logger.debug('Registering with data:', userData, 'authService.js', 'register');
    try {
      const response = await api.post('/auth/register', userData);
      logger.info('Registration API call successful', 'authService.js', 'register');
      return response.data;
    } catch (error) {
      logger.error(`Registration API call failed: ${error.message}`, 'authService.js', 'register');
      logger.error(`Registration error details:`, error.response?.data, 'authService.js', 'register');
      
      // Extract meaningful error message from backend response
      let errorMessage = 'Registration failed';
      
      if (error.response?.status === 422) {
        // Handle validation errors
        const validationErrors = error.response?.data?.detail;
        if (Array.isArray(validationErrors) && validationErrors.length > 0) {
          errorMessage = validationErrors.map(err => `${err.loc?.join('.')}: ${err.msg}`).join(', ');
        } else {
          errorMessage = 'Invalid input data';
        }
      } else if (error.response?.data?.detail?.message) {
        errorMessage = error.response.data.detail.message;
      } else if (error.response?.data?.message) {
        errorMessage = error.response.data.message;
      } else if (error.response?.data?.detail) {
        errorMessage = typeof error.response.data.detail === 'string' 
          ? error.response.data.detail 
          : 'Registration failed';
      } else if (error.message) {
        errorMessage = error.message;
      }
      
      const newError = new Error(errorMessage);
      newError.status = error.response?.status;
      newError.code = error.response?.data?.detail?.code;
      throw newError;
    }
  },

  async logout() {
    logger.info('Logout API call initiated', 'authService.js', 'logout');
    try {
      await api.post('/auth/logout');
      localStorage.removeItem('token');
      logger.info('Logout API call completed', 'authService.js', 'logout');
    } catch (error) {
      logger.error(`Logout API call failed: ${error.message}`, 'authService.js', 'logout');
      // Still remove token locally even if server call fails
      localStorage.removeItem('token');
      throw error;
    }
  },

  async getCurrentUser() {
    logger.debug('Getting current user information', 'authService.js', 'getCurrentUser');
    try {
      const response = await api.get('/auth/me');
      logger.debug('Current user information retrieved successfully', 'authService.js', 'getCurrentUser');
      return response.data;
    } catch (error) {
      logger.error(`Failed to get current user: ${error.message}`, 'authService.js', 'getCurrentUser');
      throw error;
    }
  },

  async updateProfile(userData) {
    logger.info('Profile update API call initiated', 'authService.js', 'updateProfile');
    try {
      const response = await api.put('/auth/profile', userData);
      logger.info('Profile update API call successful', 'authService.js', 'updateProfile');
      return response.data;
    } catch (error) {
      logger.error(`Profile update API call failed: ${error.message}`, 'authService.js', 'updateProfile');
      throw error;
    }
  },

  async changePassword(passwordData) {
    logger.info('Password change API call initiated', 'authService.js', 'changePassword');
    try {
      const response = await api.put('/auth/password', passwordData);
      logger.info('Password change API call successful', 'authService.js', 'changePassword');
      return response.data;
    } catch (error) {
      logger.error(`Password change API call failed: ${error.message}`, 'authService.js', 'changePassword');
      throw error;
    }
  },

  async forgotPassword(email) {
    logger.info(`Forgot password API call initiated for email: ${email}`, 'authService.js', 'forgotPassword');
    try {
      const response = await api.post('/auth/forgot-password', { email });
      logger.info('Forgot password API call successful', 'authService.js', 'forgotPassword');
      return response.data;
    } catch (error) {
      logger.error(`Forgot password API call failed: ${error.message}`, 'authService.js', 'forgotPassword');
      throw error;
    }
  },

  async resetPassword(token, password) {
    logger.info('Password reset API call initiated', 'authService.js', 'resetPassword');
    try {
      const response = await api.post('/auth/reset-password', { token, password });
      logger.info('Password reset API call successful', 'authService.js', 'resetPassword');
      return response.data;
    } catch (error) {
      logger.error(`Password reset API call failed: ${error.message}`, 'authService.js', 'resetPassword');
      throw error;
    }
  },

  async refreshToken() {
    logger.debug('Token refresh API call initiated', 'authService.js', 'refreshToken');
    try {
      const response = await api.post('/auth/refresh');
      logger.debug('Token refresh API call successful', 'authService.js', 'refreshToken');
      return response.data;
    } catch (error) {
      logger.error(`Token refresh API call failed: ${error.message}`, 'authService.js', 'refreshToken');
      throw error;
    }
  }
};

export default api;