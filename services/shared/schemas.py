"""Pydantic schemas for API requests and responses."""

from datetime import datetime
from typing import Optional, List, Dict, Any, Union, Generic, TypeVar
from pydantic import BaseModel, Field, ConfigDict
from enum import Enum

# Type variable for generic API responses
T = TypeVar('T')

# Enums
class UserRole(str, Enum):
    ADMIN = "admin"
    USER = "user"
    VIEWER = "viewer"

class SystemType(str, Enum):
    LLM = "llm"
    ML = "ml"
    HYBRID = "hybrid"

class TestStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    NEEDS_REVIEW = "needs_review"

class DocumentFormat(str, Enum):
    PDF = "pdf"
    HTML = "html"
    MARKDOWN = "markdown"
    DOCX = "docx"

class DocumentStatus(str, Enum):
    DRAFT = "draft"
    REVIEW = "review"
    APPROVED = "approved"
    PUBLISHED = "published"

class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

# Base schemas
class BaseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

# User schemas
class UserBase(BaseSchema):
    username: str = Field(..., min_length=3, max_length=50)
    full_name: str = Field(..., min_length=1, max_length=100)
    email: Optional[str] = Field(None, max_length=255)
    role: UserRole = UserRole.USER

class UserCreate(UserBase):
    password: str = Field(..., min_length=8)

class UserUpdate(BaseSchema):
    full_name: Optional[str] = Field(None, min_length=1, max_length=100)
    email: Optional[str] = Field(None, max_length=255)
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None

class UserResponse(UserBase):
    user_id: int
    created_at: datetime
    last_login: Optional[datetime] = None
    is_active: bool

# Authentication schemas
class AuthRequest(BaseSchema):
    username: str
    password: str

class AuthResponse(BaseSchema):
    user: UserResponse
    token: str
    refresh_token: str
    expires_in: int

class TokenRefreshRequest(BaseSchema):
    refresh_token: str

# AI Model Configuration schemas
class AIModelConfigBase(BaseSchema):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    provider: str = Field(..., min_length=1, max_length=50)
    model_id: str = Field(..., min_length=1, max_length=100)
    api_key: Optional[str] = None
    api_url: Optional[str] = None  # custom endpoint for OpenAI-compatible providers (deepseek, groq, vLLM...)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=1000, gt=0)
    top_p: Optional[float] = Field(default=1.0, ge=0.0, le=1.0)
    frequency_penalty: Optional[float] = Field(default=0.0, ge=-2.0, le=2.0)
    presence_penalty: Optional[float] = Field(default=0.0, ge=-2.0, le=2.0)
    timeout: Optional[int] = Field(default=30, gt=0)
    enabled: bool = Field(default=True)
    tags: Optional[List[str]] = Field(default_factory=list)

class AIModelConfigCreate(AIModelConfigBase):
    pass

class AIModelConfigUpdate(BaseSchema):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    provider: Optional[str] = Field(None, min_length=1, max_length=50)
    model_id: Optional[str] = Field(None, min_length=1, max_length=100)
    api_key: Optional[str] = None
    api_url: Optional[str] = None
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(None, gt=0)
    top_p: Optional[float] = Field(None, ge=0.0, le=1.0)
    frequency_penalty: Optional[float] = Field(None, ge=-2.0, le=2.0)
    presence_penalty: Optional[float] = Field(None, ge=-2.0, le=2.0)
    timeout: Optional[int] = Field(None, gt=0)
    enabled: Optional[bool] = None
    tags: Optional[List[str]] = None

class AIModelConfigResponse(AIModelConfigBase):
    id: int = Field(..., alias="config_id")  # Frontend expects 'id' field
    config_id: int
    created_at: datetime
    updated_at: datetime
    created_by: int

# AI System schemas
class AISystemBase(BaseSchema):
    model_config = {"protected_namespaces": ()}  # Allow model_ fields
    
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    version: Optional[str] = Field(None, max_length=50)
    system_type: Optional[SystemType] = SystemType.LLM
    compliance_frameworks: List[str] = Field(default_factory=list)
    model_config_id: Optional[int] = Field(None, description="ID of the AI model configuration to use")
    industry: Optional[str] = Field(None, max_length=50, description="Industry context for compliance")

class AISystemCreate(AISystemBase):
    pass

class AISystemUpdate(BaseSchema):
    model_config = {"protected_namespaces": ()}  # Allow model_ fields
    
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    version: Optional[str] = Field(None, max_length=50)
    system_type: Optional[SystemType] = None
    compliance_frameworks: Optional[List[str]] = None
    model_config_id: Optional[int] = Field(None, description="ID of the AI model configuration to use")
    industry: Optional[str] = Field(None, max_length=50, description="Industry context for compliance")

class AISystemResponse(AISystemBase):
    model_config = {"protected_namespaces": ()}  # Allow model_ fields
    
    system_id: int
    created_at: datetime
    updated_at: datetime
    user_id: int
    model_name: Optional[str] = Field(None, description="Name of the associated AI model configuration")
    status: str = Field(default="active", description="Current status of the AI system")
    last_tested: Optional[datetime] = Field(None, description="Timestamp of last compliance test")
    compliance_scores: dict = Field(default_factory=dict, description="Latest compliance scores by framework")

# Compliance Framework schemas
class ComplianceFrameworkBase(BaseSchema):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    version: Optional[str] = Field(None, max_length=20)
    requirements: Dict[str, Any] = Field(default_factory=dict)

class ComplianceFrameworkResponse(ComplianceFrameworkBase):
    framework_id: int
    is_active: bool
    created_at: datetime

