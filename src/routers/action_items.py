# src/routers/action_items.py - Simplified version without regex patterns
from fastapi import APIRouter, Depends, HTTPException, Query
from supabase import Client
from database.base import get_supabase
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field, validator
import uuid

router = APIRouter()

class ActionItemCreate(BaseModel):
    meeting_id: str = Field(..., description="UUID of the meeting", example="550e8400-e29b-41d4-a716-446655440000")
    description: str = Field(..., description="Description of the action item", example="Review project timeline")
    owner: Optional[str] = Field(None, description="Email of the person responsible", example="john.doe@example.com")
    due_date: Optional[datetime] = Field(None, description="Due date for the action item")
    priority: str = Field("medium", description="Priority level (low, medium, high)", example="high")
    status: str = Field("pending", description="Current status (pending, completed, cancelled)", example="pending")
    
    @validator('meeting_id')
    def validate_meeting_id(cls, v):
        try:
            uuid.UUID(v)
            return v
        except ValueError:
            raise ValueError('meeting_id must be a valid UUID')
    
    @validator('priority')
    def validate_priority(cls, v):
        if v not in ['low', 'medium', 'high']:
            raise ValueError('priority must be low, medium, or high')
        return v
    
    @validator('status')
    def validate_status(cls, v):
        if v not in ['pending', 'completed', 'cancelled']:
            raise ValueError('status must be pending, completed, or cancelled')
        return v

class ActionItemUpdate(BaseModel):
    description: Optional[str] = Field(None, description="Updated description")
    owner: Optional[str] = Field(None, description="Updated owner email")
    due_date: Optional[datetime] = Field(None, description="Updated due date")
    priority: Optional[str] = Field(None, description="Updated priority (low, medium, high)")
    status: Optional[str] = Field(None, description="Updated status (pending, completed, cancelled)")
    
    @validator('priority')
    def validate_priority(cls, v):
        if v is not None and v not in ['low', 'medium', 'high']:
            raise ValueError('priority must be low, medium, or high')
        return v
    
    @validator('status')
    def validate_status(cls, v):
        if v is not None and v not in ['pending', 'completed', 'cancelled']:
            raise ValueError('status must be pending, completed, or cancelled')
        return v

class ActionItemResponse(BaseModel):
    action_id: str
    meeting_id: str
    description: str
    owner: Optional[str]
    due_date: Optional[datetime]
    priority: str
    status: str
    created_at: datetime
    completed_at: Optional[datetime]

@router.get("/test-data")
def get_test_data(
    user_id: str = Query(..., description="User ID to get test data for"),
    supabase: Client = Depends(get_supabase)
):
    """
    Get valid test data for creating action items.
    This endpoint helps you find valid meeting IDs for testing.
    """
    try:
        # Get user's accessible meetings
        meetings_response = supabase.table("meetings") \
            .select("meeting_id, title, scheduled_at, projects!inner(project_name, project_members!inner(*))") \
            .eq("projects.project_members.user_id", user_id) \
            .limit(5) \
            .execute()
        
        if not meetings_response.data:
            return {
                "message": "No accessible meetings found for this user",
                "user_id": user_id,
                "meetings": []
            }
        
        test_meetings = []
        for meeting in meetings_response.data:
            test_meetings.append({
                "meeting_id": meeting["meeting_id"],
                "title": meeting["title"],
                "project_name": meeting["projects"]["project_name"],
                "scheduled_at": meeting["scheduled_at"]
            })
        
        return {
            "message": "Found accessible meetings for testing",
            "user_id": user_id,
            "meetings": test_meetings,
            "example_request": {
                "url": f"/action-items/?user_id={user_id}",
                "method": "POST",
                "body": {
                    "meeting_id": test_meetings[0]["meeting_id"] if test_meetings else "no-meetings-found",
                    "description": "Test action item",
                    "owner": "test@example.com",
                    "priority": "medium",
                    "status": "pending"
                }
            }
        }
        
    except Exception as e:
        print(f"Error getting test data: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get test data: {str(e)}")

@router.post("/", response_model=ActionItemResponse)
def create_action_item(
    action_item: ActionItemCreate,
    user_id: str = Query(..., description="User ID creating the action item"),
    supabase: Client = Depends(get_supabase)
):
    """
    Create a new action item for a meeting.
    """
    try:
        print(f"Creating action item for user: {user_id}, meeting: {action_item.meeting_id}")
        
        # Verify meeting exists and user has access
        meeting_response = supabase.table("meetings") \
            .select("*, projects!inner(project_members!inner(*))") \
            .eq("meeting_id", str(action_item.meeting_id)) \
            .eq("projects.project_members.user_id", str(user_id)) \
            .execute()
        
        print(f"Meeting query result: {meeting_response.data}")
        
        if not meeting_response.data:
            raise HTTPException(status_code=404, detail="Meeting not found or access denied")
        
        # Create action item
        action_data = {
            "meeting_id": str(action_item.meeting_id),
            "description": action_item.description,
            "owner": action_item.owner,
            "due_date": action_item.due_date.isoformat() if action_item.due_date else None,
            "priority": action_item.priority,
            "status": action_item.status,
            "created_at": datetime.utcnow().isoformat()
        }
        
        print(f"Inserting action data: {action_data}")
        
        response = supabase.table("action_items").insert(action_data).execute()
        
        print(f"Insert response: {response}")
        
        if not response.data:
            raise HTTPException(status_code=500, detail="Failed to create action item")
        
        return response.data[0]
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error creating action item: {str(e)}")
        print(f"Error type: {type(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to create action item: {str(e)}")

