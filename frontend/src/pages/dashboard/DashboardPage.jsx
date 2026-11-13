import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import {
  Shield,
  FileText,
  Zap,
  AlertTriangle,
  CheckCircle,
  Clock,
  Rocket
} from 'lucide-react';
import Card from '../../components/ui/Card';
import Button from '../../components/ui/Button';
import SetupProgressTracker from '../../components/dashboard/SetupProgressTracker';
import QuickSetupWizard from '../../components/dashboard/QuickSetupWizard';
import { analyticsService } from '../../services/apiService';
import logger from '../../utils/logger.js';

const MetricCard = ({ title, value, icon: Icon, trend, color = 'blue' }) => {
  logger.debug(`MetricCard rendered: ${title} = ${value}`, 'DashboardPage.jsx', 'MetricCard');
  const colorClasses = {
    blue: 'text-blue-600 bg-blue-100',
    green: 'text-green-600 bg-green-100',
    yellow: 'text-yellow-600 bg-yellow-100',
    red: 'text-red-600 bg-red-100'
  };

  return (
    <Card>
      <div className="flex items-center">
        <div className={`p-3 rounded-lg ${colorClasses[color]}`}>
          <Icon className="w-6 h-6" />
        </div>
        <div className="ml-4 flex-1">
          <p className="text-sm font-medium text-neutral-600">{title}</p>
          <div className="flex items-center">
            <p className="text-2xl font-semibold text-neutral-900">{value}</p>
            {trend && (
              <span className={`ml-2 text-sm ${
                trend > 0 ? 'text-green-600' : 'text-red-600'
              }`}>
                {trend > 0 ? '+' : ''}{trend}%
              </span>
            )}
          </div>
        </div>
      </div>
    </Card>
  );
};

const QuickAction = ({ title, description, icon: Icon, to, color = 'blue' }) => {
  logger.debug(`QuickAction rendered: ${title} -> ${to}`, 'DashboardPage.jsx', 'QuickAction');
  const colorClasses = {
    blue: 'text-blue-600 bg-blue-50 hover:bg-blue-100',
    green: 'text-green-600 bg-green-50 hover:bg-green-100',
    purple: 'text-purple-600 bg-purple-50 hover:bg-purple-100',
    orange: 'text-orange-600 bg-orange-50 hover:bg-orange-100'
  };

  return (
    <Link
      to={to}
      className={`block p-4 rounded-lg border-2 border-dashed border-neutral-200 hover:border-neutral-300 transition-colors ${colorClasses[color]}`}
    >
      <div className="flex items-center">
        <Icon className="w-8 h-8" />
        <div className="ml-3">
          <h3 className="text-sm font-medium text-neutral-900">{title}</h3>
          <p className="text-xs text-neutral-600">{description}</p>
        </div>
      </div>
    </Link>
  );
};

const DashboardPage = () => {
  logger.info('DashboardPage component initialized', 'DashboardPage.jsx', 'DashboardPage');
  
  const [metrics, setMetrics] = useState({
    totalSystems: 0,
    activeTests: 0,
    complianceScore: 0
  });
  const [loading, setLoading] = useState(true);
  const [showQuickSetup, setShowQuickSetup] = useState(false);

  useEffect(() => {
    const fetchMetrics = async () => {
      logger.info('DashboardPage: Fetching dashboard metrics', 'DashboardPage.jsx', 'fetchMetrics');
      try {
        const data = await analyticsService.getDashboardMetrics();
        setMetrics(data);
        logger.info('DashboardPage: Dashboard metrics loaded successfully', 'DashboardPage.jsx', 'fetchMetrics');
      } catch (error) {
        logger.error(`DashboardPage: Failed to fetch dashboard metrics: ${error.message}`, 'DashboardPage.jsx', 'fetchMetrics');
      } finally {
        setLoading(false);
      }
    };

    fetchMetrics();
  }, []);

  if (loading) {
    logger.debug('DashboardPage: Showing loading state', 'DashboardPage.jsx', 'DashboardPage');
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
  
  logger.debug('DashboardPage: Rendering dashboard with metrics', 'DashboardPage.jsx', 'DashboardPage');

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="page-header flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-neutral-900">Dashboard</h1>
          <p className="text-neutral-600">
            Welcome to your AI Compliance Platform overview
          </p>
        </div>
        <Button onClick={() => setShowQuickSetup(true)}>
          <Rocket className="w-4 h-4 mr-2" />
          Quick Setup
        </Button>
      </div>

      {/* Metrics Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <MetricCard
          title="AI Systems"
          value={metrics.totalSystems}
          icon={Shield}
          trend={5}
          color="blue"
        />
        <MetricCard
          title="Active Tests"
          value={metrics.activeTests}
          icon={Clock}
          color="yellow"
        />
        <MetricCard
          title="Compliance Score"
          value={`${metrics.complianceScore}%`}
          icon={CheckCircle}
          trend={2}
          color="green"
        />
      </div>

      {/* Setup Progress Tracker */}
      <SetupProgressTracker onQuickSetup={() => setShowQuickSetup(true)} />

      {/* Quick Actions */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        <QuickAction
          title="Run Compliance Test"
          description="Test your AI systems for compliance"
          icon={Shield}
          to="/compliance/systems"
          color="blue"
        />
        <QuickAction
          title="Generate Prompts"
          description="Create and optimize AI prompts"
          icon={Zap}
          to="/prompts/engineering"
          color="purple"
        />
        <QuickAction
          title="Create Document"
          description="Generate compliance documentation"
          icon={FileText}
          to="/documents/generator"
          color="green"
        />
      </div>

      {/* Recent Activity */}
      <Card>
        <Card.Header>
          <Card.Title>Recent Test Results</Card.Title>
        </Card.Header>
        <Card.Content>
          <div className="space-y-3">
            {[
              { name: 'Healthcare AI Model', status: 'passed', time: '2 hours ago' },
              { name: 'Financial Risk Assessment', status: 'warning', time: '4 hours ago' },
              { name: 'Content Moderation System', status: 'passed', time: '1 day ago' }
            ].map((test, index) => (
              <div key={index} className="flex items-center justify-between py-2">
                <div className="flex items-center">
                  {test.status === 'passed' ? (
                    <CheckCircle className="w-4 h-4 text-green-500 mr-2" />
                  ) : (
                    <AlertTriangle className="w-4 h-4 text-yellow-500 mr-2" />
                  )}
                  <span className="text-sm font-medium">{test.name}</span>
                </div>
                <span className="text-xs text-neutral-500">{test.time}</span>
              </div>
            ))}
          </div>
          <div className="mt-4">
            <Link to="/compliance/results">
              <Button variant="outline" size="sm" className="w-full">
                View All Results
              </Button>
            </Link>
          </div>
        </Card.Content>
      </Card>

      {/* Quick Setup Wizard Modal */}
      {showQuickSetup && (
        <QuickSetupWizard onClose={() => setShowQuickSetup(false)} />
      )}
    </div>
  );
};

export default DashboardPage;