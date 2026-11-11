import React, { useState } from 'react';
import { ArrowRight, ArrowLeft, FileText, Download, Eye } from 'lucide-react';
import Card from '../../components/ui/Card';
import Button from '../../components/ui/Button';
import Input from '../../components/ui/Input';

const StepIndicator = ({ currentStep, totalSteps }) => {
  return (
    <div className="flex items-center justify-center mb-8">
      {Array.from({ length: totalSteps }, (_, i) => (
        <React.Fragment key={i}>
          <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium ${
            i + 1 <= currentStep 
              ? 'bg-brand-600 text-white' 
              : 'bg-neutral-200 text-neutral-600'
          }`}>
            {i + 1}
          </div>
          {i < totalSteps - 1 && (
            <div className={`w-12 h-1 mx-2 ${
              i + 1 < currentStep ? 'bg-brand-600' : 'bg-neutral-200'
            }`} />
          )}
        </React.Fragment>
      ))}
    </div>
  );
};

const ProjectInfoStep = ({ data, onChange }) => (
  <Card>
    <Card.Header>
      <Card.Title>Project Information</Card.Title>
    </Card.Header>
    <Card.Content className="space-y-4">
      <Input
        label="Organization Name"
        value={data.organizationName}
        onChange={(e) => onChange({ organizationName: e.target.value })}
        placeholder="Enter your organization name"
      />
      
      <div>
        <label className="block text-sm font-medium text-neutral-700 mb-1">
          Industry
        </label>
        <select
          value={data.industry}
          onChange={(e) => onChange({ industry: e.target.value })}
          className="input"
        >
          <option value="">Select industry</option>
          <option value="healthcare">Healthcare</option>
          <option value="finance">Finance</option>
          <option value="technology">Technology</option>
          <option value="retail">Retail</option>
          <option value="manufacturing">Manufacturing</option>
          <option value="other">Other</option>
        </select>
      </div>

      <div>
        <label className="block text-sm font-medium text-neutral-700 mb-1">
          ML/LLM System Description
        </label>
        <textarea
          value={data.systemDescription}
          onChange={(e) => onChange({ systemDescription: e.target.value })}
          placeholder="Describe your ML/LLM system, its purpose, and key features..."
          rows={4}
          className="input"
        />
      </div>

      <div>
        <label className="block text-sm font-medium text-neutral-700 mb-1">
          Operating Countries
        </label>
        <input
          type="text"
          value={data.operatingCountries}
          onChange={(e) => onChange({ operatingCountries: e.target.value })}
          placeholder="e.g., United States, Canada, European Union"
          className="input"
        />
      </div>
    </Card.Content>
  </Card>
);

const DataModelStep = ({ data, onChange }) => (
  <Card>
    <Card.Header>
      <Card.Title>Data Model Information</Card.Title>
    </Card.Header>
    <Card.Content className="space-y-4">
      <div>
        <label className="block text-sm font-medium text-neutral-700 mb-1">
          Data Types
        </label>
        <div className="space-y-2">
          {['Personal Data', 'Health Data', 'Financial Data', 'Biometric Data', 'Location Data'].map((type) => (
            <label key={type} className="flex items-center">
              <input
                type="checkbox"
                checked={data.dataTypes.includes(type)}
                onChange={(e) => {
                  const newTypes = e.target.checked
                    ? [...data.dataTypes, type]
                    : data.dataTypes.filter(t => t !== type);
                  onChange({ dataTypes: newTypes });
                }}
                className="mr-2"
              />
              {type}
            </label>
          ))}
        </div>
      </div>

      <div>
        <label className="block text-sm font-medium text-neutral-700 mb-1">
          Data Sources
        </label>
        <textarea
          value={data.dataSources}
          onChange={(e) => onChange({ dataSources: e.target.value })}
          placeholder="Describe your data sources, collection methods, and storage..."
          rows={3}
          className="input"
        />
      </div>

      <div>
        <label className="block text-sm font-medium text-neutral-700 mb-1">
          Model Architecture
        </label>
        <select
          value={data.modelArchitecture}
          onChange={(e) => onChange({ modelArchitecture: e.target.value })}
          className="input"
        >
          <option value="">Select architecture</option>
          <option value="transformer">Transformer</option>
          <option value="cnn">Convolutional Neural Network</option>
          <option value="rnn">Recurrent Neural Network</option>
          <option value="ensemble">Ensemble</option>
          <option value="other">Other</option>
        </select>
      </div>

      <Input
        label="Model Version"
        value={data.modelVersion}
        onChange={(e) => onChange({ modelVersion: e.target.value })}
        placeholder="e.g., v1.2.0"
      />
    </Card.Content>
  </Card>
);

const ComplianceInfoStep = ({ data, onChange }) => (
  <Card>
    <Card.Header>
      <Card.Title>Compliance Requirements</Card.Title>
    </Card.Header>
    <Card.Content className="space-y-4">
      <div>
        <label className="block text-sm font-medium text-neutral-700 mb-1">
          Regulatory Frameworks
        </label>
        <div className="space-y-2">
          {['GDPR', 'HIPAA', 'SOX', 'PCI DSS', 'CCPA', 'FDA', 'FTC'].map((framework) => (
            <label key={framework} className="flex items-center">
              <input
                type="checkbox"
                checked={data.frameworks.includes(framework)}
                onChange={(e) => {
                  const newFrameworks = e.target.checked
                    ? [...data.frameworks, framework]
                    : data.frameworks.filter(f => f !== framework);
                  onChange({ frameworks: newFrameworks });
                }}
                className="mr-2"
              />
              {framework}
            </label>
          ))}
        </div>
      </div>

      <div>
        <label className="block text-sm font-medium text-neutral-700 mb-1">
          Risk Assessment Level
        </label>
        <select
          value={data.riskLevel}
          onChange={(e) => onChange({ riskLevel: e.target.value })}
          className="input"
        >
          <option value="">Select risk level</option>
          <option value="low">Low Risk</option>
          <option value="medium">Medium Risk</option>
          <option value="high">High Risk</option>
          <option value="critical">Critical Risk</option>
        </select>
      </div>

      <div>
        <label className="block text-sm font-medium text-neutral-700 mb-1">
          Audit Requirements
        </label>
        <textarea
          value={data.auditRequirements}
          onChange={(e) => onChange({ auditRequirements: e.target.value })}
          placeholder="Describe any specific audit requirements or compliance standards..."
          rows={3}
          className="input"
        />
      </div>
    </Card.Content>
  </Card>
);

const GenerationStep = ({ data, onGenerate, generating, result }) => (
  <Card>
    <Card.Header>
      <Card.Title>Document Generation</Card.Title>
    </Card.Header>
    <Card.Content>
      {!result ? (
        <div className="text-center py-8">
          <FileText className="w-16 h-16 mx-auto text-neutral-400 mb-4" />
          <h3 className="text-lg font-medium text-neutral-900 mb-2">Ready to Generate</h3>
          <p className="text-neutral-600 mb-6">
            Review your information and generate comprehensive compliance documentation
          </p>
          
          <div className="bg-neutral-50 p-4 rounded-lg mb-6 text-left">
            <h4 className="font-medium text-neutral-900 mb-2">Generation Summary:</h4>
            <ul className="text-sm text-neutral-600 space-y-1">
              <li>• Organization: {data.organizationName}</li>
              <li>• Industry: {data.industry}</li>
              <li>• Frameworks: {data.frameworks.join(', ')}</li>
              <li>• Risk Level: {data.riskLevel}</li>
              <li>• Data Types: {data.dataTypes.length} selected</li>
            </ul>
          </div>

          <Button
            onClick={onGenerate}
            loading={generating}
            disabled={generating}
            size="lg"
          >
            <FileText className="w-5 h-5 mr-2" />
            Generate Documentation
          </Button>
        </div>
      ) : (
        <div className="text-center py-8">
          <div className="w-16 h-16 mx-auto bg-green-100 rounded-full flex items-center justify-center mb-4">
            <FileText className="w-8 h-8 text-green-600" />
          </div>
          <h3 className="text-lg font-medium text-neutral-900 mb-2">Documentation Generated!</h3>
          <p className="text-neutral-600 mb-6">
            Your compliance documentation has been successfully generated
          </p>
          
          <div className="flex items-center justify-center space-x-4">
            <Button variant="outline">
              <Eye className="w-4 h-4 mr-2" />
              Preview
            </Button>
            <Button>
              <Download className="w-4 h-4 mr-2" />
              Download PDF
            </Button>
          </div>
        </div>
      )}
    </Card.Content>
  </Card>
);

const DocumentGeneratorPage = () => {
  const [currentStep, setCurrentStep] = useState(1);
  const [generating, setGenerating] = useState(false);
  const [result, setResult] = useState(null);
  const [formData, setFormData] = useState({
    organizationName: '',
    industry: '',
    systemDescription: '',
    operatingCountries: '',
    dataTypes: [],
    dataSources: '',
    modelArchitecture: '',
    modelVersion: '',
    frameworks: [],
    riskLevel: '',
    auditRequirements: ''
  });

  const totalSteps = 4;

  const updateFormData = (updates) => {
    setFormData(prev => ({ ...prev, ...updates }));
  };

  const handleNext = () => {
    if (currentStep < totalSteps) {
      setCurrentStep(currentStep + 1);
    }
  };

  const handlePrevious = () => {
    if (currentStep > 1) {
      setCurrentStep(currentStep - 1);
    }
  };

  const handleGenerate = async () => {
    setGenerating(true);
    try {
      // Simulate document generation
      await new Promise(resolve => setTimeout(resolve, 3000));
      setResult({
        documentId: 'doc_123',
        pages: 45,
        sections: 12,
        generatedAt: new Date().toISOString()
      });
    } catch (error) {
      console.error('Failed to generate document:', error);
    } finally {
      setGenerating(false);
    }
  };

  const canProceed = () => {
    switch (currentStep) {
      case 1:
        return formData.organizationName && formData.industry && formData.systemDescription;
      case 2:
        return formData.dataTypes.length > 0 && formData.dataSources;
      case 3:
        return formData.frameworks.length > 0 && formData.riskLevel;
      default:
        return true;
    }
  };

  const renderStep = () => {
    switch (currentStep) {
      case 1:
        return <ProjectInfoStep data={formData} onChange={updateFormData} />;
      case 2:
        return <DataModelStep data={formData} onChange={updateFormData} />;
      case 3:
        return <ComplianceInfoStep data={formData} onChange={updateFormData} />;
      case 4:
        return (
          <GenerationStep
            data={formData}
            onGenerate={handleGenerate}
            generating={generating}
            result={result}
          />
        );
      default:
        return null;
    }
  };

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="page-header">
        <h1 className="text-2xl font-bold text-neutral-900">Document Generator</h1>
        <p className="text-neutral-600">
          Generate comprehensive compliance documentation for your AI systems
        </p>
      </div>

      {/* Step Indicator */}
      <StepIndicator currentStep={currentStep} totalSteps={totalSteps} />

      {/* Step Content */}
      <div className="max-w-2xl mx-auto">
        {renderStep()}

        {/* Navigation */}
        <div className="flex items-center justify-between mt-8">
          <Button
            variant="outline"
            onClick={handlePrevious}
            disabled={currentStep === 1}
          >
            <ArrowLeft className="w-4 h-4 mr-2" />
            Previous
          </Button>

          {currentStep < totalSteps ? (
            <Button
              onClick={handleNext}
              disabled={!canProceed()}
            >
              Next
              <ArrowRight className="w-4 h-4 ml-2" />
            </Button>
          ) : null}
        </div>
      </div>
    </div>
  );
};

export default DocumentGeneratorPage;