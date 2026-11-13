import { useState } from 'react';
import { 
  Heart, 
  FileText, 
  CheckCircle, 
  AlertTriangle, 
  Clock,
  Download,
  Play,
  Settings
} from 'lucide-react';
import Card from '../../components/ui/Card';
import Button from '../../components/ui/Button';

const ComplianceModule = ({ title, description, status, progress, items, onStart, onView }) => {
  const getStatusColor = (status) => {
    switch (status) {
      case 'completed':
        return 'text-green-600 bg-green-100';
      case 'in-progress':
        return 'text-yellow-600 bg-yellow-100';
      case 'pending':
        return 'text-neutral-600 bg-neutral-100';
      default:
        return 'text-neutral-600 bg-neutral-100';
    }
  };

  const getStatusIcon = (status) => {
    switch (status) {
      case 'completed':
        return <CheckCircle className="w-4 h-4" />;
      case 'in-progress':
        return <Clock className="w-4 h-4" />;
      case 'pending':
        return <AlertTriangle className="w-4 h-4" />;
      default:
        return <Clock className="w-4 h-4" />;
    }
  };

  return (
    <Card className="hover:shadow-md transition-shadow">
      <div className="flex items-start justify-between mb-4">
        <div className="flex-1">
          <div className="flex items-center space-x-2 mb-2">
            <h3 className="text-lg font-semibold text-neutral-900">{title}</h3>
            <span className={`px-2 py-1 rounded-full text-xs font-medium flex items-center space-x-1 ${getStatusColor(status)}`}>
              {getStatusIcon(status)}
              <span className="ml-1">{status.replace('-', ' ')}</span>
            </span>
          </div>
          <p className="text-neutral-600 text-sm mb-3">{description}</p>
        </div>
      </div>

      {/* Progress Bar */}
      <div className="mb-4">
        <div className="flex items-center justify-between text-sm mb-1">
          <span className="text-neutral-600">Progress</span>
          <span className="font-medium">{progress}%</span>
        </div>
        <div className="w-full bg-neutral-200 rounded-full h-2">
          <div 
            className={`h-2 rounded-full transition-all duration-300 ${
              progress === 100 ? 'bg-green-600' : 
              progress > 0 ? 'bg-blue-600' : 'bg-neutral-300'
            }`}
            style={{ width: `${progress}%` }}
          ></div>
        </div>
      </div>

      {/* Checklist Items */}
      <div className="space-y-2 mb-4">
        {items.slice(0, 3).map((item, index) => (
          <div key={index} className="flex items-center space-x-2 text-sm">
            {item.completed ? (
              <CheckCircle className="w-4 h-4 text-green-500" />
            ) : (
              <div className="w-4 h-4 border-2 border-neutral-300 rounded"></div>
            )}
            <span className={item.completed ? 'text-neutral-900' : 'text-neutral-600'}>
              {item.name}
            </span>
          </div>
        ))}
        {items.length > 3 && (
          <div className="text-xs text-neutral-500 ml-6">
            +{items.length - 3} more items
          </div>
        )}
      </div>

      {/* Actions */}
      <div className="flex items-center space-x-2">
        <Button
          variant="outline"
          size="sm"
          onClick={() => onView(title)}
        >
          <FileText className="w-4 h-4 mr-1" />
          View Details
        </Button>
        <Button
          size="sm"
          onClick={() => onStart(title)}
          disabled={status === 'completed'}
        >
          <Play className="w-4 h-4 mr-1" />
          {status === 'completed' ? 'Completed' : status === 'in-progress' ? 'Continue' : 'Start'}
        </Button>
      </div>
    </Card>
  );
};

