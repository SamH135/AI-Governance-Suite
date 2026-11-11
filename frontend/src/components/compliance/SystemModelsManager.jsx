import React, { useState, useEffect } from 'react';
import { Plus, Play, Edit, Trash2, Settings, Brain, Copy } from 'lucide-react';
import Button from '../ui/Button';
import Card from '../ui/Card';
import Input from '../ui/Input';
import LoadingSpinner from '../ui/LoadingSpinner';
import { modelsService, apiKeysService } from '../../services/apiService';

const SystemModelsManager = ({ systemId, system, availableTemplates, onTestModel }) => {
  const [systemModels, setSystemModels] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showAddModal, setShowAddModal] = useState(false);
  const [editingModel, setEditingModel] = useState(null);

  useEffect(() => {
    fetchSystemModels();
  }, [systemId]);

  const fetchSystemModels = async () => {
    try {
      setLoading(true);
      // Fetch all user models, then filter down to those explicitly
      // linked to this system. We consider a model linked if:
      // - it has a tag of the form `system:<systemId>`, or
      // - it has a direct `system_id` field equal to this system, or
      // - it has metadata with such linkage (future-proof)
      const allModels = await modelsService.getModels();
      const modelsArray = Array.isArray(allModels?.data) ? allModels.data : allModels;

      const systemTag = `system:${systemId}`;
      const filtered = (modelsArray || []).filter((m) => {
        // Prefer explicit tag linkage
        if (Array.isArray(m?.tags) && m.tags.includes(systemTag)) return true;

        // Fallbacks for alternate shapes
        if (m?.system_id && String(m.system_id) === String(systemId)) return true;
        if (m?.metadata?.system_id && String(m.metadata.system_id) === String(systemId)) return true;

        return false;
      });

      setSystemModels(filtered);
    } catch (error) {
      console.error('Failed to fetch system models:', error);
      setSystemModels([]);
    } finally {
      setLoading(false);
    }
  };

  const handleAddModel = () => {
    setEditingModel(null);
    setShowAddModal(true);
  };

  const handleEditModel = (model) => {
    setEditingModel(model);
    setShowAddModal(true);
  };

  const handleDeleteModel = async (model) => {
    if (window.confirm(`Are you sure you want to delete "${model.name}"?`)) {
      try {
        await modelsService.deleteModel(model.config_id || model.id);
        await fetchSystemModels();
      } catch (error) {
        console.error('Failed to delete model:', error);
      }
    }
  };

  const handleSaveModel = async (modelData) => {
    try {
      if (editingModel) {
        await modelsService.updateModel(editingModel.config_id || editingModel.id, modelData);
      } else {
        // Ensure the model is explicitly linked to this system via tags,
        // and marked as a test subject. We preserve any user-provided tags.
        const existingTags = Array.isArray(modelData.tags) ? modelData.tags.slice() : [];
        const systemTag = `system:${systemId}`;
        if (!existingTags.includes(systemTag)) existingTags.push(systemTag);
        if (!existingTags.includes('test_subject')) existingTags.push('test_subject');

        await modelsService.createModel({
          ...modelData,
          system_id: systemId,
          usage_type: 'test_subject',
          tags: existingTags,
        });
      }
      
      setShowAddModal(false);
      setEditingModel(null);
      await fetchSystemModels();
    } catch (error) {
      console.error('Failed to save model:', error);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-8">
        <LoadingSpinner size="lg" />
        <span className="ml-2 text-neutral-600">Loading models...</span>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Models List */}
      {systemModels.length === 0 ? (
        <div className="text-center py-8">
          <Brain className="w-12 h-12 text-neutral-400 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-neutral-900 mb-2">No Models Configured</h3>
          <p className="text-neutral-600 mb-6">
            Add AI models to this system to enable compliance testing. You can create custom models 
            or use pre-configured templates.
          </p>
          <Button onClick={handleAddModel}>
            <Plus className="w-4 h-4 mr-2" />
            Add First Model
          </Button>
        </div>
      ) : (
        <div className="space-y-3">
          {systemModels.map((model) => (
            <ModelCard
              key={model.config_id || model.id}
              model={model}
              onTest={() => onTestModel(model)}
              onEdit={() => handleEditModel(model)}
              onDelete={() => handleDeleteModel(model)}
            />
          ))}
          
          <div className="pt-4 border-t border-neutral-200">
            <Button onClick={handleAddModel} variant="outline" size="sm">
              <Plus className="w-4 h-4 mr-2" />
              Add Another Model
            </Button>
          </div>
        </div>
      )}

      {/* Add/Edit Model Modal */}
      {showAddModal && (
        <ModelFormModal
          isOpen={showAddModal}
          onClose={() => {
            setShowAddModal(false);
            setEditingModel(null);
          }}
          onSave={handleSaveModel}
          model={editingModel}
          availableTemplates={availableTemplates}
          systemName={system?.name}
        />
      )}
    </div>
  );
};

