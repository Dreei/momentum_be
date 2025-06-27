# src/routers/auth.py - Authentication router
from fastapi import APIRouter, Depends, HTTPException, status
from supabase import Client
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from src.database.base import get_supabase
from src.core.dependencies import get_current_user, CurrentUser
from src.services.auth_service import auth_service
from src.core.exceptions import AuthenticationError

router = APIRouter()

# Pydantic models
class GoogleTokenRequest(BaseModel):
    token: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: dict

class UserProfileResponse(BaseModel):
    user_id: str
    first_name: str
    last_name: str
    email: str
    status: str
    created_at: str
    updated_at: str
    last_login: Optional[str]
    timezone: str
    last_active_org_id: Optional[str]
    last_active_project_id: Optional[str]
    organizations: list
    projects: list

@router.post("/google", response_model=TokenResponse)
async def authenticate_with_google(
    request: GoogleTokenRequest,
    supabase: Client = Depends(get_supabase)
):
    """
    Authenticate user with Google OAuth token
    
    Args:
        request: Contains Google ID token
        
    Returns:
        JWT access token and user information
    """
    try:
        access_token, user_data = auth_service.authenticate_google_user(
            request.token, 
            supabase
        )
        
        return TokenResponse(
            access_token=access_token,
            expires_in=auth_service.access_token_expire_minutes * 60,
            user={
                "user_id": user_data["user_id"],
                "email": user_data["email"],
                "first_name": user_data["first_name"],
                "last_name": user_data["last_name"],
                "status": user_data["status"]
            }
        )
        
    except AuthenticationError:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Authentication failed: {str(e)}"
        )

@router.get("/me", response_model=UserProfileResponse)
async def get_current_user_profile(
    current_user: CurrentUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase)
):
    """
    Get current authenticated user's complete profile
    
    Returns:
        Complete user profile with organizations and projects
    """
    try:
        profile = auth_service.get_user_profile(current_user, supabase)
        if profile.get('status') != 'active':
            raise HTTPException(status_code=403, detail='User is not active. Please contact support or sign up.')
        return UserProfileResponse(**profile)
        
    except AuthenticationError:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve user profile: {str(e)}"
        )

@router.post("/refresh")
async def refresh_token(
    current_user: CurrentUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase)
):
    """
    Refresh user's access token and update activity
    
    Returns:
        New access token
    """
    try:
        # Update user activity
        auth_service.update_user_activity(current_user.user_id, supabase)
        
        # Create new token
        token_data = {"sub": current_user.email, "user_id": current_user.user_id}
        access_token = auth_service.create_access_token(token_data)
        
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "expires_in": auth_service.access_token_expire_minutes * 60
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to refresh token: {str(e)}"
        )

@router.post("/logout")
async def logout(
    current_user: CurrentUser = Depends(get_current_user),
    supabase: Client = Depends(get_supabase)
):
    """
    Logout current user
    
    Note: Since we're using stateless JWT tokens, this mainly serves
    to update the user's last activity. The frontend should discard the token.
    """
    try:
        # Update user status (optional - could be used for tracking)
        supabase.table('users').update({
            'last_login': datetime.utcnow().isoformat()
        }).eq('user_id', current_user.user_id).execute()
        
        return {"message": "Successfully logged out"}
        
    except Exception as e:
        # Don't fail logout even if database update fails
        return {"message": "Successfully logged out"}

@router.get("/verify")
async def verify_token(current_user: CurrentUser = Depends(get_current_user)):
    """
    Verify if the current token is valid
    
    Returns:
        User information if token is valid
    """
    return {
        "valid": True,
        "user": {
            "user_id": current_user.user_id,
            "email": current_user.email,
            "full_name": current_user.full_name
        }
    }