from fastapi import APIRouter, Depends, HTTPException, Request, Query, Response
from database.base import get_supabase
from supabase import Client
from typing import Optional
import requests
from datetime import datetime, timedelta, timezone
import uuid
from urllib.parse import urlencode
from core.config import ZOOM_CLIENT_ID, ZOOM_CLIENT_SECRET, ZOOM_REDIRECT_URI, RECALL_WEBHOOK_URL
from services.email_service import EmailService, MeetingInviteData
from services.recallai_services import recall_service
from services.ai_summary_pipeline import ai_summary_pipeline

router = APIRouter()
email_service = EmailService()

def get_valid_zoom_token(supabase: Client, user_id: uuid.UUID) -> str:
    """
    Get a valid Zoom access token for a user, refreshing it if necessary.
    
    Args:
        supabase (Client): Supabase client
        user_id (uuid.UUID): ID of the user requesting the token
        
    Returns:
        str: Valid Zoom access token
        
    Raises:
        HTTPException: If user has no Zoom connection or token refresh fails
    """
    token_response = supabase.table("oauth_tokens") \
        .select("*") \
        .eq("user_id", str(user_id)) \
        .eq("platform", "zoom") \
        .execute()
    
    if not token_response.data:
        raise HTTPException(status_code=401, detail="Zoom account not connected")
    
    token = token_response.data[0]
    # Check if token needs refresh
    if datetime.utcnow() >= datetime.fromisoformat(token["expires_at"]):
        # Refresh token
        refresh_url = "https://zoom.us/oauth/token"
        data = {
            "grant_type": "refresh_token",
            "refresh_token": token["refresh_token"],
            "client_id": ZOOM_CLIENT_ID,
            "client_secret": ZOOM_CLIENT_SECRET
        }
        response = requests.post(refresh_url, data=data)
        if response.status_code != 200:
            raise HTTPException(status_code=401, detail="Failed to refresh Zoom token")
        
        token_data = response.json()
        
        # Update token in database
        supabase.table("oauth_tokens") \
            .update({
                "access_token": token_data["access_token"],
                "refresh_token": token_data["refresh_token"],
                "expires_at": (datetime.utcnow() + timedelta(seconds=token_data["expires_in"])).isoformat()
            }) \
            .eq("user_id", str(user_id)) \
            .eq("platform", "zoom") \
            .execute()
        
        return token_data["access_token"]
    
    return token["access_token"]



"""

/meeting-platform/zoom/authorize/{user_id}
Initiate the Zoom OAuth flow and return the authorization URL.

This endpoint starts the OAuth process by generating a state parameter and
constructing the Zoom authorization URL. The state parameter includes the
user_id for security and verification during the callback.

Args:
    user_id (uuid.UUID): ID of the user requesting Zoom authorization
    
Returns:
    dict: Contains authorization URL, state, user_id, and instructions
        {
            "authorization_url": str,
            "state": str,
            "user_id": str,
            "instructions": str
        }
"""

@router.get("/authorize/{user_id}")
async def zoom_authorize(user_id: uuid.UUID):
    # Generate a state parameter for security
    state = str(uuid.uuid4())
    print("Authorize")
    # Build the authorization URL with user_id in state
    params = {
        "response_type": "code",
        "client_id": ZOOM_CLIENT_ID,
        "redirect_uri": ZOOM_REDIRECT_URI,
        "state": f"{state}_{user_id}"  # Include user_id in state
    }
    print(f"Zoom authorization URL params: {params}")
    auth_url = f"https://zoom.us/oauth/authorize?{urlencode(params)}"
    
    return {
        "authorization_url": auth_url,
        "state": state,
        "user_id": str(user_id),
        "instructions": "1. Open the authorization_url in your browser\n2. Authorize the application\n3. Copy the entire redirect URL\n4. Use the /callback endpoint with the code and state from the URL"
    }

"""
    /meeting-platform/zoom/callback
    Handle the Zoom OAuth callback and store the access tokens.
    
    This endpoint processes the OAuth callback from Zoom, verifies the state parameter,
    exchanges the authorization code for access tokens, and stores them in the database.
    
    Args:
        request (Request): FastAPI request object
        code (str): Authorization code received from Zoom
        state (str): State parameter from authorization request (format: state_userid)
        supabase (Client): Supabase client
        
    Returns:
        dict: Success message and token expiration details
            {
                "message": str,
                "status": str,
                "expires_at": str
            }
            
    Raises:
        HTTPException: If state is invalid, user not found, or token exchange fails
    """

