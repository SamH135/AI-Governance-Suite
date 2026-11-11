import api from './authService';
import logger from '../utils/logger.js';

// Configuration for API service behavior
const CONFIG = {
  // Mock fallbacks disabled for production readiness - system must provide clear error messages
  enableMockFallback: false,
  // Retry configuration
  maxRetries: 2,
  retryDelay: 1000
};

// Helper function to handle API calls with retry
async function apiCallWithRetry(apiCall, context) {
  let lastError;
  
  // Retry logic
  for (let attempt = 1; attempt <= CONFIG.maxRetries; attempt++) {
    try {
      logger.debug(`API call attempt ${attempt}/${CONFIG.maxRetries}`, 'apiService.js', context);
      const response = await apiCall();
      logger.debug(`API call successful on attempt ${attempt}`, 'apiService.js', context);
      return response.data;
    } catch (error) {
      lastError = error;
      logger.warn(`API call attempt ${attempt} failed: ${error.message}`, 'apiService.js', context);
      
      if (attempt < CONFIG.maxRetries) {
        await new Promise(resolve => setTimeout(resolve, CONFIG.retryDelay));
      }
    }
  }
  
  // All retries failed - provide detailed error information for debugging
  logger.error(`All API retry attempts failed: ${lastError.message}`, 'apiService.js', context);
  
  // Extract detailed error message from response
  let errorMessage = 'Service call failed';
  if (lastError.response?.data?.detail) {
    errorMessage = lastError.response.data.detail;
  } else if (lastError.response?.data?.message) {
    errorMessage = lastError.response.data.message;
  } else if (lastError.message) {
    errorMessage = lastError.message;
  }
  
  // Create a detailed error but throw a user-friendly message
  const errorDetails = {
    context,
    attempts: CONFIG.maxRetries,
    status: lastError.response?.status,
    statusText: lastError.response?.statusText,
    endpoint: lastError.config?.url,
    userMessage: errorMessage
  };
  
  logger.error(`Detailed error: ${JSON.stringify(errorDetails)}`, 'apiService.js', context);
  throw new Error(errorMessage);
}

export const systemsService = {
  async getSystems() {
    logger.info('Fetching systems list', 'apiService.js', 'getSystems');
    
    const result = await apiCallWithRetry(
      () => api.get('/compliance/systems'),
      'getSystems'
    );
    // Unwrap ApiResponse shape if present
    return result?.data ?? result;
  },

  async getSystem(id) {
    logger.info(`Fetching system with ID: ${id}`, 'apiService.js', 'getSystem');
    
    const result = await apiCallWithRetry(
      () => api.get(`/compliance/systems/${id}`),
      'getSystem'
    );
    return result?.data ?? result;
  },

  async createSystem(systemData) {
    logger.info(`Creating new system: ${systemData.name}`, 'apiService.js', 'createSystem');
    
    const result = await apiCallWithRetry(
      () => api.post('/compliance/systems', systemData),
      'createSystem'
    );
    return result?.data ?? result;
  },

  async updateSystem(id, systemData) {
    logger.info(`Updating system with ID: ${id}`, 'apiService.js', 'updateSystem');
    
    const result = await apiCallWithRetry(
      () => api.put(`/compliance/systems/${id}`, systemData),
      'updateSystem'
    );
    return result?.data ?? result;
  },

  async deleteSystem(id) {
    logger.info(`Deleting system with ID: ${id}`, 'apiService.js', 'deleteSystem');
    
    // Custom delete logic that doesn't retry on 404 (already deleted)
    try {
      const response = await api.delete(`/compliance/systems/${id}`);
      logger.debug('System deleted successfully', 'apiService.js', 'deleteSystem');
      return response.data;
    } catch (error) {
      // 404 means already deleted - treat as success
      if (error.response?.status === 404) {
        logger.info('System already deleted (404), treating as success', 'apiService.js', 'deleteSystem');
        return { success: true, message: 'System already deleted', deleted_id: parseInt(id) };
      }
      
      // For other errors, throw to let calling code handle
      logger.error(`Failed to delete system: ${error.message}`, 'apiService.js', 'deleteSystem');
      throw error;
    }
  },

  async runTest(systemId, testConfig) {
    logger.info(`Running test on system ${systemId} with config: ${JSON.stringify(testConfig)}`, 'apiService.js', 'runTest');
    
    const framework = testConfig.evaluators?.[0] || testConfig.framework || 'generic_compliance';
    const testPrompt = testConfig.test_prompts || testConfig.testPrompts || testConfig.text || 'Test input for compliance evaluation';
    
    try {
      // Direct evaluator test via Gateway proxy to compliance service
      const response = await api.post(`/compliance/evaluators/test/${encodeURIComponent(framework)}`, {
        text: testPrompt,
        llm_config: testConfig.llm_config || {
          provider: testConfig.provider || 'local',
          model_id: testConfig.model_id || 'local-mock'
        }
      });
      
      const payload = response.data?.data ?? response.data;
      return {
        testId: 'eval_' + Date.now(),
        status: 'completed',
        message: `Compliance evaluation for ${framework} completed`,
        systemId: systemId,
        started_at: new Date().toISOString(),
        result: payload
      };
    } catch (e1) {
      logger.warn(`Direct evaluator call failed (${e1.message}), trying system-based endpoint`, 'apiService.js', 'runTest');
      try {
        const response = await api.post(`/compliance/systems/${systemId}/test`, testConfig);
        const payload = response.data?.data ?? response.data;
        if (payload && !payload.testId && payload.test_id) {
          payload.testId = String(payload.test_id);
        }
        return payload;
      } catch (e2) {
        logger.error(`System test execution failed: ${e2.message}`, 'apiService.js', 'runTest');
        throw e2;
      }
    }
  }
};

