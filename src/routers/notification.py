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
    # First, get the notifications for the user
    query = supabase.table("notifications").select("*").eq("user_id", user_id)
    if only_unread:
        query = query.eq("status", "unread")
    
    notifications_response = query.order("created_at", desc=True).execute()
    
    # Transform each notification by fetching related data
    notifications = []
    for notification in notifications_response.data:
        # Get meeting details
        meeting_response = supabase.table("meetings").select("title, project_id").eq("meeting_id", notification["meeting_id"]).execute()
        meeting = meeting_response.data[0] if meeting_response.data else {}
        
        # Get project details
        project = {}
        if meeting.get("project_id"):
            project_response = supabase.table("projects").select("project_name, org_id").eq("project_id", meeting["project_id"]).execute()
            project = project_response.data[0] if project_response.data else {}
        
        # Get organization details
        organization = {}
        if project.get("org_id"):
            org_response = supabase.table("organizations").select("org_name").eq("org_id", project["org_id"]).execute()
            organization = org_response.data[0] if org_response.data else {}
        
        # Get creator details from summary_edit_requests
        creator = {}
        if notification.get("edit_request_id"):
            edit_request_response = supabase.table("summary_edit_requests").select("proposed_by").eq("edit_id", notification["edit_request_id"]).execute()
            if edit_request_response.data:
                proposed_by = edit_request_response.data[0]["proposed_by"]
                user_response = supabase.table("users").select("first_name, last_name").eq("user_id", proposed_by).execute()
                creator = user_response.data[0] if user_response.data else {}
        
        transformed_notification = {
            "notification_id": notification.get("notification_id"),
            "user_id": notification.get("user_id"),
            "meeting_id": notification.get("meeting_id"),
            "edit_request_id": notification.get("edit_request_id"),
            "type": notification.get("type"),
            "status": notification.get("status"),
            "created_at": notification.get("created_at"),
            "updated_at": notification.get("updated_at"),
            # Human-readable fields instead of UUIDs
            "meeting_title": meeting.get("title", ""),
            "project_name": project.get("project_name", ""),
            "organization_name": organization.get("org_name", ""),
            "creator_name": f"{creator.get('first_name', '')} {creator.get('last_name', '')}".strip(),
            "creator_first_name": creator.get("first_name", ""),
            "creator_last_name": creator.get("last_name", "")
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