const ModelCard = ({ model, onTest, onEdit, onDelete }) => {
  return (
    <div className="p-4 border rounded-lg border-neutral-200 hover:border-neutral-300 transition-colors">
      <div className="flex items-center justify-between">
        <div className="flex-1">
          <div className="flex items-center gap-2">
            <h4 className="font-medium text-neutral-900">{model.name}</h4>
            {model.usage_type === 'test_subject' && (
              <span className="px-2 py-1 text-xs bg-blue-100 text-blue-700 rounded-full">
                Test Subject
              </span>
            )}
          </div>
          <p className="text-sm text-neutral-600 mt-1">
            {model.provider} • {model.model_id}
            {model.temperature && ` • temp: ${model.temperature}`}
          </p>
          {model.description && (
            <p className="text-sm text-neutral-500 mt-1">{model.description}</p>
          )}
        </div>
        <div className="flex items-center space-x-2">
          <Button size="sm" variant="primary" onClick={onTest}>
            <Play className="w-4 h-4 mr-1" />
            Test
          </Button>
          <Button size="sm" variant="outline" onClick={onEdit}>
            <Edit className="w-4 h-4" />
          </Button>
          <Button size="sm" variant="outline" onClick={onDelete}>
            <Trash2 className="w-4 h-4 text-red-600" />
          </Button>
        </div>
      </div>
    </div>
  );
};

