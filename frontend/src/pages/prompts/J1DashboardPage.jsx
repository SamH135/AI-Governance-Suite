import React, { useState, useEffect } from 'react';
import { 
  Brain, 
  Zap, 
  TrendingUp, 
  AlertTriangle, 
  Play, 
  Pause, 
  Settings, 
  BarChart3,
  Activity,
  Target,
  Cpu,
  RefreshCw
} from 'lucide-react';
import { 
  LineChart, 
  Line, 
  AreaChart, 
  Area, 
  BarChart, 
  Bar, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  Legend, 
  ResponsiveContainer,
  ScatterChart,
  Scatter
} from 'recharts';
import Card from '../../components/ui/Card';
import Button from '../../components/ui/Button';

const MetricCard = ({ title, value, change, icon: Icon, color = 'blue', status }) => {
  const colorClasses = {
    blue: 'text-blue-600 bg-blue-100',
    green: 'text-green-600 bg-green-100',
    yellow: 'text-yellow-600 bg-yellow-100',
    red: 'text-red-600 bg-red-100',
    purple: 'text-purple-600 bg-purple-100'
  };

  return (
    <Card>
      <div className="flex items-center justify-between">
        <div className="flex-1">
          <div className="flex items-center justify-between mb-2">
            <p className="text-sm font-medium text-neutral-600">{title}</p>
            {status && (
              <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                status === 'active' ? 'bg-green-100 text-green-800' :
                status === 'training' ? 'bg-yellow-100 text-yellow-800' :
                'bg-neutral-100 text-neutral-800'
              }`}>
                {status}
              </span>
            )}
          </div>
          <p className="text-2xl font-bold text-neutral-900">{value}</p>
          {change !== undefined && (
            <p className={`text-sm mt-1 ${change >= 0 ? 'text-green-600' : 'text-red-600'}`}>
              {change >= 0 ? '+' : ''}{change}% from last hour
            </p>
          )}
        </div>
        <div className={`p-3 rounded-lg ${colorClasses[color]}`}>
          <Icon className="w-6 h-6" />
        </div>
      </div>
    </Card>
  );
};

const ControlPanel = ({ title, children, status, onToggle }) => {
  return (
    <Card>
      <Card.Header>
        <div className="flex items-center justify-between">
          <Card.Title>{title}</Card.Title>
          <div className="flex items-center space-x-2">
            <span className={`px-2 py-1 rounded-full text-xs font-medium ${
              status === 'active' ? 'bg-green-100 text-green-800' :
              status === 'training' ? 'bg-yellow-100 text-yellow-800' :
              'bg-neutral-100 text-neutral-800'
            }`}>
              {status}
            </span>
            <Button
              variant="outline"
              size="sm"
              onClick={onToggle}
            >
              {status === 'active' ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
            </Button>
          </div>
        </div>
      </Card.Header>
      <Card.Content>
        {children}
      </Card.Content>
    </Card>
  );
};

const ThinkingTrace = ({ trace }) => {
  return (
    <div className="space-y-3">
      {trace.map((step, index) => (
        <div key={index} className="border-l-2 border-brand-200 pl-4">
          <div className="flex items-center space-x-2 mb-1">
            <span className="text-xs font-medium text-brand-600">Step {index + 1}</span>
            <span className="text-xs text-neutral-500">{step.duration}ms</span>
          </div>
          <p className="text-sm text-neutral-700">{step.thought}</p>
          {step.confidence && (
            <div className="mt-2">
              <div className="flex items-center justify-between text-xs">
                <span className="text-neutral-600">Confidence</span>
                <span className="font-medium">{(step.confidence * 100).toFixed(1)}%</span>
              </div>
              <div className="w-full bg-neutral-200 rounded-full h-1.5 mt-1">
                <div 
                  className="bg-brand-600 h-1.5 rounded-full" 
                  style={{ width: `${step.confidence * 100}%` }}
                ></div>
              </div>
            </div>
          )}
        </div>
      ))}
    </div>
  );
};

const J1DashboardPage = () => {
  const [systemStatus, setSystemStatus] = useState({
    j1Model: 'active',
    geneticAlgorithm: 'training',
    reinforcementLearning: 'active',
    biasDetection: 'active'
  });

  const [metrics, setMetrics] = useState({
    thinkingQuality: 87.3,
    responseTime: 245,
    tokenEfficiency: 92.1,
    biasScore: 8.2
  });

  const [performanceData] = useState([
    { time: '00:00', quality: 85, efficiency: 88, bias: 12 },
    { time: '04:00', quality: 87, efficiency: 90, bias: 10 },
    { time: '08:00', quality: 89, efficiency: 92, bias: 8 },
    { time: '12:00', quality: 87, efficiency: 89, bias: 9 },
    { time: '16:00', quality: 91, efficiency: 94, bias: 7 },
    { time: '20:00', quality: 88, efficiency: 91, bias: 8 }
  ]);

  const [geneticData] = useState([
    { generation: 1, fitness: 0.65, diversity: 0.8 },
    { generation: 5, fitness: 0.72, diversity: 0.75 },
    { generation: 10, fitness: 0.78, diversity: 0.7 },
    { generation: 15, fitness: 0.83, diversity: 0.68 },
    { generation: 20, fitness: 0.87, diversity: 0.65 },
    { generation: 25, fitness: 0.89, diversity: 0.63 }
  ]);

  const [thinkingTrace] = useState([
    {
      thought: "Analyzing the user's query about AI compliance requirements...",
      duration: 45,
      confidence: 0.92
    },
    {
      thought: "Identifying relevant regulatory frameworks (GDPR, HIPAA, SOX)...",
      duration: 67,
      confidence: 0.88
    },
    {
      thought: "Cross-referencing with industry-specific requirements...",
      duration: 123,
      confidence: 0.85
    },
    {
      thought: "Formulating comprehensive response with actionable recommendations...",
      duration: 89,
      confidence: 0.91
    }
  ]);

  const handleToggleSystem = (system) => {
    setSystemStatus(prev => ({
      ...prev,
      [system]: prev[system] === 'active' ? 'inactive' : 'active'
    }));
  };

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="page-header flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-neutral-900">J1 Model Dashboard</h1>
          <p className="text-neutral-600">
            Advanced AI model performance monitoring and control
          </p>
        </div>
        <div className="flex items-center space-x-3">
          <Button variant="outline">
            <RefreshCw className="w-4 h-4 mr-2" />
            Refresh
          </Button>
          <Button variant="outline">
            <Settings className="w-4 h-4 mr-2" />
            Configure
          </Button>
        </div>
      </div>

      {/* Key Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <MetricCard
          title="Thinking Quality"
          value={`${metrics.thinkingQuality}%`}
          change={2.1}
          icon={Brain}
          color="purple"
          status={systemStatus.j1Model}
        />
        <MetricCard
          title="Response Time"
          value={`${metrics.responseTime}ms`}
          change={-5.3}
          icon={Zap}
          color="blue"
        />
        <MetricCard
          title="Token Efficiency"
          value={`${metrics.tokenEfficiency}%`}
          change={1.8}
          icon={Target}
          color="green"
        />
        <MetricCard
          title="Bias Score"
          value={metrics.biasScore}
          change={-12.5}
          icon={AlertTriangle}
          color="yellow"
        />
      </div>

      {/* Performance Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <Card.Header>
            <Card.Title>Real-time Performance</Card.Title>
          </Card.Header>
          <Card.Content>
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={performanceData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="time" />
                <YAxis />
                <Tooltip />
                <Legend />
                <Line 
                  type="monotone" 
                  dataKey="quality" 
                  stroke="#8b5cf6" 
                  strokeWidth={2}
                  name="Thinking Quality"
                />
                <Line 
                  type="monotone" 
                  dataKey="efficiency" 
                  stroke="#10b981" 
                  strokeWidth={2}
                  name="Token Efficiency"
                />
                <Line 
                  type="monotone" 
                  dataKey="bias" 
                  stroke="#f59e0b" 
                  strokeWidth={2}
                  name="Bias Score"
                />
              </LineChart>
            </ResponsiveContainer>
          </Card.Content>
        </Card>

        <Card>
          <Card.Header>
            <Card.Title>Genetic Algorithm Evolution</Card.Title>
          </Card.Header>
          <Card.Content>
            <ResponsiveContainer width="100%" height={300}>
              <AreaChart data={geneticData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="generation" />
                <YAxis />
                <Tooltip />
                <Legend />
                <Area 
                  type="monotone" 
                  dataKey="fitness" 
                  stackId="1"
                  stroke="#3b82f6" 
                  fill="#3b82f6"
                  fillOpacity={0.6}
                  name="Fitness Score"
                />
                <Area 
                  type="monotone" 
                  dataKey="diversity" 
                  stackId="2"
                  stroke="#06b6d4" 
                  fill="#06b6d4"
                  fillOpacity={0.6}
                  name="Population Diversity"
                />
              </AreaChart>
            </ResponsiveContainer>
          </Card.Content>
        </Card>
      </div>

      {/* Control Panels */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <ControlPanel
          title="J1 Model Control"
          status={systemStatus.j1Model}
          onToggle={() => handleToggleSystem('j1Model')}
        >
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-neutral-700 mb-1">
                  Temperature
                </label>
                <input
                  type="range"
                  min="0"
                  max="2"
                  step="0.1"
                  defaultValue="0.7"
                  className="w-full"
                />
                <div className="flex justify-between text-xs text-neutral-500 mt-1">
                  <span>0.0</span>
                  <span>2.0</span>
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-neutral-700 mb-1">
                  Max Tokens
                </label>
                <input
                  type="number"
                  defaultValue="1000"
                  min="100"
                  max="4000"
                  className="input"
                />
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-neutral-700 mb-1">
                Thinking Depth
              </label>
              <select className="input">
                <option value="shallow">Shallow (Fast)</option>
                <option value="medium" selected>Medium (Balanced)</option>
                <option value="deep">Deep (Thorough)</option>
              </select>
            </div>
          </div>
        </ControlPanel>

        <ControlPanel
          title="Genetic Algorithm"
          status={systemStatus.geneticAlgorithm}
          onToggle={() => handleToggleSystem('geneticAlgorithm')}
        >
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-neutral-700 mb-1">
                  Population Size
                </label>
                <input
                  type="number"
                  defaultValue="50"
                  min="10"
                  max="200"
                  className="input"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-neutral-700 mb-1">
                  Mutation Rate
                </label>
                <input
                  type="range"
                  min="0.01"
                  max="0.5"
                  step="0.01"
                  defaultValue="0.1"
                  className="w-full"
                />
              </div>
            </div>
            <div className="text-sm text-neutral-600">
              <p>Generation: 25 | Best Fitness: 0.89 | Avg Fitness: 0.76</p>
            </div>
          </div>
        </ControlPanel>

        <ControlPanel
          title="Reinforcement Learning"
          status={systemStatus.reinforcementLearning}
          onToggle={() => handleToggleSystem('reinforcementLearning')}
        >
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-neutral-700 mb-1">
                  Learning Rate
                </label>
                <input
                  type="range"
                  min="0.001"
                  max="0.1"
                  step="0.001"
                  defaultValue="0.01"
                  className="w-full"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-neutral-700 mb-1">
                  Exploration Rate
                </label>
                <input
                  type="range"
                  min="0.1"
                  max="1.0"
                  step="0.1"
                  defaultValue="0.3"
                  className="w-full"
                />
              </div>
            </div>
            <div className="text-sm text-neutral-600">
              <p>Episodes: 1,247 | Avg Reward: 0.83 | Success Rate: 91%</p>
            </div>
          </div>
        </ControlPanel>

        <ControlPanel
          title="Bias Detection"
          status={systemStatus.biasDetection}
          onToggle={() => handleToggleSystem('biasDetection')}
        >
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-neutral-700 mb-1">
                  Sensitivity
                </label>
                <select className="input">
                  <option value="low">Low</option>
                  <option value="medium" selected>Medium</option>
                  <option value="high">High</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-neutral-700 mb-1">
                  Categories
                </label>
                <select className="input" multiple size="3">
                  <option value="gender" selected>Gender</option>
                  <option value="race" selected>Race</option>
                  <option value="age" selected>Age</option>
                </select>
              </div>
            </div>
            <div className="text-sm text-neutral-600">
              <p>Last Scan: 2 min ago | Issues Found: 0 | Confidence: 94%</p>
            </div>
          </div>
        </ControlPanel>
      </div>

      {/* Thinking Trace */}
      <Card>
        <Card.Header>
          <Card.Title>Latest Thinking Trace</Card.Title>
        </Card.Header>
        <Card.Content>
          <ThinkingTrace trace={thinkingTrace} />
        </Card.Content>
      </Card>

      {/* System Alerts */}
      <Card>
        <Card.Header>
          <Card.Title>System Alerts</Card.Title>
        </Card.Header>
        <Card.Content>
          <div className="space-y-3">
            <div className="flex items-center space-x-3 p-3 bg-yellow-50 border border-yellow-200 rounded-lg">
              <AlertTriangle className="w-5 h-5 text-yellow-600" />
              <div className="flex-1">
                <p className="text-sm font-medium text-yellow-800">
                  Genetic Algorithm Performance Degradation
                </p>
                <p className="text-xs text-yellow-700">
                  Fitness improvement has slowed in the last 5 generations. Consider adjusting mutation rate.
                </p>
              </div>
              <span className="text-xs text-yellow-600">2 min ago</span>
            </div>
            
            <div className="flex items-center space-x-3 p-3 bg-blue-50 border border-blue-200 rounded-lg">
              <Activity className="w-5 h-5 text-blue-600" />
              <div className="flex-1">
                <p className="text-sm font-medium text-blue-800">
                  High Token Usage Detected
                </p>
                <p className="text-xs text-blue-700">
                  Token consumption is 15% above normal. Monitor for efficiency optimization opportunities.
                </p>
              </div>
              <span className="text-xs text-blue-600">5 min ago</span>
            </div>

            <div className="flex items-center space-x-3 p-3 bg-green-50 border border-green-200 rounded-lg">
              <Target className="w-5 h-5 text-green-600" />
              <div className="flex-1">
                <p className="text-sm font-medium text-green-800">
                  Thinking Quality Milestone Reached
                </p>
                <p className="text-xs text-green-700">
                  J1 model has achieved 87% thinking quality score, exceeding the target threshold.
                </p>
              </div>
              <span className="text-xs text-green-600">1 hour ago</span>
            </div>
          </div>
        </Card.Content>
      </Card>
    </div>
  );
};

export default J1DashboardPage;