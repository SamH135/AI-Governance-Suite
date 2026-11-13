import { useState } from 'react';
import { 
  Plus, 
  Search, 
  Filter, 
  Download, 
  Upload, 
  Eye, 
  Edit, 
  Trash2,
  Star,
  Copy,
  Zap,
  FileText,
  Users,
  Calendar
} from 'lucide-react';
import Card from '../../components/ui/Card';
import Button from '../../components/ui/Button';
import Input from '../../components/ui/Input';

const TemplateCard = ({ template, onEdit, onDelete, onView, onEnhance }) => {
  const [showMenu, setShowMenu] = useState(false);

  const getIndustryColor = (industry) => {
    const colors = {
      'Healthcare': 'bg-blue-100 text-blue-800',
      'Finance': 'bg-green-100 text-green-800',
      'Technology': 'bg-purple-100 text-purple-800',
      'Legal': 'bg-red-100 text-red-800',
      'General': 'bg-neutral-100 text-neutral-800'
    };
    return colors[industry] || colors['General'];
  };

  return (
    <Card className="hover:shadow-md transition-shadow">
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center space-x-2">
          <FileText className="w-5 h-5 text-brand-600" />
          <h3 className="text-lg font-semibold text-neutral-900">{template.name}</h3>
          {template.featured && (
            <Star className="w-4 h-4 text-yellow-500 fill-current" />
          )}
        </div>
        <div className="relative">
          <button
            onClick={() => setShowMenu(!showMenu)}
            className="p-1 hover:bg-neutral-100 rounded"
          >
            <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
              <path d="M10 6a2 2 0 110-4 2 2 0 010 4zM10 12a2 2 0 110-4 2 2 0 010 4zM10 18a2 2 0 110-4 2 2 0 010 4z" />
            </svg>
          </button>
          {showMenu && (
            <div className="absolute right-0 mt-1 w-48 bg-white rounded-md shadow-lg border border-neutral-200 py-1 z-10">
              <button
                onClick={() => {
                  onView(template);
                  setShowMenu(false);
                }}
                className="flex items-center w-full px-4 py-2 text-sm text-neutral-700 hover:bg-neutral-100"
              >
                <Eye className="w-4 h-4 mr-2" />
                View Template
              </button>
              <button
                onClick={() => {
                  onEnhance(template);
                  setShowMenu(false);
                }}
                className="flex items-center w-full px-4 py-2 text-sm text-neutral-700 hover:bg-neutral-100"
              >
                <Zap className="w-4 h-4 mr-2" />
                AI Enhance
              </button>
              <button
                onClick={() => {
                  onEdit(template);
                  setShowMenu(false);
                }}
                className="flex items-center w-full px-4 py-2 text-sm text-neutral-700 hover:bg-neutral-100"
              >
                <Edit className="w-4 h-4 mr-2" />
                Edit
              </button>
              <button
                onClick={() => {
                  navigator.clipboard.writeText(template.content);
                  setShowMenu(false);
                }}
                className="flex items-center w-full px-4 py-2 text-sm text-neutral-700 hover:bg-neutral-100"
              >
                <Copy className="w-4 h-4 mr-2" />
                Copy Content
              </button>
              <button
                onClick={() => {
                  onDelete(template);
                  setShowMenu(false);
                }}
                className="flex items-center w-full px-4 py-2 text-sm text-red-600 hover:bg-red-50"
              >
                <Trash2 className="w-4 h-4 mr-2" />
                Delete
              </button>
            </div>
          )}
        </div>
      </div>

      <p className="text-neutral-600 text-sm mb-3">{template.description}</p>

      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center space-x-2">
          <span className={`px-2 py-1 rounded-full text-xs font-medium ${getIndustryColor(template.industry)}`}>
            {template.industry}
          </span>
          <span className="text-xs text-neutral-500">
            v{template.version}
          </span>
        </div>
        <div className="flex items-center space-x-3 text-xs text-neutral-500">
          <div className="flex items-center">
            <Users className="w-3 h-3 mr-1" />
            {template.usage}
          </div>
          <div className="flex items-center">
            <Calendar className="w-3 h-3 mr-1" />
            {new Date(template.updatedAt).toLocaleDateString()}
          </div>
        </div>
      </div>

      <div className="flex flex-wrap gap-1 mb-3">
        {template.frameworks.map((framework, index) => (
          <span
            key={index}
            className="px-2 py-1 bg-neutral-100 text-neutral-600 text-xs rounded"
          >
            {framework}
          </span>
        ))}
      </div>

      <div className="flex items-center justify-between">
        <div className="text-xs text-neutral-500">
          {template.sections} sections • {template.pages} pages
        </div>
        <div className="flex items-center space-x-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => onView(template)}
          >
            <Eye className="w-4 h-4 mr-1" />
            Preview
          </Button>
          <Button
            size="sm"
            onClick={() => onEnhance(template)}
          >
            <Zap className="w-4 h-4 mr-1" />
            Enhance
          </Button>
        </div>
      </div>
    </Card>
  );
};

