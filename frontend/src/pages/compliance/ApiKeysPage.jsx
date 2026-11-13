import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import Card from '../../components/ui/Card';
import Button from '../../components/ui/Button';
import Input from '../../components/ui/Input';
import LoadingSpinner from '../../components/ui/LoadingSpinner';
import { Key, Plus, Eye, EyeOff, Trash2, ArrowLeft } from 'lucide-react';
import { apiKeysService } from '../../services/apiService';
import logger from '../../utils/logger.js';

const ApiKeysPage = () => {
  logger.info('ApiKeysPage component rendered', 'ApiKeysPage.jsx', 'ApiKeysPage');

  const [apiKeys, setApiKeys] = useState([]);
  const [envKeys, setEnvKeys] = useState([]);
  const [apiKeysLoading, setApiKeysLoading] = useState(false);
  const [showCreateApiKey, setShowCreateApiKey] = useState(false);
  const [newApiKey, setNewApiKey] = useState({
    provider: 'openai',
    key_value: '',
    name: '',
    description: ''
  });
  const [supportedProviders, setSupportedProviders] = useState([]);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);
  const [loading, setLoading] = useState(false);
  const [viewableKeys, setViewableKeys] = useState(new Set());
  const [keyValues, setKeyValues] = useState(new Map());
  const [loadingKeyValue, setLoadingKeyValue] = useState(new Set());

  useEffect(() => {
    loadApiKeys();
    loadSupportedProviders();
  }, []);

  useEffect(() => {
    if (error || success) {
      const timer = setTimeout(() => {
        setError(null);
        setSuccess(null);
      }, 5000);
      return () => clearTimeout(timer);
    }
  }, [error, success]);

  const loadApiKeys = async () => {
    setApiKeysLoading(true);
    setError(null);
    try {
      const [keys, env] = await Promise.all([
        apiKeysService.getApiKeys(),
        apiKeysService.getEnvApiKeys().catch(() => [])
      ]);
      const activeKeys = keys.filter(key => key.status !== 'revoked');
      setApiKeys(activeKeys);
      setEnvKeys(env.filter(k => k.configured));
      logger.info('API keys loaded successfully', 'ApiKeysPage.jsx', 'loadApiKeys');
    } catch (error) {
      logger.error(`Failed to load API keys: ${error.message}`, 'ApiKeysPage.jsx', 'loadApiKeys');
      setError('Failed to load API keys. Please try again.');
    } finally {
      setApiKeysLoading(false);
    }
  };

  const loadSupportedProviders = async () => {
    try {
      const providers = await apiKeysService.getSupportedProviders();
      setSupportedProviders(providers);
      logger.info('Supported providers loaded successfully', 'ApiKeysPage.jsx', 'loadSupportedProviders');
    } catch (error) {
      logger.error(`Failed to load supported providers: ${error.message}`, 'ApiKeysPage.jsx', 'loadSupportedProviders');
      setSupportedProviders(['openai', 'anthropic', 'google', 'azure', 'huggingface', 'cohere']);
    }
  };

  const handleCreateApiKey = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setSuccess(null);

    try {
      await apiKeysService.createApiKey(newApiKey);
      setNewApiKey({ provider: 'openai', key_value: '', name: '', description: '' });
      setShowCreateApiKey(false);
      setSuccess('API key created successfully!');
      await loadApiKeys();
      logger.info('API key created successfully', 'ApiKeysPage.jsx', 'handleCreateApiKey');
    } catch (error) {
      logger.error(`Failed to create API key: ${error.message}`, 'ApiKeysPage.jsx', 'handleCreateApiKey');
      let errorMessage = 'Failed to create API key. Please try again.';
      if (error.message) {
        try {
          const errorData = JSON.parse(error.message.substring(error.message.indexOf('{')));
          if (errorData.detail) {
            errorMessage = errorData.detail;
          }
        } catch (parseError) {
          if (error.message.includes('must start with')) {
            errorMessage = error.message;
          }
        }
      }
      setError(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteApiKey = async (keyId) => {
    if (!confirm('Are you sure you want to delete this API key? This action cannot be undone.')) {
      return;
    }

    setError(null);
    setSuccess(null);

    try {
      await apiKeysService.deleteApiKey(keyId);
      setSuccess('API key deleted successfully!');
      await loadApiKeys();
      logger.info('API key deleted successfully', 'ApiKeysPage.jsx', 'handleDeleteApiKey');
    } catch (error) {
      logger.error(`Failed to delete API key: ${error.message}`, 'ApiKeysPage.jsx', 'handleDeleteApiKey');
      setError('Failed to delete API key. Please try again.');
    }
  };

  const getProviderDisplayName = (provider) => {
    const names = {
      'openai': 'OpenAI',
      'anthropic': 'Anthropic',
      'google': 'Google',
      'azure': 'Azure OpenAI',
      'huggingface': 'Hugging Face',
      'cohere': 'Cohere'
    };
    return names[provider] || provider.charAt(0).toUpperCase() + provider.slice(1);
  };

  const formatDate = (dateString) => {
    return new Date(dateString).toLocaleString();
  };

  const toggleViewKey = async (keyId) => {
    if (viewableKeys.has(keyId)) {
      setViewableKeys(prev => {
        const newSet = new Set(prev);
        newSet.delete(keyId);
        return newSet;
      });
    } else {
      if (!keyValues.has(keyId)) {
        setLoadingKeyValue(prev => new Set(prev).add(keyId));
        try {
          const response = await apiKeysService.getApiKeyValue(keyId);
          setKeyValues(prev => new Map(prev).set(keyId, response.key_value));
        } catch (error) {
          logger.error(`Failed to load API key value: ${error.message}`, 'ApiKeysPage.jsx', 'toggleViewKey');
          setError('Failed to load API key value. Please try again.');
          setLoadingKeyValue(prev => {
            const newSet = new Set(prev);
            newSet.delete(keyId);
            return newSet;
          });
          return;
        } finally {
          setLoadingKeyValue(prev => {
            const newSet = new Set(prev);
            newSet.delete(keyId);
            return newSet;
          });
        }
      }
      setViewableKeys(prev => new Set(prev).add(keyId));
    }
  };

  const maskApiKey = (key) => {
    if (!key) return '••••••••••••••••';
    if (key.length <= 8) return '••••••••';
    return key.substring(0, 4) + '••••••••••••' + key.substring(key.length - 4);
  };

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
          <h1 className="text-2xl font-bold text-neutral-900">API Keys</h1>
          <p className="text-neutral-600">
            Manage API keys for AI model providers
          </p>
        </div>
        <Button onClick={() => setShowCreateApiKey(true)}>
          <Plus className="w-4 h-4 mr-2" />
          Add API Key
        </Button>
      </div>

      {/* Error/Success Messages */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-md p-4">
          <div className="flex items-center gap-2">
            <div className="w-4 h-4 text-red-600">⚠</div>
            <p className="text-sm text-red-800">{error}</p>
          </div>
        </div>
      )}

      {success && (
        <div className="bg-green-50 border border-green-200 rounded-md p-4">
          <div className="flex items-center gap-2">
            <div className="w-4 h-4 text-green-600">✓</div>
            <p className="text-sm text-green-800">{success}</p>
          </div>
        </div>
      )}

      {/* Info Card */}
      <Card>
        <Card.Content className="bg-blue-50 border border-blue-200 rounded-md p-4">
          <p className="text-sm text-blue-800">
            API keys are encrypted and stored securely. They are used to authenticate with AI providers when running tests and evaluations.
            Each provider can have one active API key at a time.
          </p>
        </Card.Content>
      </Card>

      {/* Create API Key Form */}
      {showCreateApiKey && (
        <Card className="border-dashed">
          <Card.Header>
            <Card.Title>Add New API Key</Card.Title>
          </Card.Header>
          <Card.Content>
            <form onSubmit={handleCreateApiKey} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-neutral-700 mb-1">Provider</label>
                <select
                  value={newApiKey.provider}
                  onChange={(e) => setNewApiKey(prev => ({ ...prev, provider: e.target.value }))}
                  className="input w-full"
                  required
                >
                  {supportedProviders.map(provider => (
                    <option key={provider} value={provider}>
                      {getProviderDisplayName(provider)}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-neutral-700 mb-1">Name</label>
                <Input
                  value={newApiKey.name}
                  onChange={(e) => setNewApiKey(prev => ({ ...prev, name: e.target.value }))}
                  placeholder="e.g., OpenAI Production Key"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-neutral-700 mb-1">API Key</label>
                <Input
                  type="password"
                  value={newApiKey.key_value}
                  onChange={(e) => setNewApiKey(prev => ({ ...prev, key_value: e.target.value }))}
                  placeholder="Enter your API key"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-neutral-700 mb-1">Description (Optional)</label>
                <textarea
                  value={newApiKey.description}
                  onChange={(e) => setNewApiKey(prev => ({ ...prev, description: e.target.value }))}
                  className="input w-full"
                  rows="2"
                  placeholder="Add a description for this key"
                />
              </div>
              <div className="flex gap-3">
                <Button type="submit" variant="primary" loading={loading} disabled={loading}>
                  Save API Key
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => {
                    setShowCreateApiKey(false);
                    setNewApiKey({ provider: 'openai', key_value: '', name: '', description: '' });
                  }}
                >
                  Cancel
                </Button>
              </div>
            </form>
          </Card.Content>
        </Card>
      )}

      {/* Environment-provided keys (read-only) */}
      {envKeys.length > 0 && (
        <Card>
          <Card.Header>
            <Card.Title>Environment Keys</Card.Title>
          </Card.Header>
          <Card.Content className="space-y-2">
            <p className="text-sm text-neutral-600">
              These keys are loaded from server environment variables and are used automatically when no saved key exists.
            </p>
            {envKeys.map((envKey) => (
              <div
                key={envKey.provider}
                className="flex items-center justify-between border rounded-md p-3 bg-neutral-50"
              >
                <div className="flex items-center gap-2">
                  <div className="w-2 h-2 rounded-full bg-green-500"></div>
                  <span className="font-medium">{getProviderDisplayName(envKey.provider)}</span>
                  <span className="text-xs bg-blue-100 text-blue-800 px-2 py-1 rounded">environment</span>
                </div>
                <span className="font-mono text-xs text-neutral-500">
                  {envKey.env_var} {envKey.masked}
                </span>
              </div>
            ))}
          </Card.Content>
        </Card>
      )}

      {/* API Keys List */}
      {apiKeysLoading ? (
        <Card>
          <Card.Content className="flex justify-center p-4">
            <LoadingSpinner />
          </Card.Content>
        </Card>
      ) : apiKeys.length === 0 ? (
        <Card className="text-center py-12">
          <Key className="w-12 h-12 mx-auto mb-3 text-neutral-400" />
          <h3 className="text-lg font-medium text-neutral-900 mb-2">No API Keys Configured</h3>
          <p className="text-neutral-600 mb-4">
            Add your first API key to get started with AI models
          </p>
          <Button onClick={() => setShowCreateApiKey(true)}>
            <Plus className="w-4 h-4 mr-2" />
            Add Your First API Key
          </Button>
        </Card>
      ) : (
        <div className="space-y-3">
          {apiKeys.map((key) => (
            <Card key={key.key_id}>
              <Card.Content className={`border rounded-md p-4 ${
                key.status === 'active' ? 'bg-white' : 'bg-neutral-50'
              }`}>
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <div className={`w-2 h-2 rounded-full ${
                      key.status === 'active' ? 'bg-green-500' :
                      key.status === 'expired' ? 'bg-red-500' : 'bg-gray-400'
                    }`}></div>
                    <h4 className="font-medium">{key.name || getProviderDisplayName(key.provider)}</h4>
                    <span className="text-xs bg-neutral-100 px-2 py-1 rounded">
                      {getProviderDisplayName(key.provider)}
                    </span>
                  </div>
                  <div className="flex gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => toggleViewKey(key.key_id)}
                      disabled={loadingKeyValue.has(key.key_id)}
                    >
                      {loadingKeyValue.has(key.key_id) ? (
                        <div className="w-4 h-4 animate-spin">⟳</div>
                      ) : viewableKeys.has(key.key_id) ? (
                        <EyeOff className="w-4 h-4" />
                      ) : (
                        <Eye className="w-4 h-4" />
                      )}
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => handleDeleteApiKey(key.key_id)}
                      className="text-red-600 hover:text-red-700"
                    >
                      <Trash2 className="w-4 h-4" />
                    </Button>
                  </div>
                </div>

                <div className="mb-3">
                  <label className="text-xs text-neutral-500 mb-1 block">API Key</label>
                  <div className="font-mono text-sm bg-neutral-100 p-2 rounded border break-all">
                    {viewableKeys.has(key.key_id) && keyValues.has(key.key_id)
                      ? keyValues.get(key.key_id)
                      : maskApiKey(keyValues.get(key.key_id))
                    }
                  </div>
                </div>

                <div className="text-sm text-neutral-600 space-y-1">
                  <p>Created: {formatDate(key.created_at)}</p>
                  {key.expires_at && (
                    <p>Expires: {formatDate(key.expires_at)}</p>
                  )}
                  {key.description && (
                    <p className="text-xs text-neutral-500">{key.description}</p>
                  )}
                </div>
              </Card.Content>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
};

export default ApiKeysPage;
