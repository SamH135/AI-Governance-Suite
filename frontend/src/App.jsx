import { Routes, Route, Navigate } from 'react-router-dom';
import { useAuth } from './contexts/AuthContext';
import logger from './utils/logger.js';
import MainLayout from './components/layout/MainLayout';
import LoginPage from './pages/auth/LoginPage';
import RegisterPage from './pages/auth/RegisterPage';
import DashboardPage from './pages/dashboard/DashboardPage';
import SystemsListPage from './pages/compliance/SystemsListPage';
import SystemModelConfigPage from './pages/compliance/SystemModelConfigPage';
import TestConfigPage from './pages/compliance/TestConfigPage';
import TestResultsPage from './pages/compliance/TestResultsPage';
import RAGTestPage from './pages/compliance/RAGTestPage';
import ApiKeysPage from './pages/compliance/ApiKeysPage';
import ModelConfigurationsPage from './pages/compliance/ModelConfigurationsPage';
import PromptEngineeringPage from './pages/prompts/PromptEngineeringPage';
import J1DashboardPage from './pages/prompts/J1DashboardPage';
import PromptCategoriesPage from './pages/prompts/PromptCategoriesPage';
import DocumentGeneratorPage from './pages/documents/DocumentGeneratorPage';
import TemplateManagementPage from './pages/documents/TemplateManagementPage';
import SettingsPage from './pages/settings/SettingsPage';
import LoadingSpinner from './components/ui/LoadingSpinner';
import ErrorBoundary from './components/common/ErrorBoundary';
import { ToastProvider } from './components/ui/Toast';

const ProtectedRoute = ({ children }) => {
  logger.info('ProtectedRoute component called', 'App.jsx', 'ProtectedRoute');
  const { isAuthenticated, loading } = useAuth();
  
  logger.debug(`Authentication state - isAuthenticated: ${isAuthenticated}, loading: ${loading}`, 'App.jsx', 'ProtectedRoute');
  
  if (loading) {
    logger.info('Showing loading spinner for protected route', 'App.jsx', 'ProtectedRoute');
    return <LoadingSpinner />;
  }
  
  const result = isAuthenticated ? children : <Navigate to="/login" />;
  logger.info(`Protected route result: ${isAuthenticated ? 'allowing access' : 'redirecting to login'}`, 'App.jsx', 'ProtectedRoute');
  return result;
};

const PublicRoute = ({ children }) => {
  logger.info('PublicRoute component called', 'App.jsx', 'PublicRoute');
  const { isAuthenticated, loading } = useAuth();
  
  logger.debug(`Authentication state - isAuthenticated: ${isAuthenticated}, loading: ${loading}`, 'App.jsx', 'PublicRoute');
  
  if (loading) {
    logger.info('Showing loading spinner for public route', 'App.jsx', 'PublicRoute');
    return <LoadingSpinner />;
  }
  
  const result = !isAuthenticated ? children : <Navigate to="/" />;
  logger.info(`Public route result: ${!isAuthenticated ? 'allowing access' : 'redirecting to dashboard'}`, 'App.jsx', 'PublicRoute');
  return result;
};

function App() {
  logger.info('App component initializing', 'App.jsx', 'App');
  
  logger.debug('Setting up application routes', 'App.jsx', 'App');
  return (
    <ErrorBoundary message="The application encountered an unexpected error. Please refresh the page or contact support if the problem persists.">
      <ToastProvider>
        <Routes>
      {/* Public Routes */}
      <Route path="/login" element={
        <PublicRoute>
          <LoginPage />
        </PublicRoute>
      } />
      <Route path="/register" element={
        <PublicRoute>
          <RegisterPage />
        </PublicRoute>
      } />

      {/* Protected Routes */}
      <Route path="/" element={
        <ProtectedRoute>
          <MainLayout />
        </ProtectedRoute>
      }>
        <Route index element={<DashboardPage />} />

        {/* AI Systems & Testing Routes */}
        <Route path="compliance">
          <Route index element={<SystemsListPage />} />
          <Route path="systems" element={<SystemsListPage />} />
          <Route path="systems/:systemId/models" element={<SystemModelConfigPage />} />
          <Route path="api-keys" element={<ApiKeysPage />} />
          <Route path="models" element={<ModelConfigurationsPage />} />
          <Route path="rag" element={<RAGTestPage />} />
          <Route path="test/configure/:systemId" element={<TestConfigPage />} />
          <Route path="results" element={<TestResultsPage />} />
          <Route path="results/:testId" element={<TestResultsPage />} />
        </Route>

        {/* Prompt Engineering Routes */}
        <Route path="prompts">
          <Route index element={<PromptCategoriesPage />} />
          <Route path="categories" element={<PromptCategoriesPage />} />
          <Route path="engineering" element={<PromptEngineeringPage />} />
          <Route path="j1-dashboard" element={<J1DashboardPage />} />
        </Route>

        {/* Documentation Routes */}
        <Route path="documents">
          <Route index element={<DocumentGeneratorPage />} />
          <Route path="generator" element={<DocumentGeneratorPage />} />
          <Route path="templates" element={<TemplateManagementPage />} />
        </Route>

        {/* Settings Routes */}
        <Route path="settings">
          <Route index element={<SettingsPage />} />
          <Route path="data" element={<SettingsPage />} />
          <Route path="profile" element={<SettingsPage />} />
          <Route path="security" element={<SettingsPage />} />
          <Route path="notifications" element={<SettingsPage />} />
        </Route>
      </Route>

      {/* Catch all route */}
      <Route path="*" element={<Navigate to="/" />} />
        </Routes>
      </ToastProvider>
    </ErrorBoundary>
  );
}

export default App;