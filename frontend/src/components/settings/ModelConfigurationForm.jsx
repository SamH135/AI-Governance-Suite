import React, { useState, useEffect } from 'react';
import Card from '../ui/Card';
import Button from '../ui/Button';
import Input from '../ui/Input';
import { Brain, Settings, Eye, EyeOff, TestTube, CheckCircle, XCircle, AlertCircle, Key } from 'lucide-react';
import { apiKeysService } from '../../services/apiService';
import logger from '../../utils/logger.js';

const ModelConfigurationForm = ({ config = null, onSave, onCancel, onTest }) => {
  logger.info('ModelConfigurationForm component rendered', 'ModelConfigurationForm.jsx', 'ModelConfigurationForm');
  console.log('🔧 ModelConfigurationForm: Component loaded with new API key dropdown UI');

  const [formData, setFormData] = useState({
    name: '',
    description: '',
    provider: 'google',
    model_id: '',
    api_key: '',
    api_key_id: '',
    temperature: 0.7,
    max_tokens: 1000,
    top_p: 1.0,
    frequency_penalty: 0.0,
    presence_penalty: 0.0,
    timeout: 30,
    enabled: true,
    tags: []
  });

  const [showApiKey, setShowApiKey] = useState(false);
  const [loading, setLoading] = useState(false);
  const [testResult, setTestResult] = useState(null);
  const [tagInput, setTagInput] = useState('');
  const [availableApiKeys, setAvailableApiKeys] = useState([]);
  const [loadingApiKeys, setLoadingApiKeys] = useState(false);
  const [showApiKeyDropdown, setShowApiKeyDropdown] = useState(false);
  const [selectedKeyIndex, setSelectedKeyIndex] = useState(-1);

  // Provider-specific configurations
  const providerConfigs = {
    google: {
      name: 'Google (Gemini)',
      requiredFields: ['api_key', 'model_id'],
      supportedParams: ['temperature', 'max_tokens', 'top_p']
    },
    openai: {
      name: 'OpenAI',
      requiredFields: ['api_key', 'model_id'],
      supportedParams: ['temperature', 'max_tokens', 'top_p', 'frequency_penalty', 'presence_penalty']
    },
    anthropic: {
      name: 'Anthropic (Claude)',
      requiredFields: ['api_key', 'model_id'],
      supportedParams: ['temperature', 'max_tokens', 'top_p']
    },
    local: {
      name: 'Local Models',
      requiredFields: ['model_id'],
      supportedParams: ['temperature', 'max_tokens', 'top_p']
    }
  };

  useEffect(() => {
    if (config) {
      setFormData({
        name: config.name || '',
        description: config.description || '',
        provider: config.provider || 'google',
        model_id: config.model_id || '',
        api_key: config.api_key || '',
        api_key_id: config.api_key_id || '',
        temperature: config.temperature || 0.7,
        max_tokens: config.max_tokens || 1000,
        top_p: config.top_p || 1.0,
        frequency_penalty: config.frequency_penalty || 0.0,
        presence_penalty: config.presence_penalty || 0.0,
        timeout: config.timeout || 30,
        enabled: config.enabled !== undefined ? config.enabled : true,
        tags: config.tags || []
      });
      
      // Configuration loaded - no need to set specific mode anymore
    }
    
    // Load API keys when component mounts or provider changes
    loadApiKeys();
  }, [config]);

  // Load API keys when provider changes
  useEffect(() => {
    loadApiKeys();
  }, [formData.provider]);

  const loadApiKeys = async () => {
    try {
      setLoadingApiKeys(true);
      logger.info('Loading available API keys', 'ModelConfigurationForm.jsx', 'loadApiKeys');
      
      const keys = await apiKeysService.getApiKeys();
      setAvailableApiKeys(keys);
      logger.info(`Loaded ${keys.length} API keys`, 'ModelConfigurationForm.jsx', 'loadApiKeys');
    } catch (error) {
      logger.error(`Failed to load API keys: ${error.message}`, 'ModelConfigurationForm.jsx', 'loadApiKeys');
      setAvailableApiKeys([]);
    } finally {
      setLoadingApiKeys(false);
    }
  };

  const handleInputChange = (field, value) => {
    logger.debug(`Updating field ${field} with value: ${value}`, 'ModelConfigurationForm.jsx', 'handleInputChange');
    setFormData(prev => ({ ...prev, [field]: value }));
  };

  const handleProviderChange = (provider) => {
    logger.info(`Provider changed to: ${provider}`, 'ModelConfigurationForm.jsx', 'handleProviderChange');
    setFormData(prev => ({
      ...prev,
      provider,
      model_id: '', // Reset model when provider changes
      api_key: prev.provider === provider ? prev.api_key : '', // Keep API key if same provider
      api_key_id: prev.provider === provider ? prev.api_key_id : '' // Keep API key ID if same provider
    }));
  };

  const handleApiKeySelect = (key) => {
    logger.info(`Selected saved API key: ${key.key_id}`, 'ModelConfigurationForm.jsx', 'handleApiKeySelect');
    setFormData(prev => ({ 
      ...prev, 
      api_key_id: key.key_id,
      api_key: '' // Clear the input field when using saved key
    }));
    setShowApiKeyDropdown(false);
  };

  const handleApiKeyInputChange = (value) => {
    setFormData(prev => ({ ...prev, api_key: value, api_key_id: '' }));
    setShowApiKeyDropdown(value.length > 0 && getProviderApiKeys().length > 0);
  };

  const handleApiKeyInputFocus = () => {
    if (getProviderApiKeys().length > 0) {
      setShowApiKeyDropdown(true);
      setSelectedKeyIndex(-1);
    }
  };

  const handleApiKeyInputBlur = () => {
    // Delay hiding dropdown to allow for clicks
    setTimeout(() => {
      setShowApiKeyDropdown(false);
      setSelectedKeyIndex(-1);
    }, 150);
  };

  const handleApiKeyInputKeyDown = (e) => {
    const keys = getProviderApiKeys();
    if (!showApiKeyDropdown || keys.length === 0) return;

    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault();
        setSelectedKeyIndex(prev => Math.min(prev + 1, keys.length - 1));
        break;
      case 'ArrowUp':
        e.preventDefault();
        setSelectedKeyIndex(prev => Math.max(prev - 1, -1));
        break;
      case 'Enter':
        e.preventDefault();
        if (selectedKeyIndex >= 0) {
          handleApiKeySelect(keys[selectedKeyIndex]);
        }
        break;
      case 'Escape':
        setShowApiKeyDropdown(false);
        setSelectedKeyIndex(-1);
        break;
    }
  };

  // Get available API keys filtered by current provider
  const getProviderApiKeys = () => {
    return availableApiKeys.filter(key => 
      key.provider === formData.provider && key.status === 'active'
    );
  };

  const addTag = () => {
    if (tagInput.trim() && !formData.tags.includes(tagInput.trim())) {
      handleInputChange('tags', [...formData.tags, tagInput.trim()]);
      setTagInput('');
    }
  };

  const removeTag = (tagToRemove) => {
    handleInputChange('tags', formData.tags.filter(tag => tag !== tagToRemove));
  };

  const handleTestModel = async () => {
    logger.info('Testing model configuration', 'ModelConfigurationForm.jsx', 'handleTestModel');
    setLoading(true);
    setTestResult(null);
    
    try {
      const result = await onTest(formData);
      // Check if the test actually succeeded based on the response
      const isSuccess = result.success !== false && !result.error_message;
      setTestResult({
        success: isSuccess,
        message: isSuccess ? (result.message || 'Model test successful!') : (result.error_message || 'Model test failed'),
        details: isSuccess ? result.details : result.error_message
      });
      if (isSuccess) {
        logger.info('Model test successful', 'ModelConfigurationForm.jsx', 'handleTestModel');
      } else {
        logger.error(`Model test failed: ${result.error_message}`, 'ModelConfigurationForm.jsx', 'handleTestModel');
      }
    } catch (error) {
      setTestResult({
        success: false,
        message: error.message || 'Model test failed',
        details: error.message.includes('not available') ? 
          'Backend service must be running to test model configurations.' : 
          error.details
      });
      logger.error(`Model test failed: ${error.message}`, 'ModelConfigurationForm.jsx', 'handleTestModel');
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    logger.info('Saving model configuration', 'ModelConfigurationForm.jsx', 'handleSave');
    setLoading(true);
    
    try {
      await onSave(formData);
      logger.info('Model configuration saved successfully', 'ModelConfigurationForm.jsx', 'handleSave');
    } catch (error) {
      logger.error(`Failed to save model configuration: ${error.message}`, 'ModelConfigurationForm.jsx', 'handleSave');
    } finally {
      setLoading(false);
    }
  };

  const currentProvider = providerConfigs[formData.provider];
  const isFormValid = currentProvider?.requiredFields.every(field => {
    if (field === 'api_key') {
      // API key is valid if either api_key or api_key_id is provided
      return formData.api_key?.trim() || formData.api_key_id?.trim();
    }
    return formData[field]?.trim();
  });

  // Check if current input matches a saved API key
  const isUsingSavedKey = () => {
    return formData.api_key_id && getProviderApiKeys().find(k => k.key_id === formData.api_key_id);
  };

  return (
    <Card>
      <Card.Header>
        <Card.Title className="flex items-center gap-2">
          <Brain className="w-5 h-5" />
          {config ? 'Edit AI Model Configuration' : 'Add AI Model Configuration'}
        </Card.Title>
        <Card.Description>
          Configure AI models for use with the Unified AI API system
        </Card.Description>
      </Card.Header>
      
      <Card.Content className="space-y-6">
        {/* Basic Information */}
        <div className="space-y-4">
          <h3 className="text-lg font-medium text-neutral-900">Basic Information</h3>
          
          <Input
            label="Configuration Name"
            value={formData.name}
            onChange={(e) => handleInputChange('name', e.target.value)}
            placeholder="e.g., Primary GPT-4 Model"
            required
          />
          
          <div className="space-y-2">
            <label className="block text-sm font-medium text-neutral-700">
              Description
            </label>
            <textarea
              value={formData.description}
              onChange={(e) => handleInputChange('description', e.target.value)}
              placeholder="Describe the intended use case for this model configuration"
              className="w-full px-3 py-2 border border-neutral-300 rounded-md focus:outline-none focus:ring-2 focus:ring-brand-500"
              rows={3}
            />
          </div>
        </div>

        {/* Provider Selection */}
        <div className="space-y-4">
          <h3 className="text-lg font-medium text-neutral-900">Provider Configuration</h3>
          
          <div className="space-y-2">
            <label className="block text-sm font-medium text-neutral-700">
              AI Provider
            </label>
            <select
              value={formData.provider}
              onChange={(e) => handleProviderChange(e.target.value)}
              className="w-full px-3 py-2 border border-neutral-300 rounded-md focus:outline-none focus:ring-2 focus:ring-brand-500"
            >
              {Object.entries(providerConfigs).map(([key, provider]) => (
                <option key={key} value={key}>
                  {provider.name}
                </option>
              ))}
            </select>
          </div>

          <div className="space-y-2">
            <label className="block text-sm font-medium text-neutral-700">
              Model ID
            </label>
            <Input
              value={formData.model_id}
              onChange={(e) => handleInputChange('model_id', e.target.value)}
              placeholder="Enter the exact model ID from your provider's documentation"
              required
            />
            <p className="text-xs text-neutral-600">
              Enter the exact model identifier as specified by your AI provider (e.g., model names, versions, or endpoints).
            </p>
          </div>

          {currentProvider?.requiredFields.includes('api_key') && (
            <div className="space-y-2">
              <label className="block text-sm font-medium text-neutral-700">
                API Key
                {getProviderApiKeys().length > 0 && (
                  <span className="ml-2 text-xs text-neutral-500">
                    (Type manually or select from saved keys)
                  </span>
                )}
              </label>
              
              <div className="relative">
                <div className="relative">
                  <input
                    type={showApiKey ? 'text' : 'password'}
                    value={isUsingSavedKey() ? '' : formData.api_key}
                    onChange={(e) => handleApiKeyInputChange(e.target.value)}
                    onFocus={handleApiKeyInputFocus}
                    onBlur={handleApiKeyInputBlur}
                    onKeyDown={handleApiKeyInputKeyDown}
                    placeholder={isUsingSavedKey() 
                      ? `Using saved key: ${getProviderApiKeys().find(k => k.key_id === formData.api_key_id)?.name}`
                      : getProviderApiKeys().length > 0 
                        ? "Enter API key or click to select saved key" 
                        : "Enter your API key"
                    }
                    className={`w-full px-3 py-2 pr-20 border rounded-md focus:outline-none focus:ring-2 focus:ring-brand-500 ${
                      isUsingSavedKey() 
                        ? 'border-green-300 bg-green-50' 
                        : 'border-neutral-300'
                    }`}
                    required
                    autoComplete="off"
                    readOnly={isUsingSavedKey()}
                  />
                  <div className="absolute inset-y-0 right-0 flex items-center">
                    {isUsingSavedKey() ? (
                      <>
                        <Key className="w-4 h-4 text-green-600 mr-1" title="Using saved API key" />
                        <button
                          type="button"
                          onClick={() => setFormData(prev => ({ ...prev, api_key_id: '', api_key: '' }))}
                          className="px-2 py-1 text-neutral-400 hover:text-red-600"
                          title="Clear saved key and enter manually"
                        >
                          <XCircle className="w-4 h-4" />
                        </button>
                      </>
                    ) : (
                      <>
                        {getProviderApiKeys().length > 0 && (
                          <button
                            type="button"
                            onClick={() => setShowApiKeyDropdown(!showApiKeyDropdown)}
                            className="px-2 py-1 text-neutral-400 hover:text-neutral-600"
                            title="Select from saved keys"
                          >
                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7" />
                            </svg>
                          </button>
                        )}
                        <button
                          type="button"
                          onClick={() => setShowApiKey(!showApiKey)}
                          className="px-2 py-1 text-neutral-400 hover:text-neutral-600"
                        >
                          {showApiKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                        </button>
                      </>
                    )}
                  </div>
                </div>

                {/* Dropdown for saved API keys */}
                {showApiKeyDropdown && getProviderApiKeys().length > 0 && (
                  <div className="absolute z-10 w-full mt-1 bg-white border border-neutral-200 rounded-md shadow-lg max-h-60 overflow-auto">
                    {loadingApiKeys ? (
                      <div className="px-3 py-2 text-sm text-neutral-500">Loading saved keys...</div>
                    ) : (
                      <>
                        <div className="px-3 py-2 text-xs font-medium text-neutral-600 bg-neutral-50 border-b">
                          Saved {formData.provider} API Keys
                        </div>
                        {getProviderApiKeys().map((key, index) => (
                          <button
                            key={key.key_id}
                            type="button"
                            onClick={() => handleApiKeySelect(key)}
                            className={`w-full px-3 py-2 text-left focus:outline-none ${
                              index === selectedKeyIndex 
                                ? 'bg-brand-50 border-brand-200' 
                                : 'hover:bg-neutral-50 focus:bg-neutral-50'
                            }`}
                          >
                            <div className="flex items-center justify-between">
                              <div>
                                <div className={`text-sm font-medium ${
                                  index === selectedKeyIndex ? 'text-brand-900' : 'text-neutral-900'
                                }`}>
                                  {key.name}
                                </div>
                                {key.description && (
                                  <div className={`text-xs ${
                                    index === selectedKeyIndex ? 'text-brand-600' : 'text-neutral-500'
                                  }`}>
                                    {key.description}
                                  </div>
                                )}
                              </div>
                              <div className={`flex items-center text-xs ${
                                index === selectedKeyIndex ? 'text-brand-500' : 'text-neutral-400'
                              }`}>
                                <Key className="w-3 h-3 mr-1" />
                                {key.provider}
                              </div>
                            </div>
                          </button>
                        ))}
                      </>
                    )}
                  </div>
                )}
              </div>

              {/* Status indicators */}
              {isUsingSavedKey() && (
                <div className="flex items-center text-xs text-green-600">
                  <CheckCircle className="w-3 h-3 mr-1" />
                  Using saved API key: {getProviderApiKeys().find(k => k.key_id === formData.api_key_id)?.name}
                </div>
              )}
              
              {formData.api_key && !formData.api_key_id && (
                <p className="text-xs text-neutral-600">
                  Using manually entered API key. Consider saving it in Settings for easier management.
                </p>
              )}
              
              {getProviderApiKeys().length === 0 && (
                <p className="text-xs text-neutral-600">
                  No saved {formData.provider} API keys found. You can manage API keys in Settings.
                </p>
              )}
            </div>
          )}
        </div>

        {/* Model Parameters */}
        <div className="space-y-4">
          <h3 className="text-lg font-medium text-neutral-900">Model Parameters</h3>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {currentProvider?.supportedParams.includes('temperature') && (
              <div className="space-y-2">
                <label className="block text-sm font-medium text-neutral-700">
                  Temperature ({formData.temperature})
                </label>
                <input
                  type="range"
                  min="0"
                  max="2"
                  step="0.1"
                  value={formData.temperature}
                  onChange={(e) => handleInputChange('temperature', parseFloat(e.target.value))}
                  className="w-full"
                />
                <div className="flex justify-between text-xs text-neutral-500">
                  <span>Focused</span>
                  <span>Creative</span>
                </div>
              </div>
            )}

            {currentProvider?.supportedParams.includes('max_tokens') && (
              <Input
                label="Max Tokens"
                type="number"
                value={formData.max_tokens}
                onChange={(e) => handleInputChange('max_tokens', parseInt(e.target.value))}
                min="1"
                max="32000"
                placeholder="1000"
              />
            )}

            {currentProvider?.supportedParams.includes('top_p') && (
              <div className="space-y-2">
                <label className="block text-sm font-medium text-neutral-700">
                  Top P ({formData.top_p})
                </label>
                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.1"
                  value={formData.top_p}
                  onChange={(e) => handleInputChange('top_p', parseFloat(e.target.value))}
                  className="w-full"
                />
              </div>
            )}

            {currentProvider?.supportedParams.includes('frequency_penalty') && (
              <div className="space-y-2">
                <label className="block text-sm font-medium text-neutral-700">
                  Frequency Penalty ({formData.frequency_penalty})
                </label>
                <input
                  type="range"
                  min="-2"
                  max="2"
                  step="0.1"
                  value={formData.frequency_penalty}
                  onChange={(e) => handleInputChange('frequency_penalty', parseFloat(e.target.value))}
                  className="w-full"
                />
              </div>
            )}

            {currentProvider?.supportedParams.includes('presence_penalty') && (
              <div className="space-y-2">
                <label className="block text-sm font-medium text-neutral-700">
                  Presence Penalty ({formData.presence_penalty})
                </label>
                <input
                  type="range"
                  min="-2"
                  max="2"
                  step="0.1"
                  value={formData.presence_penalty}
                  onChange={(e) => handleInputChange('presence_penalty', parseFloat(e.target.value))}
                  className="w-full"
                />
              </div>
            )}
          </div>

          <Input
            label="Timeout (seconds)"
            type="number"
            value={formData.timeout}
            onChange={(e) => handleInputChange('timeout', parseInt(e.target.value))}
            min="5"
            max="300"
            placeholder="30"
          />
        </div>

        {/* Tags */}
        <div className="space-y-4">
          <h3 className="text-lg font-medium text-neutral-900">Tags</h3>
          
          <div className="space-y-2">
            <div className="flex gap-2">
              <input
                type="text"
                value={tagInput}
                onChange={(e) => setTagInput(e.target.value)}
                placeholder="Add tags (e.g., production, testing, high-quality)"
                className="flex-1 px-3 py-2 border border-neutral-300 rounded-md focus:outline-none focus:ring-2 focus:ring-brand-500"
                onKeyPress={(e) => e.key === 'Enter' && (e.preventDefault(), addTag())}
              />
              <Button type="button" onClick={addTag} variant="outline">
                Add
              </Button>
            </div>
            
            {formData.tags.length > 0 && (
              <div className="flex flex-wrap gap-2">
                {formData.tags.map((tag) => (
                  <span
                    key={tag}
                    className="inline-flex items-center gap-1 px-2 py-1 bg-brand-100 text-brand-800 text-sm rounded-md"
                  >
                    {tag}
                    <button
                      type="button"
                      onClick={() => removeTag(tag)}
                      className="text-brand-600 hover:text-brand-800"
                    >
                      ×
                    </button>
                  </span>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Status */}
        <div className="space-y-2">
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={formData.enabled}
              onChange={(e) => handleInputChange('enabled', e.target.checked)}
              className="rounded"
            />
            <span className="text-sm font-medium text-neutral-700">
              Enable this configuration
            </span>
          </label>
        </div>

        {/* Test Result */}
        {testResult && (
          <div className={`rounded-md p-4 ${
            testResult.success 
              ? 'bg-green-50 border border-green-200' 
              : 'bg-red-50 border border-red-200'
          }`}>
            <div className="flex items-start gap-2">
              {testResult.success ? (
                <CheckCircle className="w-5 h-5 text-green-600 flex-shrink-0 mt-0.5" />
              ) : (
                <XCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
              )}
              <div>
                <p className={`font-medium ${
                  testResult.success ? 'text-green-800' : 'text-red-800'
                }`}>
                  {testResult.message}
                </p>
                {testResult.details && (
                  <p className={`text-sm mt-1 ${
                    testResult.success ? 'text-green-700' : 'text-red-700'
                  }`}>
                    {testResult.details}
                  </p>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Actions */}
        <div className="flex gap-3 pt-4 border-t">
          <Button
            type="button"
            onClick={handleTestModel}
            variant="outline"
            loading={loading}
            disabled={!isFormValid || loading}
            className="flex items-center gap-2"
          >
            <TestTube className="w-4 h-4" />
            Test Configuration
          </Button>
          
          <Button
            type="button"
            onClick={handleSave}
            variant="primary"
            loading={loading}
            disabled={!isFormValid || loading}
          >
            {config ? 'Update Configuration' : 'Save Configuration'}
          </Button>
          
          <Button
            type="button"
            onClick={onCancel}
            variant="outline"
            disabled={loading}
          >
            Cancel
          </Button>
        </div>
      </Card.Content>
    </Card>
  );
};

export default ModelConfigurationForm;