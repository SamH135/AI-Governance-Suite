import { createContext, useContext, useState, useCallback, useEffect } from 'react';
import { useAuth } from './AuthContext';
import logger from '../utils/logger.js';

const WebSocketContext = createContext();

export const WebSocketProvider = ({ children }) => {
  const [socket, setSocket] = useState(null);
  const [connected, setConnected] = useState(false);
  const [subscriptions, setSubscriptions] = useState(new Set());
  const [isConnecting, setIsConnecting] = useState(false);
  const { isAuthenticated } = useAuth();

  logger.debug('WebSocketProvider render', 'WebSocketContext.jsx', 'WebSocketProvider');

  const connect = useCallback(() => {
    if (!isAuthenticated || socket || isConnecting) {
      logger.debug('WebSocket connection skipped - not authenticated, already connected, or connecting in progress', 'WebSocketContext.jsx', 'connect');
      return;
    }

    setIsConnecting(true);
    const wsUrl = import.meta.env.VITE_WS_URL || 'ws://localhost:8000';
    const token = localStorage.getItem('token');
    
    logger.info(`Attempting WebSocket connection to: ${wsUrl}`, 'WebSocketContext.jsx', 'connect');
    const ws = new WebSocket(`${wsUrl}/ws/connect?token=${token}`);
    
    ws.onopen = () => {
      logger.info('WebSocket connection established', 'WebSocketContext.jsx', 'connect');
      setConnected(true);
      setSocket(ws);
      setIsConnecting(false);
    };

    ws.onclose = () => {
      logger.warn('WebSocket connection closed', 'WebSocketContext.jsx', 'connect');
      setConnected(false);
      setSocket(null);
      setIsConnecting(false);
      
      // Only attempt reconnect if still authenticated and not already connecting
      setTimeout(() => {
        if (isAuthenticated && !socket && !isConnecting) {
          logger.info('Attempting WebSocket reconnection', 'WebSocketContext.jsx', 'connect');
          connect();
        }
      }, 3000);
    };

    ws.onerror = (error) => {
      logger.error(`WebSocket error: ${error.message || 'Unknown error'}`, 'WebSocketContext.jsx', 'connect');
      setIsConnecting(false);
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        logger.debug(`WebSocket message received: ${data.type || 'unknown type'}`, 'WebSocketContext.jsx', 'connect');
        // Handle incoming messages
        handleMessage(data);
      } catch (error) {
        logger.error(`Error parsing WebSocket message: ${error.message}`, 'WebSocketContext.jsx', 'connect');
      }
    };

    return ws;
  }, [isAuthenticated, socket, isConnecting]);

  const disconnect = useCallback(() => {
    if (socket) {
      logger.info('Disconnecting WebSocket', 'WebSocketContext.jsx', 'disconnect');
      socket.close();
      setSocket(null);
      setConnected(false);
      setSubscriptions(new Set());
      setIsConnecting(false);
    }
  }, [socket]);

  const subscribe = useCallback((channel) => {
    if (socket && connected) {
      logger.info(`Subscribing to WebSocket channel: ${channel}`, 'WebSocketContext.jsx', 'subscribe');
      socket.send(JSON.stringify({
        type: 'subscribe',
        channel
      }));
      setSubscriptions(prev => new Set([...prev, channel]));
    } else {
      logger.warn(`Cannot subscribe to channel ${channel} - socket not connected`, 'WebSocketContext.jsx', 'subscribe');
    }
  }, [socket, connected]);

  const unsubscribe = useCallback((channel) => {
    if (socket && connected) {
      logger.info(`Unsubscribing from WebSocket channel: ${channel}`, 'WebSocketContext.jsx', 'unsubscribe');
      socket.send(JSON.stringify({
        type: 'unsubscribe',
        channel
      }));
      setSubscriptions(prev => {
        const newSet = new Set(prev);
        newSet.delete(channel);
        return newSet;
      });
    } else {
      logger.warn(`Cannot unsubscribe from channel ${channel} - socket not connected`, 'WebSocketContext.jsx', 'unsubscribe');
    }
  }, [socket, connected]);

  const send = useCallback((message) => {
    if (socket && connected) {
      logger.debug(`Sending WebSocket message: ${message.type || 'unknown type'}`, 'WebSocketContext.jsx', 'send');
      socket.send(JSON.stringify(message));
    } else {
      logger.warn('Cannot send WebSocket message - socket not connected', 'WebSocketContext.jsx', 'send');
    }
  }, [socket, connected]);

  const handleMessage = (data) => {
    logger.debug(`Handling WebSocket message of type: ${data.type}`, 'WebSocketContext.jsx', 'handleMessage');
    
    // Dispatch custom events for different message types
    const event = new CustomEvent('websocket-message', { detail: data });
    window.dispatchEvent(event);

    // Handle specific message types
    switch (data.type) {
      case 'test_progress':
        logger.info('Test progress update received', 'WebSocketContext.jsx', 'handleMessage');
        window.dispatchEvent(new CustomEvent('test-progress', { detail: data }));
        break;
      case 'system_metrics':
        logger.debug('System metrics update received', 'WebSocketContext.jsx', 'handleMessage');
        window.dispatchEvent(new CustomEvent('system-metrics', { detail: data }));
        break;
      case 'notification':
        logger.info(`Notification received: ${data.message || 'no message'}`, 'WebSocketContext.jsx', 'handleMessage');
        window.dispatchEvent(new CustomEvent('notification', { detail: data }));
        break;
      default:
        logger.debug(`Unhandled message type: ${data.type}`, 'WebSocketContext.jsx', 'handleMessage');
        break;
    }
  };

  useEffect(() => {
    if (isAuthenticated && !socket) {
      connect();
    } else if (!isAuthenticated && socket) {
      disconnect();
    }

    return () => {
      if (socket) {
        socket.close();
        setSocket(null);
        setConnected(false);
      }
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps -- mount-only effect
  }, [isAuthenticated]);

  const value = {
    socket,
    connected,
    isConnecting,
    subscriptions,
    connect,
    disconnect,
    subscribe,
    unsubscribe,
    send
  };

  return (
    <WebSocketContext.Provider value={value}>
      {children}
    </WebSocketContext.Provider>
  );
};

export const useWebSocket = () => {
  logger.debug('useWebSocket hook called', 'WebSocketContext.jsx', 'useWebSocket');
  const context = useContext(WebSocketContext);
  if (!context) {
    logger.error('useWebSocket called outside of WebSocketProvider', 'WebSocketContext.jsx', 'useWebSocket');
    throw new Error('useWebSocket must be used within a WebSocketProvider');
  }
  return context;
};