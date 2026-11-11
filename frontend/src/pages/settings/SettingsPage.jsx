import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import Card from '../../components/ui/Card';
import Button from '../../components/ui/Button';
import Input from '../../components/ui/Input';
import { useAuth } from '../../contexts/AuthContext';
import { Settings, User, Shield, Bell, Database } from 'lucide-react';
import logger from '../../utils/logger.js';

const SettingsPage = () => {
  logger.info('SettingsPage component rendered', 'SettingsPage.jsx', 'SettingsPage');

  const { section } = useParams();
  const navigate = useNavigate();
  const { user, updateProfile } = useAuth();

  // Map URL section to tab ID
  const getTabFromSection = (section) => {
    const sectionMap = {
      'profile': 'profile',
      'security': 'security',
      'notifications': 'notifications',
      'data': 'data'
    };
    return sectionMap[section] || 'profile';
  };

  const [activeTab, setActiveTab] = useState(getTabFromSection(section));
  const [profile, setProfile] = useState({
    fullName: user?.full_name || '',
    email: user?.email || '',
    username: user?.username || ''
  });
  const [loading, setLoading] = useState(false);

  const handleTabChange = (tabId) => {
    setActiveTab(tabId);
    navigate(`/settings/${tabId}`);
  };

  // Update active tab when URL changes
  useEffect(() => {
    if (section) {
      setActiveTab(getTabFromSection(section));
    }
  }, [section]);

  const handleProfileUpdate = async (e) => {
    e.preventDefault();
    logger.info('Profile update initiated', 'SettingsPage.jsx', 'handleProfileUpdate');
    setLoading(true);
    try {
      await updateProfile(profile);
      logger.info('Profile update successful', 'SettingsPage.jsx', 'handleProfileUpdate');
    } catch (error) {
      logger.error(`Profile update failed: ${error.message}`, 'SettingsPage.jsx', 'handleProfileUpdate');
    } finally {
      setLoading(false);
    }
  };

  const tabs = [
    { id: 'profile', name: 'Profile', icon: User },
    { id: 'security', name: 'Security', icon: Shield },
    { id: 'notifications', name: 'Notifications', icon: Bell },
    { id: 'data', name: 'Data Management', icon: Database }
  ];

  const renderTabContent = () => {
    switch (activeTab) {
      case 'profile':
        return (
          <Card>
            <Card.Header>
              <Card.Title>Profile Information</Card.Title>
              <Card.Description>Update your personal information and account details</Card.Description>
            </Card.Header>
            <Card.Content>
              <form onSubmit={handleProfileUpdate} className="space-y-4">
                <Input
                  label="Full Name"
                  value={profile.fullName}
                  onChange={(e) => setProfile(prev => ({ ...prev, fullName: e.target.value }))}
                  placeholder="Enter your full name"
                />
                <Input
                  label="Email Address"
                  type="email"
                  value={profile.email}
                  onChange={(e) => setProfile(prev => ({ ...prev, email: e.target.value }))}
                  placeholder="Enter your email address"
                />
                <Input
                  label="Username"
                  value={profile.username}
                  onChange={(e) => setProfile(prev => ({ ...prev, username: e.target.value }))}
                  placeholder="Enter your username"
                />
                <div className="flex gap-3 pt-4">
                  <Button
                    type="submit"
                    variant="primary"
                    loading={loading}
                    disabled={loading}
                  >
                    Save Changes
                  </Button>
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => setProfile({
                      fullName: user?.full_name || '',
                      email: user?.email || '',
                      username: user?.username || ''
                    })}
                  >
                    Reset
                  </Button>
                </div>
              </form>
            </Card.Content>
          </Card>
        );

      case 'security':
        return (
          <div className="space-y-6">
            <Card>
              <Card.Header>
                <Card.Title>Password & Authentication</Card.Title>
                <Card.Description>Manage your account security settings</Card.Description>
              </Card.Header>
              <Card.Content className="space-y-3">
                <Button variant="outline" className="w-full justify-start">
                  Change Password
                </Button>
                <Button variant="outline" className="w-full justify-start">
                  Enable Two-Factor Authentication
                </Button>
                <Button variant="outline" className="w-full justify-start">
                  View Active Sessions
                </Button>
                <Button variant="outline" className="w-full justify-start text-red-600 hover:text-red-700">
                  Revoke All Sessions
                </Button>
              </Card.Content>
            </Card>
          </div>
        );

      case 'notifications':
        return (
          <Card>
            <Card.Header>
              <Card.Title>Notification Preferences</Card.Title>
              <Card.Description>Configure how you receive notifications</Card.Description>
            </Card.Header>
            <Card.Content className="space-y-4">
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <div>
                    <h4 className="font-medium">Email Notifications</h4>
                    <p className="text-sm text-neutral-600">Receive updates via email</p>
                  </div>
                  <input type="checkbox" className="rounded" defaultChecked />
                </div>
                <div className="flex items-center justify-between">
                  <div>
                    <h4 className="font-medium">Test Completion Alerts</h4>
                    <p className="text-sm text-neutral-600">Get notified when compliance tests finish</p>
                  </div>
                  <input type="checkbox" className="rounded" defaultChecked />
                </div>
                <div className="flex items-center justify-between">
                  <div>
                    <h4 className="font-medium">System Status Updates</h4>
                    <p className="text-sm text-neutral-600">Receive notifications about system changes</p>
                  </div>
                  <input type="checkbox" className="rounded" />
                </div>
              </div>
              <Button variant="primary" className="mt-4">
                Save Preferences
              </Button>
            </Card.Content>
          </Card>
        );

      case 'data':
        return (
          <Card>
            <Card.Header>
              <Card.Title>Data Management</Card.Title>
              <Card.Description>Manage your data and privacy settings</Card.Description>
            </Card.Header>
            <Card.Content className="space-y-4">
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <div>
                    <h4 className="font-medium">Export Your Data</h4>
                    <p className="text-sm text-neutral-600">Download all your data in a machine-readable format</p>
                  </div>
                  <Button variant="outline" size="sm">
                    Export
                  </Button>
                </div>
                <div className="flex items-center justify-between">
                  <div>
                    <h4 className="font-medium">Delete Test Results</h4>
                    <p className="text-sm text-neutral-600">Remove historical test results older than 90 days</p>
                  </div>
                  <Button variant="outline" size="sm">
                    Cleanup
                  </Button>
                </div>
                <div className="flex items-center justify-between">
                  <div>
                    <h4 className="font-medium text-red-600">Delete Account</h4>
                    <p className="text-sm text-neutral-600">Permanently delete your account and all data</p>
                  </div>
                  <Button variant="outline" size="sm" className="text-red-600 hover:text-red-700">
                    Delete
                  </Button>
                </div>
              </div>
            </Card.Content>
          </Card>
        );

      default:
        return null;
    }
  };

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="page-header">
        <h1 className="text-2xl font-bold text-neutral-900">Settings</h1>
        <p className="text-neutral-600">
          Manage your account and preferences
        </p>
      </div>

      {/* Tabs */}
      <div className="border-b border-neutral-200">
        <nav className="flex space-x-8">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => handleTabChange(tab.id)}
              className={`flex items-center px-1 py-4 border-b-2 font-medium text-sm transition-colors ${
                activeTab === tab.id
                  ? 'border-brand-500 text-brand-600'
                  : 'border-transparent text-neutral-500 hover:text-neutral-700 hover:border-neutral-300'
              }`}
            >
              <tab.icon className="w-4 h-4 mr-2" />
              {tab.name}
            </button>
          ))}
        </nav>
      </div>

      {/* Tab Content */}
      {renderTabContent()}
    </div>
  );
};

export default SettingsPage;