const HealthcareCompliancePage = () => {
  const [modules] = useState([
    {
      title: 'FDA Validation',
      description: 'Comprehensive FDA validation for medical AI systems including 510(k), PMA, De Novo, and SaMD pathways',
      status: 'in-progress',
      progress: 65,
      items: [
        { name: 'Predicate Device Analysis', completed: true },
        { name: 'Clinical Validation Study', completed: true },
        { name: 'Risk Classification Assessment', completed: false },
        { name: 'Quality Management System', completed: false },
        { name: 'Regulatory Submission Preparation', completed: false }
      ]
    },
    {
      title: 'HIPAA Compliance',
      description: 'Complete HIPAA compliance assessment covering Administrative, Physical, and Technical safeguards',
      status: 'completed',
      progress: 100,
      items: [
        { name: 'Administrative Safeguards', completed: true },
        { name: 'Physical Safeguards', completed: true },
        { name: 'Technical Safeguards', completed: true },
        { name: 'Business Associate Agreements', completed: true },
        { name: 'Breach Notification Procedures', completed: true }
      ]
    },
    {
      title: 'Clinical Validation',
      description: 'Clinical study design, endpoints definition, and regulatory submissions for medical AI',
      status: 'pending',
      progress: 0,
      items: [
        { name: 'Study Protocol Development', completed: false },
        { name: 'Primary Endpoint Definition', completed: false },
        { name: 'Statistical Analysis Plan', completed: false },
        { name: 'IRB/Ethics Committee Approval', completed: false },
        { name: 'Clinical Data Collection', completed: false }
      ]
    },
    {
      title: 'Medical Device Documentation',
      description: 'IEC 62304, ISO 14971, cybersecurity, and other medical device standards compliance',
      status: 'in-progress',
      progress: 30,
      items: [
        { name: 'IEC 62304 Software Lifecycle', completed: true },
        { name: 'ISO 14971 Risk Management', completed: false },
        { name: 'Cybersecurity Documentation', completed: false },
        { name: 'Usability Engineering (IEC 62366)', completed: false },
        { name: 'Clinical Evaluation (MDR)', completed: false }
      ]
    }
  ]);

  const [overallStats] = useState({
    totalModules: 4,
    completedModules: 1,
    inProgressModules: 2,
    pendingModules: 1,
    overallProgress: 49
  });

  const handleStartModule = (moduleTitle) => {
    console.log('Starting module:', moduleTitle);
    // In a real app, this would navigate to the module workflow
  };

  const handleViewModule = (moduleTitle) => {
    console.log('Viewing module:', moduleTitle);
    // In a real app, this would show detailed module information
  };

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="page-header flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <div className="p-2 bg-blue-100 rounded-lg">
            <Heart className="w-6 h-6 text-blue-600" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-neutral-900">Healthcare Compliance</h1>
            <p className="text-neutral-600">
              Comprehensive healthcare and medical device compliance management
            </p>
          </div>
        </div>
        <div className="flex items-center space-x-3">
          <Button variant="outline">
            <Settings className="w-4 h-4 mr-2" />
            Configure
          </Button>
          <Button variant="outline">
            <Download className="w-4 h-4 mr-2" />
            Export Report
          </Button>
        </div>
      </div>

      {/* Overall Progress */}
      <Card>
        <Card.Header>
          <Card.Title>Overall Healthcare Compliance Progress</Card.Title>
        </Card.Header>
        <Card.Content>
          <div className="grid grid-cols-1 md:grid-cols-5 gap-6">
            <div className="text-center">
              <div className="text-3xl font-bold text-neutral-900 mb-1">
                {overallStats.overallProgress}%
              </div>
              <div className="text-sm text-neutral-600">Overall Progress</div>
              <div className="w-full bg-neutral-200 rounded-full h-2 mt-2">
                <div 
                  className="bg-blue-600 h-2 rounded-full transition-all duration-300"
                  style={{ width: `${overallStats.overallProgress}%` }}
                ></div>
              </div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-green-600 mb-1">
                {overallStats.completedModules}
              </div>
              <div className="text-sm text-neutral-600">Completed</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-yellow-600 mb-1">
                {overallStats.inProgressModules}
              </div>
              <div className="text-sm text-neutral-600">In Progress</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-neutral-600 mb-1">
                {overallStats.pendingModules}
              </div>
              <div className="text-sm text-neutral-600">Pending</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-blue-600 mb-1">
                {overallStats.totalModules}
              </div>
              <div className="text-sm text-neutral-600">Total Modules</div>
            </div>
          </div>
        </Card.Content>
      </Card>

      {/* Compliance Modules */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {modules.map((module, index) => (
          <ComplianceModule
            key={index}
            title={module.title}
            description={module.description}
            status={module.status}
            progress={module.progress}
            items={module.items}
            onStart={handleStartModule}
            onView={handleViewModule}
          />
        ))}
      </div>

      {/* Regulatory Timeline */}
      <Card>
        <Card.Header>
          <Card.Title>Regulatory Submission Timeline</Card.Title>
        </Card.Header>
        <Card.Content>
          <div className="space-y-4">
            {[
              { phase: 'Pre-Submission Meeting', date: '2024-02-15', status: 'completed', description: 'FDA Q-Sub meeting completed' },
              { phase: 'Clinical Protocol Finalization', date: '2024-03-01', status: 'in-progress', description: 'Finalizing clinical study protocol' },
              { phase: 'Clinical Study Initiation', date: '2024-03-15', status: 'pending', description: 'Begin patient enrollment' },
              { phase: '510(k) Submission', date: '2024-06-01', status: 'pending', description: 'Submit 510(k) application to FDA' },
              { phase: 'FDA Review Period', date: '2024-06-01', status: 'pending', description: '90-day FDA review period' },
              { phase: 'Market Authorization', date: '2024-09-01', status: 'pending', description: 'Expected FDA clearance' }
            ].map((milestone, index) => (
              <div key={index} className="flex items-center space-x-4">
                <div className={`w-3 h-3 rounded-full ${
                  milestone.status === 'completed' ? 'bg-green-500' :
                  milestone.status === 'in-progress' ? 'bg-yellow-500' :
                  'bg-neutral-300'
                }`}></div>
                <div className="flex-1">
                  <div className="flex items-center justify-between">
                    <h4 className="font-medium text-neutral-900">{milestone.phase}</h4>
                    <span className="text-sm text-neutral-500">{milestone.date}</span>
                  </div>
                  <p className="text-sm text-neutral-600">{milestone.description}</p>
                </div>
              </div>
            ))}
          </div>
        </Card.Content>
      </Card>

      {/* Key Regulatory Requirements */}
      <Card>
        <Card.Header>
          <Card.Title>Key Regulatory Requirements</Card.Title>
        </Card.Header>
        <Card.Content>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {[
              { title: 'FDA 21 CFR Part 820', description: 'Quality System Regulation', status: 'completed' },
              { title: 'ISO 13485', description: 'Medical Device QMS', status: 'in-progress' },
              { title: 'IEC 62304', description: 'Medical Device Software', status: 'completed' },
              { title: 'ISO 14971', description: 'Risk Management', status: 'in-progress' },
              { title: 'IEC 62366', description: 'Usability Engineering', status: 'pending' },
              { title: 'HIPAA', description: 'Health Information Privacy', status: 'completed' }
            ].map((req, index) => (
              <div key={index} className="p-4 border border-neutral-200 rounded-lg">
                <div className="flex items-center justify-between mb-2">
                  <h4 className="font-medium text-neutral-900">{req.title}</h4>
                  <span className={`w-3 h-3 rounded-full ${
                    req.status === 'completed' ? 'bg-green-500' :
                    req.status === 'in-progress' ? 'bg-yellow-500' :
                    'bg-neutral-300'
                  }`}></span>
                </div>
                <p className="text-sm text-neutral-600">{req.description}</p>
              </div>
            ))}
          </div>
        </Card.Content>
      </Card>
    </div>
  );
};

export default HealthcareCompliancePage;