@router.get("/callback")
async def zoom_callback(
    request: Request,
    code: str = Query(..., description="Authorization code from Zoom"),
    state: str = Query(..., description="State parameter from authorization request"),
    supabase: Client = Depends(get_supabase)
):
    # Extract user_id from state (format: state_userid)
    try:
        state_parts = state.split('_')
        if len(state_parts) != 2:
            raise ValueError("Invalid state format")
        state_value, user_id = state_parts
        user_id = uuid.UUID(user_id)
    except (ValueError, IndexError):
        raise HTTPException(status_code=400, detail="Invalid state parameter format")

    # Verify user exists
    user_response = supabase.table("users") \
        .select("*") \
        .eq("user_id", str(user_id)) \
        .execute()
    
    if not user_response.data:
        raise HTTPException(status_code=404, detail="User not found")

    # Exchange code for access token
    token_url = "https://zoom.us/oauth/token"
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": ZOOM_REDIRECT_URI,
        "client_id": ZOOM_CLIENT_ID,
        "client_secret": ZOOM_CLIENT_SECRET
    }
    
    response = requests.post(token_url, data=data)
    if response.status_code != 200:
        raise HTTPException(status_code=400, detail="Failed to get access token")
    
    token_data = response.json()
    
    # Store tokens in database
    token_data = {
        "user_id": str(user_id),
        "platform": "zoom",
        "access_token": token_data["access_token"],
        "refresh_token": token_data["refresh_token"],
        "expires_at": (datetime.utcnow() + timedelta(seconds=token_data["expires_in"])).isoformat()
    }
    
    # Update existing token or create new one
    existing_token_response = supabase.table("oauth_tokens") \
        .select("*") \
        .eq("user_id", str(user_id)) \
        .eq("platform", "zoom") \
        .execute()
    
    if existing_token_response.data:
        supabase.table("oauth_tokens") \
            .update(token_data) \
            .eq("user_id", str(user_id)) \
            .eq("platform", "zoom") \
            .execute()
    else:
        supabase.table("oauth_tokens").insert(token_data).execute()
    
    return {
        "message": "Successfully connected Zoom account",
        "status": "connected",
        "expires_at": token_data["expires_at"]
    }


"""
    /meeting-platform/zoom/status
    Check the status of a user's Zoom connection.
    
    This endpoint verifies if a user has an active Zoom connection and checks
    if their access token is still valid.
    
    Args:
        user_id (uuid.UUID): ID of the user to check
        supabase (Client): Supabase client
        
    Returns:
        dict: Connection status and token expiration details
            {
                "status": str,  # "connected", "not_connected", or "expired"
                "expires_at": str,
                "is_expired": bool
            }
            
    Raises:
        HTTPException: If user is not found
"""
@router.get("/status")
async def zoom_status(
    user_id: uuid.UUID = Query(..., description="User ID to check Zoom connection status"),
    supabase: Client = Depends(get_supabase)
):
    # Verify user exists
    user_response = supabase.table("users") \
        .select("*") \
        .eq("user_id", str(user_id)) \
        .execute()
    
    if not user_response.data:
        raise HTTPException(status_code=404, detail="User not found")

    token_response = supabase.table("oauth_tokens") \
        .select("*") \
        .eq("user_id", str(user_id)) \
        .eq("platform", "zoom") \
        .execute()
    
    if not token_response.data:
        return {
            "status": "not_connected",
            "message": "Zoom account not connected"
        }
    
    token = token_response.data[0]
    is_expired = datetime.utcnow() >= datetime.fromisoformat(token["expires_at"])
    
    return {
        "status": "connected" if not is_expired else "expired",
        "expires_at": token["expires_at"],
        "is_expired": is_expired
    }


"""
    /meeting-platform/zoom/generate-link
    Generate a Zoom meeting link for a given user, date, and time.
    
    This endpoint performs Zoom OAuth validation and returns the join URL.
    Args:
        user_id (uuid.UUID): User ID generating the meeting link (must have Zoom connected)
        date (str): Meeting date (YYYY-MM-DD)
        time (str): Meeting time (HH:MM, 24h)
        title (str): Meeting title (optional)
        duration (int): Duration in minutes (default 60)
    Returns:
        dict: { status, meeting_link }
    Raises:
        HTTPException: If user is not Zoom-authenticated or Zoom API fails
"""

