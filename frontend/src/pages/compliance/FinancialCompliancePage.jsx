import React, { useState } from 'react';
import { 
  DollarSign, 
  Shield, 
  FileText, 
  CheckCircle, 
  AlertTriangle, 
  Clock,
  Download,
  Play,
  Settings,
  TrendingUp,
  Eye,
  Calendar
} from 'lucide-react';
import Card from '../../components/ui/Card';
import Button from '../../components/ui/Button';

const ComplianceModule = ({ title, description, status, progress, items, regulations, onStart, onView }) => {
  const getStatusColor = (status) => {
    switch (status) {
      case 'compliant':
        return 'text-green-600 bg-green-100';
      case 'at-risk':
        return 'text-yellow-600 bg-yellow-100';
      case 'non-compliant':
        return 'text-red-600 bg-red-100';
      case 'pending':
        return 'text-neutral-600 bg-neutral-100';
      default:
        return 'text-neutral-600 bg-neutral-100';
    }
  };

  const getStatusIcon = (status) => {
    switch (status) {
      case 'compliant':
        return <CheckCircle className="w-4 h-4" />;
      case 'at-risk':
        return <AlertTriangle className="w-4 h-4" />;
      case 'non-compliant':
        return <AlertTriangle className="w-4 h-4" />;
      case 'pending':
        return <Clock className="w-4 h-4" />;
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

      {/* Compliance Score */}
      <div className="mb-4">
        <div className="flex items-center justify-between text-sm mb-1">
          <span className="text-neutral-600">Compliance Score</span>
          <span className="font-medium">{progress}%</span>
        </div>
        <div className="w-full bg-neutral-200 rounded-full h-2">
          <div 
            className={`h-2 rounded-full transition-all duration-300 ${
              progress >= 90 ? 'bg-green-600' : 
              progress >= 70 ? 'bg-yellow-600' : 
              progress >= 50 ? 'bg-orange-600' : 'bg-red-600'
            }`}
            style={{ width: `${progress}%` }}
          ></div>
        </div>
      </div>

      {/* Regulations */}
      <div className="mb-4">
        <div className="text-xs text-neutral-600 mb-2">Key Regulations:</div>
        <div className="flex flex-wrap gap-1">
          {regulations.map((reg, index) => (
            <span
              key={index}
              className="px-2 py-1 bg-neutral-100 text-neutral-600 text-xs rounded"
            >
              {reg}
            </span>
          ))}
        </div>
      </div>

      {/* Key Items */}
      <div className="space-y-2 mb-4">
        {items.slice(0, 3).map((item, index) => (
          <div key={index} className="flex items-center space-x-2 text-sm">
            {item.compliant ? (
              <CheckCircle className="w-4 h-4 text-green-500" />
            ) : (
              <AlertTriangle className="w-4 h-4 text-red-500" />
            )}
            <span className={item.compliant ? 'text-neutral-900' : 'text-red-700'}>
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
          <Eye className="w-4 h-4 mr-1" />
          View Details
        </Button>
        <Button
          size="sm"
          onClick={() => onStart(title)}
          disabled={status === 'compliant'}
        >
          <Play className="w-4 h-4 mr-1" />
          {status === 'compliant' ? 'Review' : 'Remediate'}
        </Button>
      </div>
    </Card>
  );
};

const AuditTrailItem = ({ timestamp, user, action, details, risk }) => {
  const getRiskColor = (risk) => {
    switch (risk) {
      case 'high':
        return 'text-red-600 bg-red-100';
      case 'medium':
        return 'text-yellow-600 bg-yellow-100';
      case 'low':
        return 'text-green-600 bg-green-100';
      default:
        return 'text-neutral-600 bg-neutral-100';
    }
  };

  return (
    <div className="flex items-start space-x-3 p-3 border border-neutral-200 rounded-lg">
      <div className="flex-shrink-0">
        <div className={`w-2 h-2 rounded-full mt-2 ${
          risk === 'high' ? 'bg-red-500' :
          risk === 'medium' ? 'bg-yellow-500' :
          'bg-green-500'
        }`}></div>
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center justify-between">
          <p className="text-sm font-medium text-neutral-900">{action}</p>
          <span className={`px-2 py-1 rounded-full text-xs font-medium ${getRiskColor(risk)}`}>
            {risk} risk
          </span>
        </div>
        <p className="text-sm text-neutral-600 mt-1">{details}</p>
        <div className="flex items-center space-x-4 mt-2 text-xs text-neutral-500">
          <span>{user}</span>
          <span>{new Date(timestamp).toLocaleString()}</span>
        </div>
      </div>
    </div>
  );
};

const FinancialCompliancePage = () => {
  const [modules] = useState([
    {
      title: 'Fair Lending Compliance',
      description: 'ECOA, HMDA, and CRA compliance monitoring for AI-driven lending decisions',
      status: 'at-risk',
      progress: 78,
      regulations: ['ECOA', 'HMDA', 'CRA', 'UDAAP'],
      items: [
        { name: 'Disparate Impact Testing', compliant: true },
        { name: 'HMDA Data Reporting', compliant: true },
        { name: 'CRA Assessment Areas', compliant: false },
        { name: 'Fair Lending Monitoring', compliant: true },
        { name: 'Adverse Action Notices', compliant: false }
      ]
    },
    {
      title: 'Model Risk Management',
      description: 'SR 11-7 compliance for model development, validation, and governance',
      status: 'compliant',
      progress: 92,
      regulations: ['SR 11-7', 'OCC 2011-12', 'CCAR'],
      items: [
        { name: 'Model Development Standards', compliant: true },
        { name: 'Independent Model Validation', compliant: true },
        { name: 'Model Governance Framework', compliant: true },
        { name: 'Model Risk Assessment', compliant: true },
        { name: 'Model Performance Monitoring', compliant: true }
      ]
    },
    {
      title: 'Regulatory Reporting',
      description: 'Automated regulatory reports and compliance calendar management',
      status: 'compliant',
      progress: 95,
      regulations: ['Call Reports', 'FFIEC', 'CCAR', 'DFAST'],
      items: [
        { name: 'Call Report Automation', compliant: true },
        { name: 'CCAR Stress Testing', compliant: true },
        { name: 'DFAST Submissions', compliant: true },
        { name: 'Regulatory Calendar', compliant: true },
        { name: 'Data Quality Controls', compliant: true }
      ]
    },
    {
      title: 'Anti-Money Laundering',
      description: 'AML/BSA compliance monitoring and suspicious activity detection',
      status: 'non-compliant',
      progress: 45,
      regulations: ['BSA', 'USA PATRIOT Act', 'FinCEN'],
      items: [
        { name: 'Customer Due Diligence', compliant: false },
        { name: 'Suspicious Activity Monitoring', compliant: true },
        { name: 'Currency Transaction Reporting', compliant: false },
        { name: 'OFAC Screening', compliant: true },
        { name: 'AML Training Program', compliant: false }
      ]
    }
  ]);

  const [auditTrail] = useState([
    {
      timestamp: '2024-01-16T10:30:00Z',
      user: 'Sarah Johnson',
      action: 'Model Validation Override',
      details: 'Overrode credit scoring model validation for high-value customer segment',
      risk: 'high'
    },
    {
      timestamp: '2024-01-16T09:15:00Z',
      user: 'Michael Chen',
      action: 'Fair Lending Test Failed',
      details: 'Disparate impact detected in mortgage approval model for protected class',
      risk: 'high'
    },
    {
      timestamp: '2024-01-16T08:45:00Z',
      user: 'System',
      action: 'Automated Report Generated',
      details: 'HMDA LAR report generated and submitted to regulatory portal',
      risk: 'low'
    },
    {
      timestamp: '2024-01-15T16:20:00Z',
      user: 'David Rodriguez',
      action: 'Model Performance Alert',
      details: 'Credit risk model showing degraded performance metrics',
      risk: 'medium'
    }
  ]);

  const [overallStats] = useState({
    totalModules: 4,
    compliantModules: 2,
    atRiskModules: 1,
    nonCompliantModules: 1,
    overallScore: 78
  });

  const handleStartModule = (moduleTitle) => {
    console.log('Starting remediation for:', moduleTitle);
  };

  const handleViewModule = (moduleTitle) => {
    console.log('Viewing module:', moduleTitle);
  };

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="page-header flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <div className="p-2 bg-green-100 rounded-lg">
            <DollarSign className="w-6 h-6 text-green-600" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-neutral-900">Financial Compliance</h1>
            <p className="text-neutral-600">
              Comprehensive financial services compliance monitoring and management
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

      {/* Overall Compliance Dashboard */}
      <Card>
        <Card.Header>
          <Card.Title>Overall Financial Compliance Status</Card.Title>
        </Card.Header>
        <Card.Content>
          <div className="grid grid-cols-1 md:grid-cols-5 gap-6">
            <div className="text-center">
              <div className="text-3xl font-bold text-neutral-900 mb-1">
                {overallStats.overallScore}%
              </div>
              <div className="text-sm text-neutral-600">Overall Score</div>
              <div className="w-full bg-neutral-200 rounded-full h-2 mt-2">
                <div 
                  className={`h-2 rounded-full transition-all duration-300 ${
                    overallStats.overallScore >= 90 ? 'bg-green-600' :
                    overallStats.overallScore >= 70 ? 'bg-yellow-600' :
                    'bg-red-600'
                  }`}
                  style={{ width: `${overallStats.overallScore}%` }}
                ></div>
              </div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-green-600 mb-1">
                {overallStats.compliantModules}
              </div>
              <div className="text-sm text-neutral-600">Compliant</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-yellow-600 mb-1">
                {overallStats.atRiskModules}
              </div>
              <div className="text-sm text-neutral-600">At Risk</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-red-600 mb-1">
                {overallStats.nonCompliantModules}
              </div>
              <div className="text-sm text-neutral-600">Non-Compliant</div>
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
            regulations={module.regulations}
            onStart={handleStartModule}
            onView={handleViewModule}
          />
        ))}
      </div>

      {/* Regulatory Calendar */}
      <Card>
        <Card.Header>
          <div className="flex items-center justify-between">
            <Card.Title>Upcoming Regulatory Deadlines</Card.Title>
            <Button variant="outline" size="sm">
              <Calendar className="w-4 h-4 mr-2" />
              View Full Calendar
            </Button>
          </div>
        </Card.Header>
        <Card.Content>
          <div className="space-y-3">
            {[
              { deadline: '2024-01-31', report: 'Call Report (FFIEC 031)', status: 'pending', priority: 'high' },
              { deadline: '2024-02-15', report: 'HMDA LAR Submission', status: 'in-progress', priority: 'high' },
              { deadline: '2024-02-28', report: 'CRA Assessment Update', status: 'pending', priority: 'medium' },
              { deadline: '2024-03-15', report: 'CCAR Stress Test Results', status: 'pending', priority: 'high' },
              { deadline: '2024-03-31', report: 'BSA/AML Annual Review', status: 'pending', priority: 'medium' }
            ].map((item, index) => (
              <div key={index} className="flex items-center justify-between p-3 border border-neutral-200 rounded-lg">
                <div className="flex items-center space-x-3">
                  <div className={`w-3 h-3 rounded-full ${
                    item.priority === 'high' ? 'bg-red-500' :
                    item.priority === 'medium' ? 'bg-yellow-500' :
                    'bg-green-500'
                  }`}></div>
                  <div>
                    <h4 className="font-medium text-neutral-900">{item.report}</h4>
                    <p className="text-sm text-neutral-600">Due: {item.deadline}</p>
                  </div>
                </div>
                <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                  item.status === 'pending' ? 'bg-neutral-100 text-neutral-800' :
                  item.status === 'in-progress' ? 'bg-yellow-100 text-yellow-800' :
                  'bg-green-100 text-green-800'
                }`}>
                  {item.status.replace('-', ' ')}
                </span>
              </div>
            ))}
          </div>
        </Card.Content>
      </Card>

      {/* Audit Trail */}
      <Card>
        <Card.Header>
          <div className="flex items-center justify-between">
            <Card.Title>Recent Audit Trail Activity</Card.Title>
            <Button variant="outline" size="sm">
              <TrendingUp className="w-4 h-4 mr-2" />
              View Full Trail
            </Button>
          </div>
        </Card.Header>
        <Card.Content>
          <div className="space-y-3">
            {auditTrail.map((item, index) => (
              <AuditTrailItem
                key={index}
                timestamp={item.timestamp}
                user={item.user}
                action={item.action}
                details={item.details}
                risk={item.risk}
              />
            ))}
          </div>
        </Card.Content>
      </Card>
    </div>
  );
};

export default FinancialCompliancePage;