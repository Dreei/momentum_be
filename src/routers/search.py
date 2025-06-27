# src/routers/search.py
from fastapi import APIRouter, Depends, HTTPException, Query
from supabase import Client
from database.base import get_supabase
from typing import List, Optional, Dict, Any
from datetime import datetime, date
from pydantic import BaseModel
import json

router = APIRouter()

class MeetingSearchResult(BaseModel):
    meeting_id: str
    title: str
    description: Optional[str]
    scheduled_at: datetime
    meeting_status: str
    created_at: datetime
    project_name: str
    organization_name: str
    creator_name: str
    participants: List[Dict[str, Any]]
    summaries: List[Dict[str, Any]]
    action_items_count: int
    decisions_count: int
    discussions_count: int

class SearchFilters(BaseModel):
    query: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    participants: Optional[List[str]] = None
    meeting_status: Optional[str] = None
    has_summaries: Optional[bool] = None
    has_action_items: Optional[bool] = None

@router.get("/meetings", response_model=List[MeetingSearchResult])
def search_meetings(
    project_id: str = Query(..., description="Project ID to search within"),
    user_id: str = Query(..., description="User ID performing the search"),
    query: Optional[str] = Query(None, description="Search query for title, description, or participants"),
    start_date: Optional[date] = Query(None, description="Start date filter (YYYY-MM-DD)"),
    end_date: Optional[date] = Query(None, description="End date filter (YYYY-MM-DD)"),
    participants: Optional[str] = Query(None, description="Comma-separated list of participant emails"),
    meeting_status: Optional[str] = Query(None, description="Meeting status filter"),
    has_summaries: Optional[bool] = Query(None, description="Filter meetings with summaries"),
    has_action_items: Optional[bool] = Query(None, description="Filter meetings with action items"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of records to return"),
    supabase: Client = Depends(get_supabase)
):
    """
    Search meetings within a project using various filters.
    
    Args:
        project_id: ID of the project to search within
        user_id: ID of the user performing the search
        query: Search query for title, description, or participants
        start_date: Start date filter
        end_date: End date filter
        participants: Comma-separated participant emails
        meeting_status: Meeting status filter
        has_summaries: Filter meetings with summaries
        has_action_items: Filter meetings with action items
        skip: Number of records to skip
        limit: Maximum number of records to return
        supabase: Supabase client
        
    Returns:
        List of meetings matching the search criteria
    """
    try:
        # Verify user has access to the project
        project_member_response = supabase.table("project_members") \
            .select("*") \
            .eq("project_id", project_id) \
            .eq("user_id", user_id) \
            .execute()
        
        if not project_member_response.data:
            raise HTTPException(status_code=403, detail="Access denied to project")
        
        # Build base query for meetings in the project
        base_query = supabase.table("meetings") \
            .select("""
                *,
                projects!inner(*, organizations!inner(*)),
                users!inner(*),
                meeting_participants(*),
                meeting_summaries(*),
                action_items(*),
                meeting_decisions(*),
                meeting_discussions(*)
            """) \
            .eq("project_id", project_id)
        
        # Apply date filters
        if start_date:
            base_query = base_query.gte("scheduled_at", start_date.isoformat())
        
        if end_date:
            # Add one day to include the entire end date
            end_datetime = datetime.combine(end_date, datetime.max.time())
            base_query = base_query.lte("scheduled_at", end_datetime.isoformat())
        
        # Apply status filter
        if meeting_status:
            base_query = base_query.eq("meeting_status", meeting_status)
        
        # Execute base query
        meetings_response = base_query.order("scheduled_at", desc=True).execute()
        
        if not meetings_response.data:
            return []
        
        meetings = meetings_response.data
        
        # Apply text search filter
        if query:
            filtered_meetings = []
            query_lower = query.lower()
            
            for meeting in meetings:
                # Search in title and description
                title_match = query_lower in meeting.get("title", "").lower()
                description_match = query_lower in meeting.get("description", "").lower()
                
                # Search in participant names and emails
                participant_match = False
                if meeting.get("meeting_participants"):
                    for participant in meeting["meeting_participants"]:
                        participant_email = participant.get("email", "").lower()
                        if query_lower in participant_email:
                            participant_match = True
                            break
                
                # Search in creator name
                creator_match = False
                if meeting.get("users"):
                    creator_name = f"{meeting['users'].get('first_name', '')} {meeting['users'].get('last_name', '')}".lower()
                    creator_email = meeting['users'].get('email', '').lower()
                    creator_match = query_lower in creator_name or query_lower in creator_email
                
                # Search in summaries content
                summary_match = False
                if meeting.get("meeting_summaries"):
                    for summary in meeting["meeting_summaries"]:
                        content = summary.get("content", "")
                        # Handle JSON content
                        if content.startswith("{"):
                            try:
                                content_json = json.loads(content)
                                content = json.dumps(content_json).lower()
                            except:
                                content = content.lower()
                        else:
                            content = content.lower()
                        
                        if query_lower in content:
                            summary_match = True
                            break
                
                if title_match or description_match or participant_match or creator_match or summary_match:
                    filtered_meetings.append(meeting)
            
            meetings = filtered_meetings
        
        # Apply participant filter
        if participants:
            participant_emails = [email.strip().lower() for email in participants.split(",")]
            filtered_meetings = []
            
            for meeting in meetings:
                meeting_participants = meeting.get("meeting_participants", [])
                meeting_participant_emails = [p.get("email", "").lower() for p in meeting_participants]
                
                # Check if any of the specified participants are in this meeting
                if any(email in meeting_participant_emails for email in participant_emails):
                    filtered_meetings.append(meeting)
            
            meetings = filtered_meetings
        
        # Apply summary filter
        if has_summaries is not None:
            if has_summaries:
                meetings = [m for m in meetings if m.get("meeting_summaries")]
            else:
                meetings = [m for m in meetings if not m.get("meeting_summaries")]
        
        # Apply action items filter
        if has_action_items is not None:
            if has_action_items:
                meetings = [m for m in meetings if m.get("action_items")]
            else:
                meetings = [m for m in meetings if not m.get("action_items")]
        
        # Apply pagination
        paginated_meetings = meetings[skip:skip + limit]
        
        # Format response
        search_results = []
        for meeting in paginated_meetings:
            # Format participants
            participants_formatted = []
            for participant in meeting.get("meeting_participants", []):
                participants_formatted.append({
                    "email": participant.get("email"),
                    "role": participant.get("role"),
                    "status": participant.get("status")
                })
            
            # Format summaries
            summaries_formatted = []
            for summary in meeting.get("meeting_summaries", []):
                content = summary.get("content", "")
                # Try to parse JSON content for better display
                try:
                    if content.startswith("{"):
                        content_json = json.loads(content)
                        if isinstance(content_json, dict) and "overview" in content_json:
                            content = content_json.get("overview", content)
                except:
                    pass
                
                summaries_formatted.append({
                    "summary_id": summary.get("summary_id"),
                    "summary_type": summary.get("summary_type"),
                    "content": content[:200] + "..." if len(content) > 200 else content,
                    "created_at": summary.get("created_at")
                })
            
            # Creator name
            creator = meeting.get("users", {})
            creator_name = f"{creator.get('first_name', '')} {creator.get('last_name', '')}".strip()
            if not creator_name:
                creator_name = creator.get("email", "Unknown")
            
            # Project and organization info
            project = meeting.get("projects", {})
            organization = project.get("organizations", {})
            
            search_result = MeetingSearchResult(
                meeting_id=meeting["meeting_id"],
                title=meeting["title"],
                description=meeting.get("description"),
                scheduled_at=datetime.fromisoformat(meeting["scheduled_at"]),
                meeting_status=meeting["meeting_status"],
                created_at=datetime.fromisoformat(meeting["created_at"]),
                project_name=project.get("project_name", "Unknown Project"),
                organization_name=organization.get("org_name", "Unknown Organization"),
                creator_name=creator_name,
                participants=participants_formatted,
                summaries=summaries_formatted,
                action_items_count=len(meeting.get("action_items", [])),
                decisions_count=len(meeting.get("meeting_decisions", [])),
                discussions_count=len(meeting.get("meeting_discussions", []))
            )
            
            search_results.append(search_result)
        
        return search_results
        
    except Exception as e:
        print(f"Error searching meetings: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to search meetings: {str(e)}")

@router.get("/summaries")
def search_summaries(
    project_id: str = Query(..., description="Project ID to search within"),
    user_id: str = Query(..., description="User ID performing the search"),
    query: Optional[str] = Query(None, description="Search query for summary content"),
    summary_type: Optional[str] = Query(None, description="Filter by summary type"),
    start_date: Optional[date] = Query(None, description="Start date filter"),
    end_date: Optional[date] = Query(None, description="End date filter"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of records to return"),
    supabase: Client = Depends(get_supabase)
):
    """
    Search meeting summaries within a project.
    
    Args:
        project_id: ID of the project to search within
        user_id: ID of the user performing the search
        query: Search query for summary content
        summary_type: Filter by summary type
        start_date: Start date filter
        end_date: End date filter
        skip: Number of records to skip
        limit: Maximum number of records to return
        supabase: Supabase client
        
    Returns:
        List of summaries matching the search criteria
    """
    try:
        # Verify user has access to the project
        project_member_response = supabase.table("project_members") \
            .select("*") \
            .eq("project_id", project_id) \
            .eq("user_id", user_id) \
            .execute()
        
        if not project_member_response.data:
            raise HTTPException(status_code=403, detail="Access denied to project")
        
        # Build query for summaries
        base_query = supabase.table("meeting_summaries") \
            .select("*, meetings!inner(*, projects!inner(*))") \
            .eq("meetings.project_id", project_id)
        
        # Apply filters
        if summary_type:
            base_query = base_query.eq("summary_type", summary_type)
        
        if start_date:
            base_query = base_query.gte("created_at", start_date.isoformat())
        
        if end_date:
            end_datetime = datetime.combine(end_date, datetime.max.time())
            base_query = base_query.lte("created_at", end_datetime.isoformat())
        
        # Execute query
        summaries_response = base_query.order("created_at", desc=True).execute()
        
        if not summaries_response.data:
            return []
        
        summaries = summaries_response.data
        
        # Apply text search filter
        if query:
            filtered_summaries = []
            query_lower = query.lower()
            
            for summary in summaries:
                content = summary.get("content", "")
                
                # Handle JSON content
                if content.startswith("{"):
                    try:
                        content_json = json.loads(content)
                        content_text = json.dumps(content_json).lower()
                    except:
                        content_text = content.lower()
                else:
                    content_text = content.lower()
                
                # Search in content and meeting title
                content_match = query_lower in content_text
                title_match = query_lower in summary.get("meetings", {}).get("title", "").lower()
                
                if content_match or title_match:
                    filtered_summaries.append(summary)
            
            summaries = filtered_summaries
        
        # Apply pagination
        paginated_summaries = summaries[skip:skip + limit]
        
        # Format response
        formatted_summaries = []
        for summary in paginated_summaries:
            content = summary.get("content", "")
            
            # Try to extract overview from structured summary
            display_content = content
            try:
                if content.startswith("{"):
                    content_json = json.loads(content)
                    if isinstance(content_json, dict):
                        display_content = content_json.get("overview", content)
            except:
                pass
            
            meeting = summary.get("meetings", {})
            
            formatted_summary = {
                "summary_id": summary["summary_id"],
                "meeting_id": summary["meeting_id"],
                "summary_type": summary["summary_type"],
                "content": display_content[:300] + "..." if len(display_content) > 300 else display_content,
                "full_content": content,
                "context_group": summary.get("context_group"),
                "created_at": summary["created_at"],
                "meeting_title": meeting.get("title"),
                "meeting_date": meeting.get("scheduled_at"),
                "meeting_status": meeting.get("meeting_status")
            }
            
            formatted_summaries.append(formatted_summary)
        
        return formatted_summaries
        
    except Exception as e:
        print(f"Error searching summaries: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to search summaries: {str(e)}")

@router.get("/action-items")
def search_action_items(
    project_id: str = Query(..., description="Project ID to search within"),
    user_id: str = Query(..., description="User ID performing the search"),
    query: Optional[str] = Query(None, description="Search query for action item description"),
    status: Optional[str] = Query(None, description="Filter by status"),
    owner: Optional[str] = Query(None, description="Filter by owner"),
    priority: Optional[str] = Query(None, description="Filter by priority"),
    due_date_start: Optional[date] = Query(None, description="Due date start filter"),
    due_date_end: Optional[date] = Query(None, description="Due date end filter"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of records to return"),
    supabase: Client = Depends(get_supabase)
):
    """
    Search action items within a project.
    
    Args:
        project_id: ID of the project to search within
        user_id: ID of the user performing the search
        query: Search query for action item description
        status: Filter by status
        owner: Filter by owner
        priority: Filter by priority
        due_date_start: Due date start filter
        due_date_end: Due date end filter
        skip: Number of records to skip
        limit: Maximum number of records to return
        supabase: Supabase client
        
    Returns:
        List of action items matching the search criteria
    """
    try:
        # Verify user has access to the project
        project_member_response = supabase.table("project_members") \
            .select("*") \
            .eq("project_id", project_id) \
            .eq("user_id", user_id) \
            .execute()
        
        if not project_member_response.data:
            raise HTTPException(status_code=403, detail="Access denied to project")
        
        # Build query for action items
        base_query = supabase.table("action_items") \
            .select("*, meetings!inner(*, projects!inner(*))") \
            .eq("meetings.project_id", project_id)
        
        # Apply filters
        if status:
            base_query = base_query.eq("status", status)
        
        if owner:
            base_query = base_query.eq("owner", owner)
        
        if priority:
            base_query = base_query.eq("priority", priority)
        
        if due_date_start:
            base_query = base_query.gte("due_date", due_date_start.isoformat())
        
        if due_date_end:
            end_datetime = datetime.combine(due_date_end, datetime.max.time())
            base_query = base_query.lte("due_date", end_datetime.isoformat())
        
        # Execute query
        action_items_response = base_query.order("created_at", desc=True).execute()
        
        if not action_items_response.data:
            return []
        
        action_items = action_items_response.data
        
        # Apply text search filter
        if query:
            filtered_items = []
            query_lower = query.lower()
            
            for item in action_items:
                # Search in description and owner
                description_match = query_lower in item.get("description", "").lower()
                owner_match = query_lower in item.get("owner", "").lower()
                meeting_title_match = query_lower in item.get("meetings", {}).get("title", "").lower()
                
                if description_match or owner_match or meeting_title_match:
                    filtered_items.append(item)
            
            action_items = filtered_items
        
        # Apply pagination
        paginated_items = action_items[skip:skip + limit]
        
        # Format response
        formatted_items = []
        for item in paginated_items:
            meeting = item.get("meetings", {})
            
            formatted_item = {
                "action_id": item["action_id"],
                "meeting_id": item["meeting_id"],
                "description": item["description"],
                "owner": item.get("owner"),
                "due_date": item.get("due_date"),
                "priority": item["priority"],
                "status": item["status"],
                "created_at": item["created_at"],
                "completed_at": item.get("completed_at"),
                "meeting_title": meeting.get("title"),
                "meeting_date": meeting.get("scheduled_at")
            }
            
            formatted_items.append(formatted_item)
        
        return formatted_items
        
    except Exception as e:
        print(f"Error searching action items: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to search action items: {str(e)}")

@router.get("/global")
def global_search(
    user_id: str = Query(..., description="User ID performing the search"),
    query: str = Query(..., description="Search query"),
    project_ids: Optional[str] = Query(None, description="Comma-separated project IDs to search within"),
    content_types: Optional[str] = Query("meetings,summaries,action_items", description="Comma-separated content types to search"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of records to return"),
    supabase: Client = Depends(get_supabase)
):
    """
    Perform a global search across meetings, summaries, and action items.
    
    Args:
        user_id: ID of the user performing the search
        query: Search query
        project_ids: Optional comma-separated project IDs to limit search
        content_types: Content types to search (meetings, summaries, action_items)
        skip: Number of records to skip
        limit: Maximum number of records to return
        supabase: Supabase client
        
    Returns:
        Aggregated search results from all content types
    """
    try:
        # Get user's accessible projects
        user_projects_response = supabase.table("project_members") \
            .select("project_id, projects(*)") \
            .eq("user_id", user_id) \
            .execute()
        
        if not user_projects_response.data:
            return {"results": [], "total_count": 0}
        
        accessible_project_ids = [p["project_id"] for p in user_projects_response.data]
        
        # Filter by specified project IDs if provided
        if project_ids:
            specified_project_ids = [pid.strip() for pid in project_ids.split(",")]
            accessible_project_ids = [pid for pid in accessible_project_ids if pid in specified_project_ids]
        
        if not accessible_project_ids:
            return {"results": [], "total_count": 0}
        
        # Parse content types
        search_types = [ct.strip() for ct in content_types.split(",")]
        
        all_results = []
        
        # Search meetings
        if "meetings" in search_types:
            try:
                meetings_query = supabase.table("meetings") \
                    .select("""
                        *,
                        projects!inner(*),
                        users!inner(*),
                        meeting_participants(*)
                    """) \
                    .in_("project_id", accessible_project_ids)
                
                meetings_response = meetings_query.execute()
                
                if meetings_response.data:
                    query_lower = query.lower()
                    for meeting in meetings_response.data:
                        # Check if query matches title, description, or participants
                        title_match = query_lower in meeting.get("title", "").lower()
                        description_match = query_lower in meeting.get("description", "").lower()
                        
                        participant_match = False
                        if meeting.get("meeting_participants"):
                            for participant in meeting["meeting_participants"]:
                                if query_lower in participant.get("email", "").lower():
                                    participant_match = True
                                    break
                        
                        if title_match or description_match or participant_match:
                            all_results.append({
                                "type": "meeting",
                                "id": meeting["meeting_id"],
                                "title": meeting["title"],
                                "content": meeting.get("description", ""),
                                "project_name": meeting.get("projects", {}).get("project_name", ""),
                                "created_at": meeting["created_at"],
                                "scheduled_at": meeting.get("scheduled_at"),
                                "relevance_score": 1.0  # Simple scoring, can be enhanced
                            })
            except Exception as e:
                print(f"Error searching meetings: {str(e)}")
        
        # Search summaries
        if "summaries" in search_types:
            try:
                summaries_query = supabase.table("meeting_summaries") \
                    .select("*, meetings!inner(*, projects!inner(*))") \
                    .in_("meetings.project_id", accessible_project_ids)
                
                summaries_response = summaries_query.execute()
                
                if summaries_response.data:
                    query_lower = query.lower()
                    for summary in summaries_response.data:
                        content = summary.get("content", "")
                        
                        # Handle JSON content
                        content_text = content
                        try:
                            if content.startswith("{"):
                                content_json = json.loads(content)
                                content_text = json.dumps(content_json)
                        except:
                            pass
                        
                        if query_lower in content_text.lower():
                            # Extract display content
                            display_content = content
                            try:
                                if content.startswith("{"):
                                    content_json = json.loads(content)
                                    if isinstance(content_json, dict):
                                        display_content = content_json.get("overview", content)
                            except:
                                pass
                            
                            meeting = summary.get("meetings", {})
                            all_results.append({
                                "type": "summary",
                                "id": summary["summary_id"],
                                "title": f"Summary: {meeting.get('title', 'Unknown Meeting')}",
                                "content": display_content[:200] + "..." if len(display_content) > 200 else display_content,
                                "project_name": meeting.get("projects", {}).get("project_name", ""),
                                "created_at": summary["created_at"],
                                "meeting_id": summary["meeting_id"],
                                "summary_type": summary.get("summary_type"),
                                "relevance_score": 0.8
                            })
            except Exception as e:
                print(f"Error searching summaries: {str(e)}")
        
        # Search action items
        if "action_items" in search_types:
            try:
                action_items_query = supabase.table("action_items") \
                    .select("*, meetings!inner(*, projects!inner(*))") \
                    .in_("meetings.project_id", accessible_project_ids)
                
                action_items_response = action_items_query.execute()
                
                if action_items_response.data:
                    query_lower = query.lower()
                    for item in action_items_response.data:
                        description_match = query_lower in item.get("description", "").lower()
                        owner_match = query_lower in item.get("owner", "").lower()
                        
                        if description_match or owner_match:
                            meeting = item.get("meetings", {})
                            all_results.append({
                                "type": "action_item",
                                "id": item["action_id"],
                                "title": f"Action: {item['description'][:50]}...",
                                "content": item["description"],
                                "project_name": meeting.get("projects", {}).get("project_name", ""),
                                "created_at": item["created_at"],
                                "meeting_id": item["meeting_id"],
                                "status": item["status"],
                                "owner": item.get("owner"),
                                "due_date": item.get("due_date"),
                                "relevance_score": 0.6
                            })
            except Exception as e:
                print(f"Error searching action items: {str(e)}")
        
        # Sort by relevance and creation date
        all_results.sort(key=lambda x: (x["relevance_score"], x["created_at"]), reverse=True)
        
        # Apply pagination
        total_count = len(all_results)
        paginated_results = all_results[skip:skip + limit]
        
        return {
            "results": paginated_results,
            "total_count": total_count,
            "search_query": query,
            "accessible_projects": len(accessible_project_ids),
            "content_types_searched": search_types
        }
        
    except Exception as e:
        print(f"Error in global search: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to perform global search: {str(e)}")

@router.get("/stats")
def get_search_stats(
    user_id: str = Query(..., description="User ID to get stats for"),
    project_id: Optional[str] = Query(None, description="Optional project ID filter"),
    supabase: Client = Depends(get_supabase)
):
    """
    Get search statistics for the user.
    
    Args:
        user_id: ID of the user
        project_id: Optional project ID filter
        supabase: Supabase client
        
    Returns:
        Statistics about searchable content
    """
    try:
        # Get user's accessible projects
        user_projects_response = supabase.table("project_members") \
            .select("project_id") \
            .eq("user_id", user_id) \
            .execute()
        
        if not user_projects_response.data:
            return {
                "total_meetings": 0,
                "total_summaries": 0,
                "total_action_items": 0,
                "projects_accessible": 0
            }
        
        accessible_project_ids = [p["project_id"] for p in user_projects_response.data]
        
        # Filter by project if specified
        if project_id:
            if project_id not in accessible_project_ids:
                raise HTTPException(status_code=403, detail="Access denied to project")
            accessible_project_ids = [project_id]
        
        # Count meetings
        meetings_count = 0
        try:
            meetings_response = supabase.table("meetings") \
                .select("meeting_id", count="exact") \
                .in_("project_id", accessible_project_ids) \
                .execute()
            meetings_count = meetings_response.count or 0
        except:
            pass
        
        # Count summaries
        summaries_count = 0
        try:
            summaries_response = supabase.table("meeting_summaries") \
                .select("summary_id", count="exact") \
                .in_("meetings.project_id", accessible_project_ids) \
                .execute()
            summaries_count = summaries_response.count or 0
        except:
            pass
        
        # Count action items
        action_items_count = 0
        try:
            action_items_response = supabase.table("action_items") \
                .select("action_id", count="exact") \
                .in_("meetings.project_id", accessible_project_ids) \
                .execute()
            action_items_count = action_items_response.count or 0
        except:
            pass
        
        return {
            "total_meetings": meetings_count,
            "total_summaries": summaries_count,
            "total_action_items": action_items_count,
            "projects_accessible": len(accessible_project_ids)
        }
        
    except Exception as e:
        print(f"Error getting search stats: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get search stats: {str(e)}")