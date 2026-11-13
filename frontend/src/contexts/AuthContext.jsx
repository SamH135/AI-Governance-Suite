import { createContext, useContext, useReducer, useEffect } from 'react';
import { authService } from '../services/authService';
import logger from '../utils/logger.js';

const AuthContext = createContext();

const initialState = {
  user: null,
  isAuthenticated: false,
  loading: true,
  error: null
};

const authReducer = (state, action) => {
  logger.debug(`Auth reducer called with action: ${action.type}`, 'AuthContext.jsx', 'authReducer');
  
  switch (action.type) {
    case 'LOGIN_START':
      logger.info('Starting login process', 'AuthContext.jsx', 'authReducer');
      return { ...state, loading: true, error: null };
    case 'LOGIN_SUCCESS':
      logger.info(`Login successful for user: ${action.payload?.username || 'unknown'}`, 'AuthContext.jsx', 'authReducer');
      return { 
        ...state, 
        user: action.payload, 
        isAuthenticated: true, 
        loading: false, 
        error: null 
      };
    case 'LOGIN_FAILURE':
      logger.error(`Login failed: ${action.payload}`, 'AuthContext.jsx', 'authReducer');
      return { 
        ...state, 
        user: null, 
        isAuthenticated: false, 
        loading: false, 
        error: action.payload 
      };
    case 'LOGOUT':
      logger.info('User logged out successfully', 'AuthContext.jsx', 'authReducer');
      return { 
        ...state, 
        user: null, 
        isAuthenticated: false, 
        loading: false, 
        error: null 
      };
    case 'SET_LOADING':
      return { ...state, loading: action.payload };
    case 'CLEAR_ERROR':
      return { ...state, error: null };
    case 'UPDATE_USER':
      return { ...state, user: { ...state.user, ...action.payload } };
    default:
      return state;
  }
};

export const AuthProvider = ({ children }) => {
  logger.info('AuthProvider component initializing', 'AuthContext.jsx', 'AuthProvider');
  const [state, dispatch] = useReducer(authReducer, initialState);

  useEffect(() => {
    const initAuth = async () => {
      logger.info('Initializing authentication state', 'AuthContext.jsx', 'initAuth');
      try {
        const token = localStorage.getItem('token');
        if (token) {
          logger.debug('Token found in localStorage, validating user', 'AuthContext.jsx', 'initAuth');
          const user = await authService.getCurrentUser();
          dispatch({ type: 'LOGIN_SUCCESS', payload: user });
        } else {
          logger.debug('No token found in localStorage', 'AuthContext.jsx', 'initAuth');
          dispatch({ type: 'SET_LOADING', payload: false });
        }
      } catch (error) {
        logger.error(`Authentication initialization failed: ${error.message}`, 'AuthContext.jsx', 'initAuth');
        localStorage.removeItem('token');
        dispatch({ type: 'SET_LOADING', payload: false });
      }
    };

    initAuth();
  }, []);

  const login = async (credentials) => {
    logger.info(`Login attempt for user: ${credentials.username || credentials.email}`, 'AuthContext.jsx', 'login');
    dispatch({ type: 'LOGIN_START' });
    try {
      const response = await authService.login(credentials);
      logger.info('Login API call successful', 'AuthContext.jsx', 'login');
      localStorage.setItem('token', response.data.token);
      dispatch({ type: 'LOGIN_SUCCESS', payload: response.data.user });
      logger.info('Login process completed successfully', 'AuthContext.jsx', 'login');
      return response.data;
    } catch (error) {
      logger.error(`Login failed: ${error.message}`, 'AuthContext.jsx', 'login');
      dispatch({ type: 'LOGIN_FAILURE', payload: error.message });
      throw error;
    }
  };

  const logout = () => {
    logger.info('Logout initiated', 'AuthContext.jsx', 'logout');
    localStorage.removeItem('token');
    dispatch({ type: 'LOGOUT' });
    logger.info('Logout completed successfully', 'AuthContext.jsx', 'logout');
  };

  const register = async (userData) => {
    logger.info(`Registration attempt for user: ${userData.username || userData.email}`, 'AuthContext.jsx', 'register');
    dispatch({ type: 'LOGIN_START' });
    try {
      const response = await authService.register(userData);
      logger.info('Registration API call successful', 'AuthContext.jsx', 'register');
      localStorage.setItem('token', response.data.token);
      dispatch({ type: 'LOGIN_SUCCESS', payload: response.data.user });
      logger.info('Registration process completed successfully', 'AuthContext.jsx', 'register');
      return response.data;
    } catch (error) {
      logger.error(`Registration failed: ${error.message}`, 'AuthContext.jsx', 'register');
      dispatch({ type: 'LOGIN_FAILURE', payload: error.message });
      throw error;
    }
  };

  const updateProfile = async (userData) => {
    logger.info('Profile update initiated', 'AuthContext.jsx', 'updateProfile');
    try {
      const updatedUser = await authService.updateProfile(userData);
      dispatch({ type: 'UPDATE_USER', payload: updatedUser });
      logger.info('Profile update completed successfully', 'AuthContext.jsx', 'updateProfile');
      return updatedUser;
    } catch (error) {
      logger.error(`Profile update failed: ${error.message}`, 'AuthContext.jsx', 'updateProfile');
      throw error;
    }
  };

  const clearError = () => {
    dispatch({ type: 'CLEAR_ERROR' });
  };

  const value = {
    ...state,
    login,
    logout,
    register,
    updateProfile,
    clearError
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  logger.debug('useAuth hook called', 'AuthContext.jsx', 'useAuth');
  const context = useContext(AuthContext);
  if (!context) {
    logger.error('useAuth called outside of AuthProvider', 'AuthContext.jsx', 'useAuth');
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};