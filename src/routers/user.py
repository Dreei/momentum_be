"""
User router: Handles user management, authentication, and profile updates.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, Body
from database.base import get_supabase
from supabase import Client
import uuid
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, EmailStr
from enum import Enum

router = APIRouter()

class UserStatus(str, Enum):
    PENDING = "pending"
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"

class UserBase(BaseModel):
    first_name: str
    last_name: str
    email: EmailStr
    timezone: Optional[str] = "UTC"

class UserCreate(UserBase):
    user_id: Optional[str] = None  # Supabase Auth user ID

class UserUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[EmailStr] = None
    timezone: Optional[str] = None
    status: Optional[UserStatus] = None

class UserResponse(UserBase):
    user_id: uuid.UUID
    status: UserStatus
    created_at: datetime
    updated_at: datetime
    last_login: Optional[datetime]
    last_active_org_id: Optional[uuid.UUID]
    last_active_project_id: Optional[uuid.UUID]

    class Config:
        from_attributes = True

class ProjectContext(BaseModel):
    project_id: str
    project_name: str
    project_role: str

class OrgContext(BaseModel):
    org_id: str
    org_name: str
    org_role: str
    projects: List[ProjectContext] = []

"""
[POST]
/users:
Create a new user.

Args:
    user (UserCreate): User data to create.
    supabase (Client): Supabase client (injected).

Returns:
    UserResponse: Created user data.
"""
@router.post("/", response_model=UserResponse)
def create_user(user: UserCreate, supabase: Client = Depends(get_supabase)):
    # Check if a user with this email exists
    existing_user = supabase.table("users") \
        .select("*") \
        .eq("email", user.email) \
        .execute()
    if existing_user.data:
        user_data = existing_user.data[0]
        if user_data.get("status") == UserStatus.PENDING.value:
            # Activate the pending user
            supabase.table("users").update({
                "first_name": user.first_name,
                "last_name": user.last_name,
                "timezone": user.timezone,
                "status": UserStatus.ACTIVE.value,
                "last_login": datetime.utcnow().isoformat()
            }).eq("user_id", user_data["user_id"]).execute()
            # Fetch updated user
            updated_user = supabase.table("users").select("*").eq("user_id", user_data["user_id"]).execute().data[0]
            return updated_user
        else:
            raise HTTPException(status_code=400, detail="Email already registered")
    # Create new user
    user_data = {
        "first_name": user.first_name,
        "last_name": user.last_name,
        "email": user.email,
        "timezone": user.timezone,
        "status": UserStatus.ACTIVE.value,
        "last_login": datetime.utcnow().isoformat()
    }
    if user.user_id:
        user_data["user_id"] = user.user_id
    response = supabase.table("users").insert(user_data).execute()
    return response.data[0]

"""
[GET]
/users/{user_id}:
Get user information by ID.

Args:
    user_id (uuid.UUID): User ID to retrieve.
    supabase (Client): Supabase client (injected).

Returns:
    UserResponse: User data.
"""
@router.get("/{user_id}", response_model=UserResponse)
def get_user(user_id: uuid.UUID, supabase: Client = Depends(get_supabase)):
    response = supabase.table("users") \
        .select("*") \
        .eq("user_id", str(user_id)) \
        .execute()
    
    if not response.data:
        raise HTTPException(status_code=404, detail="User not found")
    
    return response.data[0]

"""
[GET]
/users:
List users with optional filtering.

Args:
    status (Optional[UserStatus]): Filter by user status.
    skip (int): Number of records to skip.
    limit (int): Maximum number of records to return.
    supabase (Client): Supabase client (injected).

Returns:
    List[UserResponse]: List of users.
"""
@router.get("/", response_model=List[UserResponse])
def list_users(
    status: Optional[UserStatus] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    supabase: Client = Depends(get_supabase)
):
    query = supabase.table("users").select("*")
    
    if status:
        query = query.eq("status", status.value)
    
    response = query.range(skip, skip + limit - 1).execute()
    return response.data

"""
[PATCH]
/users/{user_id}:
Update user information.