@router.patch("/{action_id}", response_model=ActionItemResponse)
def update_action_item(
    action_id: str,
    action_update: ActionItemUpdate,
    user_id: str = Query(..., description="User ID updating the action item"),
    supabase: Client = Depends(get_supabase)
):
    """
    Update an action item's status or other properties.
    """
    try:
        # Get the action item and verify user has access
        action_item_response = supabase.table("action_items") \
            .select("*, meetings!inner(*, projects!inner(project_members!inner(*)))") \
            .eq("action_id", action_id) \
            .eq("meetings.projects.project_members.user_id", user_id) \
            .execute()
        
        if not action_item_response.data:
            raise HTTPException(status_code=404, detail="Action item not found or access denied")
        
        current_action_item = action_item_response.data[0]
        
        # Prepare update data
        update_data = {}
        
        if action_update.description is not None:
            update_data["description"] = action_update.description
        
        if action_update.owner is not None:
            update_data["owner"] = action_update.owner
        
        if action_update.due_date is not None:
            update_data["due_date"] = action_update.due_date.isoformat()
        
        if action_update.priority is not None:
            update_data["priority"] = action_update.priority
        
        if action_update.status is not None:
            update_data["status"] = action_update.status
            
            # If marking as completed, set completed_at timestamp
            if action_update.status == "completed":
                update_data["completed_at"] = datetime.utcnow().isoformat()
            # If marking as not completed, clear completed_at
            elif action_update.status != "completed" and current_action_item.get("completed_at"):
                update_data["completed_at"] = None
        
        if not update_data:
            raise HTTPException(status_code=400, detail="No fields to update")
        
        # Update the action item
        response = supabase.table("action_items") \
            .update(update_data) \
            .eq("action_id", action_id) \
            .execute()
        
        if not response.data:
            raise HTTPException(status_code=500, detail="Failed to update action item")
        
        return response.data[0]
        
    except Exception as e:
        print(f"Error updating action item: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to update action item: {str(e)}")

@router.get("/meeting/{meeting_id}", response_model=List[ActionItemResponse])
def get_meeting_action_items(
    meeting_id: str,
    user_id: str = Query(..., description="User ID requesting action items"),
    supabase: Client = Depends(get_supabase)
):
    """
    Get all action items for a specific meeting.
    """
    try:
        # Verify meeting exists and user has access
        meeting_response = supabase.table("meetings") \
            .select("*, projects!inner(project_members!inner(*))") \
            .eq("meeting_id", meeting_id) \
            .eq("projects.project_members.user_id", user_id) \
            .execute()
        
        if not meeting_response.data:
            raise HTTPException(status_code=404, detail="Meeting not found or access denied")
        
        # Get action items for the meeting
        action_items_response = supabase.table("action_items") \
            .select("*") \
            .eq("meeting_id", meeting_id) \
            .order("created_at", desc=False) \
            .execute()
        
        return action_items_response.data or []
        
    except Exception as e:
        print(f"Error retrieving action items: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve action items: {str(e)}")

@router.delete("/{action_id}")
def delete_action_item(
    action_id: str,
    user_id: str = Query(..., description="User ID deleting the action item"),
    supabase: Client = Depends(get_supabase)
):
    """
    Delete an action item.
    """
    try:
        # Verify the action item exists and user has access
        action_item_response = supabase.table("action_items") \
            .select("*, meetings!inner(*, projects!inner(project_members!inner(*)))") \
            .eq("action_id", action_id) \
            .eq("meetings.projects.project_members.user_id", user_id) \
            .execute()
        
        if not action_item_response.data:
            raise HTTPException(status_code=404, detail="Action item not found or access denied")
        
        # Delete the action item
        response = supabase.table("action_items") \
            .delete() \
            .eq("action_id", action_id) \
            .execute()
        
        return {"status": "success", "message": "Action item deleted successfully"}
        
    except Exception as e:
        print(f"Error deleting action item: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to delete action item: {str(e)}")

@router.get("/", response_model=List[ActionItemResponse])
def list_action_items(
    user_id: str = Query(..., description="User ID requesting action items"),
    meeting_id: Optional[str] = Query(None, description="Filter by meeting ID"),
    status: Optional[str] = Query(None, description="Filter by status"),
    owner: Optional[str] = Query(None, description="Filter by owner"),
    project_id: Optional[str] = Query(None, description="Filter by project ID"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of records to return"),
    supabase: Client = Depends(get_supabase)
):
    """
    List action items with optional filtering.
    """
    try:
        # Build base query ensuring user has access
        query = supabase.table("action_items") \
            .select("*, meetings!inner(*, projects!inner(project_members!inner(*)))") \
            .eq("meetings.projects.project_members.user_id", user_id)
        
        # Apply filters
        if meeting_id:
            query = query.eq("meeting_id", meeting_id)
        
        if status:
            query = query.eq("status", status)
        
        if owner:
            query = query.eq("owner", owner)
        
        if project_id:
            query = query.eq("meetings.project_id", project_id)
        
        # Execute query with pagination
        response = query.order("created_at", desc=True) \
            .range(skip, skip + limit - 1) \
            .execute()
        
        return response.data or []
        
    except Exception as e:
        print(f"Error listing action items: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to list action items: {str(e)}")