export const testingService = {
  async runTest(testConfig) {
    logger.info(`Running test with config: ${JSON.stringify(testConfig)}`, 'apiService.js', 'runTest');
    
    return await apiCallWithRetry(
      () => api.post('/tests/executions', testConfig),
      'runTest'
    );
  },

  async getTestResults(testId) {
    logger.info(`Fetching test results for ID: ${testId}`, 'apiService.js', 'getTestResults');
    const response = await apiCallWithRetry(
      () => api.get(`/compliance/tests/${testId}/results`),
      'getTestResults'
    );
    return response;
  },

  async getTestHistory(systemId) {
    logger.info(`Fetching test history for system ID: ${systemId}`, 'apiService.js', 'getTestHistory');
    const response = await apiCallWithRetry(
      () => api.get(`/systems/${systemId}/test-history`),
      'getTestHistory'
    );
    return response;
  },

  async getSystemTest(systemId, testId) {
    logger.info(`Fetching system test result systemId=${systemId} testId=${testId}`, 'apiService.js', 'getSystemTest');
    const response = await apiCallWithRetry(
      () => api.get(`/compliance/systems/${systemId}/tests/${testId}`),
      'getSystemTest'
    );
    return response?.data ?? response;
  },

  async getEvaluators() {
    logger.info('Fetching available evaluators', 'apiService.js', 'getEvaluators');
    const response = await apiCallWithRetry(
      () => api.get('/compliance/evaluators/'),
      'getEvaluators'
    );
    
    // Handle ApiResponse format from backend
    let evaluatorsData = response;
    if (response?.data) {
      evaluatorsData = response.data;
    }
    
    // Transform backend format to frontend expected format
    const transformedEvaluators = evaluatorsData.map(evaluator => ({
      id: evaluator.framework,
      name: evaluator.name,
      description: evaluator.description,
      category: evaluator.category,
      version: evaluator.version,
      tags: evaluator.tags,
      capabilities: evaluator.capabilities,
      framework: evaluator.framework
    }));
    
    logger.debug(`Retrieved ${transformedEvaluators?.length || 0} evaluators`, 'apiService.js', 'getEvaluators');
    return transformedEvaluators;
  }
};

