import React, { useState, useEffect } from 'react';
import { 
  TrendingUp, 
  BarChart3, 
  PieChart, 
  Download, 
  Filter,
  Calendar,
  RefreshCw
} from 'lucide-react';
import { 
  LineChart, 
  Line, 
  BarChart, 
  Bar, 
  PieChart as RechartsPieChart,
  Pie,
  Cell, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  Legend, 
  ResponsiveContainer,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar
} from 'recharts';
// Import UI components
import Card from '../../components/ui/Card';
import Button from '../../components/ui/Button';
import { analyticsService } from '../../services/apiService';

const COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#06b6d4'];

const MetricCard = ({ title, value, change, icon: Icon, color = 'blue' }) => {
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
        <div>
          <p className="text-sm font-medium text-neutral-600">{title}</p>
          <p className="text-2xl font-bold text-neutral-900">{value}</p>
          {change && (
            <p className={`text-sm ${change >= 0 ? 'text-green-600' : 'text-red-600'}`}>
              {change >= 0 ? '+' : ''}{change}% from last month
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

const AnalyticsPage = () => {
  const [timeRange, setTimeRange] = useState('30d');
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState({
    metrics: {
      totalTests: 156,
      avgComplianceScore: 87,
      activeModels: 12,
      criticalIssues: 3
    },
    performanceTrend: [
      { name: 'Jan', compliance: 82, performance: 78, security: 85 },
      { name: 'Feb', compliance: 85, performance: 82, security: 88 },
      { name: 'Mar', compliance: 87, performance: 85, security: 90 },
      { name: 'Apr', compliance: 89, performance: 88, security: 87 },
      { name: 'May', compliance: 91, performance: 90, security: 92 },
      { name: 'Jun', compliance: 87, performance: 87, security: 89 }
    ],
    modelComparison: [
      { name: 'GPT-4', score: 92, tests: 45 },
      { name: 'Claude-3', score: 88, tests: 38 },
      { name: 'Llama-2', score: 85, tests: 32 },
      { name: 'BERT', score: 79, tests: 28 },
      { name: 'Custom', score: 83, tests: 13 }
    ],
    riskDistribution: [
      { name: 'Low Risk', value: 65, color: '#10b981' },
      { name: 'Medium Risk', value: 25, color: '#f59e0b' },
      { name: 'High Risk', value: 8, color: '#ef4444' },
      { name: 'Critical', value: 2, color: '#dc2626' }
    ],
    complianceRadar: [
      { framework: 'GDPR', score: 92 },
      { framework: 'HIPAA', score: 88 },
      { framework: 'SOX', score: 85 },
      { framework: 'PCI DSS', score: 90 },
      { framework: 'CCPA', score: 87 },
      { framework: 'FDA', score: 82 }
    ]
  });

  useEffect(() => {
    const fetchAnalytics = async () => {
      try {
        setLoading(true);
        // In a real app, this would fetch from the API
        await new Promise(resolve => setTimeout(resolve, 1000));
        // Data is already set in state for demo
      } catch (error) {
        console.error('Failed to fetch analytics:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchAnalytics();
  }, [timeRange]);

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="animate-pulse">
          <div className="h-8 bg-neutral-200 rounded w-1/4 mb-6"></div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
            {[...Array(4)].map((_, i) => (
              <div key={i} className="h-24 bg-neutral-200 rounded"></div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="page-header flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-neutral-900">Analytics Dashboard</h1>
          <p className="text-neutral-600">
            Comprehensive insights into your AI compliance performance
          </p>
        </div>
        <div className="flex items-center space-x-3">
          <select
            value={timeRange}
            onChange={(e) => setTimeRange(e.target.value)}
            className="input w-auto"
          >
            <option value="7d">Last 7 days</option>
            <option value="30d">Last 30 days</option>
            <option value="90d">Last 90 days</option>
            <option value="1y">Last year</option>
          </select>
          <Button variant="outline">
            <RefreshCw className="w-4 h-4 mr-2" />
            Refresh
          </Button>
          <Button variant="outline">
            <Download className="w-4 h-4 mr-2" />
            Export
          </Button>
        </div>
      </div>

      {/* Key Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <MetricCard
          title="Total Tests"
          value={data.metrics.totalTests}
          change={12}
          icon={BarChart3}
          color="blue"
        />
        <MetricCard
          title="Avg Compliance Score"
          value={`${data.metrics.avgComplianceScore}%`}
          change={5}
          icon={TrendingUp}
          color="green"
        />
        <MetricCard
          title="Active Models"
          value={data.metrics.activeModels}
          change={-2}
          icon={PieChart}
          color="purple"
        />
        <MetricCard
          title="Critical Issues"
          value={data.metrics.criticalIssues}
          change={-25}
          icon={TrendingUp}
          color="red"
        />
      </div>

      {/* Charts Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Performance Trend */}
        <Card>
          <Card.Header>
            <Card.Title>Performance Trends</Card.Title>
          </Card.Header>
          <Card.Content>
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={data.performanceTrend}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="name" />
                <YAxis />
                <Tooltip />
                <Legend />
                <Line 
                  type="monotone" 
                  dataKey="compliance" 
                  stroke="#3b82f6" 
                  strokeWidth={2}
                  name="Compliance"
                />
                <Line 
                  type="monotone" 
                  dataKey="performance" 
                  stroke="#10b981" 
                  strokeWidth={2}
                  name="Performance"
                />
                <Line 
                  type="monotone" 
                  dataKey="security" 
                  stroke="#f59e0b" 
                  strokeWidth={2}
                  name="Security"
                />
              </LineChart>
            </ResponsiveContainer>
          </Card.Content>
        </Card>

        {/* Model Comparison */}
        <Card>
          <Card.Header>
            <Card.Title>Model Performance Comparison</Card.Title>
          </Card.Header>
          <Card.Content>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={data.modelComparison}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="name" />
                <YAxis />
                <Tooltip />
                <Bar dataKey="score" fill="#3b82f6" name="Compliance Score" />
              </BarChart>
            </ResponsiveContainer>
          </Card.Content>
        </Card>

        {/* Risk Distribution */}
        <Card>
          <Card.Header>
            <Card.Title>Risk Distribution</Card.Title>
          </Card.Header>
          <Card.Content>
            <ResponsiveContainer width="100%" height={300}>
              <RechartsPieChart>
                {/* Pie chart component from recharts */}
                <Pie
                  data={data.riskDistribution}
                  cx="50%"
                  cy="50%"
                  labelLine={false}
                  label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                  outerRadius={80}
                  fill="#8884d8"
                  dataKey="value"
                >
                  {data.riskDistribution.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip />
              </RechartsPieChart>
            </ResponsiveContainer>
          </Card.Content>
        </Card>

        {/* Compliance Radar */}
        <Card>
          <Card.Header>
            <Card.Title>Compliance Framework Scores</Card.Title>
          </Card.Header>
          <Card.Content>
            <ResponsiveContainer width="100%" height={300}>
              <RadarChart data={data.complianceRadar}>
                <PolarGrid />
                <PolarAngleAxis dataKey="framework" />
                <PolarRadiusAxis angle={90} domain={[0, 100]} />
                <Radar
                  name="Compliance Score"
                  dataKey="score"
                  stroke="#3b82f6"
                  fill="#3b82f6"
                  fillOpacity={0.3}
                />
                <Tooltip />
              </RadarChart>
            </ResponsiveContainer>
          </Card.Content>
        </Card>
      </div>

      {/* Detailed Analytics Table */}
      <Card>
        <Card.Header>
          <div className="flex items-center justify-between">
            <Card.Title>Recent Test Results</Card.Title>
            <Button variant="outline" size="sm">
              <Filter className="w-4 h-4 mr-2" />
              Filter
            </Button>
          </div>
        </Card.Header>
        <Card.Content>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-neutral-200">
                  <th className="text-left py-3 px-4 font-medium text-neutral-900">System</th>
                  <th className="text-left py-3 px-4 font-medium text-neutral-900">Model</th>
                  <th className="text-left py-3 px-4 font-medium text-neutral-900">Score</th>
                  <th className="text-left py-3 px-4 font-medium text-neutral-900">Risk Level</th>
                  <th className="text-left py-3 px-4 font-medium text-neutral-900">Date</th>
                  <th className="text-left py-3 px-4 font-medium text-neutral-900">Status</th>
                </tr>
              </thead>
              <tbody>
                {[
                  { system: 'Healthcare AI', model: 'GPT-4', score: 92, risk: 'Low', date: '2024-01-15', status: 'Passed' },
                  { system: 'Financial Risk', model: 'Claude-3', score: 78, risk: 'Medium', date: '2024-01-14', status: 'Warning' },
                  { system: 'Content Moderation', model: 'BERT', score: 95, risk: 'Low', date: '2024-01-13', status: 'Passed' },
                  { system: 'Fraud Detection', model: 'Custom', score: 65, risk: 'High', date: '2024-01-12', status: 'Failed' }
                ].map((row, index) => (
                  <tr key={index} className="border-b border-neutral-100 hover:bg-neutral-50">
                    <td className="py-3 px-4 font-medium">{row.system}</td>
                    <td className="py-3 px-4 text-neutral-600">{row.model}</td>
                    <td className="py-3 px-4">
                      <span className={`font-medium ${
                        row.score >= 80 ? 'text-green-600' : 
                        row.score >= 60 ? 'text-yellow-600' : 'text-red-600'
                      }`}>
                        {row.score}%
                      </span>
                    </td>
                    <td className="py-3 px-4">
                      <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                        row.risk === 'Low' ? 'bg-green-100 text-green-800' :
                        row.risk === 'Medium' ? 'bg-yellow-100 text-yellow-800' :
                        'bg-red-100 text-red-800'
                      }`}>
                        {row.risk}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-neutral-600">{row.date}</td>
                    <td className="py-3 px-4">
                      <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                        row.status === 'Passed' ? 'bg-green-100 text-green-800' :
                        row.status === 'Warning' ? 'bg-yellow-100 text-yellow-800' :
                        'bg-red-100 text-red-800'
                      }`}>
                        {row.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card.Content>
      </Card>
    </div>
  );
};

export default AnalyticsPage;