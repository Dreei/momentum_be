"""
Project router: Handles project creation, updating, deletion, and participant management within an organization.
"""
from fastapi import APIRouter, Depends, HTTPException, Body, Query
from database.base import get_supabase
from supabase import Client
import uuid
from services.email_service import EmailService
from crud import generate_context_groups
from src.core.config import ML_AVAILABLE, GEMINI_AVAILABLE

router = APIRouter()
email_service = EmailService()


"""
/proj/setActive:
Set a project as the active project for a user.

Args:
    project_id (uuid.UUID): Project ID.
    user_id (uuid.UUID): User ID.
    supabase (Client): Supabase client (injected).

Returns:
    dict: Status message.
"""
@router.post("/setActive")
def set_active_project(project_id: uuid.UUID = Query(...), user_id: uuid.UUID = Query(...), supabase: Client = Depends(get_supabase)):
    # Update user's active project
    supabase.table("users") \
        .update({"last_active_project_id": str(project_id)}) \
        .eq("user_id", str(user_id)) \
        .execute()
    
    return {"status": "active project set"}


"""
/proj/setProjectStatus:
Set the status of a project.

Args:
    project_id (uuid.UUID): Project ID.
    status (str): New status for the project (active/inactive).
    supabase (Client): Supabase client (injected).

Returns:
    dict: Status message.
"""
@router.patch("/setProjectStatus")
def set_project_status(user_id: uuid.UUID = Query(...), project_id: uuid.UUID = Query(...), status: str = Query(...), supabase: Client = Depends(get_supabase)):
    """
    Set the status of a project.

    Args:
        project_id (uuid.UUID): Project ID.
        status (str): New status for the project (active/inactive).
        supabase (Client): Supabase client (injected).

    Returns:
        dict: Status message.
    """
    # Check if user is admin
    admin_response = supabase.table("project_members") \
        .select("*") \
        .eq("project_id", str(project_id)) \
        .eq("user_id", str(user_id)) \
        .eq("role", "project_admin") \
        .execute()
    
    if not admin_response.data:
        raise HTTPException(status_code=403, detail="Not authorized")

    if status not in ["active", "inactive"]:
        raise HTTPException(status_code=400, detail="Invalid status. Must be 'active' or 'inactive'")

    # Update project status
    supabase.table("projects") \
        .update({"status": status}) \
        .eq("project_id", str(project_id)) \
        .execute()
    
    return {"status": "success", "message": f"Project status updated to {status}"}


"""
/proj/create:
Create a new project within an organization and assign the creator as project admin.

Args:
    name (str): Name of the project.
    description (str): Project description.
    org_id (uuid.UUID): Organization ID the project belongs to.
    user_id (uuid.UUID): User ID of the creator.
    supabase (Client): Supabase client (injected).

Returns:
    dict: Contains project_id and project_name of the created project.
"""
@router.post("/create")
def create_project(
    name: str = Query(...),
    description: str = Query(...),
    org_id: uuid.UUID = Query(...),
    user_id: uuid.UUID = Query(...),
    supabase: Client = Depends(get_supabase)
):
    print(f"Creating project: {name}, Org ID: {org_id}, User ID: {user_id}")
    
    # Create project
    project_data = {
        "project_name": name,
        "description": description,
        "org_id": str(org_id),
        "created_by": str(user_id),
        "status": "active"
    }
    project_response = supabase.table("projects").insert(project_data).execute()
    project = project_response.data[0]

    # Add creator as project admin (include org_id)
    member_data = {
        "user_id": str(user_id),
        "project_id": project["project_id"],
        "org_id": str(org_id),
        "role": "project_admin"
    }
    supabase.table("project_members").insert(member_data).execute()

    # After adding to project_members
    org_id = project["org_id"]
    org_member_exists = supabase.table("organization_members") \
        .select("user_id") \
        .eq("user_id", user_id) \
        .eq("org_id", org_id) \
        .execute()

    if not org_member_exists.data:
        supabase.table("organization_members").insert({
            "user_id": str(user_id),
            "org_id": str(org_id),
            "role": "org_member",
            "status": "active"
        }).execute()

    return {"project_id": project["project_id"], "project_name": project["project_name"]}



