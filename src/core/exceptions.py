# src/core/exceptions.py - Custom exception classes
from fastapi import HTTPException
from typing import Optional, Any

class CustomHTTPException(HTTPException):
    """Base custom HTTP exception with error codes"""
    def __init__(
        self,
        status_code: int,
        detail: str,
        error_code: str,
        headers: Optional[dict] = None
    ):
        super().__init__(status_code, detail, headers)
        self.error_code = error_code

class AuthenticationError(CustomHTTPException):
    """Authentication related errors"""
    def __init__(self, detail: str = "Authentication failed"):
        super().__init__(
            status_code=401,
            detail=detail,
            error_code="AUTH_ERROR",
            headers={"WWW-Authenticate": "Bearer"}
        )

class AuthorizationError(CustomHTTPException):
    """Authorization related errors"""
    def __init__(self, detail: str = "Not authorized to perform this action"):
        super().__init__(
            status_code=403,
            detail=detail,
            error_code="AUTHZ_ERROR"
        )

class ValidationError(CustomHTTPException):
    """Validation related errors"""
    def __init__(self, detail: str, field: Optional[str] = None):
        error_code = f"VALIDATION_ERROR_{field.upper()}" if field else "VALIDATION_ERROR"
        super().__init__(
            status_code=422,
            detail=detail,
            error_code=error_code
        )

class NotFoundError(CustomHTTPException):
    """Resource not found errors"""
    def __init__(self, resource: str, resource_id: Optional[str] = None):
        detail = f"{resource} not found"
        if resource_id:
            detail += f" with ID: {resource_id}"
        
        super().__init__(
            status_code=404,
            detail=detail,
            error_code=f"{resource.upper()}_NOT_FOUND"
        )

class ConflictError(CustomHTTPException):
    """Resource conflict errors"""
    def __init__(self, detail: str, resource: Optional[str] = None):
        error_code = f"{resource.upper()}_CONFLICT" if resource else "CONFLICT_ERROR"
        super().__init__(
            status_code=409,
            detail=detail,
            error_code=error_code
        )

class ServiceError(CustomHTTPException):
    """External service errors"""
    def __init__(self, service: str, detail: str = "Service unavailable"):
        super().__init__(
            status_code=503,
            detail=f"{service}: {detail}",
            error_code=f"{service.upper()}_SERVICE_ERROR"
        )

class BusinessLogicError(CustomHTTPException):
    """Business logic validation errors"""
    def __init__(self, detail: str, code: str = "BUSINESS_LOGIC_ERROR"):
        super().__init__(
            status_code=400,
            detail=detail,
            error_code=code
        )

# Common error messages
class ErrorMessages:
    # Authentication
    TOKEN_EXPIRED = "Access token has expired"
    TOKEN_INVALID = "Invalid access token"
    USER_NOT_FOUND = "User not found"
    INVALID_CREDENTIALS = "Invalid credentials"
    
    # Authorization
    INSUFFICIENT_PERMISSIONS = "Insufficient permissions"
    NOT_ORGANIZATION_ADMIN = "Must be organization admin"
    NOT_PROJECT_ADMIN = "Must be project admin"
    NOT_PROJECT_MEMBER = "Must be project member"
    
    # Validation
    EMAIL_ALREADY_EXISTS = "Email already registered"
    INVALID_EMAIL_FORMAT = "Invalid email format"
    REQUIRED_FIELD_MISSING = "Required field is missing"
    
    # Resources
    ORGANIZATION_NOT_FOUND = "Organization not found"
    PROJECT_NOT_FOUND = "Project not found"
    MEETING_NOT_FOUND = "Meeting not found"
    USER_NOT_FOUND = "User not found"
    
    # Business Logic
    ALREADY_MEMBER = "User is already a member"
    CANNOT_REMOVE_LAST_ADMIN = "Cannot remove the last admin"
    MEETING_ALREADY_STARTED = "Meeting has already started"
    INVALID_MEETING_TIME = "Meeting time must be in the future"

# Helper functions for common exceptions
def raise_not_found(resource: str, resource_id: Optional[str] = None) -> None:
    """Raise a standardized not found exception"""
    raise NotFoundError(resource, resource_id)

def raise_authentication_error(detail: str = ErrorMessages.TOKEN_INVALID) -> None:
    """Raise a standardized authentication error"""
    raise AuthenticationError(detail)

def raise_authorization_error(detail: str = ErrorMessages.INSUFFICIENT_PERMISSIONS) -> None:
    """Raise a standardized authorization error"""
    raise AuthorizationError(detail)

def raise_validation_error(detail: str, field: Optional[str] = None) -> None:
    """Raise a standardized validation error"""
    raise ValidationError(detail, field)

def raise_conflict_error(detail: str, resource: Optional[str] = None) -> None:
    """Raise a standardized conflict error"""
    raise ConflictError(detail, resource)