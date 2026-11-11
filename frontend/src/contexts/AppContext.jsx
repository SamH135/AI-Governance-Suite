import React, { createContext, useContext, useReducer } from 'react';
import logger from '../utils/logger.js';

const AppContext = createContext();

const initialState = {
  theme: 'light',
  sidebar: { collapsed: false },
  notifications: [],
  loading: false,
  error: null
};

const appReducer = (state, action) => {
  logger.debug(`App reducer called with action: ${action.type}`, 'AppContext.jsx', 'appReducer');
  
  switch (action.type) {
    case 'SET_THEME':
      logger.info(`Theme changed to: ${action.payload}`, 'AppContext.jsx', 'appReducer');
      return { ...state, theme: action.payload };
    case 'TOGGLE_SIDEBAR':
      logger.debug(`Sidebar toggled to: ${!state.sidebar.collapsed ? 'collapsed' : 'expanded'}`, 'AppContext.jsx', 'appReducer');
      return { 
        ...state, 
        sidebar: { ...state.sidebar, collapsed: !state.sidebar.collapsed } 
      };
    case 'SET_SIDEBAR_COLLAPSED':
      return { 
        ...state, 
        sidebar: { ...state.sidebar, collapsed: action.payload } 
      };
    case 'ADD_NOTIFICATION':
      logger.info(`Notification added: ${action.payload.type || 'unknown'} - ${action.payload.message}`, 'AppContext.jsx', 'appReducer');
      return { 
        ...state, 
        notifications: [...state.notifications, action.payload] 
      };
    case 'REMOVE_NOTIFICATION':
      return { 
        ...state, 
        notifications: state.notifications.filter(n => n.id !== action.payload) 
      };
    case 'CLEAR_NOTIFICATIONS':
      return { ...state, notifications: [] };
    case 'SET_LOADING':
      return { ...state, loading: action.payload };
    case 'SET_ERROR':
      logger.error(`App error set: ${action.payload}`, 'AppContext.jsx', 'appReducer');
      return { ...state, error: action.payload };
    case 'CLEAR_ERROR':
      return { ...state, error: null };
    default:
      return state;
  }
};

export const AppProvider = ({ children }) => {
  logger.info('AppProvider component initializing', 'AppContext.jsx', 'AppProvider');
  const [state, dispatch] = useReducer(appReducer, initialState);

  const setTheme = (theme) => {
    logger.info(`Setting theme to: ${theme}`, 'AppContext.jsx', 'setTheme');
    dispatch({ type: 'SET_THEME', payload: theme });
    localStorage.setItem('theme', theme);
    
    if (theme === 'dark') {
      document.documentElement.classList.add('dark');
      logger.debug('Dark theme class added to document', 'AppContext.jsx', 'setTheme');
    } else {
      document.documentElement.classList.remove('dark');
      logger.debug('Dark theme class removed from document', 'AppContext.jsx', 'setTheme');
    }
  };

  const toggleSidebar = () => {
    dispatch({ type: 'TOGGLE_SIDEBAR' });
  };

  const setSidebarCollapsed = (collapsed) => {
    dispatch({ type: 'SET_SIDEBAR_COLLAPSED', payload: collapsed });
  };

  const addNotification = (notification) => {
    const id = Date.now().toString();
    logger.info(`Adding notification with ID: ${id}`, 'AppContext.jsx', 'addNotification');
    dispatch({ 
      type: 'ADD_NOTIFICATION', 
      payload: { ...notification, id } 
    });

    // Auto-remove notification after 5 seconds
    setTimeout(() => {
      logger.debug(`Auto-removing notification with ID: ${id}`, 'AppContext.jsx', 'addNotification');
      dispatch({ type: 'REMOVE_NOTIFICATION', payload: id });
    }, 5000);
  };

  const removeNotification = (id) => {
    dispatch({ type: 'REMOVE_NOTIFICATION', payload: id });
  };

  const clearNotifications = () => {
    dispatch({ type: 'CLEAR_NOTIFICATIONS' });
  };

  const setLoading = (loading) => {
    dispatch({ type: 'SET_LOADING', payload: loading });
  };

  const setError = (error) => {
    dispatch({ type: 'SET_ERROR', payload: error });
  };

  const clearError = () => {
    dispatch({ type: 'CLEAR_ERROR' });
  };

  const value = {
    ...state,
    setTheme,
    toggleSidebar,
    setSidebarCollapsed,
    addNotification,
    removeNotification,
    clearNotifications,
    setLoading,
    setError,
    clearError
  };

  return (
    <AppContext.Provider value={value}>
      {children}
    </AppContext.Provider>
  );
};

export const useApp = () => {
  logger.debug('useApp hook called', 'AppContext.jsx', 'useApp');
  const context = useContext(AppContext);
  if (!context) {
    logger.error('useApp called outside of AppProvider', 'AppContext.jsx', 'useApp');
    throw new Error('useApp must be used within an AppProvider');
  }
  return context;
};