"""
/proj/byOrg:
Get all projects belonging to a specific organization.

Args:
    org_id (uuid.UUID): Organization ID.
    supabase (Client): Supabase client (injected).

Returns:
    list: List of project objects.
"""
@router.get("/byOrg")
def get_projects_by_org(org_id: uuid.UUID, supabase: Client = Depends(get_supabase)):
    response = supabase.table("projects") \
        .select("*") \
        .eq("org_id", str(org_id)) \
        .eq("status", "active") \
        .execute()
    return response.data


"""
[PUT]
/proj/{project_id}:
Update a project's name, description, and profile picture URL. Only project admins can update.

Args:
    project_id (uuid.UUID): Project ID.
    name (str): New project name.
    description (str): New description.
    profilePicUrl (str): New profile picture URL.
    user_id (uuid.UUID): User ID of the requester.
    supabase (Client): Supabase client (injected).

Returns:
    dict: Status message.
"""
@router.put("/{project_id}")
def update_project(
    project_id: uuid.UUID,
    name: str = Query(...),
    description: str = Query(...),
    profilePicUrl: str = Query(...),
    user_id: uuid.UUID = Query(...),
    supabase: Client = Depends(get_supabase)
):
    # Check if user is admin
    admin_response = supabase.table("project_members") \
        .select("*") \
        .eq("project_id", str(project_id)) \
        .eq("user_id", str(user_id)) \
        .eq("role", "project_admin") \
        .execute()
    
    if not admin_response.data:
        raise HTTPException(status_code=403, detail="Not authorized")

    # Update project
    supabase.table("projects") \
        .update({
            "project_name": name,
            "description": description,
            "profile_url": profilePicUrl,
            "updated_at": "now()"
        }) \
        .eq("project_id", str(project_id)) \
        .execute()
    
    return {"status": "updated"}





"""
[DELETE]
/proj/{project_id}:
Soft delete a project by setting its status to 'inactive'. Only project_admins can delete.

Args:
    project_id (uuid.UUID): Project ID.
    user_id (uuid.UUID): User ID of the requester (must be admin, passed as query param).
    supabase (Client): Supabase client (injected).

Returns:
    dict: Status message.
"""
@router.delete("/{project_id}")
def delete_project(project_id: uuid.UUID, user_id: uuid.UUID = Query(...), supabase: Client = Depends(get_supabase)):
    # Check if user is admin
    admin_response = supabase.table("project_members") \
        .select("*") \
        .eq("project_id", str(project_id)) \
        .eq("user_id", str(user_id)) \
        .eq("role", "project_admin") \
        .execute()
    if not admin_response.data:
        raise HTTPException(status_code=403, detail="Not authorized")

    # Set status to inactive (soft delete)
    supabase.table("projects") \
        .update({"status": "inactive"}) \
        .eq("project_id", str(project_id)) \
        .execute()

    return {"status": "deleted (soft)", "message": "Project set to inactive"}





"""
[GET]
/proj/{project_id}/participants:
Get all participants for a specific project.

Args:
    project_id (uuid.UUID): Project ID.
    supabase (Client): Supabase client (injected).

Returns:
    list: List of project participants with their details.
"""
@router.get("/{project_id}/participants")
def get_project_participants(project_id: uuid.UUID, supabase: Client = Depends(get_supabase)):
    # Verify project exists
    project_response = supabase.table("projects") \
        .select("*") \
        .eq("project_id", str(project_id)) \
        .execute()
    
    if not project_response.data:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Get all participants with their user details (only active participants)
    participants_response = supabase.table("project_members") \
        .select("*, users(*)") \
        .eq("project_id", str(project_id)) \
        .eq("status", "active") \
        .execute()
    
    return [{
        "user_id": p["users"]["user_id"],
        "first_name": p["users"]["first_name"],
        "last_name": p["users"]["last_name"],
        "email": p["users"]["email"],
        "role": p["role"],
        "joined_at": p["joined_at"]
    } for p in participants_response.data]











