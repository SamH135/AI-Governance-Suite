"""Shared database models."""

from datetime import datetime
from typing import Optional, List
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, DECIMAL, ARRAY, JSON, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base

class User(Base):
    __tablename__ = "users"
    
    user_id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(100), nullable=False)
    email = Column(String(255), unique=True, index=True)
    role = Column(String(50), default="user", nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_login = Column(DateTime(timezone=True))
    is_active = Column(Boolean, default=True)
    
    # Relationships
    ai_systems = relationship("AISystem", back_populates="user")
    tests = relationship("Test", back_populates="created_by_user")
    generated_prompts = relationship("GeneratedPrompt", back_populates="created_by_user")
    generated_documents = relationship("GeneratedDocument", back_populates="created_by_user")

class AISystem(Base):
    __tablename__ = "ai_systems"
    
    system_id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    version = Column(String(50))
    system_type = Column(String(50), default="llm")
    compliance_frameworks = Column(ARRAY(String))
    model_config_id = Column(Integer, ForeignKey("ai_model_configs.config_id"), nullable=True)
    industry = Column(String(50), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="ai_systems")
    model_config = relationship("AIModelConfig", foreign_keys=[model_config_id])
    tests = relationship("Test", back_populates="system")
    generated_prompts = relationship("GeneratedPrompt", back_populates="system")
    generated_documents = relationship("GeneratedDocument", back_populates="system")
    test_executions = relationship("TestExecution", back_populates="system")

class ComplianceFramework(Base):
    __tablename__ = "compliance_frameworks"
    
    framework_id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)
    description = Column(Text)
    version = Column(String(20))
    requirements = Column(JSON)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    framework_requirements = relationship("FrameworkRequirement", back_populates="framework")
    tests = relationship("Test", back_populates="framework")

class FrameworkRequirement(Base):
    __tablename__ = "framework_requirements"
    
    requirement_id = Column(Integer, primary_key=True, index=True)
    framework_id = Column(Integer, ForeignKey("compliance_frameworks.framework_id"), nullable=False)
    requirement_code = Column(String(50))
    title = Column(String(255))
    description = Column(Text)
    category = Column(String(100))
    severity = Column(String(20), default="medium")
    
    # Relationships
    framework = relationship("ComplianceFramework", back_populates="framework_requirements")

class Test(Base):
    __tablename__ = "tests"
    
    test_id = Column(Integer, primary_key=True, index=True)
    system_id = Column(Integer, ForeignKey("ai_systems.system_id"), nullable=False)
    framework_id = Column(Integer, ForeignKey("compliance_frameworks.framework_id"))
    test_name = Column(String(100), nullable=False)
    test_type = Column(String(50), nullable=False)
    configuration = Column(JSON)
    status = Column(String(50), default="pending")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    created_by = Column(Integer, ForeignKey("users.user_id"))
    
    # Relationships
    system = relationship("AISystem", back_populates="tests")
    framework = relationship("ComplianceFramework", back_populates="tests")
    created_by_user = relationship("User", back_populates="tests")
    test_results = relationship("TestResult", back_populates="test")

class TestResult(Base):
    __tablename__ = "test_results"
    
    result_id = Column(Integer, primary_key=True, index=True)
    test_id = Column(Integer, ForeignKey("tests.test_id"), nullable=False)
    score = Column(DECIMAL(5, 2))
    passed = Column(Boolean)
    details = Column(JSON)
    recommendations = Column(ARRAY(String))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    test = relationship("Test", back_populates="test_results")

class DocumentTemplate(Base):
    __tablename__ = "document_templates"
    
    template_id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    template_type = Column(String(50))
    content = Column(JSON, nullable=False)
    framework = Column(String(50))
    version = Column(String(20), default="1.0")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    created_by = Column(Integer, ForeignKey("users.user_id"))
    
    # Relationships
    generated_documents = relationship("GeneratedDocument", back_populates="template")

