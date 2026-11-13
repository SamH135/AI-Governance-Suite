import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Card from '../ui/Card';
import Button from '../ui/Button';
import Input from '../ui/Input';
import LoadingSpinner from '../ui/LoadingSpinner';
import { Key, Brain, Shield, CheckCircle, ArrowRight, ArrowLeft, X } from 'lucide-react';
import { apiKeysService, modelsService, systemsService } from '../../services/apiService';
import logger from '../../utils/logger.js';

const QuickSetupWizard = ({ onClose }) => {
  logger.info('QuickSetupWizard component rendered', 'QuickSetupWizard.jsx', 'QuickSetupWizard');

  const navigate = useNavigate();
  const [currentStep, setCurrentStep] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Step 1: API Keys
  const [apiKeyData, setApiKeyData] = useState({
    provider: 'openai',
    key_value: '',
    name: '',
    description: ''
  });

  // Step 2: Model Configuration
  const [modelData, setModelData] = useState({
    provider: 'openai',
    model_id: 'gpt-4',
    name: '',
    description: '',
    temperature: 0.7,
    max_tokens: 1000,
    enabled: true
  });

  // Step 3: AI System
  const [systemData, setSystemData] = useState({
    name: '',
    description: '',
    system_type: 'llm',
    industry: 'general'
  });

  const steps = [
    { id: 1, title: 'API Keys', icon: Key },
    { id: 2, title: 'Model Configuration', icon: Brain },
    { id: 3, title: 'AI System', icon: Shield },
    { id: 4, title: 'Complete', icon: CheckCircle }
  ];

  const handleNext = async () => {
    setError(null);

    if (currentStep === 1) {
      // Validate and save API Key
      if (!apiKeyData.key_value || !apiKeyData.name) {
        setError('Please fill in all required fields');
        return;
      }

      setLoading(true);
      try {
        await apiKeysService.createApiKey(apiKeyData);
        logger.info('API key created successfully in wizard', 'QuickSetupWizard.jsx', 'handleNext');
        setCurrentStep(2);
      } catch (error) {
        logger.error(`Failed to create API key: ${error.message}`, 'QuickSetupWizard.jsx', 'handleNext');
        setError('Failed to create API key. Please try again.');
      } finally {
        setLoading(false);
      }
    } else if (currentStep === 2) {
      // Validate and save Model Configuration
      if (!modelData.name || !modelData.model_id) {
        setError('Please fill in all required fields');
        return;
      }

      setLoading(true);
      try {
        // Include API key for validation
        const modelPayload = {
          ...modelData,
          api_key: apiKeyData.key_value
        };

        // Test the model configuration first
        await modelsService.testModel(modelPayload);
        logger.info('Model test successful in wizard', 'QuickSetupWizard.jsx', 'handleNext');

        // Save the model configuration
        await modelsService.createModel(modelData);
        logger.info('Model configuration created successfully in wizard', 'QuickSetupWizard.jsx', 'handleNext');
        setCurrentStep(3);
      } catch (error) {
        logger.error(`Failed to create model configuration: ${error.message}`, 'QuickSetupWizard.jsx', 'handleNext');
        setError('Failed to validate or save model configuration. Please check your API key and model settings.');
      } finally {
        setLoading(false);
      }
    } else if (currentStep === 3) {
      // Validate and save AI System
      if (!systemData.name) {
        setError('Please enter a system name');
        return;
      }

      setLoading(true);
      try {
        await systemsService.createSystem(systemData);
        logger.info('AI system created successfully in wizard', 'QuickSetupWizard.jsx', 'handleNext');
        setCurrentStep(4);
      } catch (error) {
        logger.error(`Failed to create AI system: ${error.message}`, 'QuickSetupWizard.jsx', 'handleNext');
        setError('Failed to create AI system. Please try again.');
      } finally {
        setLoading(false);
      }
    }
  };

  const handleBack = () => {
    if (currentStep > 1) {
      setCurrentStep(currentStep - 1);
    }
  };

  const handleSkip = () => {
    if (currentStep < 3) {
      setCurrentStep(currentStep + 1);
    }
  };

  const handleFinish = () => {
    navigate('/compliance/systems');
    if (onClose) onClose();
  };

  const renderStepContent = () => {
    switch (currentStep) {
      case 1:
        return (
          <div className="space-y-4">
            <div className="flex items-center gap-3 mb-4">
              <div className="p-3 bg-blue-100 rounded-lg">
                <Key className="w-6 h-6 text-blue-600" />
              </div>
              <div>
                <h3 className="text-lg font-semibold text-neutral-900">Add API Key</h3>
                <p className="text-sm text-neutral-600">
                  Add an API key for your AI provider to enable model testing
                </p>
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-neutral-700 mb-1">Provider</label>
              <select
                value={apiKeyData.provider}
                onChange={(e) => setApiKeyData(prev => ({ ...prev, provider: e.target.value }))}
                className="input w-full"
              >
                <option value="openai">OpenAI</option>
                <option value="anthropic">Anthropic</option>
                <option value="google">Google</option>
                <option value="azure">Azure OpenAI</option>
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-neutral-700 mb-1">Name</label>
              <Input
                value={apiKeyData.name}
                onChange={(e) => setApiKeyData(prev => ({ ...prev, name: e.target.value }))}
                placeholder="e.g., OpenAI Production Key"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-neutral-700 mb-1">API Key</label>
              <Input
                type="password"
                value={apiKeyData.key_value}
                onChange={(e) => setApiKeyData(prev => ({ ...prev, key_value: e.target.value }))}
                placeholder="Enter your API key"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-neutral-700 mb-1">Description (Optional)</label>
              <textarea
                value={apiKeyData.description}
                onChange={(e) => setApiKeyData(prev => ({ ...prev, description: e.target.value }))}
                className="input w-full"
                rows="2"
                placeholder="Add a description for this key"
              />
            </div>
          </div>
        );

      case 2:
        return (
          <div className="space-y-4">
            <div className="flex items-center gap-3 mb-4">
              <div className="p-3 bg-purple-100 rounded-lg">
                <Brain className="w-6 h-6 text-purple-600" />
              </div>
              <div>
                <h3 className="text-lg font-semibold text-neutral-900">Configure Model</h3>
                <p className="text-sm text-neutral-600">
                  Set up an AI model configuration using your API key
                </p>
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-neutral-700 mb-1">Provider</label>
              <select
                value={modelData.provider}
                onChange={(e) => setModelData(prev => ({ ...prev, provider: e.target.value }))}
                className="input w-full"
              >
                <option value="openai">OpenAI</option>
                <option value="anthropic">Anthropic</option>
                <option value="google">Google</option>
                <option value="azure">Azure OpenAI</option>
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-neutral-700 mb-1">Model ID</label>
              <Input
                value={modelData.model_id}
                onChange={(e) => setModelData(prev => ({ ...prev, model_id: e.target.value }))}
                placeholder="e.g., gpt-4, claude-3-opus"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-neutral-700 mb-1">Configuration Name</label>
              <Input
                value={modelData.name}
                onChange={(e) => setModelData(prev => ({ ...prev, name: e.target.value }))}
                placeholder="e.g., GPT-4 Production"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-neutral-700 mb-1">Description (Optional)</label>
              <textarea
                value={modelData.description}
                onChange={(e) => setModelData(prev => ({ ...prev, description: e.target.value }))}
                className="input w-full"
                rows="2"
                placeholder="Describe this model configuration"
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-neutral-700 mb-1">Temperature</label>
                <Input
                  type="number"
                  step="0.1"
                  min="0"
                  max="2"
                  value={modelData.temperature}
                  onChange={(e) => setModelData(prev => ({ ...prev, temperature: parseFloat(e.target.value) }))}
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-neutral-700 mb-1">Max Tokens</label>
                <Input
                  type="number"
                  min="1"
                  value={modelData.max_tokens}
                  onChange={(e) => setModelData(prev => ({ ...prev, max_tokens: parseInt(e.target.value) }))}
                />
              </div>
            </div>
          </div>
        );

      case 3:
        return (
          <div className="space-y-4">
            <div className="flex items-center gap-3 mb-4">
              <div className="p-3 bg-green-100 rounded-lg">
                <Shield className="w-6 h-6 text-green-600" />
              </div>
              <div>
                <h3 className="text-lg font-semibold text-neutral-900">Create AI System</h3>
                <p className="text-sm text-neutral-600">
                  Define the AI system you want to test for compliance
                </p>
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-neutral-700 mb-1">System Name</label>
              <Input
                value={systemData.name}
                onChange={(e) => setSystemData(prev => ({ ...prev, name: e.target.value }))}
                placeholder="e.g., Customer Support Chatbot"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-neutral-700 mb-1">Description</label>
              <textarea
                value={systemData.description}
                onChange={(e) => setSystemData(prev => ({ ...prev, description: e.target.value }))}
                className="input w-full"
                rows="3"
                placeholder="Describe your AI system and its use case"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-neutral-700 mb-1">System Type</label>
              <select
                value={systemData.system_type}
                onChange={(e) => setSystemData(prev => ({ ...prev, system_type: e.target.value }))}
                className="input w-full"
              >
                <option value="llm">Large Language Model</option>
                <option value="ml_model">Machine Learning Model</option>
                <option value="multi_agent">Multi-Agent System</option>
                <option value="rag">RAG System</option>
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-neutral-700 mb-1">Industry</label>
              <select
                value={systemData.industry}
                onChange={(e) => setSystemData(prev => ({ ...prev, industry: e.target.value }))}
                className="input w-full"
              >
                <option value="general">General</option>
                <option value="healthcare">Healthcare</option>
                <option value="finance">Finance</option>
                <option value="legal">Legal</option>
                <option value="education">Education</option>
              </select>
            </div>
          </div>
        );

      case 4:
        return (
          <div className="text-center py-8">
            <div className="p-4 bg-green-100 rounded-full w-16 h-16 mx-auto mb-4">
              <CheckCircle className="w-8 h-8 text-green-600" />
            </div>
            <h3 className="text-xl font-semibold text-neutral-900 mb-2">Setup Complete!</h3>
            <p className="text-neutral-600 mb-6">
              Your AI compliance testing environment is now configured. You can start running tests on your AI systems.
            </p>
            <div className="space-y-2 text-sm text-neutral-600">
              <p>✓ API key configured</p>
              <p>✓ Model configuration created and validated</p>
              <p>✓ AI system registered</p>
            </div>
          </div>
        );

      default:
        return null;
    }
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <Card className="w-full max-w-2xl max-h-[90vh] overflow-y-auto">
        <Card.Header className="flex items-center justify-between">
          <div>
            <Card.Title>Quick Setup</Card.Title>
            <Card.Description>
              Get started with AI compliance testing in a few simple steps
            </Card.Description>
          </div>
          <Button variant="ghost" size="sm" onClick={onClose}>
            <X className="w-4 h-4" />
          </Button>
        </Card.Header>

        <Card.Content>
          {/* Progress Steps */}
          <div className="flex items-center justify-between mb-8">
            {steps.map((step, index) => (
              <div key={step.id} className="flex items-center flex-1">
                <div className="flex flex-col items-center">
                  <div className={`w-10 h-10 rounded-full flex items-center justify-center ${
                    currentStep >= step.id
                      ? 'bg-brand-500 text-white'
                      : 'bg-neutral-200 text-neutral-500'
                  }`}>
                    {currentStep > step.id ? (
                      <CheckCircle className="w-5 h-5" />
                    ) : (
                      <step.icon className="w-5 h-5" />
                    )}
                  </div>
                  <span className={`text-xs mt-2 ${
                    currentStep >= step.id ? 'text-brand-600 font-medium' : 'text-neutral-500'
                  }`}>
                    {step.title}
                  </span>
                </div>
                {index < steps.length - 1 && (
                  <div className={`flex-1 h-0.5 mx-2 ${
                    currentStep > step.id ? 'bg-brand-500' : 'bg-neutral-200'
                  }`} />
                )}
              </div>
            ))}
          </div>

          {/* Error Message */}
          {error && (
            <div className="bg-red-50 border border-red-200 rounded-md p-4 mb-4">
              <p className="text-sm text-red-800">{error}</p>
            </div>
          )}

          {/* Step Content */}
          {loading ? (
            <div className="flex flex-col items-center justify-center py-12">
              <LoadingSpinner />
              <p className="text-sm text-neutral-600 mt-4">Processing...</p>
            </div>
          ) : (
            renderStepContent()
          )}
        </Card.Content>

        {/* Footer Actions */}
        {currentStep < 4 && (
          <Card.Footer className="flex items-center justify-between pt-4 border-t border-neutral-200">
            <div className="flex gap-2">
              {currentStep > 1 && (
                <Button variant="outline" onClick={handleBack} disabled={loading}>
                  <ArrowLeft className="w-4 h-4 mr-2" />
                  Back
                </Button>
              )}
              {currentStep < 3 && (
                <Button variant="ghost" onClick={handleSkip} disabled={loading}>
                  Skip
                </Button>
              )}
            </div>
            <Button onClick={handleNext} disabled={loading}>
              {currentStep === 3 ? 'Complete Setup' : 'Next'}
              <ArrowRight className="w-4 h-4 ml-2" />
            </Button>
          </Card.Footer>
        )}

        {currentStep === 4 && (
          <Card.Footer className="flex justify-end pt-4 border-t border-neutral-200">
            <Button onClick={handleFinish} variant="primary">
              Go to AI Systems
              <ArrowRight className="w-4 h-4 ml-2" />
            </Button>
          </Card.Footer>
        )}
      </Card>
    </div>
  );
};

export default QuickSetupWizard;