"""
[POST]
/proj/{project_id}/participants:
Add a participant to a project. Only project admins can add.

Args:
    project_id (uuid.UUID): Project ID.
    email (str): Email of the participant.
    role (str): Role to assign.
    requester_id (uuid.UUID): User ID of the requester (must be admin).
    supabase (Client): Supabase client (injected).

Returns:
    dict: Status message.
"""
@router.post("/{project_id}/participants")
def add_participant(project_id: uuid.UUID, email: str, role: str = "member", requester_id: uuid.UUID = None, supabase: Client = Depends(get_supabase)):
    try:
        print(f"Adding participant - Project ID: {project_id}, Email: {email}, Role: {role}, Requester ID: {requester_id}")
        
        # Check if requester is admin
        admin_response = supabase.table("project_members") \
            .select("*") \
            .eq("project_id", str(project_id)) \
            .eq("user_id", str(requester_id)) \
            .eq("role", "project_admin") \
            .execute()
        
        print(f"Admin check result: {len(admin_response.data) if admin_response.data else 0} records found")
        
        if not admin_response.data:
            raise HTTPException(status_code=403, detail="Not authorized")

        # Get org_id for the current project
        project_resp = supabase.table("projects").select("org_id, project_name").eq("project_id", project_id).single().execute()
        if not project_resp.data:
            raise ValueError("Project not found")
        org_id = project_resp.data["org_id"]
        project_name = project_resp.data["project_name"]
        print("the current project is", project_name)

        # Look up user by email or create new user
        print(f"Looking up user by email: {email}")
        user_resp = supabase.table("users").select("*").eq("email", email).execute()
        
        if user_resp.data and len(user_resp.data) > 0:
            # User exists, use their ID
            user_id = user_resp.data[0]["user_id"]
            print(f"Found existing user: {user_id}")
        else:
            # User doesn't exist, create new user with pending status
            user_id = str(uuid.uuid4())
            print(f"Creating new user with ID: {user_id}")
            user_insert_result = supabase.table("users").insert({
                "user_id": user_id,
                "email": email,
                "first_name": "",
                "last_name": "",
                "status": "pending",
            }).execute()
            print(f"User creation result: {user_insert_result.data if user_insert_result.data else 'No data returned'}")

        # 1. Add user to project_members for the current project (if not already present)
        exists = supabase.table("project_members") \
            .select("*") \
            .eq("project_id", str(project_id)) \
            .eq("user_id", str(user_id)) \
            .execute()
        
        print(f"Checking if user already in project: {len(exists.data) if exists.data else 0} records found")
        
        if not exists.data:
            participant_data = {
                "user_id": str(user_id),
                "project_id": str(project_id),
                "org_id": str(org_id),
                "role": role
            }
            print(f"Adding participant data: {participant_data}")
            project_member_result = supabase.table("project_members").insert(participant_data).execute()
            print(f"Project member insertion result: {project_member_result.data if project_member_result.data else 'No data returned'}")

        # 2. Add user to organization_members for the org (if not already present)
        org_member_check = supabase.table("organization_members") \
            .select("user_id") \
            .eq("user_id", user_id) \
            .eq("org_id", org_id) \
            .execute()
            
        print(f"Checking if user already in organization: {len(org_member_check.data) if org_member_check.data else 0} records found")
        
        if not org_member_check.data:
            org_member_data = {
                "user_id": str(user_id),
                "org_id": str(org_id),
                "role": "org_member",
                "status": "active"
            }
            print(f"Adding org member data: {org_member_data}")
            org_member_result = supabase.table("organization_members").insert(org_member_data).execute()
            print(f"Org member insertion result: {org_member_result.data if org_member_result.data else 'No data returned'}")

        # Send invite if user exists
        user_resp = supabase.table("users").select("email").eq("user_id", user_id).execute()
        user_email = user_resp.data[0]["email"] if user_resp.data and len(user_resp.data) > 0 else email
        try:
            email_service.send_participant_invite(user_email, project_name, "You've been added to a project.")
            print(f"Email sent successfully to: {user_email}")
        except Exception as e:
            print(f"Warning: Failed to send invite/notification: {e}")

        print("Participant added successfully")
        return {"status": "participant added and invited"}
        
    except Exception as e:
        print(f"Error in add_participant: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")







"""
[DELETE]
/proj/{project_id}/participants/{user_id}:
Remove a participant from a project. Only project admins can remove.

Args:
    project_id (uuid.UUID): Project ID.
    user_id (uuid.UUID): User ID to remove.
    requester_id (uuid.UUID): User ID of the requester (must be admin).
    supabase (Client): Supabase client (injected).

Returns:
    dict: Status message.
"""