@router.post("/generate-link")
async def generate_meeting_link(
    user_id: uuid.UUID = Query(..., description="User ID generating the meeting link"),
    date: str = Query(..., description="Meeting date in YYYY-MM-DD format"),
    time: str = Query(..., description="Meeting time in HH:MM format (24h)"),
    title: str = Query("Momentum Meeting", description="Meeting title"),
    duration: int = Query(60, description="Duration in minutes"),
    supabase: Client = Depends(get_supabase)
):
    """
    Generate a Zoom meeting link for a given user, date, and time.
    Performs Zoom OAuth validation and returns the join URL.
    Args:
        user_id (uuid.UUID): User ID generating the meeting link (must have Zoom connected)
        date (str): Meeting date (YYYY-MM-DD)
        time (str): Meeting time (HH:MM, 24h)
        title (str): Meeting title (optional)
        duration (int): Duration in minutes (default 60)
    Returns:
        dict: { status, meeting_link }
    Raises:
        HTTPException: If user is not Zoom-authenticated or Zoom API fails
    """
    # Validate user and Zoom auth
    print("in generate meeting link")
    access_token = get_valid_zoom_token(supabase, user_id)
    print("access token")
    # Compose start_time in ISO format
    try:
        start_time = datetime.strptime(f"{date}T{time}", "%Y-%m-%dT%H:%M")
        start_time_iso = start_time.isoformat()
        print("start time",start_time_iso)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid date or time format")

    # Create Zoom meeting
    zoom_url = "https://api.zoom.us/v2/users/me/meetings"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    print("after try")
    data = {
        "topic": title,
        "type": 2,  # Scheduled meeting
        "start_time": start_time_iso,
        "duration": duration,
        "settings": {
            "host_video": True,
            "participant_video": True,
            "join_before_host": False,
            "mute_upon_entry": True,
            "waiting_room": True
        }
    }
    response = requests.post(zoom_url, headers=headers, json=data)
    print(f"Zoom API response: {response.status_code} - {response.text}")
    if response.status_code != 201:
        raise HTTPException(status_code=400, detail="Failed to create Zoom meeting")
    zoom_meeting = response.json()
    print("meeting created", zoom_meeting)
    return {
        "status": "success",
        "meeting_link": zoom_meeting["join_url"]
    }

"""
    /meeting-platform/zoom/save-link
    Save a manually provided meeting link for a meeting.
    
    This endpoint allows saving meeting links from various platforms (Zoom, Teams, Google Meet).
    It validates the link format and determines the platform automatically.
    
    Args:
        meeting_id (uuid.UUID): ID of the meeting to save link for
        link (str): The meeting link URL
        user_id (uuid.UUID): ID of the user saving the link
        supabase (Client): Supabase client
        
    Returns:
        dict: Success message
            {
                "status": str,
                "message": str
            }
            
    Raises:
        HTTPException: If meeting/user not found or link format is invalid
    """

@router.post("/save-link")
async def save_meeting_link(
    meeting_id: uuid.UUID,
    link: str,
    user_id: uuid.UUID = Query(..., description="User ID saving the meeting link"),
    supabase: Client = Depends(get_supabase)
):
    # Verify meeting exists
    meeting_response = supabase.table("meetings") \
        .select("*") \
        .eq("meeting_id", str(meeting_id)) \
        .execute()
    
    if not meeting_response.data:
        raise HTTPException(status_code=404, detail="Meeting not found")

    # Save meeting link
    link_data = {
        "meeting_id": str(meeting_id),
        "platform": "zoom",
        "link_url": link,
        "created_by": str(user_id)
    }
    supabase.table("meeting_links").insert(link_data).execute()
    
    return {
        "status": "success",
        "message": "Meeting link saved successfully"
    }

