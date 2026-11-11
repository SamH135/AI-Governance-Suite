-- Unified AI Compliance Platform Database Schema
-- This script initializes the PostgreSQL database with all required tables

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Users table (enhanced from existing schema)
CREATE TABLE users (
    user_id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(100) NOT NULL,
    email VARCHAR(255) UNIQUE,
    role VARCHAR(50) DEFAULT 'user' CHECK (role IN ('admin', 'user', 'viewer')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP WITH TIME ZONE,
    is_active BOOLEAN DEFAULT TRUE
);

-- AI Systems table (enhanced)
CREATE TABLE ai_systems (
    system_id             SERIAL PRIMARY KEY,
    name                  VARCHAR(100) NOT NULL,
    description           TEXT,
    version               VARCHAR(50),
    system_type           VARCHAR(50) DEFAULT 'llm' CHECK (system_type IN ('llm', 'ml', 'hybrid')),
    compliance_frameworks TEXT[],
    industry              VARCHAR(100),
    model_config_id       INTEGER, -- FK to ai_model_configs; added after that table is created
    created_at            TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at            TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    user_id               INTEGER REFERENCES users(user_id) ON DELETE CASCADE,
    UNIQUE(user_id, name)
);

-- Compliance frameworks
CREATE TABLE compliance_frameworks (
    framework_id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    version VARCHAR(20),
    requirements JSONB,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Framework requirements
CREATE TABLE framework_requirements (
    requirement_id SERIAL PRIMARY KEY,
    framework_id INTEGER REFERENCES compliance_frameworks(framework_id) ON DELETE CASCADE,
    requirement_code VARCHAR(50),
    title VARCHAR(255),
    description TEXT,
    category VARCHAR(100),
    severity VARCHAR(20) DEFAULT 'medium' CHECK (severity IN ('low', 'medium', 'high', 'critical'))
);

-- Tests table (enhanced from existing schema)
CREATE TABLE tests (
    test_id SERIAL PRIMARY KEY,
    system_id INTEGER REFERENCES ai_systems(system_id) ON DELETE CASCADE,
    framework_id INTEGER REFERENCES compliance_frameworks(framework_id),
    test_name VARCHAR(100) NOT NULL,
    test_type VARCHAR(50) NOT NULL,
    configuration JSONB,
    status VARCHAR(50) DEFAULT 'pending' CHECK (status IN ('pending', 'running', 'completed', 'failed', 'cancelled')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_by INTEGER REFERENCES users(user_id)
);

-- Test results table (enhanced)
-- model_id FK is added after the models table is created
CREATE TABLE test_results (
    result_id       SERIAL PRIMARY KEY,
    test_id         INTEGER REFERENCES tests(test_id) ON DELETE CASCADE,
    score           DECIMAL(5,2),
    passed          BOOLEAN,
    details         JSONB,
    recommendations TEXT[],
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Document templates
CREATE TABLE document_templates (
    template_id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    template_type VARCHAR(50),
    content JSONB NOT NULL,
    framework VARCHAR(50),
    version VARCHAR(20) DEFAULT '1.0',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_by INTEGER REFERENCES users(user_id)
);

-- Generated documents
CREATE TABLE generated_documents (
    document_id SERIAL PRIMARY KEY,
    template_id INTEGER REFERENCES document_templates(template_id),
    system_id INTEGER REFERENCES ai_systems(system_id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL,
    content JSONB,
    format VARCHAR(20) DEFAULT 'pdf' CHECK (format IN ('pdf', 'html', 'markdown', 'docx')),
    file_path TEXT,
    status VARCHAR(50) DEFAULT 'draft' CHECK (status IN ('draft', 'review', 'approved', 'published')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_by INTEGER REFERENCES users(user_id)
);

-- Prompt categories
CREATE TABLE prompt_categories (
    category_id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    framework VARCHAR(50)
);

-- Generated prompts
CREATE TABLE generated_prompts (
    prompt_id SERIAL PRIMARY KEY,
    category_id INTEGER REFERENCES prompt_categories(category_id),
    system_id INTEGER REFERENCES ai_systems(system_id) ON DELETE CASCADE,
    text TEXT NOT NULL,
    metadata JSONB,
    thinking_trace JSONB,
    approval_status VARCHAR(50) DEFAULT 'pending' CHECK (approval_status IN ('pending', 'approved', 'rejected', 'needs_review')),
    feedback_score DECIMAL(3,2),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_by INTEGER REFERENCES users(user_id)
);

-- Prompt feedback
CREATE TABLE prompt_feedback (
    feedback_id SERIAL PRIMARY KEY,
    prompt_id INTEGER REFERENCES generated_prompts(prompt_id) ON DELETE CASCADE,
    user_id INTEGER REFERENCES users(user_id),
    is_approved BOOLEAN,
    feedback_text TEXT,
    score INTEGER CHECK (score >= 1 AND score <= 5),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Test executions (enhanced)
CREATE TABLE test_executions (
    execution_id SERIAL PRIMARY KEY,
    system_id INTEGER REFERENCES ai_systems(system_id) ON DELETE CASCADE,
    test_suite_name VARCHAR(100),
    status VARCHAR(50) DEFAULT 'pending' CHECK (status IN ('pending', 'running', 'completed', 'failed', 'cancelled')),
    progress INTEGER DEFAULT 0 CHECK (progress >= 0 AND progress <= 100),
    total_tests INTEGER,
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_by INTEGER REFERENCES users(user_id)
);

-- Execution results
CREATE TABLE execution_results (
    result_id SERIAL PRIMARY KEY,
    execution_id INTEGER REFERENCES test_executions(execution_id) ON DELETE CASCADE,
    test_result_id INTEGER REFERENCES test_results(result_id) ON DELETE CASCADE,
    sequence_number INTEGER
);

-- Compliance reports
CREATE TABLE compliance_reports (
    report_id SERIAL PRIMARY KEY,
    system_id INTEGER REFERENCES ai_systems(system_id) ON DELETE CASCADE,
    framework_id INTEGER REFERENCES compliance_frameworks(framework_id),
    title VARCHAR(255),
    summary JSONB,
    detailed_results JSONB,
    recommendations JSONB,
    status VARCHAR(50) DEFAULT 'draft' CHECK (status IN ('draft', 'review', 'approved', 'published')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_by INTEGER REFERENCES users(user_id)
);

-- Indexes for performance optimization
CREATE INDEX idx_users_username ON users(username);
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_ai_systems_user_id ON ai_systems(user_id);
CREATE INDEX idx_ai_systems_name ON ai_systems(name);
CREATE INDEX idx_tests_system_id ON tests(system_id);
CREATE INDEX idx_tests_status ON tests(status);
CREATE INDEX idx_test_results_test_id ON test_results(test_id);
CREATE INDEX idx_generated_prompts_system_id ON generated_prompts(system_id);
CREATE INDEX idx_generated_prompts_category_id ON generated_prompts(category_id);
CREATE INDEX idx_generated_prompts_approval_status ON generated_prompts(approval_status);
CREATE INDEX idx_generated_documents_system_id ON generated_documents(system_id);
CREATE INDEX idx_generated_documents_template_id ON generated_documents(template_id);
CREATE INDEX idx_test_executions_system_id ON test_executions(system_id);
CREATE INDEX idx_test_executions_status ON test_executions(status);
CREATE INDEX idx_compliance_reports_system_id ON compliance_reports(system_id);

-- Insert default compliance frameworks
INSERT INTO compliance_frameworks (name, description, version, requirements) VALUES
('GDPR', 'General Data Protection Regulation', '2018', '{"data_protection": true, "consent_management": true, "right_to_explanation": true}'),
('HIPAA', 'Health Insurance Portability and Accountability Act', '1996', '{"data_encryption": true, "access_controls": true, "audit_logging": true}'),
('EU AI Act', 'European Union Artificial Intelligence Act', '2024', '{"risk_assessment": true, "transparency": true, "human_oversight": true}'),
('SOC 2', 'Service Organization Control 2', '2017', '{"security": true, "availability": true, "processing_integrity": true}');

-- Create default admin user (password: admin123 - change in production!)
INSERT INTO users (username, password_hash, full_name, email, role) VALUES
('admin', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj6hsxq9w5KS', 'System Administrator', 'admin@example.com', 'admin');

-- Insert default prompt categories
INSERT INTO prompt_categories (name, description, framework) VALUES
('Safety Testing', 'Prompts for testing AI safety and harmful content detection', 'General'),
('Bias Detection', 'Prompts for detecting bias in AI model responses', 'GDPR'),
('Privacy Compliance', 'Prompts for testing privacy and data protection compliance', 'GDPR'),
('Medical Compliance', 'Prompts for testing healthcare-related compliance', 'HIPAA'),
('Transparency Testing', 'Prompts for testing AI transparency and explainability', 'EU AI Act'),
('Security Testing', 'Prompts for testing security vulnerabilities', 'SOC 2');

-- Insert default document templates
INSERT INTO document_templates (name, description, template_type, content, framework, created_by) VALUES
('GDPR Compliance Report', 'Standard template for GDPR compliance documentation', 'compliance_report',
 '{"sections": ["executive_summary", "data_processing", "consent_mechanisms", "rights_management", "recommendations"]}',
 'GDPR', 1),
('HIPAA Assessment Report', 'Template for HIPAA compliance assessment', 'compliance_report',
 '{"sections": ["covered_entities", "safeguards", "access_controls", "audit_results", "remediation"]}',
 'HIPAA', 1),
('EU AI Act Documentation', 'Template for EU AI Act compliance documentation', 'compliance_report',
 '{"sections": ["risk_classification", "quality_management", "transparency_obligations", "human_oversight", "monitoring"]}',
 'EU AI Act', 1);

-- Update timestamp trigger function
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Models table (for AI models within systems)
CREATE TABLE models (
    model_id SERIAL PRIMARY KEY,
    system_id INTEGER REFERENCES ai_systems(system_id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    model_type VARCHAR(50) DEFAULT 'llm',
    version VARCHAR(50),
    endpoint_url TEXT,
    api_key_id INTEGER,
    configuration JSONB,
    status VARCHAR(50) DEFAULT 'active' CHECK (status IN ('active', 'inactive', 'deprecated')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Plugin metadata table
CREATE TABLE plugin_metadata (
    plugin_id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    version VARCHAR(20) DEFAULT '1.0.0',
    description TEXT,
    author VARCHAR(100),
    framework VARCHAR(50),
    category VARCHAR(50) DEFAULT 'custom',
    file_path TEXT,
    config_schema JSONB,
    dependencies JSONB,
    supported_models JSONB,
    is_enabled BOOLEAN DEFAULT TRUE,
    is_installed BOOLEAN DEFAULT FALSE,
    installation_date TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Workflow approvals table
CREATE TABLE workflow_approvals (
    approval_id SERIAL PRIMARY KEY,
    document_id INTEGER REFERENCES generated_documents(document_id) ON DELETE CASCADE,
    approver_id INTEGER REFERENCES users(user_id),
    approval_status VARCHAR(50) DEFAULT 'pending' CHECK (approval_status IN ('pending', 'approved', 'rejected', 'changes_requested')),
    comments TEXT,
    approval_date TIMESTAMP WITH TIME ZONE,
    escalation_level INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Workflow rules table
CREATE TABLE workflow_rules (
    rule_id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    document_type VARCHAR(50),
    framework VARCHAR(50),
    required_approvers INTEGER DEFAULT 1,
    escalation_hours INTEGER DEFAULT 24,
    auto_approve_threshold DECIMAL(3,2),
    conditions JSONB,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_by INTEGER REFERENCES users(user_id)
);

-- Notifications table
CREATE TABLE notifications (
    notification_id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(user_id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL,
    message TEXT,
    notification_type VARCHAR(50) DEFAULT 'info' CHECK (notification_type IN ('info', 'warning', 'error', 'success')),
    category VARCHAR(50),
    related_entity_type VARCHAR(50),
    related_entity_id INTEGER,
    is_read BOOLEAN DEFAULT FALSE,
    read_at TIMESTAMP WITH TIME ZONE,
    expires_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Audit logs table
CREATE TABLE audit_logs (
    log_id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(user_id),
    action VARCHAR(100) NOT NULL,
    entity_type VARCHAR(50),
    entity_id INTEGER,
    old_values JSONB,
    new_values JSONB,
    ip_address INET,
    user_agent TEXT,
    session_id VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- User sessions table
CREATE TABLE user_sessions (
    session_id VARCHAR(255) PRIMARY KEY,
    user_id INTEGER REFERENCES users(user_id) ON DELETE CASCADE,
    ip_address INET,
    user_agent TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_activity TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP WITH TIME ZONE,
    is_active BOOLEAN DEFAULT TRUE
);

-- API keys table
CREATE TABLE api_keys (
    key_id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(user_id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    key_hash VARCHAR(255) NOT NULL,
    key_prefix VARCHAR(20),
    permissions JSONB,
    usage_count INTEGER DEFAULT 0,
    rate_limit_per_hour INTEGER DEFAULT 1000,
    last_used_at TIMESTAMP WITH TIME ZONE,
    expires_at TIMESTAMP WITH TIME ZONE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- System monitoring table
CREATE TABLE system_monitoring (
    monitor_id SERIAL PRIMARY KEY,
    metric_name VARCHAR(100) NOT NULL,
    metric_value DECIMAL(15,4),
    metric_unit VARCHAR(20),
    service_name VARCHAR(50),
    instance_id VARCHAR(100),
    tags JSONB,
    recorded_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Backup jobs table
CREATE TABLE backup_jobs (
    job_id SERIAL PRIMARY KEY,
    job_name VARCHAR(100) NOT NULL,
    backup_type VARCHAR(50) DEFAULT 'full' CHECK (backup_type IN ('full', 'incremental', 'differential')),
    status VARCHAR(50) DEFAULT 'scheduled' CHECK (status IN ('scheduled', 'running', 'completed', 'failed', 'cancelled')),
    file_path TEXT,
    file_size_bytes BIGINT,
    compression_ratio DECIMAL(5,2),
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    error_message TEXT,
    retention_days INTEGER DEFAULT 30,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_by INTEGER REFERENCES users(user_id)
);

-- Document versions table (for change tracking)
CREATE TABLE document_versions (
    version_id SERIAL PRIMARY KEY,
    document_id INTEGER REFERENCES generated_documents(document_id) ON DELETE CASCADE,
    version_number INTEGER NOT NULL,
    title VARCHAR(255),
    content JSONB,
    changes_summary TEXT,
    changed_by INTEGER REFERENCES users(user_id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Analytics cache table
CREATE TABLE analytics_cache (
    cache_id SERIAL PRIMARY KEY,
    cache_key VARCHAR(255) NOT NULL UNIQUE,
    cache_data JSONB NOT NULL,
    expires_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Additional indexes for performance optimization
CREATE INDEX idx_models_system_id ON models(system_id);
CREATE INDEX idx_models_status ON models(status);
CREATE INDEX idx_plugin_metadata_name ON plugin_metadata(name);
CREATE INDEX idx_plugin_metadata_category ON plugin_metadata(category);
CREATE INDEX idx_workflow_approvals_document_id ON workflow_approvals(document_id);
CREATE INDEX idx_workflow_approvals_approver_id ON workflow_approvals(approver_id);
CREATE INDEX idx_workflow_approvals_status ON workflow_approvals(approval_status);
CREATE INDEX idx_notifications_user_id ON notifications(user_id);
CREATE INDEX idx_notifications_is_read ON notifications(is_read);
CREATE INDEX idx_notifications_created_at ON notifications(created_at);
CREATE INDEX idx_audit_logs_user_id ON audit_logs(user_id);
CREATE INDEX idx_audit_logs_action ON audit_logs(action);
CREATE INDEX idx_audit_logs_created_at ON audit_logs(created_at);
CREATE INDEX idx_user_sessions_user_id ON user_sessions(user_id);
CREATE INDEX idx_user_sessions_expires_at ON user_sessions(expires_at);
CREATE INDEX idx_api_keys_user_id ON api_keys(user_id);
CREATE INDEX idx_api_keys_key_hash ON api_keys(key_hash);
CREATE INDEX idx_system_monitoring_metric_name ON system_monitoring(metric_name);
CREATE INDEX idx_system_monitoring_recorded_at ON system_monitoring(recorded_at);
CREATE INDEX idx_backup_jobs_status ON backup_jobs(status);
CREATE INDEX idx_backup_jobs_created_at ON backup_jobs(created_at);
CREATE INDEX idx_document_versions_document_id ON document_versions(document_id);
CREATE INDEX idx_analytics_cache_cache_key ON analytics_cache(cache_key);
CREATE INDEX idx_analytics_cache_expires_at ON analytics_cache(expires_at);

-- Link test results to models after that table exists
ALTER TABLE test_results ADD COLUMN IF NOT EXISTS model_id INTEGER REFERENCES models(model_id);
CREATE INDEX IF NOT EXISTS idx_test_results_model_id ON test_results(model_id);

-- Managed provider keys (Settings vault). Referenced by ai_model_configs.api_key_id.
-- Column names match gateway SimpleAPIKeyService / APIKeyManager (id, name, status).
CREATE TABLE user_api_keys (
    id VARCHAR(64) PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    provider VARCHAR(50) NOT NULL,
    encrypted_key TEXT NOT NULL,
    name VARCHAR(255),
    description TEXT,
    status VARCHAR(20) DEFAULT 'active' CHECK (status IN ('active', 'inactive', 'expired', 'revoked')),
    expires_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_user_api_keys_user_id ON user_api_keys(user_id);
CREATE INDEX idx_user_api_keys_user_provider ON user_api_keys(user_id, provider);
CREATE INDEX idx_user_api_keys_status ON user_api_keys(status);

-- AI Model Configurations for the Unified AI API
-- Separate from the 'models' table which is tied to AI systems
-- api_key: optional inline secret; api_key_id: preferred pointer into user_api_keys

CREATE TABLE ai_model_configs (
    config_id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    provider VARCHAR(50) NOT NULL CHECK (provider IN ('openai', 'google', 'anthropic', 'huggingface', 'local')),
    model_id VARCHAR(100) NOT NULL,
    api_key TEXT,
    api_key_id VARCHAR(64),
    api_url TEXT,
    temperature DECIMAL(3,2) DEFAULT 0.7 CHECK (temperature >= 0.0 AND temperature <= 2.0),
    max_tokens INTEGER DEFAULT 1000 CHECK (max_tokens > 0),
    timeout INTEGER DEFAULT 30 CHECK (timeout > 0),
    max_retries INTEGER DEFAULT 3 CHECK (max_retries >= 0),
    retry_delay DECIMAL(4,2) DEFAULT 1.0 CHECK (retry_delay >= 0.0),
    provider_options JSONB DEFAULT '{}',
    usage_type VARCHAR(50) DEFAULT 'utility' CHECK (usage_type IN ('test_subject', 'evaluator', 'rag', 'utility')),
    metadata JSONB DEFAULT '{}',
    tags TEXT[],
    enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_by INTEGER REFERENCES users(user_id) ON DELETE SET NULL,
    UNIQUE(name, created_by)
);

-- Model test results table
CREATE TABLE ai_model_test_results (
    test_result_id SERIAL PRIMARY KEY,
    config_id INTEGER REFERENCES ai_model_configs(config_id) ON DELETE CASCADE,
    test_prompt TEXT NOT NULL,
    response_content TEXT,
    response_time_ms INTEGER,
    tokens_used JSONB,
    error_message TEXT,
    success BOOLEAN NOT NULL,
    test_metadata JSONB DEFAULT '{}',
    evaluator_model VARCHAR(100),
    evaluator_provider VARCHAR(50),
    system_id INTEGER REFERENCES ai_systems(system_id) ON DELETE CASCADE,
    test_name VARCHAR(100),
    result VARCHAR(50) DEFAULT 'pending',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_by INTEGER REFERENCES users(user_id) ON DELETE SET NULL
);

-- Indexes for AI model configurations
CREATE INDEX idx_ai_model_configs_provider ON ai_model_configs(provider);
CREATE INDEX idx_ai_model_configs_enabled ON ai_model_configs(enabled);
CREATE INDEX idx_ai_model_configs_created_by ON ai_model_configs(created_by);
CREATE INDEX idx_ai_model_configs_usage_type ON ai_model_configs(usage_type);
CREATE INDEX idx_ai_model_configs_name ON ai_model_configs(name);
CREATE INDEX idx_ai_model_configs_api_key_id ON ai_model_configs(api_key_id);

-- Index for test results
CREATE INDEX idx_ai_model_test_results_config_id ON ai_model_test_results(config_id);
CREATE INDEX idx_ai_model_test_results_success ON ai_model_test_results(success);
CREATE INDEX idx_ai_model_test_results_created_at ON ai_model_test_results(created_at);

-- Add update triggers
CREATE TRIGGER update_ai_systems_updated_at BEFORE UPDATE ON ai_systems FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_models_updated_at BEFORE UPDATE ON models FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_plugin_metadata_updated_at BEFORE UPDATE ON plugin_metadata FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_ai_model_configs_updated_at BEFORE UPDATE ON ai_model_configs FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ==== AI SYSTEMS ENHANCEMENT FIXES ====
-- These ensure compatibility with the complete implementation

-- Add missing columns to ai_systems (in case they don't exist from the base schema)
ALTER TABLE ai_systems 
ADD COLUMN IF NOT EXISTS model_config_id INTEGER REFERENCES ai_model_configs(config_id),
ADD COLUMN IF NOT EXISTS industry VARCHAR(100);

-- Create junction table for system-model relationships
CREATE TABLE IF NOT EXISTS ai_system_model_configs (
    id SERIAL PRIMARY KEY,
    system_id INTEGER NOT NULL REFERENCES ai_systems(system_id) ON DELETE CASCADE,
    config_id INTEGER NOT NULL REFERENCES ai_model_configs(config_id) ON DELETE CASCADE,
    model_role VARCHAR(100) DEFAULT 'primary',
    is_primary BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_by INTEGER REFERENCES users(user_id) ON DELETE SET NULL,
    UNIQUE(system_id, config_id)
);

-- Create unique index for primary models (only one primary per system)
CREATE UNIQUE INDEX IF NOT EXISTS idx_system_primary_model 
ON ai_system_model_configs(system_id) WHERE (is_primary = true);

-- Add performance indexes for junction table
CREATE INDEX IF NOT EXISTS idx_system_model_configs_system ON ai_system_model_configs(system_id);
CREATE INDEX IF NOT EXISTS idx_system_model_configs_config ON ai_system_model_configs(config_id);

-- Add evaluator tracking columns to ai_model_test_results
ALTER TABLE ai_model_test_results
ADD COLUMN IF NOT EXISTS evaluator_model VARCHAR(100),
ADD COLUMN IF NOT EXISTS evaluator_provider VARCHAR(50),
ADD COLUMN IF NOT EXISTS system_id INTEGER REFERENCES ai_systems(system_id) ON DELETE CASCADE,
ADD COLUMN IF NOT EXISTS test_name VARCHAR(100),
ADD COLUMN IF NOT EXISTS result VARCHAR(50) DEFAULT 'pending';

-- Create index for test results by system
CREATE INDEX IF NOT EXISTS idx_ai_model_test_results_system_id ON ai_model_test_results(system_id);

-- Create compliance frameworks list table with standard frameworks
CREATE TABLE IF NOT EXISTS compliance_frameworks_list (
    framework_id SERIAL PRIMARY KEY,
    framework_name VARCHAR(50) UNIQUE NOT NULL,
    description TEXT
);

-- Insert standard compliance frameworks (ignore if already exist)
INSERT INTO compliance_frameworks_list (framework_name, description) VALUES
('GDPR', 'General Data Protection Regulation'),
('HIPAA', 'Health Insurance Portability and Accountability Act'),
('EU_AI_ACT', 'European Union AI Act'),
('CCPA', 'California Consumer Privacy Act'),
('SOX', 'Sarbanes-Oxley Act'),
('PCI_DSS', 'Payment Card Industry Data Security Standard')
ON CONFLICT (framework_name) DO NOTHING;

-- Add test results tracking table for compliance tests
CREATE TABLE IF NOT EXISTS compliance_test_executions (
    execution_id SERIAL PRIMARY KEY,
    system_id INTEGER REFERENCES ai_systems(system_id) ON DELETE CASCADE,
    test_name VARCHAR(100) NOT NULL,
    test_type VARCHAR(50) NOT NULL,
    framework VARCHAR(50),
    status VARCHAR(50) DEFAULT 'pending' CHECK (status IN ('pending', 'running', 'completed', 'failed', 'cancelled')),
    config_id INTEGER REFERENCES ai_model_configs(config_id),
    evaluator_model VARCHAR(100),
    evaluator_provider VARCHAR(50),
    score DECIMAL(5,2),
    result VARCHAR(50),
    details JSONB,
    error_message TEXT,
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_by INTEGER REFERENCES users(user_id)
);

-- Add indexes for compliance test executions
CREATE INDEX IF NOT EXISTS idx_compliance_test_executions_system_id ON compliance_test_executions(system_id);
CREATE INDEX IF NOT EXISTS idx_compliance_test_executions_status ON compliance_test_executions(status);
CREATE INDEX IF NOT EXISTS idx_compliance_test_executions_framework ON compliance_test_executions(framework);

-- Add foreign key constraint for ai_model_configs.api_key_id after tables are created
ALTER TABLE ai_model_configs
ADD CONSTRAINT fk_ai_model_configs_api_key_id
FOREIGN KEY (api_key_id) REFERENCES user_api_keys(id) ON DELETE SET NULL;

-- Provider configurations table
CREATE TABLE IF NOT EXISTS provider_configs (
    provider_id SERIAL PRIMARY KEY,
    name VARCHAR(50) UNIQUE NOT NULL,
    display_name VARCHAR(100) NOT NULL,
    env_key_name VARCHAR(100),
    default_model VARCHAR(100),
    api_url_template TEXT,
    enabled BOOLEAN DEFAULT TRUE,
    config_schema JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Provider models catalog table (cache of discovered models)
CREATE TABLE IF NOT EXISTS provider_models (
    model_id SERIAL PRIMARY KEY,
    provider_id INTEGER REFERENCES provider_configs(provider_id) ON DELETE CASCADE,
    provider_model_id VARCHAR(100) NOT NULL,
    name VARCHAR(200) NOT NULL,
    description TEXT,
    context_window INTEGER,
    max_tokens INTEGER,
    input_price_per_1k DECIMAL(10,6),
    output_price_per_1k DECIMAL(10,6),
    capabilities JSONB DEFAULT '[]'::jsonb,
    deprecated BOOLEAN DEFAULT FALSE,
    discovered_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    source VARCHAR(20) DEFAULT 'discovered' CHECK (source IN ('discovered', 'static', 'manual')),
    provider_metadata JSONB DEFAULT '{}'::jsonb,
    UNIQUE(provider_id, provider_model_id)
);

-- Create indexes for provider tables
CREATE INDEX IF NOT EXISTS idx_provider_models_provider_id ON provider_models(provider_id);
CREATE INDEX IF NOT EXISTS idx_provider_models_provider_model_id ON provider_models(provider_model_id);
CREATE INDEX IF NOT EXISTS idx_provider_models_deprecated ON provider_models(deprecated);
CREATE INDEX IF NOT EXISTS idx_provider_models_source ON provider_models(source);
CREATE INDEX IF NOT EXISTS idx_provider_models_last_updated ON provider_models(last_updated);

-- Insert default provider configurations
-- Note: Models are discovered dynamically via API and cached in provider_models table
-- Users must specify model_id manually or use the refresh endpoint to populate the cache
INSERT INTO provider_configs (name, display_name, env_key_name, default_model, api_url_template, enabled) VALUES
('openai', 'OpenAI', 'OPENAI_API_KEY', NULL, 'https://api.openai.com/v1', TRUE),
('anthropic', 'Anthropic', 'ANTHROPIC_API_KEY', NULL, 'https://api.anthropic.com/v1', TRUE),
('google', 'Google', 'GOOGLE_API_KEY', NULL, 'https://generativelanguage.googleapis.com/v1beta', TRUE),
('huggingface', 'HuggingFace (Local)', 'HF_TOKEN', NULL, NULL, TRUE),
('local', 'Local/Mock', NULL, 'local-mock', NULL, TRUE)
ON CONFLICT (name) DO NOTHING;