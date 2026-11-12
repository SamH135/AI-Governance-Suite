import { useState, useEffect } from 'react';
import logger from '../utils/logger.js';

export const useApi = (apiCall, dependencies = []) => {
  logger.debug('useApi hook initialized', 'useApi.js', 'useApi');
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchData = async () => {
      logger.debug('useApi: Starting data fetch', 'useApi.js', 'fetchData');
      try {
        setLoading(true);
        setError(null);
        const result = await apiCall();
        logger.debug('useApi: Data fetch successful', 'useApi.js', 'fetchData');
        setData(result);
      } catch (err) {
        logger.error(`useApi: Data fetch failed: ${err.message}`, 'useApi.js', 'fetchData');
        setError(err.message || 'An error occurred');
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, dependencies);

  const refetch = async () => {
    logger.info('useApi: Manual refetch initiated', 'useApi.js', 'refetch');
    try {
      setLoading(true);
      setError(null);
      const result = await apiCall();
      logger.debug('useApi: Manual refetch successful', 'useApi.js', 'refetch');
      setData(result);
    } catch (err) {
      logger.error(`useApi: Manual refetch failed: ${err.message}`, 'useApi.js', 'refetch');
      setError(err.message || 'An error occurred');
    } finally {
      setLoading(false);
    }
  };

  return { data, loading, error, refetch };
};

export const useSystems = () => {
  logger.debug('useSystems hook called', 'useApi.js', 'useSystems');
  return useApi(() => {
    logger.debug('useSystems: Fetching systems data', 'useApi.js', 'useSystems');
    return api.get('/compliance/systems').then(response => response.data);
  });
};

export const useTestResults = () => {
  logger.debug('useTestResults hook called', 'useApi.js', 'useTestResults');
  return useApi((systemId) => {
    logger.debug('useTestResults: Fetching test results data', 'useApi.js', 'useTestResults');
    return api.get(`/systems/${systemId}/tests`).then(response => response.data);
  });
};