@router.delete("/{project_id}/participants/{user_id}")
def remove_participant(project_id: uuid.UUID, user_id: uuid.UUID, requester_id: uuid.UUID, supabase: Client = Depends(get_supabase)):
    # Check if requester is admin
    admin_response = supabase.table("project_members") \
        .select("*") \
        .eq("project_id", str(project_id)) \
        .eq("user_id", str(requester_id)) \
        .eq("role", "project_admin") \
        .execute()
    
    if not admin_response.data:
        raise HTTPException(status_code=403, detail="Not authorized")

    # Get user and project info for email
    user_response = supabase.table("users").select("*").eq("user_id", str(user_id)).execute()
    project_response = supabase.table("projects").select("*").eq("project_id", str(project_id)).execute()

    if user_response.data and project_response.data:
        user = user_response.data[0]
        project = project_response.data[0]
        email_service.send_removal_notification(user["email"], project["project_name"])

    # Remove participant
    supabase.table("project_members") \
        .delete() \
        .eq("project_id", str(project_id)) \
        .eq("user_id", str(user_id)) \
        .execute()
    
    return {"status": "participant removed"}



"""
[PATCH]
/proj/{project_id}/participants/{user_id}:
Update a participant's role in a project. Only project admins can update.

Args:
    project_id (uuid.UUID): Project ID.
    user_id (uuid.UUID): User ID to update.
    role (str): New role.
    requester_id (uuid.UUID): User ID of the requester (must be admin).
    supabase (Client): Supabase client (injected).

Returns:
    dict: Status message.
"""
@router.patch("/{project_id}/participants/{user_id}")
def update_participant_role(project_id: uuid.UUID, user_id: uuid.UUID, role: str, requester_id: uuid.UUID, supabase: Client = Depends(get_supabase)):
    # Check if requester is admin
    admin_response = supabase.table("project_members") \
        .select("*") \
        .eq("project_id", str(project_id)) \
        .eq("user_id", str(requester_id)) \
        .eq("role", "project_admin") \
        .execute()
    
    if not admin_response.data:
        raise HTTPException(status_code=403, detail="Not authorized")

    # Update role
    supabase.table("project_members") \
        .update({"role": role}) \
        .eq("project_id", str(project_id)) \
        .eq("user_id", str(user_id)) \
        .execute()

    # Send email notification
    user_response = supabase.table("users").select("*").eq("user_id", str(user_id)).execute()
    project_response = supabase.table("projects").select("*").eq("project_id", str(project_id)).execute()
    
    if user_response.data and project_response.data:
        user = user_response.data[0]
        project = project_response.data[0]
        email_service.send_role_update(user["email"], project["project_name"], role)

    return {"status": "role updated"}


@router.get("/active")
def get_active_project(user_id: str, supabase: Client = Depends(get_supabase)):
    user_response = supabase.table("users").select("*").eq("user_id", user_id).execute()
    if not user_response.data:
        raise HTTPException(status_code=404, detail="User not found")
    user = user_response.data[0]
    project_id = user.get("last_active_project_id")
    if not project_id:
        return None
    project_response = supabase.table("projects").select("*").eq("project_id", project_id).execute()
    if not project_response.data:
        return None
    return project_response.data[0]

"""
[GET]
/proj/{project_id}:
Get a single project by its ID.

Args:
    project_id (uuid.UUID): Project ID.
    supabase (Client): Supabase client (injected).

Returns:
    dict: Project object.
"""
@router.get("/{project_id}")
def get_project(project_id: uuid.UUID, supabase: Client = Depends(get_supabase)):
    project_response = supabase.table("projects") \
        .select("*") \
        .eq("project_id", str(project_id)) \
        .execute()
    if not project_response.data:
        raise HTTPException(status_code=404, detail="Project not found")
    return project_response.data[0]

@router.post("/{project_id}/generate-context-groups", tags=["Context Groups"])
async def generate_context_groups_route(project_id: str):
    """Generate context groups for a project using AI clustering"""
    if not ML_AVAILABLE:
        raise HTTPException(
            status_code=503, 
            detail="Machine learning libraries not available. Please install scikit-learn and numpy."
        )
    if not GEMINI_AVAILABLE:
        raise HTTPException(
            status_code=503, 
            detail="AI libraries not available. Please install google-generativeai."
        )
    try:
        result = generate_context_groups(project_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate context groups: {str(e)}")