@router.post("/generate-link-with-recording/{meeting_id}")
async def generate_meeting_link_with_recording(
    meeting_id: uuid.UUID,
    user_id: uuid.UUID = Query(..., description="User ID generating the meeting link"),
    webhook_url: str = RECALL_WEBHOOK_URL,
    supabase: Client = Depends(get_supabase)
):
    """
    Generate a Zoom meeting link and start Recall.ai recording.
    
    This endpoint creates a new Zoom meeting, generates a join link, and starts
    a Recall.ai bot to record and transcribe the meeting. It also sets up
    automatic AI summary processing when the meeting starts.
    
    Args:
        meeting_id (uuid.UUID): ID of the meeting to generate link for
        user_id (uuid.UUID): ID of the user generating the link
        webhook_url (str): URL for receiving transcription webhooks
        supabase (Client): Supabase client
        
    Returns:
        dict: Generated meeting link and recording status
            {
                "status": str,
                "meeting_link": str,
                "recording": {
                    "botId": str,
                    "status": str
                },
                "ai_pipeline_ready": bool
            }
    """
    try:
        # First generate the Zoom meeting link
        zoom_result = await generate_meeting_link(meeting_id, user_id, supabase)
        
        # Check if meeting is ongoing before starting the bot
        meeting_response = supabase.table("meetings") \
            .select("*") \
            .eq("meeting_id", str(meeting_id)) \
            .execute()
        if not meeting_response.data:
            raise HTTPException(status_code=404, detail="Meeting not found")
        meeting = meeting_response.data[0]
        scheduled_at = datetime.fromisoformat(meeting["scheduled_at"])
        now = datetime.now(timezone.utc)
        window_start = scheduled_at - timedelta(minutes=10)
        window_end = scheduled_at + timedelta(hours=2)
        if not (window_start <= now <= window_end):
            raise HTTPException(
                status_code=400,
                detail="Meeting is not currently ongoing. You can only start the bot shortly before or during the scheduled meeting time."
            )
        if meeting.get("meeting_status") not in ["scheduled", "started"]:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot start bot: meeting status is '{meeting.get('meeting_status')}'."
            )
        # Start Recall.ai recording
        recording_result = await recall_service.start_recording(
            meeting_url=zoom_result["meeting_link"],
            meeting_id=str(meeting_id),
            user_id=str(user_id),
            webhook_url=webhook_url
        )
        
        # Update meeting with bot information for AI processing
        supabase.table("meetings") \
            .update({
                "bot_id": recording_result["botId"],
                "ai_processing_enabled": True
            }) \
            .eq("meeting_id", str(meeting_id)) \
            .execute()
        
        return {
            "status": "success",
            "meeting_link": zoom_result["meeting_link"],
            "recording": recording_result,
            "ai_pipeline_ready": True,
            "message": "Meeting link generated with AI processing enabled"
        }
        
    except Exception as e:
        print(f"Error generating meeting link with recording: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to generate meeting link with recording: {str(e)}")

@router.post("/start-meeting/{meeting_id}")
async def start_meeting_with_ai_processing(
    meeting_id: uuid.UUID,
    user_id: uuid.UUID = Query(..., description="User ID starting the meeting"),
    supabase: Client = Depends(get_supabase)
):
    """
    Start a meeting with automatic AI processing (triggered by Momentum invite).
    
    This endpoint is called when a meeting starts via a Momentum AI invite link.
    It automatically triggers the AI summary pipeline to process the transcript.
    
    Args:
        meeting_id (uuid.UUID): ID of the meeting
        user_id (uuid.UUID): ID of the user starting the meeting
        supabase (Client): Supabase client
        
    Returns:
        dict: Meeting start status and AI processing information
            {
                "status": str,
                "meeting_started": bool,
                "ai_processing_triggered": bool,
                "bot_id": str,
                "message": str
            }
    """
    try:
        # Get meeting information
        meeting_response = supabase.table("meetings") \
            .select("*, projects!inner(*, organizations!inner(*))") \
            .eq("meeting_id", str(meeting_id)) \
            .execute()
        
        if not meeting_response.data:
            raise HTTPException(status_code=404, detail="Meeting not found")
        
        meeting = meeting_response.data[0]
        bot_id = meeting.get("bot_id")
        
        if not bot_id:
            raise HTTPException(status_code=400, detail="No recording bot found for this meeting")
        
        # Update meeting status to started
        supabase.table("meetings") \
            .update({
                "meeting_status": "started",
                "started_at": datetime.utcnow().isoformat()
            }) \
            .eq("meeting_id", str(meeting_id)) \
            .execute()
        
        # Trigger AI processing pipeline
        try:
            ai_result = await ai_summary_pipeline.process_meeting_summary(
                meeting_id=str(meeting_id),
                bot_id=bot_id,
                user_id=str(user_id),
                supabase=supabase
            )
            
            ai_processing_triggered = ai_result["status"] == "success"
            
            if ai_processing_triggered:
                # Update meeting with AI processing status
                supabase.table("meetings") \
                    .update({
                        "ai_processing_status": "completed",
                        "summary_id": ai_result.get("summary_id")
                    }) \
                    .eq("meeting_id", str(meeting_id)) \
                    .execute()
                
                message = "Meeting started with AI processing completed"
            else:
                message = "Meeting started but AI processing failed"
                
        except Exception as ai_error:
            print(f"AI processing error: {str(ai_error)}")
            ai_processing_triggered = False
            message = "Meeting started but AI processing encountered an error"
        
        return {
            "status": "success",
            "meeting_started": True,
            "ai_processing_triggered": ai_processing_triggered,
            "bot_id": bot_id,
            "meeting_title": meeting["title"],
            "project_name": meeting["projects"]["project_name"],
            "organization_name": meeting["projects"]["organizations"]["org_name"],
            "message": message
        }
        
    except Exception as e:
        print(f"Error starting meeting: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to start meeting: {str(e)}")
