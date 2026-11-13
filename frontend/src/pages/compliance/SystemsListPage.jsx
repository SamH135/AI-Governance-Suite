import { useState, useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import { Plus, Search, Filter, MoreVertical, Play, Trash2, Shield, Settings } from 'lucide-react';
import Card from '../../components/ui/Card';
import Button from '../../components/ui/Button';
import LoadingSpinner from '../../components/ui/LoadingSpinner';
import { systemsService } from '../../services/apiService';

const StatusBadge = ({ status }) => {
  const statusClasses = {
    active: 'status-success',
    inactive: 'status-error',
    testing: 'status-warning',
    pending: 'status-info'
  };

  return (
    <span className={statusClasses[status] || 'status-info'}>
      {status}
    </span>
  );
};

const SystemCard = ({ system, onEdit, onDelete, onTest, onViewDetails }) => {
  const [showMenu, setShowMenu] = useState(false);

  return (
    <Card className="hover:shadow-md transition-shadow">
      <div className="flex items-start justify-between">
        <div 
          className="flex-1 cursor-pointer" 
          onClick={() => onViewDetails(system)}
        >
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-lg font-semibold text-neutral-900">{system.name}</h3>
            <div className="relative">
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  setShowMenu(!showMenu);
                }}
                className="p-1 hover:bg-neutral-100 rounded"
              >
                <MoreVertical className="w-4 h-4" />
              </button>
              {showMenu && (
                <div className="absolute right-0 mt-1 w-48 bg-white rounded-md shadow-lg border border-neutral-200 py-1 z-10">
                  <button
                    onClick={(e) => {
                      e.preventDefault();
                      e.stopPropagation();
                      onEdit(system);
                      setShowMenu(false);
                    }}
                    className="flex items-center w-full px-4 py-2 text-sm text-neutral-700 hover:bg-neutral-100"
                  >
                    <Settings className="w-4 h-4 mr-2" />
                    Configure Models
                  </button>
                  <button
                    onClick={(e) => {
                      e.preventDefault();
                      e.stopPropagation();
                      onTest(system);
                      setShowMenu(false);
                    }}
                    className="flex items-center w-full px-4 py-2 text-sm text-neutral-700 hover:bg-neutral-100"
                  >
                    <Play className="w-4 h-4 mr-2" />
                    Run Test
                  </button>
                  <button
                    onClick={(e) => {
                      e.preventDefault();
                      e.stopPropagation();
                      onDelete(system);
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
          
          <p className="text-neutral-600 text-sm mb-3">{system.description}</p>
          
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-4">
              <StatusBadge status={system.status} />
              <span className="text-xs text-neutral-500">
                {system.models && system.models.length > 0 ? (
                  <>
                    {system.models.length} model{system.models.length > 1 ? 's' : ''} configured
                  </>
                ) : (
                  'No models configured'
                )}
              </span>
            </div>
            <div className="text-xs text-neutral-500">
              Last tested: {system.last_tested ? new Date(system.last_tested).toLocaleDateString() : 'Never'}
            </div>
          </div>
          
          {/* Models List */}
          {system.models && system.models.length > 0 && (
            <div className="mt-3 pt-3 border-t border-neutral-100">
              <div className="text-xs font-medium text-neutral-700 mb-1">Models:</div>
              <div className="space-y-1">
                {system.models.map((model, index) => (
                  <div key={model.id || `model-${index}`} className="flex items-center justify-between text-xs">
                    <span className="text-neutral-600">
                      {model.name} ({model.provider})
                    </span>
                    <span className={`px-1.5 py-0.5 rounded text-xs ${
                      model.is_primary 
                        ? 'bg-blue-100 text-blue-700' 
                        : 'bg-neutral-100 text-neutral-600'
                    }`}>
                      {model.is_primary ? 'Primary' : model.role || 'Additional'}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </Card>
  );
};

const SystemsListPage = () => {
  const location = useLocation();
  const [systems, setSystems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [filterStatus, setFilterStatus] = useState('all');
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [statusMessage, setStatusMessage] = useState(null);
  const [recentlyDeletedIds, setRecentlyDeletedIds] = useState(new Set());

  useEffect(() => {
    const fetchSystems = async () => {
      try {
        const data = await systemsService.getSystems();
        setSystems(data);
      } catch (error) {
        console.error('Failed to fetch systems:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchSystems();
  }, []);

  // Check for messages from navigation state
  useEffect(() => {
    if (location.state?.message) {
      setStatusMessage(location.state.message);
      // Clear the message after showing it
      window.history.replaceState({}, document.title);
    }
  }, [location.state]);

  // Auto-dismiss success messages after 5 seconds
  useEffect(() => {
    if (statusMessage && statusMessage.includes('successfully')) {
      const timer = setTimeout(() => setStatusMessage(null), 5000);
      return () => clearTimeout(timer);
    }
  }, [statusMessage]);

  const filteredSystems = systems.filter(system => {
    const matchesSearch = system.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         system.description.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesFilter = filterStatus === 'all' || system.status === filterStatus;
    return matchesSearch && matchesFilter;
  });

  const handleViewDetails = (system) => {
    console.log('🔍 handleViewDetails called for system:', system.system_id, system.name);
    
    // Check if this system was recently deleted
    if (recentlyDeletedIds.has(system.system_id)) {
      console.log('❌ System was recently deleted, staying on systems list page');
      return;
    }
    
    // Check if system still exists in current systems array (prevent navigation to deleted systems)
    const systemExists = systems.find(s => s.system_id === system.system_id);
    if (!systemExists) {
      console.log('❌ System no longer exists, staying on systems list page');
      return;
    }
    
    console.log('✅ Navigate to system details page for system:', system.system_id);
    // Navigate to the system details page (model configuration page)
    window.location.href = `/compliance/systems/${system.system_id}/models`;
  };

  const handleEdit = (system) => {
    console.log('✏️ handleEdit called for system:', system.system_id, system.name);
    
    // Check if this system was recently deleted
    if (recentlyDeletedIds.has(system.system_id)) {
      console.log('❌ System was recently deleted, staying on systems list page');
      return;
    }
    
    // Check if system still exists in current systems array (prevent navigation to deleted systems)
    const systemExists = systems.find(s => s.system_id === system.system_id);
    if (!systemExists) {
      console.log('❌ System no longer exists, staying on systems list page');
      return;
    }
    
    console.log('✅ Navigate to system model configuration page for system:', system.system_id);
    // Navigate to the system model configuration page to edit system details and models
    window.location.href = `/compliance/systems/${system.system_id}/models`;
  };

  const handleDelete = async (system) => {
    if (window.confirm(`Are you sure you want to delete "${system.name}"? This action cannot be undone.`)) {
      console.log('🗑️ DELETION STARTED for system:', system.system_id, system.name);
      try {
        console.log('📡 Calling API to delete system...');
        const result = await systemsService.deleteSystem(system.system_id);
        console.log('✅ DELETION API CALL COMPLETED for system:', system.system_id, 'Result:', result);
        
        console.log('📝 Updating recently deleted IDs...');
        // Add to recently deleted IDs to prevent any navigation attempts
        setRecentlyDeletedIds(prev => new Set([...prev, system.system_id]));
        console.log('✅ ADDED TO RECENTLY DELETED:', system.system_id);
        
        console.log('🔄 Updating systems state...');
        // Immediately remove from local state to prevent clicking on deleted items
        setSystems(prevSystems => {
          const newSystems = prevSystems.filter(s => s.system_id !== system.system_id);
          console.log('✅ REMOVED FROM LOCAL STATE:', system.system_id, 'Systems count:', newSystems.length);
          return newSystems;
        });
        
        console.log('💬 Setting success message...');
        // Show success message
        setStatusMessage(`AI system "${system.name}" has been successfully deleted.`);
        console.log('✅ DELETION COMPLETED SUCCESSFULLY for system:', system.system_id);
        
        // Clear the recently deleted ID after a delay to prevent memory leaks
        setTimeout(() => {
          setRecentlyDeletedIds(prev => {
            const newSet = new Set(prev);
            newSet.delete(system.system_id);
            return newSet;
          });
          console.log('🧹 CLEARED FROM RECENTLY DELETED:', system.system_id);
        }, 5000);
        
        // Ensure we stay on the systems list page and don't navigate anywhere
        return;
      } catch (error) {
        console.error('❌ Failed to delete system:', error);
        console.error('❌ Error details:', {
          message: error.message,
          status: error.status,
          response: error.response,
          stack: error.stack
        });
        setStatusMessage(`Failed to delete AI system "${system.name}". Please try again.`);
      }
    } else {
      console.log('🚫 DELETION CANCELLED for system:', system.system_id);
    }
  };

  const handleTest = (system) => {
    // Check if this system was recently deleted
    if (recentlyDeletedIds.has(system.system_id)) {
      console.log('System was recently deleted, staying on systems list page');
      return;
    }
    
    // Check if system still exists in current systems array (prevent navigation to deleted systems)
    const systemExists = systems.find(s => s.system_id === system.system_id);
    if (!systemExists) {
      console.log('System no longer exists, staying on systems list page');
      return;
    }
    
    // Navigate to test configuration
    window.location.href = `/compliance/test/configure/${system.system_id}`;
  };

  const handleCreateSystem = async () => {
    setShowCreateModal(true);
  };

  const handleCreateSubmit = async (systemData) => {
    try {
      const newSystem = await systemsService.createSystem(systemData);
      setSystems([...systems, newSystem]);
      setShowCreateModal(false);
      
      // Navigate to model management for the new system
      console.log('System created successfully, navigating to system details:', newSystem);
      window.location.href = `/compliance/systems/${newSystem.system_id}/models`;
    } catch (error) {
      console.error('Failed to create system:', error);
      // Add error handling here
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <LoadingSpinner size="lg" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Status Message */}
      {statusMessage && (
        <div className={`border rounded-lg p-4 ${
          statusMessage.includes('successfully') 
            ? 'bg-green-50 border-green-200' 
            : statusMessage.includes('Failed')
            ? 'bg-red-50 border-red-200'
            : 'bg-yellow-50 border-yellow-200'
        }`}>
          <div className="flex items-center justify-between">
            <p className={
              statusMessage.includes('successfully') 
                ? 'text-green-800' 
                : statusMessage.includes('Failed')
                ? 'text-red-800'
                : 'text-yellow-800'
            }>
              {statusMessage}
            </p>
            <button 
              onClick={() => setStatusMessage(null)}
              className={`font-medium ${
                statusMessage.includes('successfully') 
                  ? 'text-green-600 hover:text-green-800' 
                  : statusMessage.includes('Failed')
                  ? 'text-red-600 hover:text-red-800'
                  : 'text-yellow-600 hover:text-yellow-800'
              }`}
            >
              ✕
            </button>
          </div>
        </div>
      )}

      {/* Page Header */}
      <div className="page-header flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-neutral-900">AI Systems</h1>
          <p className="text-neutral-600">
            Manage and test your AI systems for compliance
          </p>
        </div>
        <Button onClick={handleCreateSystem}>
          <Plus className="w-4 h-4 mr-2" />
          Add System
        </Button>
      </div>

      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-4">
        <div className="flex-1">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-neutral-400 w-4 h-4" />
            <input
              type="text"
              placeholder="Search systems..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="input pl-10"
            />
          </div>
        </div>
        <div className="flex items-center space-x-2">
          <Filter className="w-4 h-4 text-neutral-400" />
          <select
            value={filterStatus}
            onChange={(e) => setFilterStatus(e.target.value)}
            className="input w-auto"
          >
            <option value="all">All Status</option>
            <option value="active">Active</option>
            <option value="inactive">Inactive</option>
            <option value="testing">Testing</option>
            <option value="pending">Pending</option>
          </select>
        </div>
      </div>

      {/* Systems Grid */}
      {filteredSystems.length === 0 ? (
        <Card className="text-center py-12">
          <div className="text-neutral-400 mb-4">
            <Shield className="w-12 h-12 mx-auto" />
          </div>
          <h3 className="text-lg font-medium text-neutral-900 mb-2">No systems found</h3>
          <p className="text-neutral-600 mb-4">
            {searchTerm || filterStatus !== 'all' 
              ? 'Try adjusting your search or filter criteria.'
              : 'Get started by adding your first AI system.'
            }
          </p>
          {!searchTerm && filterStatus === 'all' && (
            <Button onClick={handleCreateSystem}>
              <Plus className="w-4 h-4 mr-2" />
              Add Your First System
            </Button>
          )}
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filteredSystems.map((system) => (
            <SystemCard
              key={system.system_id}
              system={system}
              onViewDetails={handleViewDetails}
              onEdit={handleEdit}
              onDelete={handleDelete}
              onTest={handleTest}
            />
          ))}
        </div>
      )}

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card className="text-center">
          <div className="text-2xl font-bold text-neutral-900">{systems.length}</div>
          <div className="text-sm text-neutral-600">Total Systems</div>
        </Card>
        <Card className="text-center">
          <div className="text-2xl font-bold text-green-600">
            {systems.filter(s => s.status === 'active').length}
          </div>
          <div className="text-sm text-neutral-600">Active</div>
        </Card>
        <Card className="text-center">
          <div className="text-2xl font-bold text-yellow-600">
            {systems.filter(s => s.status === 'testing').length}
          </div>
          <div className="text-sm text-neutral-600">Testing</div>
        </Card>
        <Card className="text-center">
          <div className="text-2xl font-bold text-red-600">
            {systems.filter(s => s.status === 'inactive').length}
          </div>
          <div className="text-sm text-neutral-600">Inactive</div>
        </Card>
      </div>

      {/* Create System Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 w-full max-w-md">
            <h2 className="text-xl font-bold text-neutral-900 mb-4">Create New AI System</h2>
            <form onSubmit={(e) => {
              e.preventDefault();
              const formData = new FormData(e.target);
              const systemData = {
                name: formData.get('name'),
                description: formData.get('description'),
                system_type: formData.get('system_type'),
                industry: formData.get('industry'),
                compliance_frameworks: formData.get('frameworks').split(',').map(f => f.trim()).filter(f => f)
              };
              handleCreateSubmit(systemData);
            }}>
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-neutral-700 mb-1">System Name</label>
                  <input
                    name="name"
                    type="text"
                    required
                    className="input w-full"
                    placeholder="Enter system name"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-neutral-700 mb-1">Description</label>
                  <textarea
                    name="description"
                    className="input w-full"
                    rows="3"
                    placeholder="Describe your AI system"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-neutral-700 mb-1">System Type</label>
                  <select name="system_type" className="input w-full">
                    <option value="llm">Large Language Model</option>
                    <option value="ml_model">Machine Learning Model</option>
                    <option value="decision_system">Decision System</option>
                    <option value="recommendation">Recommendation System</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-neutral-700 mb-1">Industry</label>
                  <select name="industry" className="input w-full">
                    <option value="healthcare">Healthcare</option>
                    <option value="finance">Finance</option>
                    <option value="technology">Technology</option>
                    <option value="retail">Retail</option>
                    <option value="other">Other</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-neutral-700 mb-1">Compliance Frameworks</label>
                  <input
                    name="frameworks"
                    type="text"
                    className="input w-full"
                    placeholder="GDPR, HIPAA, SOC2 (comma-separated)"
                  />
                </div>
              </div>
              <div className="flex justify-end space-x-3 mt-6">
                <Button
                  type="button"
                  variant="secondary"
                  onClick={() => setShowCreateModal(false)}
                >
                  Cancel
                </Button>
                <Button type="submit">
                  Create System
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default SystemsListPage;