const EnhanceTemplateModal = ({ isOpen, onClose, template, onEnhance }) => {
  const [enhanceOptions, setEnhanceOptions] = useState({
    improveClarity: true,
    addExamples: true,
    updateCompliance: true,
    enhanceStructure: false,
    addChecklists: true
  });
  const [enhancing, setEnhancing] = useState(false);

  const handleEnhance = async () => {
    setEnhancing(true);
    try {
      // Simulate AI enhancement
      await new Promise(resolve => setTimeout(resolve, 3000));
      onEnhance(template, enhanceOptions);
      onClose();
    } catch (error) {
      console.error('Enhancement failed:', error);
    } finally {
      setEnhancing(false);
    }
  };

  if (!isOpen || !template) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg p-6 w-full max-w-md">
        <h2 className="text-xl font-bold text-neutral-900 mb-4">
          Enhance Template: {template.name}
        </h2>
        
        <div className="space-y-4">
          <p className="text-sm text-neutral-600">
            Select the enhancements you'd like to apply using AI:
          </p>

          <div className="space-y-3">
            {Object.entries({
              improveClarity: 'Improve language clarity and readability',
              addExamples: 'Add relevant examples and use cases',
              updateCompliance: 'Update with latest compliance requirements',
              enhanceStructure: 'Improve document structure and flow',
              addChecklists: 'Add compliance checklists and validation steps'
            }).map(([key, label]) => (
              <label key={key} className="flex items-center">
                <input
                  type="checkbox"
                  checked={enhanceOptions[key]}
                  onChange={(e) => setEnhanceOptions(prev => ({
                    ...prev,
                    [key]: e.target.checked
                  }))}
                  className="mr-3"
                />
                <span className="text-sm text-neutral-700">{label}</span>
              </label>
            ))}
          </div>

          <div className="bg-blue-50 p-3 rounded-lg">
            <p className="text-xs text-blue-700">
              <strong>Note:</strong> AI enhancement will create a new version of your template. 
              The original will be preserved for comparison.
            </p>
          </div>

          <div className="flex items-center justify-end space-x-3 pt-4">
            <Button
              type="button"
              variant="outline"
              onClick={onClose}
              disabled={enhancing}
            >
              Cancel
            </Button>
            <Button 
              onClick={handleEnhance}
              loading={enhancing}
              disabled={enhancing}
            >
              <Zap className="w-4 h-4 mr-2" />
              {enhancing ? 'Enhancing...' : 'Enhance Template'}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
};