class GeneratedDocument(Base):
    __tablename__ = "generated_documents"
    
    document_id = Column(Integer, primary_key=True, index=True)
    template_id = Column(Integer, ForeignKey("document_templates.template_id"))
    system_id = Column(Integer, ForeignKey("ai_systems.system_id"), nullable=False)
    title = Column(String(255), nullable=False)
    content = Column(JSON)
    format = Column(String(20), default="pdf")
    file_path = Column(Text)
    status = Column(String(50), default="draft")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    created_by = Column(Integer, ForeignKey("users.user_id"))
    
    # Relationships
    template = relationship("DocumentTemplate", back_populates="generated_documents")
    system = relationship("AISystem", back_populates="generated_documents")
    created_by_user = relationship("User", back_populates="generated_documents")

class PromptCategory(Base):
    __tablename__ = "prompt_categories"
    
    category_id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)
    description = Column(Text)
    framework = Column(String(50))
    
    # Relationships
    generated_prompts = relationship("GeneratedPrompt", back_populates="category")

class GeneratedPrompt(Base):
    __tablename__ = "generated_prompts"
    
    prompt_id = Column(Integer, primary_key=True, index=True)
    category_id = Column(Integer, ForeignKey("prompt_categories.category_id"))
    system_id = Column(Integer, ForeignKey("ai_systems.system_id"))
    text = Column(Text, nullable=False)
    prompt_metadata = Column(JSON)
    thinking_trace = Column(JSON)
    approval_status = Column(String(50), default="pending")
    feedback_score = Column(DECIMAL(3, 2))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    created_by = Column(Integer, ForeignKey("users.user_id"))
    
    # Relationships
    category = relationship("PromptCategory", back_populates="generated_prompts")
    system = relationship("AISystem", back_populates="generated_prompts")
    created_by_user = relationship("User", back_populates="generated_prompts")
    feedback = relationship("PromptFeedback", back_populates="prompt")

class PromptFeedback(Base):
    __tablename__ = "prompt_feedback"
    
    feedback_id = Column(Integer, primary_key=True, index=True)
    prompt_id = Column(Integer, ForeignKey("generated_prompts.prompt_id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.user_id"), nullable=False)
    is_approved = Column(Boolean)
    feedback_text = Column(Text)
    score = Column(Integer)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    prompt = relationship("GeneratedPrompt", back_populates="feedback")

class TestExecution(Base):
    __tablename__ = "test_executions"
    
    execution_id = Column(Integer, primary_key=True, index=True)
    system_id = Column(Integer, ForeignKey("ai_systems.system_id"), nullable=False)
    test_suite_name = Column(String(100))
    status = Column(String(50), default="pending")
    progress = Column(Integer, default=0)
    total_tests = Column(Integer)
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    created_by = Column(Integer, ForeignKey("users.user_id"))
    
    # Relationships
    system = relationship("AISystem", back_populates="test_executions")

class ComplianceReport(Base):
    __tablename__ = "compliance_reports"
    
    report_id = Column(Integer, primary_key=True, index=True)
    system_id = Column(Integer, ForeignKey("ai_systems.system_id"), nullable=False)
    framework_id = Column(Integer, ForeignKey("compliance_frameworks.framework_id"))
    title = Column(String(255))
    summary = Column(JSON)
    detailed_results = Column(JSON)
    recommendations = Column(JSON)
    status = Column(String(50), default="draft")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    created_by = Column(Integer, ForeignKey("users.user_id"))

class AIModelConfig(Base):
    __tablename__ = "ai_model_configs"
    
    config_id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    provider = Column(String(50), nullable=False)
    model_id = Column(String(100), nullable=False)
    api_key = Column(Text)
    api_key_id = Column(String(64), ForeignKey("user_api_keys.id", ondelete="SET NULL"))
    api_url = Column(Text)
    temperature = Column(DECIMAL(3, 2), default=0.7)
    max_tokens = Column(Integer, default=1000)
    timeout = Column(Integer, default=30)
    max_retries = Column(Integer, default=3)
    retry_delay = Column(DECIMAL(4, 2), default=1.0)
    provider_options = Column(JSON, default={})
    usage_type = Column(String(50), default="utility")
    model_metadata = Column("metadata", JSON, default={})
    tags = Column(ARRAY(String))
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    created_by = Column(Integer, ForeignKey("users.user_id"))