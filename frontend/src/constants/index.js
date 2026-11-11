import logger from '../utils/logger.js';

logger.debug('Loading application constants', 'constants/index.js', 'init');

export const API_ENDPOINTS = {
  AUTH: '/auth',
  SYSTEMS: '/systems',
  TESTS: '/tests',
  PROMPTS: '/prompts',
  DOCUMENTS: '/documents',
  ANALYTICS: '/analytics'
};

export const TEST_STATUSES = {
  PENDING: 'pending',
  RUNNING: 'running',
  PASSED: 'passed',
  FAILED: 'failed',
  WARNING: 'warning'
};

export const SYSTEM_STATUSES = {
  ACTIVE: 'active',
  INACTIVE: 'inactive',
  TESTING: 'testing',
  PENDING: 'pending'
};

export const COMPLIANCE_FRAMEWORKS = [
  'GDPR',
  'HIPAA', 
  'SOX',
  'PCI DSS',
  'CCPA',
  'FDA',
  'FTC'
];

export const INDUSTRIES = [
  'healthcare',
  'finance',
  'technology',
  'retail',
  'manufacturing',
  'other'
];

export const RISK_LEVELS = [
  'low',
  'medium', 
  'high',
  'critical'
];