const CreateTemplateModal = ({ isOpen, onClose, onSave }) => {
  const [formData, setFormData] = useState({
    name: '',
    description: '',
    industry: 'General',
    frameworks: '',
    content: ''
  });

  const handleSubmit = (e) => {
    e.preventDefault();
    onSave({
      ...formData,
      frameworks: formData.frameworks.split(',').map(f => f.trim()).filter(Boolean),
      id: Date.now(),
      version: '1.0',
      usage: 0,
      sections: 5,
      pages: 12,
      featured: false,
      updatedAt: new Date().toISOString()
    });
    setFormData({
      name: '',
      description: '',
      industry: 'General',
      frameworks: '',
      content: ''
    });
    onClose();
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg p-6 w-full max-w-2xl max-h-[90vh] overflow-y-auto">
        <h2 className="text-xl font-bold text-neutral-900 mb-4">Create New Template</h2>
        
        <form onSubmit={handleSubmit} className="space-y-4">
          <Input
            label="Template Name"
            value={formData.name}
            onChange={(e) => setFormData(prev => ({ ...prev, name: e.target.value }))}
            placeholder="e.g., HIPAA Compliance Assessment"
            required
          />

          <div>
            <label className="block text-sm font-medium text-neutral-700 mb-1">
              Description
            </label>
            <textarea
              value={formData.description}
              onChange={(e) => setFormData(prev => ({ ...prev, description: e.target.value }))}
              placeholder="Describe the purpose and scope of this template..."
              rows={3}
              className="input"
              required
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-neutral-700 mb-1">
              Industry
            </label>
            <select
              value={formData.industry}
              onChange={(e) => setFormData(prev => ({ ...prev, industry: e.target.value }))}
              className="input"
            >
              <option value="General">General</option>
              <option value="Healthcare">Healthcare</option>
              <option value="Finance">Finance</option>
              <option value="Technology">Technology</option>
              <option value="Legal">Legal</option>
            </select>
          </div>

          <Input
            label="Compliance Frameworks"
            value={formData.frameworks}
            onChange={(e) => setFormData(prev => ({ ...prev, frameworks: e.target.value }))}
            placeholder="GDPR, HIPAA, SOX (comma-separated)"
          />

          <div>
            <label className="block text-sm font-medium text-neutral-700 mb-1">
              Template Content
            </label>
            <textarea
              value={formData.content}
              onChange={(e) => setFormData(prev => ({ ...prev, content: e.target.value }))}
              placeholder="Enter the template content in markdown format..."
              rows={10}
              className="input font-mono text-sm"
              required
            />
          </div>

          <div className="flex items-center justify-end space-x-3 pt-4">
            <Button
              type="button"
              variant="outline"
              onClick={onClose}
            >
              Cancel
            </Button>
            <Button type="submit">
              Create Template
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
};

const TemplateManagementPage = () => {
  const [activeTab, setActiveTab] = useState('view');
  const [templates, setTemplates] = useState([
    {
      id: 1,
      name: 'HIPAA Compliance Assessment',
      description: 'Comprehensive template for healthcare organizations to assess HIPAA compliance',
      industry: 'Healthcare',
      frameworks: ['HIPAA', 'HITECH'],
      version: '2.1',
      usage: 145,
      sections: 8,
      pages: 24,
      featured: true,
      updatedAt: '2024-01-15T10:30:00Z',
      content: '# HIPAA Compliance Assessment Template...'
    },
    {
      id: 2,
      name: 'SOX Financial Controls',
      description: 'Template for documenting financial controls and compliance procedures',
      industry: 'Finance',
      frameworks: ['SOX', 'COSO'],
      version: '1.8',
      usage: 89,
      sections: 6,
      pages: 18,
      featured: false,
      updatedAt: '2024-01-14T14:20:00Z',
      content: '# SOX Financial Controls Template...'
    },
    {
      id: 3,
      name: 'GDPR Data Protection Impact Assessment',
      description: 'Template for conducting GDPR-compliant data protection impact assessments',
      industry: 'Technology',
      frameworks: ['GDPR', 'ISO 27001'],
      version: '3.0',
      usage: 203,
      sections: 10,
      pages: 32,
      featured: true,
      updatedAt: '2024-01-13T09:15:00Z',
      content: '# GDPR DPIA Template...'
    },
    {
      id: 4,
      name: 'AI Ethics Framework',
      description: 'Comprehensive framework for ethical AI development and deployment',
      industry: 'Technology',
      frameworks: ['IEEE 2857', 'ISO/IEC 23053'],
      version: '1.5',
      usage: 67,
      sections: 7,
      pages: 20,
      featured: false,
      updatedAt: '2024-01-12T16:45:00Z',
      content: '# AI Ethics Framework Template...'
    }
  ]);

  const [searchTerm, setSearchTerm] = useState('');
  const [filterIndustry, setFilterIndustry] = useState('all');
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showEnhanceModal, setShowEnhanceModal] = useState(false);
  const [selectedTemplate, setSelectedTemplate] = useState(null);

  const filteredTemplates = templates.filter(template => {
    const matchesSearch = template.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         template.description.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         template.frameworks.some(f => f.toLowerCase().includes(searchTerm.toLowerCase()));
    const matchesFilter = filterIndustry === 'all' || template.industry === filterIndustry;
    return matchesSearch && matchesFilter;
  });

  const handleEdit = (template) => {
    console.log('Edit template:', template);
  };

  const handleDelete = (template) => {
    if (window.confirm(`Are you sure you want to delete "${template.name}"?`)) {
      setTemplates(prev => prev.filter(t => t.id !== template.id));
    }
  };

  const handleView = (template) => {
    console.log('View template:', template);
  };

  const handleEnhance = (template, options = null) => {
    if (options) {
      // Apply enhancements
      const enhancedTemplate = {
        ...template,
        version: `${parseFloat(template.version) + 0.1}`,
        updatedAt: new Date().toISOString(),
        content: template.content + '\n\n<!-- AI Enhanced Content -->'
      };
      setTemplates(prev => prev.map(t => t.id === template.id ? enhancedTemplate : t));
    } else {
      // Open enhance modal
      setSelectedTemplate(template);
      setShowEnhanceModal(true);
    }
  };

  const handleCreateTemplate = (newTemplate) => {
    setTemplates(prev => [...prev, newTemplate]);
  };

  const industries = ['Healthcare', 'Finance', 'Technology', 'Legal', 'General'];
  const totalUsage = templates.reduce((sum, t) => sum + t.usage, 0);
  const featuredCount = templates.filter(t => t.featured).length;

  const tabs = [
    { id: 'view', label: 'View Templates', icon: Eye },
    { id: 'enhance', label: 'Enhance Existing', icon: Zap },
    { id: 'create', label: 'Create New', icon: Plus }
  ];

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="page-header">
        <h1 className="text-2xl font-bold text-neutral-900">Template Management</h1>
        <p className="text-neutral-600">
          Create, enhance, and manage your compliance document templates
        </p>
      </div>

      {/* Stats Overview */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card className="text-center">
          <div className="text-2xl font-bold text-neutral-900">{templates.length}</div>
          <div className="text-sm text-neutral-600">Total Templates</div>
        </Card>
        <Card className="text-center">
          <div className="text-2xl font-bold text-blue-600">{totalUsage}</div>
          <div className="text-sm text-neutral-600">Total Usage</div>
        </Card>
        <Card className="text-center">
          <div className="text-2xl font-bold text-yellow-600">{featuredCount}</div>
          <div className="text-sm text-neutral-600">Featured</div>
        </Card>
        <Card className="text-center">
          <div className="text-2xl font-bold text-green-600">{industries.length}</div>
          <div className="text-sm text-neutral-600">Industries</div>
        </Card>
      </div>

      {/* Tab Navigation */}
      <div className="border-b border-neutral-200">
        <nav className="-mb-px flex space-x-8">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`py-2 px-1 border-b-2 font-medium text-sm flex items-center space-x-2 ${
                activeTab === tab.id
                  ? 'border-brand-500 text-brand-600'
                  : 'border-transparent text-neutral-500 hover:text-neutral-700 hover:border-neutral-300'
              }`}
            >
              <tab.icon className="w-4 h-4" />
              <span>{tab.label}</span>
            </button>
          ))}
        </nav>
      </div>

      {/* Tab Content */}
      {activeTab === 'view' && (
        <div className="space-y-6">
          {/* Filters */}
          <div className="flex flex-col sm:flex-row gap-4">
            <div className="flex-1">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-neutral-400 w-4 h-4" />
                <input
                  type="text"
                  placeholder="Search templates..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="input pl-10"
                />
              </div>
            </div>
            <div className="flex items-center space-x-2">
              <Filter className="w-4 h-4 text-neutral-400" />
              <select
                value={filterIndustry}
                onChange={(e) => setFilterIndustry(e.target.value)}
                className="input w-auto"
              >
                <option value="all">All Industries</option>
                {industries.map(industry => (
                  <option key={industry} value={industry}>{industry}</option>
                ))}
              </select>
            </div>
            <Button variant="outline">
              <Download className="w-4 h-4 mr-2" />
              Export
            </Button>
          </div>

          {/* Templates Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {filteredTemplates.map((template) => (
              <TemplateCard
                key={template.id}
                template={template}
                onEdit={handleEdit}
                onDelete={handleDelete}
                onView={handleView}
                onEnhance={handleEnhance}
              />
            ))}
          </div>
        </div>
      )}

      {activeTab === 'enhance' && (
        <Card>
          <Card.Header>
            <Card.Title>AI-Powered Template Enhancement</Card.Title>
          </Card.Header>
          <Card.Content>
            <div className="text-center py-12">
              <Zap className="w-16 h-16 mx-auto text-brand-600 mb-4" />
              <h3 className="text-lg font-medium text-neutral-900 mb-2">
                Enhance Your Templates with AI
              </h3>
              <p className="text-neutral-600 mb-6 max-w-md mx-auto">
                Select a template from the "View Templates" tab and click "Enhance" to improve it with AI-powered suggestions.
              </p>
              <Button onClick={() => setActiveTab('view')}>
                <Eye className="w-4 h-4 mr-2" />
                Browse Templates
              </Button>
            </div>
          </Card.Content>
        </Card>
      )}

      {activeTab === 'create' && (
        <Card>
          <Card.Header>
            <Card.Title>Create New Template</Card.Title>
          </Card.Header>
          <Card.Content>
            <div className="text-center py-12">
              <Plus className="w-16 h-16 mx-auto text-brand-600 mb-4" />
              <h3 className="text-lg font-medium text-neutral-900 mb-2">
                Create a New Compliance Template
              </h3>
              <p className="text-neutral-600 mb-6 max-w-md mx-auto">
                Build custom templates for your specific compliance requirements and industry needs.
              </p>
              <div className="flex items-center justify-center space-x-4">
                <Button onClick={() => setShowCreateModal(true)}>
                  <Plus className="w-4 h-4 mr-2" />
                  Create from Scratch
                </Button>
                <Button variant="outline">
                  <Upload className="w-4 h-4 mr-2" />
                  Import Template
                </Button>
              </div>
            </div>
          </Card.Content>
        </Card>
      )}

      {/* Modals */}
      <CreateTemplateModal
        isOpen={showCreateModal}
        onClose={() => setShowCreateModal(false)}
        onSave={handleCreateTemplate}
      />

      <EnhanceTemplateModal
        isOpen={showEnhanceModal}
        onClose={() => {
          setShowEnhanceModal(false);
          setSelectedTemplate(null);
        }}
        template={selectedTemplate}
        onEnhance={handleEnhance}
      />
    </div>
  );
};

export default TemplateManagementPage;