"""
Organization router: Handles organization creation and retrieval of organizations for a user.
"""
from fastapi import APIRouter, Depends, HTTPException, Body, Query
from database.base import get_supabase
from supabase import Client
import uuid
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, EmailStr
from services.email_service import EmailService

router = APIRouter()
email_service = EmailService()

class OrgInviteRequest(BaseModel):
    email: EmailStr
    role: str = "org_member"

"""
/org/setActive:
Set an organization as the active organization for a user.

Args:
    org_id (uuid.UUID): Organization ID.
    user_id (uuid.UUID): User ID.
    supabase (Client): Supabase client (injected).

Returns:
    dict: Status message.
"""
@router.post("/setActive")
def set_active_org(org_id: uuid.UUID = Query(...), user_id: uuid.UUID = Query(...), supabase: Client = Depends(get_supabase)):
    # Check if user exists
    user_response = supabase.table("users").select("*").eq("user_id", str(user_id)).execute()
    if not user_response.data:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Update user's active organization
    supabase.table("users") \
        .update({"last_active_org_id": str(org_id)}) \
        .eq("user_id", str(user_id)) \
        .execute()
    
    return {"status": "active org set"}

"""
/org/setOrgStatus:
Set the status of an organization.
Args:
    user_id (uuid.UUID): User ID.
    org_id (uuid.UUID): Organization ID.
    status (str): New status for the organization(active/inactive).
    supabase (Client): Supabase client (injected).

Returns:
    dict: Status message.
"""
@router.patch("/setOrgStatus")
def set_org_status(user_id: uuid.UUID = Query(...), org_id: uuid.UUID = Query(...), status: str = Query(...), supabase: Client = Depends(get_supabase)):
    # Check if user exists
    user_response = supabase.table("users").select("*").eq("user_id", str(user_id)).execute()
    if not user_response.data:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Check if user is admin
    admin_response = supabase.table("organization_members") \
        .select("*") \
        .eq("user_id", str(user_id)) \
        .eq("org_id", str(org_id)) \
        .eq("role", "org_admin") \
        .execute()
    
    if not admin_response.data:
        raise HTTPException(status_code=403, detail="User is not an organization admin")
    
    # Check if organization exists
    org_response = supabase.table("organizations").select("*").eq("org_id", str(org_id)).execute()
    if not org_response.data:
        raise HTTPException(status_code=404, detail="Organization not found")
    
    if status not in ["active", "inactive"]:
        raise HTTPException(status_code=400, detail="Invalid status. Must be 'active' or 'inactive'")
    
    # Update organization status
    supabase.table("organizations") \
        .update({"status": status}) \
        .eq("org_id", str(org_id)) \
        .execute()
    
    return {"status": "organization status updated"}

"""
/org/create:
Create a new organization and assign the user as org admin.

Args:
    org_name (str): Name of the organization to create (query param).
    user_id (uuid.UUID): UUID of the user creating the organization (query param).
    supabase (Client): Supabase client (injected).

Returns:
    dict: Contains org_id and org_name of the created organization.
"""
@router.post("/create")
def create_org(org_name: str = Query(...), user_id: uuid.UUID = Query(...), supabase: Client = Depends(get_supabase)):
    # Create organization
    org_data = {
        "org_name": org_name,
        "status": "active"
    }
    org_response = supabase.table("organizations").insert(org_data).execute()
    org = org_response.data[0]
    
    # Create organization member
    member_data = {
        "user_id": str(user_id),
        "org_id": org["org_id"],
        "role": "org_admin"
    }
    supabase.table("organization_members").insert(member_data).execute()
    
    return {"org_id": org["org_id"], "org_name": org["org_name"]}

"""
/org/test:
Test endpoint to verify the router is working.
"""
@router.get("/test")
def test_org_router():
    print("🔍 Backend: Test endpoint called")
    return {"message": "Organization router is working", "status": "ok"}