# Test schemas
class TestBase(BaseSchema):
    test_name: str = Field(..., min_length=1, max_length=100)
    test_type: str = Field(..., min_length=1, max_length=50)
    configuration: Dict[str, Any] = Field(default_factory=dict)

class TestCreate(TestBase):
    system_id: int
    framework_id: Optional[int] = None

class TestResponse(TestBase):
    test_id: int
    system_id: int
    framework_id: Optional[int] = None
    status: TestStatus
    created_at: datetime
    created_by: Optional[int] = None

class TestResultBase(BaseSchema):
    score: Optional[float] = Field(None, ge=0, le=100)
    passed: Optional[bool] = None
    details: Dict[str, Any] = Field(default_factory=dict)
    recommendations: List[str] = Field(default_factory=list)

class TestResultResponse(TestResultBase):
    result_id: int
    test_id: int
    created_at: datetime

# Prompt schemas
class PromptCategoryBase(BaseSchema):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    framework: Optional[str] = Field(None, max_length=50)

class PromptCategoryResponse(PromptCategoryBase):
    category_id: int

class GeneratedPromptBase(BaseSchema):
    text: str = Field(..., min_length=1)
    prompt_metadata: Dict[str, Any] = Field(default_factory=dict)
    thinking_trace: Optional[Dict[str, Any]] = None

class GeneratedPromptCreate(GeneratedPromptBase):
    category_id: Optional[int] = None
    system_id: Optional[int] = None

class GeneratedPromptResponse(GeneratedPromptBase):
    prompt_id: int
    category_id: Optional[int] = None
    system_id: Optional[int] = None
    approval_status: ApprovalStatus
    feedback_score: Optional[float] = None
    created_at: datetime
    created_by: int

class PromptGenerationRequest(BaseSchema):
    requirements: str = Field(..., min_length=1)
    category_id: Optional[int] = None
    system_id: Optional[int] = None
    count: int = Field(default=1, ge=1, le=10)
    optimization_params: Dict[str, Any] = Field(default_factory=dict)
    llm_config: Optional[Dict[str, Any]] = Field(default=None, description="LLM configuration for enhanced prompt generation")

class PromptFeedbackCreate(BaseSchema):
    is_approved: bool
    feedback_text: Optional[str] = None
    score: int = Field(..., ge=1, le=5)

class PromptFeedbackResponse(PromptFeedbackCreate):
    feedback_id: int
    prompt_id: int
    user_id: int
    created_at: datetime

# Document schemas
class DocumentTemplateBase(BaseSchema):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    template_type: Optional[str] = Field(None, max_length=50)
    content: Dict[str, Any] = Field(...)
    framework: Optional[str] = Field(None, max_length=50)
    version: str = Field(default="1.0", max_length=20)

class DocumentTemplateResponse(DocumentTemplateBase):
    template_id: int
    is_active: bool
    created_at: datetime
    created_by: Optional[int] = None

class GeneratedDocumentBase(BaseSchema):
    title: str = Field(..., min_length=1, max_length=255)
    content: Optional[Dict[str, Any]] = None
    format: DocumentFormat = DocumentFormat.PDF

class GeneratedDocumentCreate(GeneratedDocumentBase):
    template_id: int
    system_id: int

class GeneratedDocumentResponse(GeneratedDocumentBase):
    document_id: int
    template_id: int
    system_id: int
    file_path: Optional[str] = None
    status: DocumentStatus
    created_at: datetime
    created_by: int

# Test Execution schemas
class TestExecutionBase(BaseSchema):
    test_suite_name: str = Field(..., min_length=1, max_length=100)
    total_tests: Optional[int] = Field(None, ge=0)

class TestExecutionCreate(TestExecutionBase):
    system_id: int

class TestExecutionResponse(TestExecutionBase):
    execution_id: int
    system_id: int
    status: TestStatus
    progress: int = Field(ge=0, le=100)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    created_by: int

class TestProgressUpdate(BaseSchema):
    execution_id: int
    progress: int = Field(ge=0, le=100)
    current_test: Optional[str] = None
    status: TestStatus
    results: Optional[List[TestResultResponse]] = None

# Compliance Report schemas
class ComplianceReportBase(BaseSchema):
    title: str = Field(..., min_length=1, max_length=255)
    summary: Dict[str, Any] = Field(default_factory=dict)
    detailed_results: Dict[str, Any] = Field(default_factory=dict)
    recommendations: Dict[str, Any] = Field(default_factory=dict)

class ComplianceReportCreate(ComplianceReportBase):
    system_id: int
    framework_id: Optional[int] = None

class ComplianceReportResponse(ComplianceReportBase):
    report_id: int
    system_id: int
    framework_id: Optional[int] = None
    status: DocumentStatus
    created_at: datetime
    created_by: int

class ComplianceResult(BaseSchema):
    overall_score: float = Field(ge=0, le=100)
    framework_compliance: Dict[str, float] = Field(default_factory=dict)
    test_results: List[TestResultResponse] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
    risk_assessment: RiskLevel

# API Response schemas
class ApiResponse(BaseSchema, Generic[T]):
    success: bool = True
    data: Optional[T] = None
    message: Optional[str] = None

class ApiError(BaseSchema):
    code: str
    message: str
    details: Optional[Dict[str, Any]] = None

class ErrorResponse(BaseSchema):
    success: bool = False
    error: ApiError

class PaginatedResponse(BaseSchema):
    items: List[Any]
    total: int
    page: int = Field(ge=1)
    per_page: int = Field(ge=1, le=100)
    total_pages: int

# WebSocket schemas
class WebSocketMessage(BaseSchema):
    type: str
    payload: Any
    timestamp: datetime = Field(default_factory=datetime.utcnow)