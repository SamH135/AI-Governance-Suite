import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import logger from './utils/logger.js';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';
import App from './App.jsx';
import { AuthProvider } from './contexts/AuthContext.jsx';
import { AppProvider } from './contexts/AppContext.jsx';
import { WebSocketProvider } from './contexts/WebSocketContext.jsx';
import './styles/index.css';

logger.info('Creating Material-UI theme configuration', 'main.jsx', 'main');
const theme = createTheme({
  palette: {
    mode: 'light',
    primary: {
      main: '#3b82f6',
    },
    secondary: {
      main: '#6b7280',
    },
  },
  typography: {
    fontFamily: 'Inter, system-ui, sans-serif',
  },
});
logger.debug('Theme configuration created successfully', 'main.jsx', 'main');

logger.info('Starting React application initialization', 'main.jsx', 'main');
logger.debug('Setting up root element and provider hierarchy', 'main.jsx', 'main');

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <BrowserRouter>
      <ThemeProvider theme={theme}>
        <CssBaseline />
        <AuthProvider>
          <AppProvider>
            <WebSocketProvider>
              <App />
            </WebSocketProvider>
          </AppProvider>
        </AuthProvider>
      </ThemeProvider>
    </BrowserRouter>
  </React.StrictMode>
);

logger.info('React application rendered successfully', 'main.jsx', 'main');