"""
/org/test-db:
Test endpoint to check database connection and list users.
"""
@router.get("/test-db")
def test_database(supabase: Client = Depends(get_supabase)):
    print("🔍 Backend: Testing database connection")
    try:
        # Test basic connection
        users_response = supabase.table("users").select("*").limit(5).execute()
        print(f"🔍 Backend: Found {len(users_response.data) if users_response.data else 0} users")
        
        # Test organizations table
        orgs_response = supabase.table("organizations").select("*").limit(5).execute()
        print(f"🔍 Backend: Found {len(orgs_response.data) if orgs_response.data else 0} organizations")
        
        return {
            "status": "success",
            "users_count": len(users_response.data) if users_response.data else 0,
            "organizations_count": len(orgs_response.data) if orgs_response.data else 0,
            "sample_users": users_response.data[:3] if users_response.data else [],
            "sample_organizations": orgs_response.data[:3] if orgs_response.data else []
        }
    except Exception as e:
        print(f"❌ Backend: Database test failed: {str(e)}")
        return {
            "status": "error",
            "error": str(e)
        }

"""
/org/user:
Get a list of organizations that a user is a member of.

Args:
    user_id (uuid.UUID): UUID of the user.
    supabase (Client): Supabase client (injected).

Returns:
    list: List of organization objects the user belongs to.
"""
@router.get("/user")
def get_user_orgs(user_id: uuid.UUID, supabase: Client = Depends(get_supabase)):
    print(f"🔍 Backend: get_user_orgs called with user_id: {user_id}")
    try:
        # First, check if the user exists
        print(f"🔍 Backend: Checking if user exists: {user_id}")
        user_response = supabase.table("users").select("*").eq("user_id", str(user_id)).execute()
        if not user_response.data:
            print(f"❌ Backend: User not found in database: {user_id}")
            return []
        print(f"✅ Backend: User found in database: {user_response.data[0]}")
        print(f"🔍 Backend: Making Supabase query for user: {user_id}")
        response = supabase.table("organizations") \
            .select("*, organization_members!inner(*)") \
            .eq("organization_members.user_id", str(user_id)) \
            .eq("status", "active") \
            .execute()
        print(f"🔍 Backend: Supabase response received: {len(response.data) if response.data else 0} organizations")
        print(f"🔍 Backend: Response data: {response.data}")
        return response.data
    except Exception as e:
        print(f"❌ Backend: Error in get_user_orgs: {str(e)}")
        print(f"❌ Backend: Error type: {type(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


"""
[POST]
/org/{org_id}/invite:
Invite a user to join an organization.

Args:
    org_id (uuid.UUID): Organization ID.
    invite_data (OrgInviteRequest): Invite data containing email and role.
    requester_id (uuid.UUID): User ID of the requester (must be admin).
    supabase (Client): Supabase client (injected).

Returns:
    dict: Status message.
"""
@router.post("/{org_id}/invite")
def invite_user_to_org(
    org_id: uuid.UUID,
    invite_data: OrgInviteRequest,
    requester_id: uuid.UUID,
    supabase: Client = Depends(get_supabase)
):
    # Check if requester is admin
    admin_response = supabase.table("organization_members") \
        .select("*") \
        .eq("org_id", str(org_id)) \
        .eq("user_id", str(requester_id)) \
        .eq("role", "org_admin") \
        .execute()
    
    if not admin_response.data:
        raise HTTPException(status_code=403, detail="Not authorized to invite users")

    # Check if organization exists
    org_response = supabase.table("organizations") \
        .select("*") \
        .eq("org_id", str(org_id)) \
        .execute()
    
    if not org_response.data:
        raise HTTPException(status_code=404, detail="Organization not found")
    
    org = org_response.data[0]

    # Check if user exists
    user_response = supabase.table("users") \
        .select("*") \
        .eq("email", invite_data.email) \
        .execute()
    
    if not user_response.data:
        raise HTTPException(status_code=404, detail="User not found")
    
    user = user_response.data[0]

    # Check if user is already a member
    existing_member = supabase.table("organization_members") \
        .select("*") \
        .eq("org_id", str(org_id)) \
        .eq("user_id", str(user["user_id"])) \
        .execute()
    
    if existing_member.data:
        raise HTTPException(status_code=400, detail="User is already a member of this organization")

    # Get inviter details
    inviter_response = supabase.table("users") \
        .select("*") \
        .eq("user_id", str(requester_id)) \
        .execute()
    
    if not inviter_response.data:
        raise HTTPException(status_code=404, detail="Inviter not found")
    
    inviter = inviter_response.data[0]

    # Add user to organization
    member_data = {
        "user_id": str(user["user_id"]),
        "org_id": str(org_id),
        "role": invite_data.role,
        "status": "active"
    }
    supabase.table("organization_members").insert(member_data).execute()

    # Send invitation email
    subject = f"You've been invited to join {org['org_name']}"
    html_content = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
            <h2 style="color: #333;">Organization Invitation</h2>
            <p>Hello {user['first_name']},</p>
            <p>{inviter['first_name']} {inviter['last_name']} has invited you to join the organization <b>{org['org_name']}</b>.</p>
            <p>Your role in the organization will be: <b>{invite_data.role}</b></p>
            <p>Please log in to your account to access the organization.</p>
            <div style="margin-top: 20px; padding: 15px; background-color: #f8f9fa; border-radius: 5px;">
                <p style="margin: 0; color: #666;">Organization: {org['org_name']}</p>
                <p style="margin: 5px 0; color: #666;">Role: {invite_data.role}</p>
                <p style="margin: 0; color: #666;">Invited by: {inviter['first_name']} {inviter['last_name']}</p>
            </div>
        </div>
    """
    
    email_service.send_email(
        to_email=user["email"],
        subject=subject,
        html_content=html_content
    )

    return {
        "status": "success",
        "message": f"User {user['email']} has been invited to the organization",
        "role": invite_data.role
    }

@router.get("/active")
def get_active_organization(user_id: str, supabase: Client = Depends(get_supabase)):
    user_response = supabase.table("users").select("*").eq("user_id", user_id).execute()
    if not user_response.data:
        raise HTTPException(status_code=404, detail="User not found")
    user = user_response.data[0]
    org_id = user.get("last_active_org_id")
    if not org_id:
        return None
    org_response = supabase.table("organizations").select("*").eq("org_id", org_id).execute()
    if not org_response.data:
        return None
    return org_response.data[0]

"""
[GET]
/org/{org_id}/members:
Get all members for a specific organization.

Args:
    org_id (uuid.UUID): Organization ID.
    supabase (Client): Supabase client (injected).

Returns:
    list: List of organization members with their details.
"""
@router.get("/{org_id}/members")
def get_organization_members(org_id: uuid.UUID, supabase: Client = Depends(get_supabase)):
    # Verify organization exists
    org_response = supabase.table("organizations") \
        .select("*") \
        .eq("org_id", str(org_id)) \
        .execute()
    
    if not org_response.data:
        raise HTTPException(status_code=404, detail="Organization not found")
    
    # Get all members with their user details (only active members)
    members_response = supabase.table("organization_members") \
        .select("*, users(*)") \
        .eq("org_id", str(org_id)) \
        .eq("status", "active") \
        .execute()
    
    return [{
        "user_id": m["users"]["user_id"],
        "first_name": m["users"]["first_name"],
        "last_name": m["users"]["last_name"],
        "email": m["users"]["email"],
        "role": m["role"],
        "status": m["status"],
        "joined_at": m["joined_at"]
    } for m in members_response.data]

"""
[PATCH]
/org/{org_id}:
Update organization fields (e.g., org_name, avatar). Only org_admins can update.

Args:
    org_id (uuid.UUID): Organization ID.
    org_name (Optional[str]): New organization name.
    avatar (Optional[str]): New avatar URL.
    user_id (uuid.UUID): User ID of the requester (must be admin).
    supabase (Client): Supabase client (injected).

Returns:
    dict: Status message.
"""
@router.patch("/{org_id}")
def update_organization(
    org_id: uuid.UUID,
    user_id: uuid.UUID = Query(...),
    org_name: Optional[str] = Query(None),
    supabase: Client = Depends(get_supabase)
):
    # Check if user is admin
    admin_response = supabase.table("organization_members") \
        .select("*") \
        .eq("org_id", str(org_id)) \
        .eq("user_id", str(user_id)) \
        .eq("role", "org_admin") \
        .execute()
    if not admin_response.data:
        raise HTTPException(status_code=403, detail="Not authorized")

    update_data = {}
    if org_name is not None:
        update_data["org_name"] = org_name
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")

    supabase.table("organizations") \
        .update(update_data) \
        .eq("org_id", str(org_id)) \
        .execute()

    return {"status": "updated"}

"""
[GET]
/org/{org_id}:
Get a single organization by its ID.

Args:
    org_id (uuid.UUID): Organization ID.
    supabase (Client): Supabase client (injected).

Returns:
    dict: Organization object.
"""
@router.get("/{org_id}")
def get_organization(org_id: uuid.UUID, supabase: Client = Depends(get_supabase)):
    org_response = supabase.table("organizations") \
        .select("*") \
        .eq("org_id", str(org_id)) \
        .execute()
    if not org_response.data:
        raise HTTPException(status_code=404, detail="Organization not found")
    return org_response.data[0]

"""
[DELETE]
/org/{org_id}:
Soft delete an organization by setting its status to 'inactive'. Only org_admin can delete.

Args:
    org_id (uuid.UUID): Organization ID.
    user_id (uuid.UUID): User ID of the requester (must be admin).
    supabase (Client): Supabase client (injected).

Returns:
    dict: Status message.
"""
@router.delete("/{org_id}")
def delete_organization(org_id: uuid.UUID, user_id: uuid.UUID = Query(...), supabase: Client = Depends(get_supabase)):
    # Check if user is admin
    admin_response = supabase.table("organization_members") \
        .select("role") \
        .eq("org_id", str(org_id)) \
        .eq("user_id", str(user_id)) \
        .execute()
    is_admin = admin_response.data and any(m["role"] == "org_admin" for m in admin_response.data)

    if not is_admin:
        raise HTTPException(status_code=403, detail="Not authorized. Only org admin can delete organization.")

    # Get current organization status
    org_status_response = supabase.table("organizations") \
        .select("status") \
        .eq("org_id", str(org_id)) \
        .single() \
        .execute()
    if not org_status_response.data:
        raise HTTPException(status_code=404, detail="Organization not found.")
    current_status = org_status_response.data.get("status")
    if current_status == "inactive":
        return {"message": "Organization is already inactive."}

    # Soft delete organization
    supabase.table("organizations") \
        .update({"status": "inactive"}) \
        .eq("org_id", str(org_id)) \
        .execute()

    # Soft delete projects under the organization
    supabase.table("projects") \
        .update({"status": "inactive"}) \
        .eq("org_id", str(org_id)) \
        .execute()

    # Soft delete organization_members
    supabase.table("organization_members") \
        .update({"status": "inactive"}) \
        .eq("org_id", str(org_id)) \
        .execute()

    # Soft delete project_members for all related projects
    project_ids_response = supabase.table("projects") \
        .select("project_id") \
        .eq("org_id", str(org_id)) \
        .execute()
    project_ids = [p["project_id"] for p in (project_ids_response.data or [])]
    for pid in project_ids:
        supabase.table("project_members") \
            .update({"status": "inactive"}) \
            .eq("project_id", pid) \
            .execute()

    # Set last_active_org_id to null for users whose last_active_org_id is this org
    supabase.table("users") \
        .update({"last_active_org_id": None}) \
        .eq("last_active_org_id", str(org_id)) \
        .execute()

    # Set last_active_project_id to null for users whose last_active_project_id is a project from this org
    if project_ids:
        supabase.table("users") \
            .update({"last_active_project_id": None}) \
            .in_("last_active_project_id", project_ids) \
            .execute()

    return {"message": "Organization and related entities set to inactive (soft deleted)."}
