import { useState } from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import {
  LayoutDashboard,
  Shield,
  FileText,
  Zap,
  Settings,
  ChevronLeft,
  ChevronRight,
  ChevronDown,
  Database,
  User,
  Lock,
  Bell
} from 'lucide-react';
import { useApp } from '../../contexts/AppContext';

const navigation = [
  { name: 'Dashboard', href: '/', icon: LayoutDashboard },
  {
    name: 'AI Systems & Testing',
    href: '/compliance',
    icon: Shield,
    children: [
      {
        name: 'Setup',
        href: '/compliance/setup',
        icon: Settings,
        children: [
          { name: 'API Keys', href: '/compliance/api-keys' },
          { name: 'Model Configurations', href: '/compliance/models' }
        ]
      },
      { name: 'AI Systems', href: '/compliance/systems' },
      { name: 'RAG Testing', href: '/compliance/rag' },
      { name: 'Test Configurations', href: '/compliance/test/configure' },
      { name: 'Test Results', href: '/compliance/results' }
    ]
  },
  {
    name: 'Prompt Engineering',
    href: '/prompts',
    icon: Zap,
    children: [
      { name: 'Categories', href: '/prompts/categories' },
      { name: 'Engineering Lab', href: '/prompts/engineering' },
      { name: 'J1 Dashboard', href: '/prompts/j1-dashboard' }
    ]
  },
  {
    name: 'Documentation',
    href: '/documents',
    icon: FileText,
    children: [
      { name: 'Report Generator', href: '/documents/generator' },
      { name: 'Templates', href: '/documents/templates' }
    ]
  },
  {
    name: 'Settings',
    href: '/settings',
    icon: Settings,
    children: [
      { name: 'Data Management', href: '/settings/data', icon: Database },
      { name: 'Profile', href: '/settings/profile', icon: User },
      { name: 'Security', href: '/settings/security', icon: Lock },
      { name: 'Notifications', href: '/settings/notifications', icon: Bell }
    ]
  },
];

const Sidebar = () => {
  const { sidebar, toggleSidebar } = useApp();
  const location = useLocation();
  const [expandedItems, setExpandedItems] = useState({});

  const toggleExpanded = (itemName) => {
    setExpandedItems(prev => ({
      ...prev,
      [itemName]: !prev[itemName]
    }));
  };

  const renderNavItem = (item, level = 0) => {
    const isActive = location.pathname === item.href ||
      (item.href !== '/' && location.pathname.startsWith(item.href));
    const isExpanded = expandedItems[item.name];
    const hasChildren = item.children && item.children.length > 0;

    return (
      <li key={item.name}>
        {hasChildren && !sidebar.collapsed ? (
          <div>
            <button
              onClick={() => toggleExpanded(item.name)}
              className={`flex items-center justify-between w-full px-3 py-2 text-sm font-medium rounded-md transition-colors ${
                isActive
                  ? 'bg-brand-100 text-brand-700'
                  : 'text-neutral-600 hover:bg-neutral-100 hover:text-neutral-900'
              }`}
            >
              <div className="flex items-center">
                {item.icon && <item.icon className={`flex-shrink-0 w-5 h-5 ${level > 0 ? 'mr-2' : 'mr-3'}`} />}
                {item.name}
              </div>
              <ChevronDown className={`w-4 h-4 transition-transform ${
                isExpanded ? 'transform rotate-180' : ''
              }`} />
            </button>
            {isExpanded && (
              <ul className={`mt-1 space-y-1 ${level > 0 ? 'ml-4' : 'ml-8'}`}>
                {item.children.map((child) => {
                  const childHasChildren = child.children && child.children.length > 0;
                  const childIsActive = location.pathname === child.href;
                  const childIsExpanded = expandedItems[child.name];

                  if (childHasChildren) {
                    // Nested children - recursively render
                    return (
                      <div key={child.name}>
                        <button
                          onClick={() => toggleExpanded(child.name)}
                          className={`flex items-center justify-between w-full px-3 py-2 text-sm font-medium rounded-md transition-colors ${
                            childIsActive
                              ? 'bg-brand-50 text-brand-600'
                              : 'text-neutral-600 hover:bg-neutral-50 hover:text-neutral-900'
                          }`}
                        >
                          <div className="flex items-center">
                            {child.icon && <child.icon className="flex-shrink-0 w-4 h-4 mr-2" />}
                            {child.name}
                          </div>
                          <ChevronDown className={`w-3 h-3 transition-transform ${
                            childIsExpanded ? 'transform rotate-180' : ''
                          }`} />
                        </button>
                        {childIsExpanded && (
                          <ul className="mt-1 ml-4 space-y-1">
                            {child.children.map((grandchild) => {
                              const grandchildIsActive = location.pathname === grandchild.href;
                              return (
                                <li key={grandchild.name}>
                                  <NavLink
                                    to={grandchild.href}
                                    className={`block px-3 py-2 text-sm rounded-md transition-colors ${
                                      grandchildIsActive
                                        ? 'bg-brand-50 text-brand-600 font-medium'
                                        : 'text-neutral-600 hover:bg-neutral-50 hover:text-neutral-900'
                                    }`}
                                  >
                                    {grandchild.name}
                                  </NavLink>
                                </li>
                              );
                            })}
                          </ul>
                        )}
                      </div>
                    );
                  } else {
                    // Regular child
                    return (
                      <li key={child.name}>
                        <NavLink
                          to={child.href}
                          className={`flex items-center px-3 py-2 text-sm rounded-md transition-colors ${
                            childIsActive
                              ? 'bg-brand-50 text-brand-600 font-medium'
                              : 'text-neutral-600 hover:bg-neutral-50 hover:text-neutral-900'
                          }`}
                        >
                          {child.icon && <child.icon className="flex-shrink-0 w-4 h-4 mr-2" />}
                          {child.name}
                        </NavLink>
                      </li>
                    );
                  }
                })}
              </ul>
            )}
          </div>
        ) : (
          <NavLink
            to={item.href}
            className={`flex items-center px-3 py-2 text-sm font-medium rounded-md transition-colors ${
              isActive
                ? 'bg-brand-100 text-brand-700'
                : 'text-neutral-600 hover:bg-neutral-100 hover:text-neutral-900'
            }`}
            title={sidebar.collapsed ? item.name : undefined}
          >
            {item.icon && <item.icon className={`flex-shrink-0 w-5 h-5 ${
              sidebar.collapsed ? '' : 'mr-3'
            }`} />}
            {!sidebar.collapsed && item.name}
          </NavLink>
        )}
      </li>
    );
  };

  return (
    <div className={`fixed inset-y-0 left-0 z-50 bg-white border-r border-neutral-200 transition-all duration-300 ${
      sidebar.collapsed ? 'w-16' : 'w-64'
    }`}>
      {/* Logo */}
      <div className="flex items-center justify-between h-16 px-4 border-b border-neutral-200">
        {!sidebar.collapsed && (
          <h1 className="text-xl font-bold text-brand-600">AI Compliance</h1>
        )}
        <button
          onClick={toggleSidebar}
          className="p-1.5 rounded-md hover:bg-neutral-100 transition-colors"
        >
          {sidebar.collapsed ? (
            <ChevronRight className="w-5 h-5" />
          ) : (
            <ChevronLeft className="w-5 h-5" />
          )}
        </button>
      </div>

      {/* Navigation */}
      <nav className="mt-8 px-3">
        <ul className="space-y-2">
          {navigation.map((item) => renderNavItem(item, 0))}
        </ul>
      </nav>
    </div>
  );
};

export default Sidebar;