import { useState, useEffect } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from './ui/card';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from './ui/tabs';
import { 
  Upload, 
  Play, 
  Square, 
  RotateCcw, 
  Settings, 
  Trash2, 
  Plus,
  CheckCircle,
  XCircle,
  AlertCircle,
  Info
} from 'lucide-react';

const PluginManager = () => {
  const [plugins, setPlugins] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedPlugin, setSelectedPlugin] = useState(null);
  const [statistics, setStatistics] = useState(null);

  useEffect(() => {
    fetchPlugins();
    fetchStatistics();
  }, []);

  const fetchPlugins = async () => {
    try {
      const response = await fetch('/api/plugins/');
      const data = await response.json();
      if (data.success) {
        setPlugins(data.data);
      }
    } catch (error) {
      console.error('Failed to fetch plugins:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchStatistics = async () => {
    try {
      const response = await fetch('/api/plugins/statistics');
      const data = await response.json();
      if (data.success) {
        setStatistics(data.data);
      }
    } catch (error) {
      console.error('Failed to fetch statistics:', error);
    }
  };

  const handlePluginAction = async (pluginName, action) => {
    try {
      const response = await fetch(`/api/plugins/${pluginName}/${action}`, {
        method: 'POST'
      });
      const data = await response.json();
      
      if (data.success) {
        fetchPlugins();
        fetchStatistics();
      } else {
        alert(`Failed to ${action} plugin: ${data.message}`);
      }
    } catch (error) {
      console.error(`Failed to ${action} plugin:`, error);
      alert(`Failed to ${action} plugin`);
    }
  };

  const getStatusIcon = (plugin) => {
    if (plugin.loaded && plugin.enabled) {
      return <CheckCircle className="h-4 w-4 text-green-500" />;
    } else if (plugin.enabled && !plugin.loaded) {
      return <AlertCircle className="h-4 w-4 text-yellow-500" />;
    } else {
      return <XCircle className="h-4 w-4 text-red-500" />;
    }
  };

  const getStatusText = (plugin) => {
    if (plugin.loaded && plugin.enabled) {
      return 'Active';
    } else if (plugin.enabled && !plugin.loaded) {
      return 'Enabled (Not Loaded)';
    } else {
      return 'Disabled';
    }
  };

  const getCategoryColor = (category) => {
    const colors = {
      'compliance': 'bg-blue-100 text-blue-800',
      'security': 'bg-red-100 text-red-800',
      'custom': 'bg-purple-100 text-purple-800',
      'example': 'bg-gray-100 text-gray-800',
      'default': 'bg-gray-100 text-gray-800'
    };
    return colors[category] || colors.default;
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Statistics Cards */}
      {statistics && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <Card>
            <CardContent className="p-4">
              <div className="flex items-center space-x-2">
                <Info className="h-4 w-4 text-blue-500" />
                <div>
                  <p className="text-sm font-medium">Total Plugins</p>
                  <p className="text-2xl font-bold">{statistics.plugins.total_discovered}</p>
                </div>
              </div>
            </CardContent>
          </Card>
          
          <Card>
            <CardContent className="p-4">
              <div className="flex items-center space-x-2">
                <CheckCircle className="h-4 w-4 text-green-500" />
                <div>
                  <p className="text-sm font-medium">Active</p>
                  <p className="text-2xl font-bold">{statistics.plugins.loaded}</p>
                </div>
              </div>
            </CardContent>
          </Card>
          
          <Card>
            <CardContent className="p-4">
              <div className="flex items-center space-x-2">
                <Settings className="h-4 w-4 text-blue-500" />
                <div>
                  <p className="text-sm font-medium">Frameworks</p>
                  <p className="text-2xl font-bold">{statistics.frameworks.total_frameworks}</p>
                </div>
              </div>
            </CardContent>
          </Card>
          
          <Card>
            <CardContent className="p-4">
              <div className="flex items-center space-x-2">
                <Plus className="h-4 w-4 text-purple-500" />
                <div>
                  <p className="text-sm font-medium">Custom</p>
                  <p className="text-2xl font-bold">{statistics.frameworks.plugin_evaluators}</p>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      <Tabs defaultValue="plugins" className="w-full">
        <TabsList>
          <TabsTrigger value="plugins">Installed Plugins</TabsTrigger>
          <TabsTrigger value="generator">Plugin Generator</TabsTrigger>
          <TabsTrigger value="install">Install Plugin</TabsTrigger>
        </TabsList>

        <TabsContent value="plugins" className="space-y-4">
          <div className="flex justify-between items-center">
            <h2 className="text-2xl font-bold">Plugin Management</h2>
            <Button onClick={fetchPlugins} variant="outline">
              <RotateCcw className="h-4 w-4 mr-2" />
              Refresh
            </Button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {plugins.map((plugin) => (
              <Card key={plugin.name} className="hover:shadow-md transition-shadow">
                <CardHeader className="pb-3">
                  <div className="flex items-start justify-between">
                    <div>
                      <CardTitle className="text-lg">{plugin.name}</CardTitle>
                      <p className="text-sm text-gray-600 mt-1">{plugin.framework}</p>
                    </div>
                    {getStatusIcon(plugin)}
                  </div>
                  
                  <div className="flex items-center space-x-2">
                    <Badge className={getCategoryColor(plugin.category)}>
                      {plugin.category}
                    </Badge>
                    <Badge variant="outline">v{plugin.version}</Badge>
                    <Badge variant={plugin.loaded && plugin.enabled ? "default" : "secondary"}>
                      {getStatusText(plugin)}
                    </Badge>
                  </div>
                </CardHeader>

                <CardContent className="pt-0">
                  <p className="text-sm text-gray-600 mb-4 line-clamp-2">
                    {plugin.description}
                  </p>
                  
                  {plugin.author && (
                    <p className="text-xs text-gray-500 mb-3">
                      by {plugin.author}
                    </p>
                  )}

                  <div className="flex flex-wrap gap-2 mb-4">
                    {plugin.tags?.slice(0, 3).map((tag) => (
                      <Badge key={tag} variant="outline" className="text-xs">
                        {tag}
                      </Badge>
                    ))}
                  </div>

                  <div className="flex space-x-2">
                    {plugin.loaded ? (
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => handlePluginAction(plugin.name, 'unload')}
                      >
                        <Square className="h-3 w-3 mr-1" />
                        Unload
                      </Button>
                    ) : (
                      <Button
                        size="sm"
                        onClick={() => handlePluginAction(plugin.name, 'load')}
                      >
                        <Play className="h-3 w-3 mr-1" />
                        Load
                      </Button>
                    )}
                    
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => handlePluginAction(plugin.name, 'reload')}
                    >
                      <RotateCcw className="h-3 w-3 mr-1" />
                      Reload
                    </Button>
                    
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => setSelectedPlugin(plugin)}
                    >
                      <Settings className="h-3 w-3 mr-1" />
                      Config
                    </Button>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>

          {plugins.length === 0 && (
            <Card>
              <CardContent className="p-8 text-center">
                <div className="text-gray-500">
                  <Plus className="h-12 w-12 mx-auto mb-4 opacity-50" />
                  <h3 className="text-lg font-medium mb-2">No plugins installed</h3>
                  <p className="text-sm">
                    Get started by installing a plugin or creating a new one using the generator.
                  </p>
                </div>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        <TabsContent value="generator">
          <PluginGenerator onPluginGenerated={fetchPlugins} />
        </TabsContent>

        <TabsContent value="install">
          <PluginInstaller onPluginInstalled={fetchPlugins} />
        </TabsContent>
      </Tabs>

      {/* Plugin Details Modal */}
      {selectedPlugin && (
        <PluginDetailsModal
          plugin={selectedPlugin}
          onClose={() => setSelectedPlugin(null)}
          onUpdate={fetchPlugins}
        />
      )}
    </div>
  );
};

// Plugin Generator Component
const PluginGenerator = ({ onPluginGenerated }) => {
  const [formData, setFormData] = useState({
    plugin_name: '',
    framework_name: '',
    description: '',
    author: '',
    category: 'custom',
    test_cases: []
  });
  const [generating, setGenerating] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setGenerating(true);

    try {
      const response = await fetch('/api/plugin-generator/generate', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(formData),
      });

      const data = await response.json();
      
      if (data.success) {
        alert('Plugin generated successfully!');
        setFormData({
          plugin_name: '',
          framework_name: '',
          description: '',
          author: '',
          category: 'custom',
          test_cases: []
        });
        onPluginGenerated();
      } else {
        alert(`Failed to generate plugin: ${data.message}`);
      }
    } catch (error) {
      console.error('Failed to generate plugin:', error);
      alert('Failed to generate plugin');
    } finally {
      setGenerating(false);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Generate New Plugin</CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium mb-2">Plugin Name</label>
              <input
                type="text"
                className="w-full p-2 border rounded-md"
                value={formData.plugin_name}
                onChange={(e) => setFormData({...formData, plugin_name: e.target.value})}
                required
              />
            </div>
            
            <div>
              <label className="block text-sm font-medium mb-2">Framework Name</label>
              <input
                type="text"
                className="w-full p-2 border rounded-md"
                value={formData.framework_name}
                onChange={(e) => setFormData({...formData, framework_name: e.target.value})}
                required
              />
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium mb-2">Description</label>
            <textarea
              className="w-full p-2 border rounded-md"
              rows={3}
              value={formData.description}
              onChange={(e) => setFormData({...formData, description: e.target.value})}
              required
            />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium mb-2">Author</label>
              <input
                type="text"
                className="w-full p-2 border rounded-md"
                value={formData.author}
                onChange={(e) => setFormData({...formData, author: e.target.value})}
              />
            </div>
            
            <div>
              <label className="block text-sm font-medium mb-2">Category</label>
              <select
                className="w-full p-2 border rounded-md"
                value={formData.category}
                onChange={(e) => setFormData({...formData, category: e.target.value})}
              >
                <option value="custom">Custom</option>
                <option value="compliance">Compliance</option>
                <option value="security">Security</option>
                <option value="privacy">Privacy</option>
                <option value="fairness">Fairness</option>
              </select>
            </div>
          </div>

          <Button type="submit" disabled={generating} className="w-full">
            {generating ? (
              <>
                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                Generating...
              </>
            ) : (
              <>
                <Plus className="h-4 w-4 mr-2" />
                Generate Plugin
              </>
            )}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
};

// Plugin Installer Component
const PluginInstaller = ({ onPluginInstalled }) => {
  const [file, setFile] = useState(null);
  const [pluginName, setPluginName] = useState('');
  const [installing, setInstalling] = useState(false);

  const handleInstall = async (e) => {
    e.preventDefault();
    if (!file) return;

    setInstalling(true);
    const formData = new FormData();
    formData.append('file', file);
    if (pluginName) {
      formData.append('plugin_name', pluginName);
    }

    try {
      const response = await fetch('/api/plugins/install', {
        method: 'POST',
        body: formData,
      });

      const data = await response.json();
      
      if (data.success) {
        alert('Plugin installed successfully!');
        setFile(null);
        setPluginName('');
        onPluginInstalled();
      } else {
        alert(`Failed to install plugin: ${data.message}`);
      }
    } catch (error) {
      console.error('Failed to install plugin:', error);
      alert('Failed to install plugin');
    } finally {
      setInstalling(false);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Install Plugin</CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleInstall} className="space-y-4">
          <div>
            <label className="block text-sm font-medium mb-2">Plugin File</label>
            <input
              type="file"
              accept=".zip,.py"
              className="w-full p-2 border rounded-md"
              onChange={(e) => setFile(e.target.files[0])}
              required
            />
          </div>

          <div>
            <label className="block text-sm font-medium mb-2">Plugin Name (Optional)</label>
            <input
              type="text"
              className="w-full p-2 border rounded-md"
              value={pluginName}
              onChange={(e) => setPluginName(e.target.value)}
              placeholder="Leave empty to use filename"
            />
          </div>

          <Button type="submit" disabled={installing || !file} className="w-full">
            {installing ? (
              <>
                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                Installing...
              </>
            ) : (
              <>
                <Upload className="h-4 w-4 mr-2" />
                Install Plugin
              </>
            )}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
};

// Plugin Details Modal Component
const PluginDetailsModal = ({ plugin, onClose }) => {
  const [, setConfig] = useState({});
  const [, setLoading] = useState(true);

  useEffect(() => {
    fetchPluginConfig();
  // eslint-disable-next-line react-hooks/exhaustive-deps -- mount-only effect
  }, [plugin]);

  const fetchPluginConfig = async () => {
    try {
      const response = await fetch(`/api/plugins/${plugin.name}/config`);
      const data = await response.json();
      if (data.success) {
        setConfig(data.data.config);
      }
    } catch (error) {
      console.error('Failed to fetch plugin config:', error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg p-6 max-w-2xl w-full mx-4 max-h-[80vh] overflow-y-auto">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-xl font-bold">{plugin.name} Details</h2>
          <Button variant="outline" onClick={onClose}>
            ×
          </Button>
        </div>

        <div className="space-y-4">
          <div>
            <h3 className="font-medium mb-2">Plugin Information</h3>
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <span className="font-medium">Framework:</span> {plugin.framework}
              </div>
              <div>
                <span className="font-medium">Version:</span> {plugin.version}
              </div>
              <div>
                <span className="font-medium">Author:</span> {plugin.author}
              </div>
              <div>
                <span className="font-medium">Category:</span> {plugin.category}
              </div>
            </div>
          </div>

          <div>
            <h3 className="font-medium mb-2">Description</h3>
            <p className="text-sm text-gray-600">{plugin.description}</p>
          </div>

          {plugin.tags && plugin.tags.length > 0 && (
            <div>
              <h3 className="font-medium mb-2">Tags</h3>
              <div className="flex flex-wrap gap-2">
                {plugin.tags.map((tag) => (
                  <Badge key={tag} variant="outline">{tag}</Badge>
                ))}
              </div>
            </div>
          )}

          {plugin.supported_models && plugin.supported_models.length > 0 && (
            <div>
              <h3 className="font-medium mb-2">Supported Models</h3>
              <div className="flex flex-wrap gap-2">
                {plugin.supported_models.map((model) => (
                  <Badge key={model} variant="secondary">{model}</Badge>
                ))}
              </div>
            </div>
          )}

          <div className="flex space-x-2 pt-4">
            <Button
              variant="destructive"
              onClick={() => {
                if (confirm('Are you sure you want to uninstall this plugin?')) {
                  // Handle uninstall
                  onClose();
                }
              }}
            >
              <Trash2 className="h-4 w-4 mr-2" />
              Uninstall
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default PluginManager;