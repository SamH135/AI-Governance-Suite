import { useState, useEffect } from 'react';
import Card from '../ui/Card';
import Button from '../ui/Button';
import LoadingSpinner from '../ui/LoadingSpinner';
import ModelConfigurationForm from './ModelConfigurationForm';
import { Brain, Plus, Edit, Trash2, TestTube, Settings, CheckCircle, XCircle, AlertTriangle } from 'lucide-react';
import { modelsService } from '../../services/apiService';
import logger from '../../utils/logger.js';

const ModelConfigurationManager = () => {
  logger.info('ModelConfigurationManager component rendered', 'ModelConfigurationManager.jsx', 'ModelConfigurationManager');

  const [models, setModels] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [editingModel, setEditingModel] = useState(null);
  const [testingModel, setTestingModel] = useState(null);

  const [error, setError] = useState(null);

  useEffect(() => {
    loadModels();
  }, []);

  const loadModels = async () => {
    logger.info('Loading model configurations', 'ModelConfigurationManager.jsx', 'loadModels');
    setLoading(true);
    setError(null);
    try {
      const data = await modelsService.getModels();
      setModels(data);
      logger.info(`Loaded ${data.length} model configurations`, 'ModelConfigurationManager.jsx', 'loadModels');
    } catch (error) {
      logger.error(`Failed to load models: ${error.message}`, 'ModelConfigurationManager.jsx', 'loadModels');
      setError(error.message);
    } finally {
      setLoading(false);
    }
  };

  const handleSaveModel = async (modelData) => {
    logger.info('Saving model configuration', 'ModelConfigurationManager.jsx', 'handleSaveModel');
    try {
      if (editingModel) {
        await modelsService.updateModel(editingModel.id, modelData);
        logger.info(`Updated model configuration: ${modelData.name}`, 'ModelConfigurationManager.jsx', 'handleSaveModel');
      } else {
        await modelsService.createModel(modelData);
        logger.info(`Created model configuration: ${modelData.name}`, 'ModelConfigurationManager.jsx', 'handleSaveModel');
      }
      
      await loadModels();
      setShowForm(false);
      setEditingModel(null);
    } catch (error) {
      logger.error(`Failed to save model: ${error.message}`, 'ModelConfigurationManager.jsx', 'handleSaveModel');
      throw error; // Re-throw to let the form handle the error
    }
  };

  const handleTestModel = async (modelData) => {
    logger.info('Testing model configuration', 'ModelConfigurationManager.jsx', 'handleTestModel');
    try {
      const result = await modelsService.testModel(modelData);
      logger.info('Model test successful', 'ModelConfigurationManager.jsx', 'handleTestModel');
      return result;
    } catch (error) {
      logger.error(`Model test failed: ${error.message}`, 'ModelConfigurationManager.jsx', 'handleTestModel');
      throw error;
    }
  };

  const handleDeleteModel = async (modelId) => {
    if (!confirm('Are you sure you want to delete this model configuration?')) {
      return;
    }

    logger.info(`Deleting model configuration: ${modelId}`, 'ModelConfigurationManager.jsx', 'handleDeleteModel');
    try {
      await modelsService.deleteModel(modelId);
      logger.info('Model configuration deleted successfully', 'ModelConfigurationManager.jsx', 'handleDeleteModel');
      await loadModels();
    } catch (error) {
      logger.error(`Failed to delete model: ${error.message}`, 'ModelConfigurationManager.jsx', 'handleDeleteModel');
    }
  };

  const handleToggleModel = async (modelId, enabled) => {
    logger.info(`Toggling model ${modelId} to ${enabled ? 'enabled' : 'disabled'}`, 'ModelConfigurationManager.jsx', 'handleToggleModel');
    try {
      await modelsService.updateModel(modelId, { enabled });
      logger.info('Model status updated successfully', 'ModelConfigurationManager.jsx', 'handleToggleModel');
      await loadModels();
    } catch (error) {
      logger.error(`Failed to toggle model: ${error.message}`, 'ModelConfigurationManager.jsx', 'handleToggleModel');
    }
  };

  const handleQuickTest = async (model) => {
    setTestingModel(model.id);
    try {
      await modelsService.testModel(model);
      logger.info(`Quick test successful for model: ${model.name}`, 'ModelConfigurationManager.jsx', 'handleQuickTest');
      // Could show a success notification here
    } catch (error) {
      logger.error(`Quick test failed for model ${model.name}: ${error.message}`, 'ModelConfigurationManager.jsx', 'handleQuickTest');
      // Could show an error notification here
    } finally {
      setTestingModel(null);
    }
  };

  const getProviderBadgeColor = (provider) => {
    const colors = {
      google: 'bg-blue-100 text-blue-800',
      openai: 'bg-green-100 text-green-800', 
      anthropic: 'bg-purple-100 text-purple-800',
      local: 'bg-gray-100 text-gray-800'
    };
    return colors[provider] || 'bg-gray-100 text-gray-800';
  };

  const getStatusIcon = (enabled, hasApiKey) => {
    if (!enabled) {
      return <XCircle className="w-4 h-4 text-gray-400" />;
    }
    if (!hasApiKey && ['google', 'openai', 'anthropic'].includes(enabled)) {
      return <AlertTriangle className="w-4 h-4 text-yellow-500" />;
    }
    return <CheckCircle className="w-4 h-4 text-green-500" />;
  };

  if (showForm) {
    return (
      <ModelConfigurationForm
        config={editingModel}
        onSave={handleSaveModel}
        onCancel={() => {
          setShowForm(false);
          setEditingModel(null);
        }}
        onTest={handleTestModel}
      />
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold text-neutral-900 flex items-center gap-2">
            <Brain className="w-6 h-6" />
            AI Model Configurations
          </h2>
          <p className="text-neutral-600 mt-1">
            Manage AI model configurations for the Unified AI API system
          </p>
        </div>
        <Button
          onClick={() => setShowForm(true)}
          variant="primary"
          className="flex items-center gap-2"
          disabled={error}
          title={error ? "Backend service must be available to add models" : "Add new AI model configuration"}
        >
          <Plus className="w-4 h-4" />
          Add Model
        </Button>
      </div>

      {/* Models List */}
      {loading ? (
        <Card>
          <Card.Content className="flex items-center justify-center py-12">
            <LoadingSpinner />
            <span className="ml-2 text-neutral-600">Loading model configurations...</span>
          </Card.Content>
        </Card>
      ) : error ? (
        <Card>
          <Card.Content className="text-center py-12">
            <AlertTriangle className="w-12 h-12 text-red-400 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-neutral-900 mb-2">Backend Service Not Available</h3>
            <p className="text-neutral-600 mb-4 max-w-md mx-auto">
              {error}
            </p>
            <div className="space-y-2 text-sm text-neutral-500">
              <p>To enable AI model configuration functionality:</p>
              <ul className="list-disc list-inside space-y-1 text-left max-w-md mx-auto">
                <li>Implement <code>/api/models</code> endpoints in the backend</li>
                <li>Connect to the Unified AI API system</li>
                <li>Ensure model configuration storage (database/config files)</li>
              </ul>
            </div>
            <Button
              onClick={loadModels}
              variant="outline"
              className="mt-4"
            >
              Retry Connection
            </Button>
          </Card.Content>
        </Card>
      ) : models.length === 0 ? (
        <Card>
          <Card.Content className="text-center py-12">
            <Brain className="w-12 h-12 text-neutral-400 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-neutral-900 mb-2">No Model Configurations</h3>
            <p className="text-neutral-600 mb-4">
              Get started by adding your first AI model configuration
            </p>
            <Button
              onClick={() => setShowForm(true)}
              variant="primary"
              className="flex items-center gap-2"
            >
              <Plus className="w-4 h-4" />
              Add Your First Model
            </Button>
          </Card.Content>
        </Card>
      ) : (
        <div className="grid gap-4">
          {models.map((model) => (
            <Card key={model.id}>
              <Card.Content>
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-2">
                      {getStatusIcon(model.enabled, model.api_key)}
                      <h3 className="text-lg font-medium text-neutral-900">
                        {model.name}
                      </h3>
                      <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getProviderBadgeColor(model.provider)}`}>
                        {model.provider}
                      </span>
                      {model.tags && model.tags.length > 0 && (
                        <div className="flex gap-1">
                          {model.tags.slice(0, 3).map((tag) => (
                            <span
                              key={tag}
                              className="inline-flex items-center px-2 py-0.5 rounded text-xs bg-neutral-100 text-neutral-600"
                            >
                              {tag}
                            </span>
                          ))}
                          {model.tags.length > 3 && (
                            <span className="inline-flex items-center px-2 py-0.5 rounded text-xs bg-neutral-100 text-neutral-600">
                              +{model.tags.length - 3} more
                            </span>
                          )}
                        </div>
                      )}
                    </div>
                    
                    <p className="text-neutral-600 text-sm mb-3">
                      {model.description || 'No description provided'}
                    </p>
                    
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                      <div>
                        <span className="text-neutral-500">Model:</span>
                        <p className="font-medium">{model.model_id}</p>
                      </div>
                      <div>
                        <span className="text-neutral-500">Temperature:</span>
                        <p className="font-medium">{model.temperature}</p>
                      </div>
                      <div>
                        <span className="text-neutral-500">Max Tokens:</span>
                        <p className="font-medium">{model.max_tokens}</p>
                      </div>
                      <div>
                        <span className="text-neutral-500">Status:</span>
                        <p className={`font-medium ${model.enabled ? 'text-green-600' : 'text-gray-500'}`}>
                          {model.enabled ? 'Enabled' : 'Disabled'}
                        </p>
                      </div>
                    </div>
                  </div>
                  
                  <div className="flex items-center gap-2 ml-4">
                    <Button
                      onClick={() => handleQuickTest(model)}
                      variant="outline"
                      size="sm"
                      disabled={!model.enabled || testingModel === model.id}
                      className="flex items-center gap-1"
                      title="Quick test this model"
                    >
                      <TestTube className="w-3 h-3" />
                      {testingModel === model.id ? 'Testing...' : 'Test'}
                    </Button>
                    
                    <Button
                      onClick={() => {
                        setEditingModel(model);
                        setShowForm(true);
                      }}
                      variant="outline"
                      size="sm"
                      className="flex items-center gap-1"
                      title="Edit configuration"
                    >
                      <Edit className="w-3 h-3" />
                      Edit
                    </Button>
                    
                    <Button
                      onClick={() => handleToggleModel(model.id, !model.enabled)}
                      variant="outline"
                      size="sm"
                      className={`flex items-center gap-1 ${
                        model.enabled 
                          ? 'text-red-600 hover:text-red-700' 
                          : 'text-green-600 hover:text-green-700'
                      }`}
                      title={model.enabled ? 'Disable model' : 'Enable model'}
                    >
                      <Settings className="w-3 h-3" />
                      {model.enabled ? 'Disable' : 'Enable'}
                    </Button>
                    
                    <Button
                      onClick={() => handleDeleteModel(model.id)}
                      variant="outline"
                      size="sm"
                      className="flex items-center gap-1 text-red-600 hover:text-red-700"
                      title="Delete configuration"
                    >
                      <Trash2 className="w-3 h-3" />
                      Delete
                    </Button>
                  </div>
                </div>
              </Card.Content>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
};

export default ModelConfigurationManager;