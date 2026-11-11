import React, { useState, useEffect } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import { ArrowLeft, Play, Settings, AlertCircle } from 'lucide-react';
import Card from '../../components/ui/Card';
import Button from '../../components/ui/Button';
import Input from '../../components/ui/Input';
import LoadingSpinner from '../../components/ui/LoadingSpinner';
import { useToast } from '../../components/ui/Toast';
import { safeApiCall } from '../../utils/apiErrorHandler';
import { systemsService, testingService, modelsService } from '../../services/apiService';

const TestConfigPage = () => {
  const { systemId } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const toast = useToast();
  const [system, setSystem] = useState(null);
  const [evaluators, setEvaluators] = useState([]);
  const [modelConfigs, setModelConfigs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [testRunning, setTestRunning] = useState(false);
  const [testConfig, setTestConfig] = useState({
    // Evaluator Configuration
    evaluators: [],
    evaluatorModelId: null, // Deprecated: use evaluator_model_id
    evaluator_model_id: null, // AI model to power the evaluators
    
    // Test Subject Configuration  
    test_subject_model_id: null, // If null, uses system's default model
    test_prompts: '',
    
    // Legacy fields (for backward compatibility)
    testPrompts: '', // Deprecated: use test_prompts
    maxTokens: 1000,
    temperature: 0.7,
    iterations: 1,
    
    // Advanced Configuration
    test_subject_params: {
      max_tokens: 1000,
      temperature: 0.7
    },
    evaluator_params: {},
    concurrent_evaluators: true,
    save_intermediate_results: true
  });

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      setError(null);
      
      try {
        // Fetch system data with enhanced error handling
        const systemData = await safeApiCall(
          () => systemsService.getSystem(systemId),
          {
            context: 'Loading AI System',
            toast,
            fallbackData: null
          }
        );
        
        // Fetch evaluators with enhanced error handling  
        const evaluatorsData = await safeApiCall(
          () => testingService.getEvaluators(),
          {
            context: 'Loading Evaluators',
            toast,
            fallbackData: [],
            showToast: false // Don't show toast for evaluators, it's non-critical
          }
        );
        
        // Fetch model configurations for evaluator selection
        const modelConfigsData = await safeApiCall(
          () => modelsService.getModels(),
          {
            context: 'Loading Model Configurations',
            toast,
            fallbackData: [],
            showToast: false
          }
        );
        
        console.log('Model configs loaded:', modelConfigsData);
        
        setSystem(systemData);
        setEvaluators(evaluatorsData);
        setModelConfigs(modelConfigsData);
        
        // Set test subject model - priority: navigation state > system default
        const preSelectedModelId = location.state?.selectedModelId;
        if (preSelectedModelId) {
          setTestConfig(prev => ({
            ...prev,
            test_subject_model_id: preSelectedModelId
          }));
          console.log('Pre-selected model ID from navigation:', preSelectedModelId);
        } else if (systemData && systemData.model_config_id) {
          setTestConfig(prev => ({
            ...prev,
            test_subject_model_id: systemData.model_config_id
          }));
          console.log('Auto-set test subject model ID to system default:', systemData.model_config_id);
        }
        
        if (systemData) {
          toast.success(`Loaded ${systemData.name} configuration`);
        }
        
      } catch (error) {
        setError(error.message);
        
        // If we can't load the system, we can't continue
        if (!error.message.includes('Evaluators')) {
          setTimeout(() => {
            navigate('/compliance/systems');
          }, 3000);
        }
      } finally {
        setLoading(false);
      }
    };

    if (systemId) {
      fetchData();
    } else {
      setError('No system ID provided');
      setLoading(false);
    }
  }, [systemId, navigate]);

  const handleEvaluatorToggle = (evaluatorId) => {
    setTestConfig(prev => ({
      ...prev,
      evaluators: prev.evaluators.includes(evaluatorId)
        ? prev.evaluators.filter(id => id !== evaluatorId)
        : [...prev.evaluators, evaluatorId]
    }));
  };

  const handleEvaluatorModelSelection = (e) => {
    e.preventDefault();
    const selectedValue = e.target.value;
    console.log('Raw evaluator model selected value:', selectedValue);
    console.log('Type of selected value:', typeof selectedValue);
    
    let modelId = null;
    if (selectedValue && selectedValue !== '') {
      modelId = parseInt(selectedValue, 10);
      console.log('Parsed evaluator model ID:', modelId);
    }
    
    console.log('About to update testConfig with evaluator_model_id:', modelId);
    
    // Update both new and legacy fields for compatibility
    setTestConfig(currentConfig => {
      console.log('Current config in evaluator model updater:', currentConfig);
      const newConfig = {
        ...currentConfig,
        evaluator_model_id: modelId,
        evaluatorModelId: modelId  // Legacy field
      };
      console.log('New config being set:', newConfig);
      return newConfig;
    });
  };

  const handleTestSubjectModelSelection = (e) => {
    e.preventDefault();
    const selectedValue = e.target.value;
    
    let modelId = null;
    if (selectedValue && selectedValue !== '') {
      modelId = parseInt(selectedValue, 10);
    }
    
    setTestConfig(currentConfig => ({
      ...currentConfig,
      test_subject_model_id: modelId
    }));
  };

  const handleRunTest = async () => {
    // Validate test configuration
    if (testConfig.evaluators.length === 0) {
      toast.warning('Please select at least one evaluator to run the test');
      return;
    }
    
    // Check for evaluator model (new or legacy field)
    const evaluatorModelId = testConfig.evaluator_model_id || testConfig.evaluatorModelId;
    if (!evaluatorModelId) {
      toast.warning('Please select an AI model to power the evaluators');
      return;
    }
    
    // Validate test prompts
    const testPrompts = testConfig.test_prompts || testConfig.testPrompts;
    if (!testPrompts || testPrompts.trim().length === 0) {
      toast.warning('Please provide test prompts to send to the AI system');
      return;
    }
    
    setTestRunning(true);
    
    try {
      toast.info('Starting compliance test...', {
        title: 'Test Execution',
        duration: 3000
      });
      
      // Prepare enhanced test payload
      const enhancedTestConfig = {
        // New field structure
        test_subject_model_id: testConfig.test_subject_model_id, // null means use system default
        test_prompts: testPrompts,
        evaluators: testConfig.evaluators,
        evaluator_model_id: evaluatorModelId,
        test_subject_params: testConfig.test_subject_params,
        evaluator_params: testConfig.evaluator_params,
        iterations: testConfig.iterations,
        concurrent_evaluators: testConfig.concurrent_evaluators,
        save_intermediate_results: testConfig.save_intermediate_results,
        
        // Legacy fields for backward compatibility
        evaluatorModelId: evaluatorModelId,
        testPrompts: testPrompts,
        maxTokens: testConfig.test_subject_params?.max_tokens || testConfig.maxTokens,
        temperature: testConfig.test_subject_params?.temperature || testConfig.temperature
      };

      console.log('Sending enhanced test config:', enhancedTestConfig);

      const result = await safeApiCall(
        () => systemsService.runTest(systemId, enhancedTestConfig),
        {
          context: 'Running Compliance Test',
          toast,
          retries: 1, // Less retries for test execution
          timeout: 60000 // Longer timeout for test execution
        }
      );
      
      // If this is a direct evaluator result, store it for the results page
      if (result.testId && result.testId.startsWith('eval_')) {
        sessionStorage.setItem(`test_result_${result.testId}`, JSON.stringify(result));
      }
      
      toast.success('Test started successfully! Redirecting to results...', {
        title: 'Test Execution'
      });
      
      setTimeout(() => {
        // Pass systemId via both URL query and navigation state for robustness (survives refresh via query)
        navigate(`/compliance/results/${result.testId}?systemId=${systemId}`, { state: { systemId } });
      }, 1500);
      
    } catch (error) {
      // Error is already handled by safeApiCall and shown in toast
      console.error('Test execution failed:', error);
    } finally {
      setTestRunning(false);
    }
  };

  const handleRetry = () => {
    // Retry fetching data
    window.location.reload();
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <LoadingSpinner size="lg" />
          <p className="mt-4 text-neutral-600">Loading test configuration...</p>
        </div>
      </div>
    );
  }

  if (error && !system) {
    return (
      <div className="flex items-center justify-center h-64">
        <Card className="max-w-md w-full">
          <Card.Header>
            <div className="flex items-center space-x-3">
              <AlertCircle className="w-6 h-6 text-red-500" />
              <Card.Title>Failed to Load Configuration</Card.Title>
            </div>
          </Card.Header>
          <Card.Content>
            <div className="space-y-4">
              <p className="text-neutral-600">{error}</p>
              <div className="flex space-x-3">
                <Button onClick={handleRetry} variant="primary" size="sm">
                  Try Again
                </Button>
                <Button 
                  onClick={() => navigate('/compliance/systems')} 
                  variant="ghost" 
                  size="sm"
                >
                  Back to Systems
                </Button>
              </div>
            </div>
          </Card.Content>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center space-x-4">
        <Button
          variant="ghost"
          onClick={() => navigate('/compliance/systems')}
        >
          <ArrowLeft className="w-4 h-4" />
        </Button>
        <div>
          <h1 className="text-2xl font-bold text-neutral-900">Configure Test</h1>
          <p className="text-neutral-600">
            {system?.name} - Set up your compliance test parameters
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Test Configuration */}
        <div className="lg:col-span-2 space-y-6">
          {/* Evaluators */}
          <Card>
            <Card.Header>
              <Card.Title>Select Evaluators</Card.Title>
            </Card.Header>
            <Card.Content>
              {evaluators.length === 0 ? (
                <div className="text-center py-8">
                  <AlertCircle className="w-12 h-12 text-yellow-500 mx-auto mb-4" />
                  <h3 className="text-lg font-medium text-neutral-900 mb-2">No Evaluators Available</h3>
                  <p className="text-neutral-600 mb-4">
                    Unable to load compliance evaluators. You can still run tests using default settings.
                  </p>
                  <Button onClick={handleRetry} variant="outline" size="sm">
                    Retry Loading Evaluators
                  </Button>
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {evaluators.map((evaluator) => (
                  <div
                    key={evaluator.id}
                    className={`p-4 border rounded-lg cursor-pointer transition-colors ${
                      testConfig.evaluators.includes(evaluator.id)
                        ? 'border-brand-500 bg-brand-50'
                        : 'border-neutral-200 hover:border-neutral-300'
                    }`}
                    onClick={() => handleEvaluatorToggle(evaluator.id)}
                  >
                    <div className="flex items-center justify-between">
                      <div>
                        <h4 className="font-medium text-neutral-900">{evaluator.name}</h4>
                        <p className="text-sm text-neutral-600">{evaluator.description}</p>
                      </div>
                      <input
                        type="checkbox"
                        checked={testConfig.evaluators.includes(evaluator.id)}
                        onChange={() => handleEvaluatorToggle(evaluator.id)}
                        className="w-4 h-4 text-brand-600 focus:ring-brand-500 border-neutral-300 rounded"
                      />
                    </div>
                  </div>
                  ))}
                </div>
              )}
            </Card.Content>
          </Card>

          {/* Evaluator Model Selection */}
          <Card>
            <Card.Header>
              <Card.Title>Evaluator AI Model</Card.Title>
              <p className="text-sm text-neutral-600 mt-1">
                Select the AI model that will power the evaluators to run compliance tests
              </p>
            </Card.Header>
            <Card.Content>
              {modelConfigs.length === 0 ? (
                <div className="text-center py-6">
                  <Settings className="w-10 h-10 text-neutral-400 mx-auto mb-3" />
                  <h4 className="font-medium text-neutral-900 mb-2">No AI Models Configured</h4>
                  <p className="text-neutral-600 mb-4">
                    You need to configure AI models first to power the evaluators.
                  </p>
                  <Button
                    onClick={() => navigate('/compliance/models')}
                    variant="outline"
                    size="sm"
                  >
                    Configure AI Models
                  </Button>
                </div>
              ) : (
                <div>
                  <label className="block text-sm font-medium text-neutral-700 mb-3">
                    Select Model for Evaluator <span className="text-red-500">*</span>
                  </label>
                  <select
                    value={testConfig.evaluator_model_id?.toString() || testConfig.evaluatorModelId?.toString() || ''}
                    onChange={handleEvaluatorModelSelection}
                    className="input w-full"
                    required
                  >
                    <option value="">Select an AI model...</option>
                    {modelConfigs.map((model) => (
                      <option key={model.id || model.config_id} value={model.id || model.config_id}>
                        {model.name} ({model.provider} - {model.model_id})
                      </option>
                    ))}
                  </select>
                  <p className="text-xs text-neutral-500 mt-2">
                    This AI model will be used by the evaluators to analyze and score your AI system's responses.
                  </p>
                  {/* Debug info - remove after fixing */}
                  <div className="text-xs text-blue-600 mt-1 font-mono">
                    Debug: evaluator_model_id = {JSON.stringify(testConfig.evaluator_model_id)} | 
                    Legacy evaluatorModelId = {JSON.stringify(testConfig.evaluatorModelId)}
                  </div>
                </div>
              )}
            </Card.Content>
          </Card>

          {/* Test Subject Model Selection */}
          <Card>
            <Card.Header>
              <Card.Title>Test Subject Model</Card.Title>
              <p className="text-sm text-neutral-600 mt-1">
                Select which AI model to test. By default, uses the system's configured model.
              </p>
            </Card.Header>
            <Card.Content>
              <div>
                <label className="block text-sm font-medium text-neutral-700 mb-3">
                  AI Model to Test
                </label>
                <select
                  value={testConfig.test_subject_model_id?.toString() || ''}
                  onChange={handleTestSubjectModelSelection}
                  className="input w-full"
                >
                  <option value="">Use System Default Model</option>
                  {modelConfigs.map((model) => (
                    <option key={model.id || model.config_id} value={model.id || model.config_id}>
                      {model.name} ({model.provider} - {model.model_id})
                    </option>
                  ))}
                </select>
                <p className="text-xs text-neutral-500 mt-2">
                  This is the AI model that will receive the test prompts. 
                  {location.state?.selectedModelId && (
                    <span className="text-brand-600 font-medium"> Model pre-selected for testing.</span>
                  )}
                  {!testConfig.test_subject_model_id && (
                    <span> If no model is selected, it will use {system?.name}'s configured default model.</span>
                  )}
                </p>
                {/* Debug info */}
                <div className="text-xs text-blue-600 mt-1 font-mono">
                  Debug: test_subject_model_id = {JSON.stringify(testConfig.test_subject_model_id)} | 
                  System default = {JSON.stringify(system?.model_config_id)}
                </div>
              </div>
            </Card.Content>
          </Card>

          {/* Test Parameters */}
          <Card>
            <Card.Header>
              <Card.Title>Test Parameters</Card.Title>
            </Card.Header>
            <Card.Content className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-neutral-700 mb-2">
                  Test Prompts
                </label>
                <textarea
                  value={testConfig.test_prompts || testConfig.testPrompts}
                  onChange={(e) => setTestConfig(prev => ({ 
                    ...prev, 
                    test_prompts: e.target.value,
                    testPrompts: e.target.value  // Legacy field
                  }))}
                  placeholder="Enter test prompts to send to the AI system..."
                  rows={6}
                  className="input"
                />
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <Input
                  label="Max Tokens"
                  type="number"
                  value={testConfig.test_subject_params?.max_tokens || testConfig.maxTokens}
                  onChange={(e) => {
                    const value = parseInt(e.target.value);
                    setTestConfig(prev => ({ 
                      ...prev, 
                      maxTokens: value,  // Legacy field
                      test_subject_params: {
                        ...prev.test_subject_params,
                        max_tokens: value
                      }
                    }));
                  }}
                  min="1"
                  max="4000"
                />
                <Input
                  label="Temperature"
                  type="number"
                  value={testConfig.test_subject_params?.temperature || testConfig.temperature}
                  onChange={(e) => {
                    const value = parseFloat(e.target.value);
                    setTestConfig(prev => ({ 
                      ...prev, 
                      temperature: value,  // Legacy field
                      test_subject_params: {
                        ...prev.test_subject_params,
                        temperature: value
                      }
                    }));
                  }}
                  min="0"
                  max="2"
                  step="0.1"
                />
                <Input
                  label="Iterations"
                  type="number"
                  value={testConfig.iterations}
                  onChange={(e) => setTestConfig(prev => ({ ...prev, iterations: parseInt(e.target.value) }))}
                  min="1"
                  max="10"
                />
              </div>
            </Card.Content>
          </Card>
        </div>

        {/* System Info & Actions */}
        <div className="space-y-6">
          <Card>
            <Card.Header>
              <Card.Title>System Information</Card.Title>
            </Card.Header>
            <Card.Content className="space-y-3">
              <div>
                <span className="text-sm font-medium text-neutral-600">Name:</span>
                <p className="text-sm text-neutral-900">{system?.name}</p>
              </div>
              <div>
                <span className="text-sm font-medium text-neutral-600">Model Type:</span>
                <p className="text-sm text-neutral-900">{system?.model_type}</p>
              </div>
              <div>
                <span className="text-sm font-medium text-neutral-600">Status:</span>
                <span className={`text-sm px-2 py-1 rounded-full ${
                  system?.status === 'active' ? 'bg-green-100 text-green-800' : 'bg-neutral-100 text-neutral-800'
                }`}>
                  {system?.status}
                </span>
              </div>
              <div>
                <span className="text-sm font-medium text-neutral-600">Last Tested:</span>
                <p className="text-sm text-neutral-900">
                  {system?.last_tested ? new Date(system.last_tested).toLocaleDateString() : 'Never'}
                </p>
              </div>
            </Card.Content>
          </Card>

          <Card>
            <Card.Header>
              <Card.Title>Test Summary</Card.Title>
            </Card.Header>
            <Card.Content className="space-y-3">
              <div className="flex justify-between">
                <span className="text-sm text-neutral-600">Selected Evaluators:</span>
                <span className="text-sm font-medium">{testConfig.evaluators.length}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-sm text-neutral-600">Test Iterations:</span>
                <span className="text-sm font-medium">{testConfig.iterations}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-sm text-neutral-600">Estimated Duration:</span>
                <span className="text-sm font-medium">
                  {Math.ceil(testConfig.evaluators.length * testConfig.iterations * 0.5)} min
                </span>
              </div>
            </Card.Content>
          </Card>

          <div className="space-y-3">
            <Button
              onClick={handleRunTest}
              disabled={
                testConfig.evaluators.length === 0 || 
                testRunning ||
                !(testConfig.evaluator_model_id || testConfig.evaluatorModelId) ||
                !(testConfig.test_prompts || testConfig.testPrompts)
              }
              className="w-full"
            >
              {testRunning ? (
                <>
                  <LoadingSpinner size="sm" className="mr-2" />
                  Running Test...
                </>
              ) : (
                <>
                  <Play className="w-4 h-4 mr-2" />
                  Run Compliance Test
                </>
              )}
            </Button>
            <Button variant="outline" className="w-full">
              <Settings className="w-4 h-4 mr-2" />
              Advanced Settings
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default TestConfigPage;