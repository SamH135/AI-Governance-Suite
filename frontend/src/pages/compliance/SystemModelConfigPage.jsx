import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, Brain, Plus, Settings, Play, Edit, Trash2 } from 'lucide-react';
import Card from '../../components/ui/Card';
import Button from '../../components/ui/Button';
import LoadingSpinner from '../../components/ui/LoadingSpinner';
import SystemModelsManager from '../../components/compliance/SystemModelsManager';
import { systemsService, modelsService } from '../../services/apiService';

const SystemModelConfigPage = () => {
  const { systemId } = useParams();
  const navigate = useNavigate();
  
  const [system, setSystem] = useState(null);
  const [models, setModels] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchData = async () => {
      if (!systemId) {
        setError('No system ID provided');
        setLoading(false);
        return;
      }

      try {
        // Fetch system details and models in parallel
        const [systemData, modelsData] = await Promise.all([
          systemsService.getSystem(systemId),
          modelsService.getModels()
        ]);
        
        setSystem(systemData);
        setModels(modelsData);
      } catch (error) {
        console.error('Failed to fetch system data:', error);
        
        // Check if it's a 404/500 error (system not found/deleted)
        if (error.status === 404 || error.status === 500 || error.message?.includes('404') || error.message?.includes('500')) {
          // System likely deleted, redirect to systems list
          console.log('System not found, redirecting to systems list');
          navigate('/compliance/systems', { 
            replace: true,
            state: { message: 'The requested AI system was not found. It may have been deleted.' }
          });
          return;
        }
        
        setError('Failed to load system data');
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [systemId]);


  const handleTestModel = (model) => {
    // Navigate to test configuration with specific model pre-selected
    navigate(`/compliance/test/configure/${systemId}`, {
      state: { selectedModelId: model.config_id || model.id }
    });
  };

  const handleContinueToTests = () => {
    // Navigate to test configuration for this system
    navigate(`/compliance/test/configure/${systemId}`);
  };

  const handleBackToSystems = () => {
    navigate('/compliance/systems');
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <LoadingSpinner size="lg" />
          <p className="mt-4 text-neutral-600">Loading system configuration...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-64">
        <Card className="max-w-md w-full">
          <Card.Header>
            <Card.Title>Error Loading System</Card.Title>
          </Card.Header>
          <Card.Content>
            <p className="text-neutral-600 mb-4">{error}</p>
            <div className="flex space-x-3">
              <Button onClick={() => window.location.reload()} variant="primary">
                Try Again
              </Button>
              <Button onClick={handleBackToSystems} variant="outline">
                Back to Systems
              </Button>
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
        <Button variant="ghost" onClick={handleBackToSystems}>
          <ArrowLeft className="w-4 h-4" />
        </Button>
        <div className="flex-1">
          <h1 className="text-2xl font-bold text-neutral-900">Configure Models</h1>
          <p className="text-neutral-600">
            {system?.name} - Set up AI models for this system
          </p>
        </div>
        <Button onClick={handleContinueToTests} variant="primary">
          Continue to Tests
        </Button>
      </div>

      {/* System Info */}
      <Card>
        <Card.Header>
          <Card.Title>System Information</Card.Title>
        </Card.Header>
        <Card.Content>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <span className="text-sm font-medium text-neutral-600">System Name:</span>
              <p className="text-neutral-900">{system?.name}</p>
            </div>
            <div>
              <span className="text-sm font-medium text-neutral-600">System Type:</span>
              <p className="text-neutral-900">{system?.system_type || 'N/A'}</p>
            </div>
            <div>
              <span className="text-sm font-medium text-neutral-600">Industry:</span>
              <p className="text-neutral-900">{system?.industry || 'N/A'}</p>
            </div>
          </div>
          {system?.description && (
            <div className="mt-4">
              <span className="text-sm font-medium text-neutral-600">Description:</span>
              <p className="text-neutral-900">{system.description}</p>
            </div>
          )}
        </Card.Content>
      </Card>

      {/* System Models */}
      <Card>
        <Card.Header>
          <Card.Title className="flex items-center gap-2">
            <Brain className="w-5 h-5" />
            Test Subject Models
          </Card.Title>
          <p className="text-sm text-neutral-600 mt-1">
            Add and manage the specific AI models you will test for <span className="font-medium text-neutral-800">{system?.name}</span>. 
            These are the models under evaluation for compliance. You can create a new configuration or start from a pre-configured template, 
            and optionally link an existing model to this system.
          </p>
        </Card.Header>
        <Card.Content>
          <SystemModelsManager 
            systemId={systemId}
            system={system}
            availableTemplates={models}
            onTestModel={handleTestModel}
          />
        </Card.Content>
      </Card>

      {/* Next Steps */}
      <Card>
        <Card.Header>
          <Card.Title>Next Steps</Card.Title>
        </Card.Header>
        <Card.Content>
          <p className="text-neutral-600 mb-4">
            Once you've configured your AI models, you can proceed to set up compliance tests for this system.
          </p>
          <div className="flex space-x-3">
            <Button onClick={handleContinueToTests} variant="primary">
              Continue to Compliance Tests
            </Button>
            <Button onClick={handleBackToSystems} variant="outline">
              Back to Systems List
            </Button>
          </div>
        </Card.Content>
      </Card>
    </div>
  );
};

export default SystemModelConfigPage;