import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import Card from '../../components/ui/Card';
import Button from '../../components/ui/Button';
import LoadingSpinner from '../../components/ui/LoadingSpinner';
import ModelConfigurationForm from '../../components/settings/ModelConfigurationForm';
import { Brain, Plus, Edit, Trash2, TestTube, Settings, CheckCircle, XCircle, AlertTriangle, ArrowLeft } from 'lucide-react';
import { modelsService } from '../../services/apiService';
import logger from '../../utils/logger.js';

const ModelConfigurationsPage = () => {
  logger.info('ModelConfigurationsPage component rendered', 'ModelConfigurationsPage.jsx', 'ModelConfigurationsPage');

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
    logger.info('Loading model configurations', 'ModelConfigurationsPage.jsx', 'loadModels');
    setLoading(true);
    setError(null);
    try {
      const data = await modelsService.getModels();
      setModels(data);
      logger.info(`Loaded ${data.length} model configurations`, 'ModelConfigurationsPage.jsx', 'loadModels');
    } catch (error) {
      logger.error(`Failed to load models: ${error.message}`, 'ModelConfigurationsPage.jsx', 'loadModels');
      setError(error.message);
    } finally {
      setLoading(false);
    }
  };

  const handleSaveModel = async (modelData) => {
    logger.info('Saving model configuration', 'ModelConfigurationsPage.jsx', 'handleSaveModel');
    try {
      if (editingModel) {
        await modelsService.updateModel(editingModel.id, modelData);
        logger.info(`Updated model configuration: ${modelData.name}`, 'ModelConfigurationsPage.jsx', 'handleSaveModel');
      } else {
        await modelsService.createModel(modelData);
        logger.info(`Created model configuration: ${modelData.name}`, 'ModelConfigurationsPage.jsx', 'handleSaveModel');
      }

      await loadModels();
      setShowForm(false);
      setEditingModel(null);
    } catch (error) {
      logger.error(`Failed to save model: ${error.message}`, 'ModelConfigurationsPage.jsx', 'handleSaveModel');
      throw error;
    }
  };

  const handleTestModel = async (modelData) => {
    logger.info('Testing model configuration', 'ModelConfigurationsPage.jsx', 'handleTestModel');
    try {
      const result = await modelsService.testModel(modelData);
      logger.info('Model test successful', 'ModelConfigurationsPage.jsx', 'handleTestModel');
      return result;
    } catch (error) {
      logger.error(`Model test failed: ${error.message}`, 'ModelConfigurationsPage.jsx', 'handleTestModel');
      throw error;
    }
  };

  const handleDeleteModel = async (modelId) => {
    if (!confirm('Are you sure you want to delete this model configuration?')) {
      return;
    }

    logger.info(`Deleting model configuration: ${modelId}`, 'ModelConfigurationsPage.jsx', 'handleDeleteModel');
    try {
      await modelsService.deleteModel(modelId);
      logger.info('Model configuration deleted successfully', 'ModelConfigurationsPage.jsx', 'handleDeleteModel');
      await loadModels();
    } catch (error) {
      logger.error(`Failed to delete model: ${error.message}`, 'ModelConfigurationsPage.jsx', 'handleDeleteModel');
    }
  };

  const handleToggleModel = async (modelId, enabled) => {
    logger.info(`Toggling model ${modelId} to ${enabled ? 'enabled' : 'disabled'}`, 'ModelConfigurationsPage.jsx', 'handleToggleModel');
    try {
      await modelsService.updateModel(modelId, { enabled });
      logger.info('Model status updated successfully', 'ModelConfigurationsPage.jsx', 'handleToggleModel');
      await loadModels();
    } catch (error) {
      logger.error(`Failed to toggle model: ${error.message}`, 'ModelConfigurationsPage.jsx', 'handleToggleModel');
    }
  };

  const handleQuickTest = async (model) => {
    setTestingModel(model.id);
    try {
      await modelsService.testModel(model);
      logger.info(`Quick test successful for model: ${model.name}`, 'ModelConfigurationsPage.jsx', 'handleQuickTest');
    } catch (error) {
      logger.error(`Quick test failed for model ${model.name}: ${error.message}`, 'ModelConfigurationsPage.jsx', 'handleQuickTest');
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
      <div className="space-y-6">
        <div className="flex items-center space-x-4">
          <Link to="/compliance/models">
            <Button variant="ghost">
              <ArrowLeft className="w-4 h-4" />
            </Button>
          </Link>
          <div className="flex-1">
            <h1 className="text-2xl font-bold text-neutral-900">
              {editingModel ? 'Edit Model Configuration' : 'Add Model Configuration'}
            </h1>
            <p className="text-neutral-600">
              {editingModel ? 'Update AI model configuration' : 'Configure a new AI model'}
            </p>
          </div>
        </div>
        <ModelConfigurationForm
          config={editingModel}
          onSave={handleSaveModel}
          onCancel={() => {
            setShowForm(false);
            setEditingModel(null);
          }}
          onTest={handleTestModel}
        />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex items-center space-x-4">
        <Link to="/compliance/systems">
          <Button variant="ghost">
            <ArrowLeft className="w-4 h-4" />
          </Button>
        </Link>
        <div className="flex-1">
          <h1 className="text-2xl font-bold text-neutral-900">Model Configurations</h1>
          <p className="text-neutral-600">
            Manage AI model configurations for testing
          </p>
        </div>
        <Button
          onClick={() => setShowForm(true)}
          variant="primary"
          disabled={error}
          title={error ? "Backend service must be available to add models" : "Add new AI model configuration"}
        >
          <Plus className="w-4 h-4 mr-2" />
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
        <Card className="text-center py-12">
          <Brain className="w-12 h-12 mx-auto mb-4 text-neutral-400" />
          <h3 className="text-lg font-medium text-neutral-900 mb-2">No Model Configurations</h3>
          <p className="text-neutral-600 mb-4">
            Get started by adding your first AI model configuration
          </p>
          <Button
            onClick={() => setShowForm(true)}
            variant="primary"
          >
            <Plus className="w-4 h-4 mr-2" />
            Add Your First Model
          </Button>
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

export default ModelConfigurationsPage;
