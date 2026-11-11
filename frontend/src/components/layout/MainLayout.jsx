import React from 'react';
import { Outlet } from 'react-router-dom';
import Sidebar from './Sidebar';
import Header from './Header';
import { useApp } from '../../contexts/AppContext';
import logger from '../../utils/logger.js';

const MainLayout = () => {
  logger.info('MainLayout component initialized', 'MainLayout.jsx', 'MainLayout');
  const { sidebar } = useApp();
  
  logger.debug(`MainLayout: Sidebar state - collapsed: ${sidebar.collapsed}`, 'MainLayout.jsx', 'MainLayout');

  return (
    <div className="flex h-screen bg-neutral-50">
      <Sidebar />
      <div className={`flex-1 flex flex-col transition-all duration-300 ${
        sidebar.collapsed ? 'ml-16' : 'ml-64'
      }`}>
        <Header />
        <main className="flex-1 overflow-auto p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
};

export default MainLayout;