export const promptsService = {
  async getPrompts() {
    logger.info('Fetching prompts list', 'apiService.js', 'getPrompts');
    try {
      const response = await api.get('/prompts');
      logger.debug(`Retrieved ${response.data?.length || 0} prompts`, 'apiService.js', 'getPrompts');
      return response.data;
    } catch (error) {
      logger.error(`Failed to fetch prompts: ${error.message}`, 'apiService.js', 'getPrompts');
      throw error;
    }
  },

  async getPrompt(id) {
    logger.info(`Fetching prompt with ID: ${id}`, 'apiService.js', 'getPrompt');
    try {
      const response = await api.get(`/prompts/${id}`);
      logger.debug('Prompt retrieved successfully', 'apiService.js', 'getPrompt');
      return response.data;
    } catch (error) {
      logger.error(`Failed to fetch prompt: ${error.message}`, 'apiService.js', 'getPrompt');
      throw error;
    }
  },

  async createPrompt(promptData) {
    logger.info(`Creating new prompt: ${promptData.title || 'Untitled'}`, 'apiService.js', 'createPrompt');
    try {
      const response = await api.post('/prompts', promptData);
      logger.info('Prompt created successfully', 'apiService.js', 'createPrompt');
      return response.data;
    } catch (error) {
      logger.error(`Failed to create prompt: ${error.message}`, 'apiService.js', 'createPrompt');
      throw error;
    }
  },

  async updatePrompt(id, promptData) {
    logger.info(`Updating prompt with ID: ${id}`, 'apiService.js', 'updatePrompt');
    try {
      const response = await api.put(`/prompts/${id}`, promptData);
      logger.info('Prompt updated successfully', 'apiService.js', 'updatePrompt');
      return response.data;
    } catch (error) {
      logger.error(`Failed to update prompt: ${error.message}`, 'apiService.js', 'updatePrompt');
      throw error;
    }
  },

  async deletePrompt(id) {
    logger.info(`Deleting prompt with ID: ${id}`, 'apiService.js', 'deletePrompt');
    try {
      const response = await api.delete(`/prompts/${id}`);
      logger.info('Prompt deleted successfully', 'apiService.js', 'deletePrompt');
      return response.data;
    } catch (error) {
      logger.error(`Failed to delete prompt: ${error.message}`, 'apiService.js', 'deletePrompt');
      throw error;
    }
  },

  async getCategories() {
    logger.info('Fetching prompt categories', 'apiService.js', 'getCategories');
    try {
      const response = await api.get('/prompts/categories');
      logger.debug(`Retrieved ${response.data?.length || 0} categories`, 'apiService.js', 'getCategories');
      return response.data;
    } catch (error) {
      logger.error(`Failed to fetch categories: ${error.message}`, 'apiService.js', 'getCategories');
      throw error;
    }
  }
};

export const documentsService = {
  async getDocuments() {
    logger.info('Fetching documents list', 'apiService.js', 'getDocuments');
    try {
      const response = await api.get('/documents');
      logger.debug(`Retrieved ${response.data?.length || 0} documents`, 'apiService.js', 'getDocuments');
      return response.data;
    } catch (error) {
      logger.error(`Failed to fetch documents: ${error.message}`, 'apiService.js', 'getDocuments');
      throw error;
    }
  },

  async getDocument(id) {
    logger.info(`Fetching document with ID: ${id}`, 'apiService.js', 'getDocument');
    try {
      const response = await api.get(`/documents/${id}`);
      logger.debug('Document retrieved successfully', 'apiService.js', 'getDocument');
      return response.data;
    } catch (error) {
      logger.error(`Failed to fetch document: ${error.message}`, 'apiService.js', 'getDocument');
      throw error;
    }
  },

  async generateDocument(documentData) {
    logger.info(`Generating document: ${documentData.title || 'Untitled'}`, 'apiService.js', 'generateDocument');
    try {
      const response = await api.post('/documents/generate', documentData);
      logger.info('Document generated successfully', 'apiService.js', 'generateDocument');
      return response.data;
    } catch (error) {
      logger.error(`Failed to generate document: ${error.message}`, 'apiService.js', 'generateDocument');
      throw error;
    }
  },

  async getTemplates() {
    logger.info('Fetching document templates', 'apiService.js', 'getTemplates');
    try {
      const response = await api.get('/documents/templates');
      logger.debug(`Retrieved ${response.data?.length || 0} templates`, 'apiService.js', 'getTemplates');
      return response.data;
    } catch (error) {
      logger.error(`Failed to fetch templates: ${error.message}`, 'apiService.js', 'getTemplates');
      throw error;
    }
  },

  async createTemplate(templateData) {
    logger.info(`Creating new template: ${templateData.name || 'Untitled'}`, 'apiService.js', 'createTemplate');
    try {
      const response = await api.post('/documents/templates', templateData);
      logger.info('Template created successfully', 'apiService.js', 'createTemplate');
      return response.data;
    } catch (error) {
      logger.error(`Failed to create template: ${error.message}`, 'apiService.js', 'createTemplate');
      throw error;
    }
  },

  async getDocumentVersions(documentId) {
    logger.info(`Fetching versions for document ID: ${documentId}`, 'apiService.js', 'getDocumentVersions');
    try {
      const response = await api.get(`/documents/${documentId}/versions`);
      logger.debug(`Retrieved ${response.data?.length || 0} document versions`, 'apiService.js', 'getDocumentVersions');
      return response.data;
    } catch (error) {
      logger.error(`Failed to fetch document versions: ${error.message}`, 'apiService.js', 'getDocumentVersions');
      throw error;
    }
  }
};