Args:
    user_id (uuid.UUID): User ID to update.
    user_update (UserUpdate): Updated user data.
    supabase (Client): Supabase client (injected).

Returns:
    UserResponse: Updated user data.
"""
@router.patch("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: uuid.UUID,
    user_update: UserUpdate,
    supabase: Client = Depends(get_supabase)
):
    
    # Check if user exists
    user_response = supabase.table("users") \
        .select("*") \
        .eq("user_id", str(user_id)) \
        .execute()
    
    if not user_response.data:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Check if new email is already in use
    if user_update.email:
        existing_user = supabase.table("users") \
            .select("*") \
            .eq("email", user_update.email) \
            .neq("user_id", str(user_id)) \
            .execute()
        
        if existing_user.data:
            raise HTTPException(status_code=400, detail="Email already in use")
    
    # Prepare update data
    update_data = user_update.model_dump(exclude_unset=True)
    if update_data:
        update_data["updated_at"] = datetime.utcnow().isoformat()
        
        response = supabase.table("users") \
            .update(update_data) \
            .eq("user_id", str(user_id)) \
            .execute()
        
        return response.data[0]
    
    return user_response.data[0]

"""
[DELETE]
/users/{user_id}:
Deactivate a user (soft delete).

Args:
    user_id (uuid.UUID): User ID to deactivate.
    supabase (Client): Supabase client (injected).

Returns:
    dict: Status message.
"""
@router.delete("/{user_id}")
def deactivate_user(user_id: uuid.UUID, supabase: Client = Depends(get_supabase)):
    # Check if user exists
    user_response = supabase.table("users") \
        .select("*") \
        .eq("user_id", str(user_id)) \
        .execute()
    
    if not user_response.data:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Deactivate user
    supabase.table("users") \
        .update({
            "status": UserStatus.INACTIVE.value,
            "updated_at": datetime.utcnow().isoformat()
        }) \
        .eq("user_id", str(user_id)) \
        .execute()
    
    return {"status": "success", "message": "User deactivated successfully"}

"""
[POST]
/users/{user_id}/update-last-active:
Update the last active organization and project for a user.

Args:
    user_id (uuid.UUID): User ID to update.
    org_id (Optional[uuid.UUID]): Organization ID.
    project_id (Optional[uuid.UUID]): Project ID.
    supabase (Client): Supabase client (injected).

Returns:
    dict: Status message.
"""
@router.post("/{user_id}/update-last-active")
def update_last_active(
    user_id: uuid.UUID,
    org_id: Optional[uuid.UUID] = None,
    project_id: Optional[uuid.UUID] = None,
    supabase: Client = Depends(get_supabase)
):
    # Check if user exists
    user_response = supabase.table("users") \
        .select("*") \
        .eq("user_id", str(user_id)) \
        .execute()
    
    if not user_response.data:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Verify organization exists if provided
    if org_id:
        org_response = supabase.table("organizations") \
            .select("*") \
            .eq("org_id", str(org_id)) \
            .execute()
        
        if not org_response.data:
            raise HTTPException(status_code=404, detail="Organization not found")
    
    # Verify project exists if provided
    if project_id:
        project_response = supabase.table("projects") \
            .select("*") \
            .eq("project_id", str(project_id)) \
            .execute()
        
        if not project_response.data:
            raise HTTPException(status_code=404, detail="Project not found")
    
    # Update last active
    update_data = {
        "updated_at": datetime.utcnow().isoformat()
    }
    
    if org_id:
        update_data["last_active_org_id"] = str(org_id)
    if project_id:
        update_data["last_active_project_id"] = str(project_id)
    
    supabase.table("users") \
        .update(update_data) \
        .eq("user_id", str(user_id)) \
        .execute()
    
    return {"status": "success", "message": "Last active updated successfully"}

"""
[GET]
/users/{user_id}/organizations:
Get all organizations a user belongs to.

