import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import Card from '../ui/Card';
import Button from '../ui/Button';
import { Key, Brain, Shield, TestTube, CheckCircle, Circle, AlertCircle, ArrowRight } from 'lucide-react';
import { apiKeysService, systemsService, modelsService, testingService } from '../../services/apiService';
import logger from '../../utils/logger.js';

const SetupProgressTracker = ({ onQuickSetup }) => {
  logger.info('SetupProgressTracker component rendered', 'SetupProgressTracker.jsx', 'SetupProgressTracker');

  const [setupStatus, setSetupStatus] = useState({
    apiKeys: { status: 'loading', count: 0 },
    modelConfigs: { status: 'loading', count: 0 },
    aiSystems: { status: 'loading', count: 0 },
    evaluators: { status: 'loading', count: 0 },
    tests: { status: 'loading', count: 0 }
  });

  useEffect(() => {
    checkSetupStatus();
  }, []);

  const checkSetupStatus = async () => {
    try {
      // Check API Keys
      try {
        const apiKeys = await apiKeysService.getApiKeys();
        const activeKeys = apiKeys.filter(key => key.status !== 'revoked');
        setSetupStatus(prev => ({
          ...prev,
          apiKeys: {
            status: activeKeys.length > 0 ? 'complete' : 'incomplete',
            count: activeKeys.length
          }
        }));
      } catch (error) {
        logger.error(`Failed to check API keys: ${error.message}`, 'SetupProgressTracker.jsx', 'checkSetupStatus');
        setSetupStatus(prev => ({
          ...prev,
          apiKeys: { status: 'incomplete', count: 0 }
        }));
      }

      // Check Model Configurations
      try {
        const models = await modelsService.getModels();
        const enabledModels = models.filter(m => m.enabled);
        setSetupStatus(prev => ({
          ...prev,
          modelConfigs: {
            status: enabledModels.length > 0 ? 'complete' : 'incomplete',
            count: enabledModels.length
          }
        }));
      } catch (error) {
        logger.error(`Failed to check model configs: ${error.message}`, 'SetupProgressTracker.jsx', 'checkSetupStatus');
        setSetupStatus(prev => ({
          ...prev,
          modelConfigs: { status: 'incomplete', count: 0 }
        }));
      }

      // Check AI Systems
      try {
        const systems = await systemsService.getSystems();
        setSetupStatus(prev => ({
          ...prev,
          aiSystems: {
            status: systems.length > 0 ? 'complete' : 'incomplete',
            count: systems.length
          }
        }));
      } catch (error) {
        logger.error(`Failed to check AI systems: ${error.message}`, 'SetupProgressTracker.jsx', 'checkSetupStatus');
        setSetupStatus(prev => ({
          ...prev,
          aiSystems: { status: 'incomplete', count: 0 }
        }));
      }

      // Check Evaluators
      try {
        const evaluators = await testingService.getEvaluators();
        setSetupStatus(prev => ({
          ...prev,
          evaluators: {
            status: evaluators.length > 0 ? 'complete' : 'incomplete',
            count: evaluators.length
          }
        }));
      } catch (error) {
        logger.error(`Failed to check evaluators: ${error.message}`, 'SetupProgressTracker.jsx', 'checkSetupStatus');
        setSetupStatus(prev => ({
          ...prev,
          evaluators: { status: 'incomplete', count: 0 }
        }));
      }

      // Check Tests (simplified - just check if systems exist)
      try {
        const systems = await systemsService.getSystems();
        const systemsWithTests = systems.filter(s => s.last_tested);
        setSetupStatus(prev => ({
          ...prev,
          tests: {
            status: systemsWithTests.length > 0 ? 'complete' : 'incomplete',
            count: systemsWithTests.length
          }
        }));
      } catch (error) {
        logger.error(`Failed to check tests: ${error.message}`, 'SetupProgressTracker.jsx', 'checkSetupStatus');
        setSetupStatus(prev => ({
          ...prev,
          tests: { status: 'incomplete', count: 0 }
        }));
      }
    } catch (error) {
      logger.error(`Failed to check setup status: ${error.message}`, 'SetupProgressTracker.jsx', 'checkSetupStatus');
    }
  };

  const getStatusIcon = (status) => {
    if (status === 'loading') {
      return <div className="w-5 h-5 animate-spin border-2 border-neutral-300 border-t-brand-500 rounded-full" />;
    }
    if (status === 'complete') {
      return <CheckCircle className="w-5 h-5 text-green-500" />;
    }
    if (status === 'incomplete') {
      return <Circle className="w-5 h-5 text-neutral-300" />;
    }
    return <AlertCircle className="w-5 h-5 text-yellow-500" />;
  };

  const getStatusText = (status, count) => {
    if (status === 'loading') return 'Checking...';
    if (status === 'complete') return `${count} configured`;
    if (status === 'incomplete') return 'Not configured';
    return 'Unknown';
  };

  const setupSteps = [
    {
      id: 'apiKeys',
      title: 'API Keys',
      description: 'Add API keys for AI providers',
      icon: Key,
      href: '/compliance/api-keys',
      actionText: 'Add Keys'
    },
    {
      id: 'modelConfigs',
      title: 'Model Configurations',
      description: 'Configure AI models for testing',
      icon: Brain,
      href: '/compliance/models',
      actionText: 'Add Models'
    },
    {
      id: 'aiSystems',
      title: 'AI Systems',
      description: 'Define the systems you want to test',
      icon: Shield,
      href: '/compliance/systems',
      actionText: 'Add System'
    },
    {
      id: 'evaluators',
      title: 'Evaluators',
      description: 'Select compliance evaluators',
      icon: TestTube,
      href: '/compliance/systems',
      actionText: 'Configure'
    },
    {
      id: 'tests',
      title: 'Run Tests',
      description: 'Execute compliance tests',
      icon: TestTube,
      href: '/compliance/systems',
      actionText: 'Run Test'
    }
  ];

  const overallProgress = Object.values(setupStatus).filter(s => s.status === 'complete').length;
  const totalSteps = Object.keys(setupStatus).length;
  const progressPercentage = (overallProgress / totalSteps) * 100;

  return (
    <Card>
      <Card.Header>
        <Card.Title>Setup Progress</Card.Title>
        <Card.Description>
          Track your compliance testing setup progress
        </Card.Description>
      </Card.Header>
      <Card.Content>
        {/* Overall Progress Bar */}
        <div className="mb-6">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-medium text-neutral-700">
              Overall Progress
            </span>
            <span className="text-sm text-neutral-600">
              {overallProgress} of {totalSteps} steps complete
            </span>
          </div>
          <div className="w-full bg-neutral-200 rounded-full h-2">
            <div
              className="bg-brand-500 h-2 rounded-full transition-all duration-500"
              style={{ width: `${progressPercentage}%` }}
            />
          </div>
        </div>

        {/* Setup Steps */}
        <div className="space-y-3">
          {setupSteps.map((step) => {
            const status = setupStatus[step.id];
            const isComplete = status.status === 'complete';
            const isIncomplete = status.status === 'incomplete';

            return (
              <div
                key={step.id}
                className={`flex items-center justify-between p-3 rounded-lg border transition-colors ${
                  isComplete
                    ? 'bg-green-50 border-green-200'
                    : isIncomplete
                    ? 'bg-neutral-50 border-neutral-200'
                    : 'bg-neutral-50 border-neutral-200'
                }`}
              >
                <div className="flex items-center flex-1">
                  {getStatusIcon(status.status)}
                  <div className="ml-3 flex-1">
                    <div className="flex items-center justify-between">
                      <h4 className="text-sm font-medium text-neutral-900">
                        {step.title}
                      </h4>
                      <span className="text-xs text-neutral-600">
                        {getStatusText(status.status, status.count)}
                      </span>
                    </div>
                    <p className="text-xs text-neutral-600">
                      {step.description}
                    </p>
                  </div>
                </div>
                <div className="ml-4">
                  {isIncomplete ? (
                    <Link to={step.href}>
                      <Button variant="outline" size="sm">
                        {step.actionText}
                        <ArrowRight className="w-3 h-3 ml-1" />
                      </Button>
                    </Link>
                  ) : (
                    <Link to={step.href}>
                      <Button variant="ghost" size="sm" className="text-neutral-600">
                        Manage
                      </Button>
                    </Link>
                  )}
                </div>
              </div>
            );
          })}
        </div>

        {/* Quick Setup CTA */}
        {progressPercentage < 100 && (
          <div className="mt-6 pt-6 border-t border-neutral-200">
            <div className="flex items-center justify-between">
              <div>
                <h4 className="text-sm font-medium text-neutral-900">
                  Need help getting started?
                </h4>
                <p className="text-xs text-neutral-600">
                  Use our guided setup wizard to configure everything step by step
                </p>
              </div>
              <Button variant="primary" size="sm" onClick={onQuickSetup}>
                Start Quick Setup
              </Button>
            </div>
          </div>
        )}
      </Card.Content>
    </Card>
  );
};

export default SetupProgressTracker;