const ModelFormModal = ({ isOpen, onClose, onSave, model, availableTemplates, systemName }) => {
  const [formData, setFormData] = useState({
    name: model?.name || '',
    description: model?.description || '',
    provider: model?.provider || 'openai',
    model_id: model?.model_id || '',
    api_key: model?.api_key || '',
    api_url: model?.api_url || '',
    temperature: model?.temperature || 0.7,
    max_tokens: model?.max_tokens || 1000,
    timeout: model?.timeout || 30
  });
  
  const [useTemplate, setUseTemplate] = useState(false);
  const [selectedTemplate, setSelectedTemplate] = useState('');
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState(null);
  const [testError, setTestError] = useState(null);
  const [savedKeys, setSavedKeys] = useState([]);
  const [loadingKeys, setLoadingKeys] = useState(false);
  const [selectedSavedKey, setSelectedSavedKey] = useState('');

  // Load saved API keys when modal opens
  useEffect(() => {
    const loadKeys = async () => {
      if (!isOpen) return;
      try {
        setLoadingKeys(true);
        const keys = await apiKeysService.getApiKeys();
        // Match Settings implementation: plain array, filter active
        const rawList = Array.isArray(keys) ? keys : (Array.isArray(keys?.data) ? keys.data : []);
        // Only show active keys that can be retrieved for API calls
        const filtered = rawList.filter((k) => k.status === 'active');
        setSavedKeys(filtered);
      } catch (e) {
        // Silently ignore; user can still paste a key manually
        setSavedKeys([]);
      } finally {
        setLoadingKeys(false);
      }
    };
    loadKeys();
  }, [isOpen]);

  const providers = [
    { value: 'openai', label: 'OpenAI' },
    { value: 'google', label: 'Google' },
    { value: 'anthropic', label: 'Anthropic' },
    { value: 'huggingface', label: 'Hugging Face' },
    { value: 'local', label: 'Local/Ollama' }
  ];

  const handleTemplateSelect = (template) => {
    setSelectedTemplate(template.config_id || template.id);
    setFormData({
      ...template,
      name: '', // Clear name so user can provide custom name
      description: template.description || ''
    });
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    onSave(formData);
  };

  const handleTest = async () => {
    try {
      setTesting(true);
      setTestResult(null);
      setTestError(null);

      // Prepare payload; if api_key is masked, omit it to avoid sending placeholder
      const payload = { ...formData };
      if (payload.api_key === '***HIDDEN***') {
        delete payload.api_key;
      }

      const result = await modelsService.testModel(payload);
      const success = result?.success ?? true;
      const data = result?.data ?? result;

      if (!success) {
        setTestError(data?.error || result?.message || 'Model test failed');
      } else {
        setTestResult({
          provider: data?.provider || payload.provider,
          model_id: data?.model_id || payload.model_id,
          response: data?.response || data?.content || JSON.stringify(data).slice(0, 400),
          usage: data?.usage,
        });
      }
    } catch (e) {
      setTestError(e?.message || 'Failed to test model configuration');
    } finally {
      setTesting(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg p-6 w-full max-w-2xl max-h-[90vh] overflow-y-auto">
        <h2 className="text-xl font-bold text-neutral-900 mb-4">
          {model ? 'Edit Model' : `Add Model to ${systemName}`}
        </h2>

        {/* Template Selection */}
        {!model && availableTemplates.length > 0 && (
          <div className="mb-6 p-4 bg-neutral-50 rounded-lg">
            <div className="flex items-center justify-between mb-3">
              <label className="flex items-center space-x-2">
                <input
                  type="checkbox"
                  checked={useTemplate}
                  onChange={(e) => setUseTemplate(e.target.checked)}
                />
                <span className="text-sm font-medium">Start from pre-configured model</span>
              </label>
            </div>
            
            {useTemplate && (
              <div className="space-y-2">
                {availableTemplates.map((template) => (
                  <div
                    key={template.config_id || template.id}
                    className={`p-3 border rounded cursor-pointer transition-colors ${
                      selectedTemplate === (template.config_id || template.id)
                        ? 'border-brand-500 bg-brand-50'
                        : 'border-neutral-200 hover:border-neutral-300'
                    }`}
                    onClick={() => handleTemplateSelect(template)}
                  >
                    <div className="flex items-center gap-2">
                      <Copy className="w-4 h-4 text-neutral-500" />
                      <span className="font-medium">{template.name}</span>
                      <span className="text-sm text-neutral-500">
                        ({template.provider} - {template.model_id})
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Model Name (Custom for this system) */}
          <Input
            label={`Model Name for ${systemName}`}
            value={formData.name}
            onChange={(e) => setFormData({ ...formData, name: e.target.value })}
            placeholder="e.g., main model, bias checker, fallback model"
            required
            help="Give this model a name that makes sense in your system context"
          />

          <Input
            label="Description"
            value={formData.description}
            onChange={(e) => setFormData({ ...formData, description: e.target.value })}
            placeholder="Describe the role of this model in your system"
          />

          {/* Provider Selection */}
          <div>
            <label className="block text-sm font-medium text-neutral-700 mb-1">Provider</label>
            <select
              value={formData.provider}
              onChange={(e) => setFormData({ ...formData, provider: e.target.value })}
              className="input w-full"
              required
            >
              {providers.map((provider) => (
                <option key={provider.value} value={provider.value}>
                  {provider.label}
                </option>
              ))}
            </select>
          </div>

          <Input
            label="Model ID"
            value={formData.model_id}
            onChange={(e) => setFormData({ ...formData, model_id: e.target.value })}
            placeholder="gpt-4, gemini-pro, claude-3-sonnet, etc."
            required
          />

          <Input
            label="API Key"
            type="password"
            value={formData.api_key}
            onChange={(e) => setFormData({ ...formData, api_key: e.target.value })}
            placeholder="Enter API key"
            required={formData.provider !== 'local'}
          />

          {/* Saved API Keys selector */}
          <div className="space-y-1">
            <label className="block text-sm font-medium text-neutral-700">Use saved API key (optional)</label>
            <div className="flex gap-2">
              <select
                className="input flex-1"
                value={selectedSavedKey}
                onChange={async (e) => {
                  const keyId = e.target.value;
                  setSelectedSavedKey(keyId);
                  if (!keyId) return;
                  try {
                    // Fetch actual key value and populate the input
                    const res = await apiKeysService.getApiKeyValue(keyId);
                    const value = res?.key_value ?? res?.data?.key_value ?? '';
                    if (typeof value === 'string' && value.length > 0) {
                      setFormData({ ...formData, api_key: value });
                    }
                  } catch (err) {
                    // Non-blocking; keep manual entry available
                  }
                }}
                disabled={loadingKeys}
              >
                <option value="">{loadingKeys ? 'Loading saved keys…' : (savedKeys.length ? 'Select a saved key' : 'No saved keys')}</option>
                {savedKeys
                  .map((k) => (
                    <option key={k.key_id} value={k.key_id}>
                      {(k.name || `Key ${k.key_id}`)}{k.provider ? ` • ${k.provider}` : ''}
                    </option>
                  ))}
              </select>
            </div>
            <p className="text-xs text-neutral-500">Choosing a saved key will fill the field above; you can still edit it manually.</p>
          </div>

          {formData.provider === 'local' && (
            <Input
              label="API URL"
              value={formData.api_url}
              onChange={(e) => setFormData({ ...formData, api_url: e.target.value })}
              placeholder="http://localhost:11434"
              required
            />
          )}

          <div className="grid grid-cols-3 gap-4">
            <Input
              label="Temperature"
              type="number"
              value={formData.temperature}
              onChange={(e) => setFormData({ ...formData, temperature: parseFloat(e.target.value) })}
              min="0"
              max="2"
              step="0.1"
            />
            <Input
              label="Max Tokens"
              type="number"
              value={formData.max_tokens}
              onChange={(e) => setFormData({ ...formData, max_tokens: parseInt(e.target.value) })}
              min="1"
              max="8000"
            />
            <Input
              label="Timeout (s)"
              type="number"
              value={formData.timeout}
              onChange={(e) => setFormData({ ...formData, timeout: parseInt(e.target.value) })}
              min="5"
              max="300"
            />
          </div>

          {/* Actions */}
          <div className="flex justify-between items-center mt-6">
            <div className="flex items-center space-x-3">
              <Button type="button" variant="outline" onClick={handleTest} disabled={testing}>
                {testing ? (
                  <span className="inline-flex items-center"><LoadingSpinner size="sm" /><span className="ml-2">Testing…</span></span>
                ) : (
                  <span>Test configuration</span>
                )}
              </Button>
            </div>
            <div className="flex justify-end space-x-3">
              <Button type="button" variant="secondary" onClick={onClose}>
              Cancel
              </Button>
              <Button type="submit">
              {model ? 'Update Model' : 'Create Model'}
              </Button>
            </div>
          </div>

          {/* Test output */}
          {(testResult || testError) && (
            <div className="mt-4 p-3 rounded border text-sm" style={{borderColor: testError ? '#fecaca' : '#d1fae5', backgroundColor: testError ? '#fef2f2' : '#ecfdf5'}}>
              {testError ? (
                <div className="text-red-700">{String(testError)}</div>
              ) : (
                <div>
                  <div className="mb-1 text-neutral-700">Test succeeded for {testResult?.provider}/{testResult?.model_id}</div>
                  {testResult?.response && (
                    <pre className="whitespace-pre-wrap break-words text-neutral-800 bg-white p-2 rounded border border-neutral-200 max-h-48 overflow-auto">{testResult.response}</pre>
                  )}
                </div>
              )}
            </div>
          )}
        </form>
      </div>
    </div>
  );
};

export default SystemModelsManager;