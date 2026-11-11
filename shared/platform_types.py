"""
Shared Python types for AI Compliance Platform
Replaces the TypeScript types with Python equivalents using Pydantic
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union, Generic, TypeVar
from pydantic import BaseModel, Field


# Type variables
T = TypeVar('T')

# Enums
class UserRole(str, Enum):
    ADMIN = "admin"
    USER = "user"
    VIEWER = "viewer"


class TestStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


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


# User and Authentication Types
class User(BaseModel):
    user_id: int
    username: str
    full_name: str
    email: Optional[str] = None
    role: UserRole
    created_at: datetime
    last_login: Optional[datetime] = None
    is_active: bool = True


class AuthRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=8)


class AuthResponse(BaseModel):
    user: User
    token: str
    refresh_token: str
    expires_in: int


class JWTPayload(BaseModel):
    user_id: int
    username: str
    role: UserRole
    iat: int
    exp: int


# AI System Types
class AISystem(BaseModel):
    system_id: int
    name: str
    description: Optional[str] = None
    version: Optional[str] = None
    system_type: str = Field(..., pattern="^(llm|ml|hybrid)$")
    compliance_frameworks: List[str] = []
    created_at: datetime
    updated_at: datetime
    user_id: int


# Compliance Testing Types
class ComplianceFramework(BaseModel):
    framework_id: int
    name: str
    description: Optional[str] = None
    version: Optional[str] = None
    requirements: Dict[str, Any] = {}
    is_active: bool = True


class ComplianceTest(BaseModel):
    test_id: int
    system_id: int
    framework_id: int
    test_name: str
    test_type: str
    configuration: Dict[str, Any] = {}
    status: TestStatus
    created_at: datetime
    created_by: int


class TestResult(BaseModel):
    result_id: int
    test_id: int
    score: float
    passed: bool
    details: Dict[str, Any] = {}
    recommendations: Optional[List[str]] = None
    created_at: datetime


class ComplianceResult(BaseModel):
    overall_score: float
    framework_compliance: Dict[str, float] = {}
    test_results: List[TestResult] = []
    recommendations: List[str] = []
    risk_assessment: RiskLevel


# Prompt Generation Types
class PromptCategory(BaseModel):
    category_id: int
    name: str
    description: Optional[str] = None
    framework: Optional[str] = None


class GeneratedPrompt(BaseModel):
    prompt_id: int
    category_id: Optional[int] = None
    system_id: Optional[int] = None
    text: str
    metadata: Dict[str, Any] = {}
    thinking_trace: Optional[Dict[str, Any]] = None
    approval_status: ApprovalStatus
    feedback_score: Optional[float] = None
    created_at: datetime
    created_by: int


class PromptFeedback(BaseModel):
    feedback_id: int
    prompt_id: int
    user_id: int
    is_approved: bool
    feedback_text: Optional[str] = None
    score: float
    created_at: datetime


class PromptGenerationRequest(BaseModel):
    requirements: str
    category_id: Optional[int] = None
    system_id: Optional[int] = None
    count: Optional[int] = 1
    optimization_params: Optional[Dict[str, Any]] = None


# Documentation Types
class DocumentTemplate(BaseModel):
    template_id: int
    name: str
    description: Optional[str] = None
    template_type: str
    content: Dict[str, Any] = {}
    framework: Optional[str] = None
    version: str
    is_active: bool = True
    created_at: datetime
    created_by: int


class GeneratedDocument(BaseModel):
    document_id: int
    template_id: int
    system_id: int
    title: str
    content: Optional[Dict[str, Any]] = None
    format: DocumentFormat
    file_path: Optional[str] = None
    status: DocumentStatus
    created_at: datetime
    created_by: int


# Test Execution Types
class TestExecution(BaseModel):
    execution_id: int
    system_id: int
    test_suite_name: str
    status: TestStatus
    progress: float = Field(..., ge=0, le=100)
    total_tests: int
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_by: int


class ExecutionResult(BaseModel):
    result_id: int
    execution_id: int
    test_result_id: int
    sequence_number: int


# API Response Types
class ApiError(BaseModel):
    code: str
    message: str
    details: Optional[Dict[str, Any]] = None


class ApiResponse(BaseModel, Generic[T]):
    success: bool
    data: Optional[T] = None
    error: Optional[ApiError] = None
    message: Optional[str] = None


class PaginatedResponse(BaseModel):
    items: List[Any]
    total: int
    page: int
    per_page: int
    total_pages: int


# WebSocket Types
class WebSocketMessage(BaseModel):
    type: str
    payload: Any
    timestamp: datetime


class TestProgressUpdate(BaseModel):
    execution_id: int
    progress: float
    current_test: Optional[str] = None
    status: TestStatus
    results: Optional[List[TestResult]] = None


# Configuration Types
class RateLimitConfig(BaseModel):
    requests: int
    window: int


class ServiceConfig(BaseModel):
    host: str
    port: int
    database_url: str
    redis_url: Optional[str] = None
    milvus_host: Optional[str] = None
    milvus_port: Optional[int] = None
    jwt_secret: str
    cors_origins: List[str] = []
    rate_limit: RateLimitConfig


# Custom Exception
class PlatformError(Exception):
    def __init__(self, message: str, code: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.code = code
        self.details = details or {}
        self.name = "PlatformError"


# Type aliases for convenience
JSONValue = Union[str, int, float, bool, None, Dict[str, Any], List[Any]]
Timestamp = datetime
UUID = str