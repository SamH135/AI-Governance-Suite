import React, { useState, useEffect } from 'react';
import { 
  Plus, 
  Search, 
  Filter, 
  MoreVertical, 
  Edit, 
  Trash2, 
  Copy,
  Tag,
  FileText,
  Users,
  TrendingUp,
  Eye
} from 'lucide-react';
import Card from '../../components/ui/Card';
import Button from '../../components/ui/Button';
import Input from '../../components/ui/Input';
import LoadingSpinner from '../../components/ui/LoadingSpinner';

const CategoryCard = ({ category, onEdit, onDelete, onView }) => {
  const [showMenu, setShowMenu] = useState(false);

  const getFrameworkColor = (framework) => {
    const colors = {
      'Healthcare': 'bg-blue-100 text-blue-800',
      'Finance': 'bg-green-100 text-green-800',
      'Legal': 'bg-purple-100 text-purple-800',
      'General': 'bg-neutral-100 text-neutral-800',
      'Technical': 'bg-orange-100 text-orange-800'
    };
    return colors[framework] || colors['General'];
  };

  return (
    <Card className="hover:shadow-md transition-shadow">
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-lg font-semibold text-neutral-900">{category.name}</h3>
            <div className="relative">
              <button
                onClick={() => setShowMenu(!showMenu)}
                className="p-1 hover:bg-neutral-100 rounded"
              >
                <MoreVertical className="w-4 h-4" />
              </button>
              {showMenu && (
                <div className="absolute right-0 mt-1 w-48 bg-white rounded-md shadow-lg border border-neutral-200 py-1 z-10">
                  <button
                    onClick={() => {
                      onView(category);
                      setShowMenu(false);
                    }}
                    className="flex items-center w-full px-4 py-2 text-sm text-neutral-700 hover:bg-neutral-100"
                  >
                    <Eye className="w-4 h-4 mr-2" />
                    View Templates
                  </button>
                  <button
                    onClick={() => {
                      onEdit(category);
                      setShowMenu(false);
                    }}
                    className="flex items-center w-full px-4 py-2 text-sm text-neutral-700 hover:bg-neutral-100"
                  >
                    <Edit className="w-4 h-4 mr-2" />
                    Edit Category
                  </button>
                  <button
                    onClick={() => {
                      navigator.clipboard.writeText(JSON.stringify(category, null, 2));
                      setShowMenu(false);
                    }}
                    className="flex items-center w-full px-4 py-2 text-sm text-neutral-700 hover:bg-neutral-100"
                  >
                    <Copy className="w-4 h-4 mr-2" />
                    Copy Config
                  </button>
                  <button
                    onClick={() => {
                      onDelete(category);
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
          
          <p className="text-neutral-600 text-sm mb-3">{category.description}</p>
          
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center space-x-2">
              <span className={`px-2 py-1 rounded-full text-xs font-medium ${getFrameworkColor(category.framework)}`}>
                {category.framework}
              </span>
              <span className="text-xs text-neutral-500">
                {category.templates} templates
              </span>
            </div>
            <div className="flex items-center space-x-4 text-xs text-neutral-500">
              <div className="flex items-center">
                <Users className="w-3 h-3 mr-1" />
                {category.usage}
              </div>
              <div className="flex items-center">
                <TrendingUp className="w-3 h-3 mr-1" />
                {category.performance}%
              </div>
            </div>
          </div>

          <div className="flex flex-wrap gap-1">
            {category.tags.map((tag, index) => (
              <span
                key={index}
                className="px-2 py-1 bg-neutral-100 text-neutral-600 text-xs rounded"
              >
                {tag}
              </span>
            ))}
          </div>
        </div>
      </div>
    </Card>
  );
};

const CreateCategoryModal = ({ isOpen, onClose, onSave }) => {
  const [formData, setFormData] = useState({
    name: '',
    description: '',
    framework: 'General',
    tags: '',
    isPublic: true
  });

  const handleSubmit = (e) => {
    e.preventDefault();
    onSave({
      ...formData,
      tags: formData.tags.split(',').map(tag => tag.trim()).filter(Boolean),
      id: Date.now(),
      templates: 0,
      usage: 0,
      performance: 0,
      createdAt: new Date().toISOString()
    });
    setFormData({
      name: '',
      description: '',
      framework: 'General',
      tags: '',
      isPublic: true
    });
    onClose();
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg p-6 w-full max-w-md">
        <h2 className="text-xl font-bold text-neutral-900 mb-4">Create New Category</h2>
        
        <form onSubmit={handleSubmit} className="space-y-4">
          <Input
            label="Category Name"
            value={formData.name}
            onChange={(e) => setFormData(prev => ({ ...prev, name: e.target.value }))}
            placeholder="e.g., Medical Diagnosis"
            required
          />

          <div>
            <label className="block text-sm font-medium text-neutral-700 mb-1">
              Description
            </label>
            <textarea
              value={formData.description}
              onChange={(e) => setFormData(prev => ({ ...prev, description: e.target.value }))}
              placeholder="Describe the purpose and use cases for this category..."
              rows={3}
              className="input"
              required
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-neutral-700 mb-1">
              Framework
            </label>
            <select
              value={formData.framework}
              onChange={(e) => setFormData(prev => ({ ...prev, framework: e.target.value }))}
              className="input"
            >
              <option value="General">General</option>
              <option value="Healthcare">Healthcare</option>
              <option value="Finance">Finance</option>
              <option value="Legal">Legal</option>
              <option value="Technical">Technical</option>
            </select>
          </div>

          <Input
            label="Tags"
            value={formData.tags}
            onChange={(e) => setFormData(prev => ({ ...prev, tags: e.target.value }))}
            placeholder="diagnosis, medical, AI, classification (comma-separated)"
          />

          <div className="flex items-center">
            <input
              type="checkbox"
              id="isPublic"
              checked={formData.isPublic}
              onChange={(e) => setFormData(prev => ({ ...prev, isPublic: e.target.checked }))}
              className="mr-2"
            />
            <label htmlFor="isPublic" className="text-sm text-neutral-700">
              Make this category public
            </label>
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
              Create Category
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
};

const PromptCategoriesPage = () => {
  const [categories, setCategories] = useState([
    {
      id: 1,
      name: 'Medical Diagnosis',
      description: 'Prompts for AI-assisted medical diagnosis and treatment recommendations',
      framework: 'Healthcare',
      templates: 24,
      usage: 156,
      performance: 92,
      tags: ['diagnosis', 'medical', 'healthcare', 'AI'],
      createdAt: '2024-01-15T10:30:00Z'
    },
    {
      id: 2,
      name: 'Financial Risk Assessment',
      description: 'Templates for evaluating financial risks and compliance requirements',
      framework: 'Finance',
      templates: 18,
      usage: 89,
      performance: 87,
      tags: ['finance', 'risk', 'compliance', 'assessment'],
      createdAt: '2024-01-14T14:20:00Z'
    },
    {
      id: 3,
      name: 'Legal Document Analysis',
      description: 'Prompts for analyzing legal documents and contracts',
      framework: 'Legal',
      templates: 31,
      usage: 203,
      performance: 89,
      tags: ['legal', 'contracts', 'analysis', 'compliance'],
      createdAt: '2024-01-13T09:15:00Z'
    },
    {
      id: 4,
      name: 'Code Review & Security',
      description: 'Templates for automated code review and security analysis',
      framework: 'Technical',
      templates: 15,
      usage: 67,
      performance: 94,
      tags: ['code', 'security', 'review', 'technical'],
      createdAt: '2024-01-12T16:45:00Z'
    },
    {
      id: 5,
      name: 'Content Moderation',
      description: 'Prompts for content filtering and moderation tasks',
      framework: 'General',
      templates: 12,
      usage: 134,
      performance: 91,
      tags: ['content', 'moderation', 'filtering', 'safety'],
      createdAt: '2024-01-11T11:20:00Z'
    }
  ]);

  const [loading, setLoading] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [filterFramework, setFilterFramework] = useState('all');
  const [showCreateModal, setShowCreateModal] = useState(false);

  const filteredCategories = categories.filter(category => {
    const matchesSearch = category.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         category.description.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         category.tags.some(tag => tag.toLowerCase().includes(searchTerm.toLowerCase()));
    const matchesFilter = filterFramework === 'all' || category.framework === filterFramework;
    return matchesSearch && matchesFilter;
  });

  const handleEdit = (category) => {
    console.log('Edit category:', category);
    // In a real app, this would open an edit modal
  };

  const handleDelete = async (category) => {
    if (window.confirm(`Are you sure you want to delete "${category.name}"?`)) {
      setCategories(prev => prev.filter(c => c.id !== category.id));
    }
  };

  const handleView = (category) => {
    console.log('View templates for category:', category);
    // In a real app, this would navigate to the templates view
  };

  const handleCreateCategory = (newCategory) => {
    setCategories(prev => [...prev, newCategory]);
  };

  const frameworks = ['Healthcare', 'Finance', 'Legal', 'Technical', 'General'];
  const totalTemplates = categories.reduce((sum, cat) => sum + cat.templates, 0);
  const totalUsage = categories.reduce((sum, cat) => sum + cat.usage, 0);
  const avgPerformance = Math.round(categories.reduce((sum, cat) => sum + cat.performance, 0) / categories.length);

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="page-header flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-neutral-900">Prompt Categories</h1>
          <p className="text-neutral-600">
            Organize and manage your prompt templates by category
          </p>
        </div>
        <Button onClick={() => setShowCreateModal(true)}>
          <Plus className="w-4 h-4 mr-2" />
          Create Category
        </Button>
      </div>

      {/* Stats Overview */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card className="text-center">
          <div className="text-2xl font-bold text-neutral-900">{categories.length}</div>
          <div className="text-sm text-neutral-600">Total Categories</div>
        </Card>
        <Card className="text-center">
          <div className="text-2xl font-bold text-blue-600">{totalTemplates}</div>
          <div className="text-sm text-neutral-600">Total Templates</div>
        </Card>
        <Card className="text-center">
          <div className="text-2xl font-bold text-green-600">{totalUsage}</div>
          <div className="text-sm text-neutral-600">Total Usage</div>
        </Card>
        <Card className="text-center">
          <div className="text-2xl font-bold text-purple-600">{avgPerformance}%</div>
          <div className="text-sm text-neutral-600">Avg Performance</div>
        </Card>
      </div>

      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-4">
        <div className="flex-1">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-neutral-400 w-4 h-4" />
            <input
              type="text"
              placeholder="Search categories, descriptions, or tags..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="input pl-10"
            />
          </div>
        </div>
        <div className="flex items-center space-x-2">
          <Filter className="w-4 h-4 text-neutral-400" />
          <select
            value={filterFramework}
            onChange={(e) => setFilterFramework(e.target.value)}
            className="input w-auto"
          >
            <option value="all">All Frameworks</option>
            {frameworks.map(framework => (
              <option key={framework} value={framework}>{framework}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Categories Grid */}
      {loading ? (
        <div className="flex items-center justify-center h-64">
          <LoadingSpinner size="lg" />
        </div>
      ) : filteredCategories.length === 0 ? (
        <Card className="text-center py-12">
          <div className="text-neutral-400 mb-4">
            <Tag className="w-12 h-12 mx-auto" />
          </div>
          <h3 className="text-lg font-medium text-neutral-900 mb-2">No categories found</h3>
          <p className="text-neutral-600 mb-4">
            {searchTerm || filterFramework !== 'all' 
              ? 'Try adjusting your search or filter criteria.'
              : 'Get started by creating your first prompt category.'
            }
          </p>
          {!searchTerm && filterFramework === 'all' && (
            <Button onClick={() => setShowCreateModal(true)}>
              <Plus className="w-4 h-4 mr-2" />
              Create Your First Category
            </Button>
          )}
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filteredCategories.map((category) => (
            <CategoryCard
              key={category.id}
              category={category}
              onEdit={handleEdit}
              onDelete={handleDelete}
              onView={handleView}
            />
          ))}
        </div>
      )}

      {/* Framework Distribution */}
      <Card>
        <Card.Header>
          <Card.Title>Framework Distribution</Card.Title>
        </Card.Header>
        <Card.Content>
          <div className="space-y-3">
            {frameworks.map(framework => {
              const count = categories.filter(c => c.framework === framework).length;
              const percentage = categories.length > 0 ? (count / categories.length) * 100 : 0;
              
              return (
                <div key={framework} className="flex items-center justify-between">
                  <div className="flex items-center space-x-3">
                    <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                      framework === 'Healthcare' ? 'bg-blue-100 text-blue-800' :
                      framework === 'Finance' ? 'bg-green-100 text-green-800' :
                      framework === 'Legal' ? 'bg-purple-100 text-purple-800' :
                      framework === 'Technical' ? 'bg-orange-100 text-orange-800' :
                      'bg-neutral-100 text-neutral-800'
                    }`}>
                      {framework}
                    </span>
                    <span className="text-sm text-neutral-600">{count} categories</span>
                  </div>
                  <div className="flex items-center space-x-2">
                    <div className="w-24 bg-neutral-200 rounded-full h-2">
                      <div 
                        className="bg-brand-600 h-2 rounded-full" 
                        style={{ width: `${percentage}%` }}
                      ></div>
                    </div>
                    <span className="text-sm text-neutral-500 w-10 text-right">
                      {percentage.toFixed(0)}%
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        </Card.Content>
      </Card>

      {/* Create Category Modal */}
      <CreateCategoryModal
        isOpen={showCreateModal}
        onClose={() => setShowCreateModal(false)}
        onSave={handleCreateCategory}
      />
    </div>
  );
};

export default PromptCategoriesPage;