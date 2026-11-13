import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import { useApp } from '../../contexts/AppContext';
import Button from '../../components/ui/Button';
import Input from '../../components/ui/Input';
import Card from '../../components/ui/Card';
import logger from '../../utils/logger.js';

const LoginPage = () => {
  logger.info('LoginPage component initialized', 'LoginPage.jsx', 'LoginPage');
  
  const [formData, setFormData] = useState({
    username: '',
    password: ''
  });
  const [loading, setLoading] = useState(false);
  const { login, error, clearError } = useAuth();
  const { addNotification } = useApp();
  const navigate = useNavigate();

  const handleChange = (e) => {
    const { name, value } = e.target;
    logger.debug(`LoginPage: Form field ${name} changed`, 'LoginPage.jsx', 'handleChange');
    setFormData(prev => ({
      ...prev,
      [name]: value
    }));
    if (error) {
      logger.debug('LoginPage: Clearing previous error', 'LoginPage.jsx', 'handleChange');
      clearError();
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    logger.info(`LoginPage: Login attempt for user: ${formData.username}`, 'LoginPage.jsx', 'handleSubmit');
    
    // Basic validation
    if (!formData.username || formData.username.trim().length < 3) {
      addNotification({
        type: 'error',
        message: 'Username must be at least 3 characters long'
      });
      return;
    }
    
    if (!formData.password || formData.password.length < 8) {
      addNotification({
        type: 'error',
        message: 'Password must be at least 8 characters long'
      });
      return;
    }
    
    setLoading(true);

    try {
      await login(formData);
      logger.info('LoginPage: Login successful, redirecting to dashboard', 'LoginPage.jsx', 'handleSubmit');
      addNotification({
        type: 'success',
        message: 'Successfully logged in!'
      });
      navigate('/');
    } catch (err) {
      logger.error(`LoginPage: Login failed: ${err.message}`, 'LoginPage.jsx', 'handleSubmit');
      addNotification({
        type: 'error',
        message: err.message || 'Login failed'
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-neutral-50 py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-md w-full space-y-8">
        <div className="text-center">
          <h2 className="mt-6 text-3xl font-bold text-neutral-900">
            Sign in to your account
          </h2>
          <p className="mt-2 text-sm text-neutral-600">
            Or{' '}
            <Link
              to="/register"
              className="font-medium text-brand-600 hover:text-brand-500"
            >
              create a new account
            </Link>
          </p>
        </div>

        <Card>
          <form onSubmit={handleSubmit} className="space-y-6">
            <Input
              label="Username"
              name="username"
              type="text"
              value={formData.username}
              onChange={handleChange}
              required
              autoComplete="username"
            />

            <Input
              label="Password"
              name="password"
              type="password"
              value={formData.password}
              onChange={handleChange}
              required
              autoComplete="current-password"
            />

            {error && (
              <div className="text-sm text-red-600 bg-red-50 p-3 rounded-md">
                {error}
              </div>
            )}

            <div className="flex items-center justify-between">
              <div className="flex items-center">
                <input
                  id="remember-me"
                  name="remember-me"
                  type="checkbox"
                  className="h-4 w-4 text-brand-600 focus:ring-brand-500 border-neutral-300 rounded"
                />
                <label htmlFor="remember-me" className="ml-2 block text-sm text-neutral-900">
                  Remember me
                </label>
              </div>

            </div>

            <Button
              type="submit"
              loading={loading}
              className="w-full"
            >
              Sign in
            </Button>
          </form>
        </Card>
      </div>
    </div>
  );
};

export default LoginPage;