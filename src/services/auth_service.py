# src/services/auth_service.py - Authentication service
from datetime import datetime, timedelta
from typing import Optional
from jose import jwt
from supabase import Client
import requests
import logging

from src.core.config import settings
from src.core.exceptions import AuthenticationError, ValidationError
from src.core.dependencies import CurrentUser

logger = logging.getLogger(__name__)

class AuthService:
    """Authentication service for handling Google OAuth and JWT tokens"""
    
    def __init__(self):
        self.secret_key = settings.SECRET_KEY
        self.algorithm = settings.ALGORITHM
        self.access_token_expire_minutes = settings.ACCESS_TOKEN_EXPIRE_MINUTES
        self.google_client_id = settings.GOOGLE_CLIENT_ID

    def verify_google_token(self, token: str) -> dict:
        """Verify Google ID token and return user info"""
        try:
            from google.auth.transport import requests as google_requests
            from google.oauth2 import id_token
            
            # Verify the token
            idinfo = id_token.verify_oauth2_token(
                token, google_requests.Request(), self.google_client_id
            )
            
            # Check if the token is for our app
            if idinfo['aud'] != self.google_client_id:
                raise ValueError('Wrong audience.')
                
            return idinfo
        except ValueError as e:
            raise AuthenticationError(f"Invalid Google token: {str(e)}")
        except ImportError:
            raise AuthenticationError("Google auth library not available")

    def create_access_token(self, data: dict, expires_delta: Optional[timedelta] = None) -> str:
        """Create JWT access token"""
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=self.access_token_expire_minutes)
        
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        return encoded_jwt

    def get_or_create_user(self, user_info: dict, supabase: Client) -> dict:
        """Get existing user or create new user from Google OAuth data or email signup"""
        email = user_info.get('email')
        if not email:
            raise ValidationError("Email is required", "email")

        # Check if a user with this email exists
        user_response = supabase.table('users').select('*').eq('email', email).execute()
        if user_response.data:
            user_data = user_response.data[0]
            # If user is pending, activate them
            if user_data.get('status') == 'pending':
                supabase.table('users').update({
                    'first_name': user_info.get('given_name', user_data.get('first_name', '')),
                    'last_name': user_info.get('family_name', user_data.get('last_name', '')),
                    'last_login': datetime.utcnow().isoformat(),
                    'status': 'active',
                    'timezone': user_data.get('timezone', 'UTC')
                }).eq('user_id', user_data['user_id']).execute()
                # Fetch updated user
                user_response = supabase.table('users').select('*').eq('user_id', user_data['user_id']).execute()
                return user_response.data[0]
            else:
                # If user is already active/inactive/suspended, just update last_login and status
                supabase.table('users').update({
                    'last_login': datetime.utcnow().isoformat(),
                    'status': 'active'
                }).eq('user_id', user_data['user_id']).execute()
                return user_data
        else:
            # No user found, create new
            user_data = {
                'first_name': user_info.get('given_name', ''),
                'last_name': user_info.get('family_name', ''),
                'email': email,
                'status': 'active',
                'last_login': datetime.utcnow().isoformat(),
                'timezone': 'UTC'
            }
            response = supabase.table('users').insert(user_data).execute()
            if not response.data:
                raise AuthenticationError("Failed to create user account")
            return response.data[0]

    def authenticate_google_user(self, google_token: str, supabase: Client) -> tuple[str, dict]:
        """Authenticate user with Google token and return JWT token + user data"""
        # Verify Google token
        user_info = self.verify_google_token(google_token)
        
        # Get or create user
        user_data = self.get_or_create_user(user_info, supabase)
        
        # Create JWT token
        token_data = {"sub": user_data['email'], "user_id": user_data['user_id']}
        access_token = self.create_access_token(token_data)
        
        return access_token, user_data

    def update_user_activity(self, user_id: str, supabase: Client) -> bool:
        """Update user's last activity timestamp"""
        try:
            supabase.table('users').update({
                'last_login': datetime.utcnow().isoformat(),
                'status': 'active'
            }).eq('user_id', user_id).execute()
            
            return True
        except Exception as e:
            logger.error(f"Failed to update user activity: {str(e)}")
            return False

    def get_user_profile(self, current_user: CurrentUser, supabase: Client) -> dict:
        """Get complete user profile with organization and project info"""
        try:
            # Get user basic info
            user_response = supabase.table('users').select('*').eq('user_id', current_user.user_id).execute()
            
            if not user_response.data:
                raise AuthenticationError("User not found")
            
            user_data = user_response.data[0]
            
            # Get organization memberships
            org_response = supabase.table('organization_members') \
                .select('*, organizations(*)') \
                .eq('user_id', current_user.user_id) \
                .execute()
            
            organizations = []
            for org_member in org_response.data:
                org = org_member['organizations']
                organizations.append({
                    'org_id': org['org_id'],
                    'org_name': org['org_name'],
                    'role': org_member['role'],
                    'joined_at': org_member['joined_at']
                })
            
            # Get project memberships
            project_response = supabase.table('project_members') \
                .select('*, projects(*, organizations(*))') \
                .eq('user_id', current_user.user_id) \
                .execute()
            
            projects = []
            for project_member in project_response.data:
                project = project_member['projects']
                projects.append({
                    'project_id': project['project_id'],
                    'project_name': project['project_name'],
                    'description': project['description'],
                    'role': project_member['role'],
                    'organization': {
                        'org_id': project['organizations']['org_id'],
                        'org_name': project['organizations']['org_name']
                    },
                    'joined_at': project_member['joined_at']
                })
            
            return {
                **user_data,
                'organizations': organizations,
                'projects': projects
            }
            
        except Exception as e:
            logger.error(f"Error getting user profile: {str(e)}")
            raise AuthenticationError("Failed to retrieve user profile")

# Create global auth service instance
auth_service = AuthService()