export const analyticsService = {
  async getDashboardMetrics() {
    logger.info('Fetching dashboard metrics', 'apiService.js', 'getDashboardMetrics');
    const response = await apiCallWithRetry(
      () => api.get('/analytics/dashboard'),
      'getDashboardMetrics'
    );
    return response;
  },

  async getSystemMetrics(systemId, timeRange) {
    logger.info(`Fetching system metrics for ID: ${systemId}, range: ${timeRange}`, 'apiService.js', 'getSystemMetrics');
    const response = await apiCallWithRetry(
      () => api.get(`/analytics/systems/${systemId}/metrics`, {
        params: { timeRange }
      }),
      'getSystemMetrics'
    );
    return response;
  },

  async getComplianceMetrics() {
    logger.info('Fetching compliance metrics', 'apiService.js', 'getComplianceMetrics');
    const response = await apiCallWithRetry(
      () => api.get('/analytics/compliance'),
      'getComplianceMetrics'
    );
    return response;
  }
};

export const apiKeysService = {
  async getApiKeys() {
    logger.info('Fetching user API keys', 'apiService.js', 'getApiKeys');
    
    return await apiCallWithRetry(
      () => api.get('/api-keys'),
      'getApiKeys'
    );
  },

  async createApiKey(keyData) {
    logger.info('Creating new API key', 'apiService.js', 'createApiKey');
    
    return await apiCallWithRetry(
      () => api.post('/api-keys', keyData),
      'createApiKey'
    );
  },

  async updateApiKey(keyId, keyData) {
    logger.info(`Updating API key: ${keyId}`, 'apiService.js', 'updateApiKey');
    
    return await apiCallWithRetry(
      () => api.put(`/api-keys/${keyId}`, keyData),
      'updateApiKey'
    );
  },

  async deleteApiKey(keyId) {
    logger.info(`Deleting API key: ${keyId}`, 'apiService.js', 'deleteApiKey');
    
    return await apiCallWithRetry(
      () => api.delete(`/api-keys/${keyId}`),
      'deleteApiKey'
    );
  },

  async rotateApiKey(keyId, keyData) {
    logger.info(`Rotating API key: ${keyId}`, 'apiService.js', 'rotateApiKey');
    
    return await apiCallWithRetry(
      () => api.post(`/api-keys/${keyId}/rotate`, keyData),
      'rotateApiKey'
    );
  },

  async getSupportedProviders() {
    logger.info('Fetching supported API key providers', 'apiService.js', 'getSupportedProviders');
    
    return await apiCallWithRetry(
      () => api.get('/api-keys/providers'),
      'getSupportedProviders'
    );
  },

  async getApiKeyValue(keyId) {
    logger.info(`Fetching API key value: ${keyId}`, 'apiService.js', 'getApiKeyValue');
    
    return await apiCallWithRetry(
      () => api.get(`/api-keys/${keyId}/value`),
      'getApiKeyValue'
    );
  }
};

export const modelsService = {
  async getModels() {
    logger.info('Fetching AI model configurations', 'apiService.js', 'getModels');
    
    return await apiCallWithRetry(
      () => api.get('/models/'),
      'getModels'
    );
  },

  async getModel(id) {
    logger.info(`Fetching AI model configuration with ID: ${id}`, 'apiService.js', 'getModel');
    
    return await apiCallWithRetry(
      () => api.get(`/models/${id}`),
      'getModel'
    );
  },

  async createModel(modelData) {
    logger.info(`Creating new AI model configuration: ${modelData.name}`, 'apiService.js', 'createModel');
    
    return await apiCallWithRetry(
      () => api.post('/models/', modelData),
      'createModel'
    );
  },

  async updateModel(id, modelData) {
    logger.info(`Updating AI model configuration: ${id}`, 'apiService.js', 'updateModel');
    
    return await apiCallWithRetry(
      () => api.put(`/models/${id}`, modelData),
      'updateModel'
    );
  },

  async deleteModel(id) {
    logger.info(`Deleting AI model configuration: ${id}`, 'apiService.js', 'deleteModel');
    
    return await apiCallWithRetry(
      () => api.delete(`/models/${id}`),
      'deleteModel'
    );
  },

  async testModel(modelData) {
    logger.info('Testing AI model configuration', 'apiService.js', 'testModel');
    
    return await apiCallWithRetry(
      () => api.post('/models/test', modelData),
      'testModel'
    );
  },

  async getProviders() {
    logger.info('Fetching available model providers', 'apiService.js', 'getProviders');
    
    return await apiCallWithRetry(
      () => api.get('/models/providers'),
      'getProviders'
    );
  }
};