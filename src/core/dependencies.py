# src/core/dependencies.py - Common dependencies and authentication
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from supabase import Client
from jose import JWTError, jwt
import requests
from typing import Optional

from src.database.base import get_supabase
from src.core.config import settings
from src.core.exceptions import AuthenticationError, AuthorizationError

# Security
security = HTTPBearer()

class CurrentUser:
    """User model for dependency injection"""
    def __init__(self, user_id: str, email: str, user_data: dict = None):
        self.user_id = user_id
        self.email = email
        self.user_data = user_data or {}
    
    @property
    def full_name(self) -> str:
        if self.user_data:
            first_name = self.user_data.get('first_name', '')
            last_name = self.user_data.get('last_name', '')
            return f"{first_name} {last_name}".strip()
        return self.email

def decode_supabase_jwt(token: str) -> dict:
    """Decode and validate Supabase JWT token"""
    try:
        # Try to decode with verification using SUPABASE_JWT_SECRET
        decoded = jwt.decode(
            token, 
            settings.SUPABASE_JWT_SECRET, 
            algorithms=["HS256"], 
            audience="authenticated",
            options={"verify_signature": True}
        )
        return decoded
        
    except jwt.ExpiredSignatureError:
        raise AuthenticationError("Token has expired")
    except jwt.InvalidTokenError:
        # Try to validate with Supabase API as fallback
        try:
            headers = {
                "Authorization": f"Bearer {token}", 
                "apikey": settings.SUPABASE_KEY
            }
            response = requests.get(
                f"{settings.SUPABASE_URL}/auth/v1/user", 
                headers=headers,
                timeout=10
            )
            if response.status_code == 200:
                return response.json()
            else:
                raise AuthenticationError("Invalid token")
        except Exception:
            raise AuthenticationError("Token validation failed")

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    supabase: Client = Depends(get_supabase)
) -> CurrentUser:
    """Get current authenticated user from JWT token"""
    try:
        token = credentials.credentials
        user_data = decode_supabase_jwt(token)
        
        email = user_data.get('email')
        if not email:
            raise AuthenticationError("Invalid token: missing email")
        
        # Get user details from database
        user_response = supabase.table('users').select('*').eq('email', email).execute()
        
        if not user_response.data:
            raise AuthenticationError("User not found in database")
        
        user_record = user_response.data[0]
        
        return CurrentUser(
            user_id=user_record['user_id'],
            email=email,
            user_data=user_record
        )
        
    except AuthenticationError:
        raise
    except Exception as e:
        raise AuthenticationError(f"Authentication failed: {str(e)}")

async def get_user_id_from_email(email: str, supabase: Client = Depends(get_supabase)) -> str:
    """Get user_id from email"""
    try:
        user_response = supabase.table('users').select('user_id').eq('email', email).execute()
        if not user_response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found in database"
            )
        return user_response.data[0]['user_id']
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving user ID: {str(e)}"
        )

async def verify_organization_admin(
    org_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase)
) -> bool:
    """Verify user is admin of organization"""
    admin_response = supabase.table("organization_members") \
        .select("*") \
        .eq("user_id", current_user.user_id) \
        .eq("org_id", org_id) \
        .eq("role", "org_admin") \
        .execute()
    
    if not admin_response.data:
        raise AuthorizationError("Not authorized to perform this action on organization")
    
    return True

async def verify_project_admin(
    project_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase)
) -> bool:
    """Verify user is admin of project"""
    admin_response = supabase.table("project_members") \
        .select("*") \
        .eq("project_id", project_id) \
        .eq("user_id", current_user.user_id) \
        .eq("role", "project_admin") \
        .execute()
    
    if not admin_response.data:
        raise AuthorizationError("Not authorized to perform this action on project")
    
    return True

async def verify_project_member(
    project_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase)
) -> bool:
    """Verify user is member of project"""
    member_response = supabase.table("project_members") \
        .select("*") \
        .eq("project_id", project_id) \
        .eq("user_id", current_user.user_id) \
        .execute()
    
    if not member_response.data:
        raise AuthorizationError("Not authorized to access this project")
    
    return True

async def verify_meeting_access(
    meeting_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase)
) -> dict:
    """Verify user has access to meeting and return meeting data"""
    # Get meeting with project information
    meeting_response = supabase.table('meetings') \
        .select('*, projects(*)') \
        .eq('meeting_id', meeting_id) \
        .execute()
    
    if not meeting_response.data:
        raise HTTPException(status_code=404, detail="Meeting not found")
    
    meeting = meeting_response.data[0]
    
    # Check if user is member of the project
    member_response = supabase.table("project_members") \
        .select("*") \
        .eq("project_id", meeting['project_id']) \
        .eq("user_id", current_user.user_id) \
        .execute()
    
    if not member_response.data:
        raise AuthorizationError("Not authorized to access this meeting")
    
    return meeting

# Optional dependencies for when auth is not required
async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    supabase: Client = Depends(get_supabase)
) -> Optional[CurrentUser]:
    """Get current user if authenticated, None otherwise"""
    if not credentials:
        return None
    
    try:
        return await get_current_user(credentials, supabase)
    except:
        return None