Args:
    user_id (uuid.UUID): User ID.
    supabase (Client): Supabase client (injected).

Returns:
    List[dict]: List of organizations with membership details.
"""
@router.get("/{user_id}/organizations")
def get_user_organizations(user_id: uuid.UUID, supabase: Client = Depends(get_supabase)):
    response = supabase.table("organization_members") \
        .select("*, organizations(*)") \
        .eq("user_id", str(user_id)) \
        .eq("status", "active") \
        .execute()
    
    # Filter for active organizations only
    active_members = []
    for member in response.data:
        if member.get("organizations") and member["organizations"].get("status") == "active":
            active_members.append({
                "org_id": member["organizations"]["org_id"],
                "org_name": member["organizations"]["org_name"],
                "role": member["role"],
                "status": member["status"],
                "joined_at": member["joined_at"]
            })
    
    return active_members

"""
[GET]
/users/{user_id}/projects:
Get all projects a user belongs to.

Args:
    user_id (uuid.UUID): User ID.
    supabase (Client): Supabase client (injected).

Returns:
    List[dict]: List of projects with membership details.
"""
@router.get("/{user_id}/projects")
def get_user_projects(user_id: uuid.UUID, supabase: Client = Depends(get_supabase)):
    response = supabase.table("project_members") \
        .select("*, projects(*)") \
        .eq("user_id", str(user_id)) \
        .eq("status", "active") \
        .execute()
    
    # Filter for active projects only
    #if possible please a filter using current org ig, i mean filter the projects based on current org
    active_members = []
    for member in response.data:
        if member.get("projects") and member["projects"].get("status") == "active" :
            active_members.append({
                "project_id": member["projects"]["project_id"],
                "org_id": member["projects"]["org_id"],
                "project_name": member["projects"]["project_name"],
                "role": member["role"],
                "status": member["status"],
                "joined_at": member["joined_at"]
            })
    
    return active_members

@router.post("/by-email")
def get_user_by_email(data: dict = Body(...), supabase: Client = Depends(get_supabase)):
    email = data.get("email")
    if not email:
        raise HTTPException(status_code=400, detail="Email is required")
    user_response = supabase.table("users").select("*").eq("email", email).execute()
    if not user_response.data:
        raise HTTPException(status_code=404, detail="User not found")
    return user_response.data[0]

@router.get("/{user_id}/context", response_model=List[OrgContext])
def get_user_context(user_id: str, supabase: Client = Depends(get_supabase)):
    try:
        org_resp = supabase.table("organization_members")\
            .select("org_id, role, organizations(org_name, status)")\
            .eq("user_id", user_id)\
            .eq("status", "active")\
            .execute()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch organizations: {str(e)}")

    active_orgs = [
        org for org in org_resp.data
        if org.get('organizations') and org['organizations'].get('status') == 'active'
    ]

    try:
        proj_resp = supabase.table("project_members")\
            .select("project_id, role, projects(project_name, status, org_id)")\
            .eq("user_id", user_id)\
            .eq("status", "active")\
            .execute()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch projects: {str(e)}")

    context = []
    for org_member in active_orgs:
        org_id = org_member["org_id"]
        org_name = org_member["organizations"]["org_name"]
        org_role = org_member["role"]

        projects = []
        for pm in proj_resp.data:
            project_data = pm.get("projects")
            if project_data and project_data.get("status") == "active" and project_data.get("org_id") == org_id:
                projects.append(ProjectContext(
                    project_id=pm["project_id"],
                    project_name=project_data["project_name"],
                    project_role=pm["role"]
                ))

        context.append(OrgContext(
            org_id=org_id,
            org_name=org_name,
            org_role=org_role,
            projects=projects
        ))

    return context
