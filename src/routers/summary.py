from fastapi import APIRouter, Depends, HTTPException, Query, Body
from database.base import get_supabase
from supabase import Client
from typing import Dict, Any, Optional
from datetime import datetime
import uuid
from .notification import create_edit_pending_notifications

router = APIRouter()

# --- Role Validation Helpers ---
def is_participant(user_id, meeting_id, supabase):
    resp = supabase.table("meeting_participants").select("*").eq("meeting_id", meeting_id).eq("user_id", user_id).execute()
    return bool(resp.data)

def is_host_or_admin(user_id, meeting_id, supabase):
    meeting = supabase.table("meetings").select("*").eq("meeting_id", meeting_id).execute().data
    if meeting and meeting[0]["created_by"] == user_id:
        return True
    project_id = meeting[0]["project_id"]
    admin = supabase.table("project_members").select("*").eq("project_id", project_id).eq("user_id", user_id).eq("role", "project_admin").execute().data
    return bool(admin)

# --- Submit Edit Request ---
@router.post("/edit-request")
async def submit_edit_request(
    meeting_id: str = Query(...),
    proposed_by: str = Query(...),
    proposed_changes: Dict[str, Any] = Body(...),
    supabase: Client = Depends(get_supabase)
):
    # if not is_participant(proposed_by, meeting_id, supabase):
    #     raise HTTPException(status_code=403, detail="Only participants can propose edits.")
    edit_id = str(uuid.uuid4())
    print("edit request submittted")
    supabase.table("summary_edit_requests").insert({
        "edit_id": edit_id,
        "meeting_id": meeting_id,
        "proposed_by": proposed_by,
        "proposed_changes": proposed_changes,
        "status": "pending_approval",
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat()
    }).execute()
    # Notify host/admins
    await create_edit_pending_notifications(meeting_id, edit_id, supabase)
    return {"edit_id": edit_id, "status": "pending_approval"}

# --- Approve/Reject Edit Request ---
@router.patch("/edit-request/{edit_id}")
async def review_edit_request(
    edit_id: str,
    reviewer_id: str = Query(...),
    approve: bool = Query(...),
    supabase: Client = Depends(get_supabase)
):
    edit = supabase.table("summary_edit_requests").select("*").eq("edit_id", edit_id).execute().data
    if not edit:
        raise HTTPException(status_code=404, detail="Edit request not found.")
    meeting_id = edit[0]["meeting_id"]
    if not is_host_or_admin(reviewer_id, meeting_id, supabase):
        raise HTTPException(status_code=403, detail="Only host or project admin can approve/reject.")
    status = "approved" if approve else "rejected"
    supabase.table("summary_edit_requests").update({
        "status": status,
        "reviewed_by": reviewer_id,
        "reviewed_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat()
    }).eq("edit_id", edit_id).execute()
    # If approved, update summary and log revision
    if approve:
        changes = edit[0]["proposed_changes"]
        summary = supabase.table("meeting_summaries").select("*").eq("meeting_id", meeting_id).order("created_at", desc=True).limit(1).execute().data
        if summary:
            summary_id = summary[0]["summary_id"]
            supabase.table("meeting_summaries").update({
                "content": changes.get("content", summary[0]["content"]),
                "updated_at": datetime.utcnow().isoformat()
            }).eq("summary_id", summary_id).execute()
        supabase.table("summary_revision_history").insert({
            "revision_id": str(uuid.uuid4()),
            "edit_id": edit_id,
            "editor_id": edit[0]["proposed_by"],
            "reviewer_id": reviewer_id,
            "content": changes,
            "status": status,
            "timestamp": datetime.utcnow().isoformat()
        }).execute()
    return {"edit_id": edit_id, "status": status}

# --- Get Revision History ---
@router.get("/revision-history/{meeting_id}")
async def get_revision_history(
    meeting_id: str,
    supabase: Client = Depends(get_supabase)
):
    # Get all edit requests for the meeting
    edits = supabase.table("summary_edit_requests").select("*").eq("meeting_id", meeting_id).order("created_at", desc=False).execute().data
    # For each edit, get revision history
    history = []
    for edit in edits:
        revisions = supabase.table("summary_revision_history").select("*").eq("edit_id", edit["edit_id"]).order("timestamp", desc=False).execute().data
        history.append({
            "edit": edit,
            "revisions": revisions
        })
    return {"history": history}

# --- Get Edit Requests (for UI listing) ---
@router.get("/edit-requests/{meeting_id}")
async def get_edit_requests(
    meeting_id: str,
    supabase: Client = Depends(get_supabase)
):
    edits = supabase.table("summary_edit_requests").select("*").eq("meeting_id", meeting_id).order("created_at", desc=False).execute().data
    return {"edit_requests": edits}

# --- Get Edit Request by Edit ID with Original Summary ---
@router.get("/edit-requests/")
async def get_edit_request_by_id(
    edit_id: str = Query(..., description="Edit request ID"),
    supabase: Client = Depends(get_supabase)
):
    """
    Get edit request by edit_id and return the edited data along with original summary.
    
    Args:
        edit_id (str): The edit request ID
        supabase (Client): Supabase client
        
    Returns:
        dict: Edit request data with original summary
            {
                "edit_request": dict,
                "original_summary": dict,
                "status": str
            }
    """
    try:
        # Get the edit request by edit_id
        edit_response = supabase.table("summary_edit_requests") \
            .select("*") \
            .eq("edit_id", edit_id) \
            .execute()
        
        if not edit_response.data:
            raise HTTPException(status_code=404, detail="Edit request not found")
        
        edit_request = edit_response.data[0]
        meeting_id = edit_request["meeting_id"]
        
        # Get the original summary from meeting_summaries table
        summary_response = supabase.table("meeting_summaries") \
            .select("*") \
            .eq("meeting_id", meeting_id) \
            .order("created_at", desc=True) \
            .limit(1) \
            .execute()
        
        original_summary = None
        if summary_response.data:
            original_summary = summary_response.data[0]
        
        return {
            "status": "success",
            "edit_request": edit_request,
            "original_summary": original_summary
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error getting edit request by ID: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get edit request: {str(e)}")

@router.patch("/direct-update")
async def direct_update_summary(
    meeting_id: str = Query(...),
    user_id: str = Query(...),
    data: Dict[str, Any] = Body(...),
    supabase: Client = Depends(get_supabase)
):
    # Only host or admin can update directly
    # if not is_host_or_admin(user_id, meeting_id, supabase):
    #     raise HTTPException(status_code=403, detail="Only host or project admin can update summary directly.")
    # Get latest summary for meeting
    summary = supabase.table("meeting_summaries").select("*").eq("meeting_id", meeting_id).order("created_at", desc=True).limit(1).execute().data
    if not summary:
        raise HTTPException(status_code=404, detail="Summary not found for meeting.")
    summary_id = summary[0]["summary_id"]
    old_content = summary[0]["content"]
    # Extract new content from the provided data
    try:
        new_content = data["summary"]["content"]
    except Exception:
        raise HTTPException(status_code=422, detail="Invalid format: expected 'summary.content' in request body.")
    # Update summary (filter by meeting_id, update content and created_at)
    supabase.table("meeting_summaries").update({
        "content": new_content,
        "created_at": datetime.utcnow().isoformat()
    }).eq("meeting_id", meeting_id).execute()
    # No revision history logging
    return {"summary_id": summary_id, "meeting_id": meeting_id, "content": new_content, "status": "updated"} 