from fastapi import APIRouter, Depends, HTTPException, Path, Query
from database.base import get_supabase
from supabase import Client
from typing import List, Dict, Any
from datetime import datetime
import uuid

router = APIRouter()

# --- Get notifications for a user (for bell icon) ---
@router.get("/user/{user_id}/notifications")
async def get_user_notifications(
    user_id: str = Path(...),
    only_unread: bool = Query(False),
    supabase: Client = Depends(get_supabase)
):
    # Build query with joins to get related data
    select_fields = """
        *,
        meetings!inner(
            title,
            project_id,
            projects!inner(
                project_name,
                org_id,
                organizations!inner(
                    org_name
                )
            ),
            users!meetings_created_by_fkey(
                first_name,
                last_name
            )
        )
    """
    
    query = supabase.table("notifications").select(select_fields).eq("user_id", user_id)
    if only_unread:
        query = query.eq("status", "unread")
    
    response = query.order("created_at", desc=True).execute()
    
    # Transform the data to flatten the nested structure
    notifications = []
    for notification in response.data:
        meeting = notification.get("meetings", {})
        project = meeting.get("projects", {}) if meeting else {}
        organization = project.get("organizations", {}) if project else {}
        creator = meeting.get("users", {}) if meeting else {}
        
        transformed_notification = {
            "notification_id": notification.get("notification_id"),
            "user_id": notification.get("user_id"),
            "meeting_id": notification.get("meeting_id"),
            "edit_request_id": notification.get("edit_request_id"),
            "type": notification.get("type"),
            "status": notification.get("status"),
            "created_at": notification.get("created_at"),
            "updated_at": notification.get("updated_at"),
            # Additional fields
            "meeting_title": meeting.get("title", ""),
            "project_title": project.get("project_name", ""),
            "organization_name": organization.get("org_name", ""),
            "creator_first_name": creator.get("first_name", ""),
            "creator_last_name": creator.get("last_name", ""),
            "creator_name": f"{creator.get('first_name', '')} {creator.get('last_name', '')}".strip()
        }
        notifications.append(transformed_notification)
    
    return {"notifications": notifications}

# --- Mark a notification as read ---
@router.patch("/notification/{notification_id}")
async def mark_notification_read(
    notification_id: str = Path(...),
    supabase: Client = Depends(get_supabase)
):
    notif = supabase.table("notifications").select("*").eq("notification_id", notification_id).execute().data
    if not notif:
        raise HTTPException(status_code=404, detail="Notification not found")
    supabase.table("notifications").update({
        "status": "read",
        "updated_at": datetime.utcnow().isoformat()
    }).eq("notification_id", notification_id).execute()
    return {"notification_id": notification_id, "status": "read"}

# --- Utility: Create notification for host/admin on edit request (to be called from summary.py) ---
async def create_edit_pending_notifications(meeting_id: str, edit_request_id: str, supabase: Client):
    # Find host and project admins for the meeting
    meeting = supabase.table("meetings").select("*").eq("meeting_id", meeting_id).execute().data
    if not meeting:
        return
    host_id = meeting[0]["created_by"]
    project_id = meeting[0]["project_id"]
    # Get all project admins
    admins = supabase.table("project_members").select("user_id").eq("project_id", project_id).eq("role", "project_admin").execute().data
    admin_ids = [a["user_id"] for a in admins] if admins else []
    # Always notify host, even if not a project admin
    notify_ids = set(admin_ids + [host_id])
    now = datetime.utcnow().isoformat()
    for user_id in notify_ids:
        notif_data = {
            "notification_id": str(uuid.uuid4()),
            "user_id": user_id,
            "meeting_id": meeting_id,
            "edit_request_id": edit_request_id,
            "type": "edit_pending",
            "status": "unread",
            "created_at": now,
            "updated_at": now
        }
        supabase.table("notifications").insert(notif_data).execute() 