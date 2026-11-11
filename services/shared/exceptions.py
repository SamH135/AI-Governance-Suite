"""Shared exception classes."""

from typing import Optional, Dict, Any

class PlatformError(Exception):
    """Base exception for platform errors."""
    
    def __init__(
        self,
        message: str,
        code: str,
        details: Optional[Dict[str, Any]] = None,
        status_code: int = 500
    ):
        self.message = message
        self.code = code
        self.details = details or {}
        self.status_code = status_code
        super().__init__(self.message)

class ValidationError(PlatformError):
    """Validation error."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            code="VALIDATION_ERROR",
            details=details,
            status_code=400
        )

class NotFoundError(PlatformError):
    """Resource not found error."""
    
    def __init__(self, resource: str, identifier: Any = None):
        message = f"{resource} not found"
        if identifier:
            message += f" (ID: {identifier})"
        super().__init__(
            message=message,
            code="NOT_FOUND",
            details={"resource": resource, "identifier": identifier},
            status_code=404
        )

class ConflictError(PlatformError):
    """Resource conflict error."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            code="CONFLICT",
            details=details,
            status_code=409
        )

class AuthenticationError(PlatformError):
    """Authentication error."""
    
    def __init__(self, message: str = "Authentication failed"):
        super().__init__(
            message=message,
            code="AUTHENTICATION_ERROR",
            status_code=401
        )

class AuthorizationError(PlatformError):
    """Authorization error."""
    
    def __init__(self, message: str = "Insufficient permissions"):
        super().__init__(
            message=message,
            code="AUTHORIZATION_ERROR",
            status_code=403
        )

class ServiceUnavailableError(PlatformError):
    """Service unavailable error."""
    
    def __init__(self, service: str, message: Optional[str] = None):
        if not message:
            message = f"{service} service is currently unavailable"
        super().__init__(
            message=message,
            code="SERVICE_UNAVAILABLE",
            details={"service": service},
            status_code=503
        )

class RateLimitError(PlatformError):
    """Rate limit exceeded error."""
    
    def __init__(self, message: str = "Rate limit exceeded"):
        super().__init__(
            message=message,
            code="RATE_LIMIT_EXCEEDED",
            status_code=429
        )

class RateLimitExceededError(PlatformError):
    """Rate limit exceeded error with detailed info."""
    
    def __init__(self, message: str, limit_info: Dict[str, Any]):
        super().__init__(
            message=message,
            code="RATE_LIMIT_EXCEEDED",
            status_code=429,
            details=limit_info
        )

class SecurityError(PlatformError):
    """Security-related error."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            code="SECURITY_ERROR",
            status_code=403,
            details=details
        )

class EvaluationError(PlatformError):
    """Evaluation process error."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            code="EVALUATION_ERROR",
            status_code=500,
            details=details
        )

class ExternalServiceError(PlatformError):
    """External service error."""
    
    def __init__(self, service: str, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=f"{service}: {message}",
            code="EXTERNAL_SERVICE_ERROR",
            details={"service": service, **(details or {})},
            status_code=502
        )

class DatabaseError(PlatformError):
    """Database operation error."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            code="DATABASE_ERROR",
            details=details,
            status_code=500
        )

class CacheError(PlatformError):
    """Cache operation error."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            code="CACHE_ERROR",
            details=details,
            status_code=500
        )