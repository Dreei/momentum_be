from fastapi import APIRouter, Depends, HTTPException, Request, Query, Response
from database.base import get_supabase
from supabase import Client
from typing import Optional, Dict, Any
import uuid
from datetime import datetime, timedelta, timezone
from services.recallai_services import recall_service, ai_summarization_service
from services.ai_summary_pipeline import ai_summary_pipeline
from core.config import RECALL_WEBHOOK_SECRET
import json

router = APIRouter()

@router.post("/start-recording")
async def start_recording(
    meeting_url: str,
    meeting_id: str = Query(..., description="Meeting ID"),
    user_id: str = Query(..., description="User ID"),
    webhook_url: str = Query(..., description="Webhook URL for transcriptions"),
    supabase: Client = Depends(get_supabase)
):
    """
    Start a Recall.ai bot recording for a meeting.
    
    Args:
        meeting_url (str): The meeting URL to join
        meeting_id (str): ID of the meeting
        user_id (str): ID of the user starting the recording
        webhook_url (str): URL for receiving transcription webhooks
        supabase (Client): Supabase client
        
    Returns:
        dict: Bot ID and status
            {
                "botId": str,
                "status": str
            }
    """
    try:
        # Verify meeting exists
        meeting_response = supabase.table("meetings") \
            .select("*") \
            .eq("meeting_id", meeting_id) \
            .execute()
        
        if not meeting_response.data:
            raise HTTPException(status_code=404, detail="Meeting not found")
        meeting = meeting_response.data[0]
        # scheduled_at = datetime.fromisoformat(meeting["scheduled_at"])
        # now = datetime.now(timezone.utc)
        # window_start = scheduled_at - timedelta(minutes=10)
        # window_end = scheduled_at + timedelta(hours=2)
        # if not (window_start <= now <= window_end):
        #     raise HTTPException(
        #         status_code=400,
        #         detail="Meeting is not currently ongoing. You can only start the bot shortly before or during the scheduled meeting time."
        #     )
        # if meeting.get("meeting_status") not in ["scheduled", "started"]:
        #     raise HTTPException(
        #         status_code=400,
        #         detail=f"Cannot start bot: meeting status is '{meeting.get('meeting_status')}'."
        #     )
        
        # Verify user exists
        user_response = supabase.table("users") \
            .select("*") \
            .eq("user_id", user_id) \
            .execute()
        
        if not user_response.data:
            raise HTTPException(status_code=404, detail="User not found")
        
        print(f"Starting Recall.ai recording for meeting: {meeting_id}")
        
        result = await recall_service.start_recording(
            meeting_url=meeting_url,
            meeting_id=meeting_id,
            user_id=user_id,
            webhook_url=webhook_url
        )
        
        # Update meeting with bot_id after successful recording start
        if result and "botId" in result:
            bot_id = result["botId"]
            print(f"Updating meeting {meeting_id} with bot_id: {bot_id}")
            
            # Update the meeting record with the bot_id
            update_response = supabase.table("meetings") \
                .update({"bot_id": bot_id}) \
                .eq("meeting_id", meeting_id) \
                .execute()
            
            if update_response.data:
                print(f"Successfully updated meeting {meeting_id} with bot_id {bot_id}")
            else:
                print(f"Warning: Failed to update meeting {meeting_id} with bot_id {bot_id}")
        
        return result
        
    except Exception as e:
        print(f"Error starting recording: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to start recording: {str(e)}")

@router.post("/stop-recording")
async def stop_recording(
    meeting_id: str = Query(..., description="Meeting ID"),
    supabase: Client = Depends(get_supabase)
):
    """
    Stop a Recall.ai bot recording.
    
    Args:
        meeting_id (str): ID of the meeting
        supabase (Client): Supabase client
        
    Returns:
        dict: Status confirmation
            {
                "status": str
            }
    """
    try:
        # Get meeting and bot_id
        meeting_response = supabase.table("meetings") \
            .select("*") \
            .eq("meeting_id", meeting_id) \
            .execute()
        
        if not meeting_response.data:
            raise HTTPException(status_code=404, detail="Meeting not found")
        
        meeting = meeting_response.data[0]
        bot_id = meeting.get("bot_id")
        
        if not bot_id:
            raise HTTPException(status_code=400, detail="No bot ID found for this meeting")
        
        # Verify session exists
        session_response = supabase.table("recall_sessions") \
            .select("*") \
            .eq("bot_id", bot_id) \
            .execute()
        
        if not session_response.data:
            raise HTTPException(status_code=404, detail="Recording session not found")
        
        print(f"Stopping Recall.ai recording for bot: {bot_id}")
        
        result = await recall_service.stop_recording(bot_id, meeting_id)
        
        return result
        
    except Exception as e:
        print(f"Error stopping recording: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to stop recording: {str(e)}")

@router.get("/recording-state")
async def get_recording_state(
    meeting_id: str = Query(..., description="Meeting ID"),
    supabase: Client = Depends(get_supabase)
):
    """
    Get the current state of a Recall.ai bot recording.
    
    Args:
        meeting_id (str): ID of the meeting
        supabase (Client): Supabase client
        
    Returns:
        dict: Bot state and transcript data
            {
                "state": str,
                "transcript": list
            }
    """
    try:
        # Get meeting and bot_id
        meeting_response = supabase.table("meetings") \
            .select("*") \
            .eq("meeting_id", meeting_id) \
            .execute()
        
        if not meeting_response.data:
            raise HTTPException(status_code=404, detail="Meeting not found")
        
        meeting = meeting_response.data[0]
        bot_id = meeting.get("bot_id")
        
        if not bot_id:
            raise HTTPException(status_code=400, detail="No bot ID found for this meeting")
        
        # Verify session exists
        session_response = supabase.table("recall_sessions") \
            .select("*") \
            .eq("bot_id", bot_id) \
            .execute()
        
        if not session_response.data:
            raise HTTPException(status_code=404, detail="Recording session not found")
        
        result = await recall_service.get_recording_state(bot_id)
        
        return result
        
    except Exception as e:
        print(f"Error getting recording state: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get recording state: {str(e)}")

@router.post("/transcription")
async def handle_transcription_webhook(
    request: Request,
    secret: str = Query(..., description="Webhook secret for verification"),
    supabase: Client = Depends(get_supabase)
):
    """
    Handle transcription webhook from Recall.ai.
    
    Args:
        request (Request): FastAPI request object
        secret (str): Webhook secret for verification
        supabase (Client): Supabase client
        
    Returns:
        dict: Success confirmation
            {
                "success": bool
            }
    """
    try:
        # Verify webhook secret
        if not recall_service.verify_webhook_signature(secret):
            raise HTTPException(status_code=401, detail="Unauthorized webhook")
        
        # Parse request body
        body = await request.json()
        
        # Only process transcript.data events
        if body.get("event") != "transcript.data":
            return {"success": True}
        
        transcript_data = body.get("data", {}).get("data")
        bot_id = body.get("data", {}).get("bot", {}).get("id")
        
        if not transcript_data or not bot_id:
            raise HTTPException(status_code=400, detail="Invalid webhook data")
        
        # Find meeting_id from bot_id
        session_response = supabase.table("recall_sessions") \
            .select("meeting_id") \
            .eq("bot_id", bot_id) \
            .execute()
        
        meeting_id = None
        if session_response.data:
            meeting_id = session_response.data[0]["meeting_id"]
            print(f"Found meeting_id: {meeting_id} for bot_id: {bot_id}")
        else:
            print(f"Warning: No recall session found for bot_id: {bot_id}")
        
        # Save transcript to database
        await recall_service.save_transcript(bot_id, transcript_data, meeting_id)
        
        print(f"Saved transcript for bot: {bot_id}")
        
        return {"success": True}
        
    except Exception as e:
        print(f"Error handling transcription webhook: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to process webhook: {str(e)}")

@router.post("/summarize")
async def summarize_transcript(
    meeting_id: str = Query(..., description="Meeting ID"),
    prompt_type: str = Query("general_summary", description="Type of summary to generate"),
    supabase: Client = Depends(get_supabase)
):
    """
    Generate a summary of the meeting transcript using AI.
    
    Args:
        meeting_id (str): ID of the meeting
        prompt_type (str): Type of summary (general_summary, action_items, decisions, next_steps, key_takeaways)
        supabase (Client): Supabase client
        
    Returns:
        dict: Generated summary
            {
                "summary": str
            }
    """
    try:
        # Get meeting and bot_id
        meeting_response = supabase.table("meetings") \
            .select("*") \
            .eq("meeting_id", meeting_id) \
            .execute()
        
        if not meeting_response.data:
            raise HTTPException(status_code=404, detail="Meeting not found")
        
        meeting = meeting_response.data[0]
        bot_id = meeting.get("bot_id")
        
        if not bot_id:
            raise HTTPException(status_code=400, detail="No bot ID found for this meeting")
        
        # Verify session exists
        session_response = supabase.table("recall_sessions") \
            .select("*") \
            .eq("bot_id", bot_id) \
            .execute()
        
        if not session_response.data:
            raise HTTPException(status_code=404, detail="Recording session not found")
        
        # Get transcripts from database
        transcript_response = supabase.table("meeting_transcripts") \
            .select("*") \
            .eq("bot_id", bot_id) \
            .order("created_at", desc=False) \
            .execute()
        
        transcripts = transcript_response.data if transcript_response.data else []
        
        if not transcripts:
            return {
                "summary": "No transcript data available to summarize.",
                "warning": "The meeting transcript appears to be empty or incomplete."
            }
        
        # Extract transcript data for processing
        transcript_data = [entry["transcript_data"] for entry in transcripts]
        
        # Generate summary using AI
        summary = await ai_summarization_service.summarize_transcript(
            transcripts=transcript_data,
            prompt_type=prompt_type
        )
        
        return {"summary": summary}
        
    except Exception as e:
        print(f"Error summarizing transcript: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to generate summary: {str(e)}")

@router.get("/sessions/{meeting_id}")
async def get_meeting_sessions(
    meeting_id: str,
    supabase: Client = Depends(get_supabase)
):
    """
    Get all recording sessions for a meeting.
    
    Args:
        meeting_id (str): ID of the meeting
        supabase (Client): Supabase client
        
    Returns:
        dict: List of recording sessions
            {
                "sessions": list
            }
    """
    try:
        # Verify meeting exists
        meeting_response = supabase.table("meetings") \
            .select("*") \
            .eq("meeting_id", meeting_id) \
            .execute()
        
        if not meeting_response.data:
            raise HTTPException(status_code=404, detail="Meeting not found")
        
        # Get sessions for meeting
        sessions_response = supabase.table("recall_sessions") \
            .select("*") \
            .eq("meeting_id", meeting_id) \
            .order("created_at", desc=True) \
            .execute()
        
        return {"sessions": sessions_response.data if sessions_response.data else []}
        
    except Exception as e:
        print(f"Error getting meeting sessions: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get sessions: {str(e)}")

@router.post("/process-structured-summary")
async def process_structured_summary(
    meeting_id: str = Query(..., description="Meeting ID"),
    user_id: str = Query(..., description="User ID requesting summary"),
    supabase: Client = Depends(get_supabase)
):
    """
    Process meeting transcript and generate structured AI summary.
    
    This endpoint triggers the AI pipeline to analyze the meeting transcript
    and generate a comprehensive structured summary including action items,
    decisions, key takeaways, and more.
    
    Args:
        meeting_id (str): ID of the meeting
        user_id (str): ID of the user requesting the summary
        supabase (Client): Supabase client
        
    Returns:
        dict: Processing result and structured summary
            {
                "status": str,
                "summary_id": str,
                "structured_summary": dict,
                "transcript_length": int,
                "processed_at": str
            }
    """
    try:
        # Verify meeting exists and get bot_id
        meeting_response = supabase.table("meetings") \
            .select("*") \
            .eq("meeting_id", meeting_id) \
            .execute()
        
        if not meeting_response.data:
            raise HTTPException(status_code=404, detail="Meeting not found")
        
        meeting = meeting_response.data[0]
        bot_id = meeting.get("bot_id")
        
        if not bot_id:
            raise HTTPException(status_code=400, detail="No bot ID found for this meeting")
        
        # Verify user exists
        user_response = supabase.table("users") \
            .select("*") \
            .eq("user_id", user_id) \
            .execute()
        
        if not user_response.data:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Process structured summary
        result = await ai_summary_pipeline.process_meeting_summary(
            meeting_id=meeting_id,
            bot_id=bot_id,
            user_id=user_id,
            supabase=supabase
        )
        
        if result["status"] == "error":
            raise HTTPException(status_code=500, detail=result["error"])
        
        # Update meeting status to completed
        supabase.table("meetings") \
            .update({"meeting_status": "completed"}) \
            .eq("meeting_id", meeting_id) \
            .execute()
        
        
        return result
        
    except Exception as e:
        print(f"Error processing structured summary: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to process structured summary: {str(e)}")

@router.get("/structured-summary/{meeting_id}")
async def get_structured_summary(
    meeting_id: str,
    user_id: str = Query(..., description="User ID requesting the summary"),
    supabase: Client = Depends(get_supabase)
):
    """
    Get structured summary for a meeting with user role information.
    
    Args:
        meeting_id (str): ID of the meeting
        user_id (str): ID of the user requesting the summary
        supabase (Client): Supabase client
        
    Returns:
        dict: Structured summary and components with user role
            {
                "status": str,
                "summary": dict,
                "action_items": list,
                "decisions": list,
                "discussions": list,
                "created_at": str,
                "user_role": str  # "host" or "participant"
            }
    """
    try:
        print(f"Getting structured summary for meeting: {meeting_id}, user: {user_id}")
        
        # Verify meeting exists
        meeting_response = supabase.table("meetings") \
            .select("*") \
            .eq("meeting_id", meeting_id) \
            .execute()
        
        if not meeting_response.data:
            print(f"Meeting not found: {meeting_id}")
            raise HTTPException(status_code=404, detail="Meeting not found")
        
        meeting = meeting_response.data[0]
        print(f"Meeting found: {meeting['title']}")
        
        # Determine user role in this meeting
        user_role = "participant"  # default
        
        # Check if user is the meeting host (created_by)
        if meeting.get("created_by") == user_id:
            user_role = "host"
        else:
            # Check if user is a participant
            participant_response = supabase.table("meeting_participants") \
                .select("role") \
                .eq("meeting_id", meeting_id) \
                .eq("user_id", user_id) \
                .execute()
            
            if participant_response.data:
                # Use the role from meeting_participants table
                participant_role = participant_response.data[0].get("role", "participant")
                # Map Creator role to host, others remain as participant
                if participant_role.lower() == "creator":
                    user_role = "host"
                else:
                    user_role = "participant"
            else:
                # User is not a participant, check if they have access through project membership
                project_member_response = supabase.table("meetings") \
                    .select("*, projects!inner(project_members!inner(*))") \
                    .eq("meeting_id", meeting_id) \
                    .eq("projects.project_members.user_id", user_id) \
                    .execute()
                
                if not project_member_response.data:
                    raise HTTPException(status_code=403, detail="Access denied: User is not a participant or project member")
        
        print(f"User role determined: {user_role}")
        
        # Get structured summary
        result = await ai_summary_pipeline.get_meeting_summary(meeting_id, supabase)
        
        print(f"Summary result status: {result.get('status')}")
        print(f"Summary result keys: {list(result.keys())}")
        
        if result["status"] == "error":
            print(f"Summary error: {result.get('error')}")
            raise HTTPException(status_code=500, detail=result["error"])
        
        if result["status"] == "not_found":
            print(f"No summary found for meeting: {meeting_id}")
            raise HTTPException(status_code=404, detail="No summary found for this meeting")
        
        # Add user role to the response
        result["user_role"] = user_role
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error retrieving structured summary: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve structured summary: {str(e)}")

@router.post("/auto-process-meeting/{meeting_id}")
async def auto_process_meeting(
    meeting_id: str,
    user_id: str = Query(..., description="User ID"),
    supabase: Client = Depends(get_supabase)
):
    """
    Automatically process meeting when it starts (triggered by Momentum invite).
    
    This endpoint is called when a meeting starts via a Momentum AI invite link.
    It automatically processes the transcript and generates a structured summary.
    
    Args:
        meeting_id (str): ID of the meeting
        user_id (str): ID of the user who started the meeting
        supabase (Client): Supabase client
        
    Returns:
        dict: Processing status and summary information
            {
                "status": str,
                "message": str,
                "summary_id": str,
                "context_group": str,
                "processed_at": str
            }
    """
    try:
        # Verify meeting exists and get bot_id
        meeting_response = supabase.table("meetings") \
            .select("*, projects!inner(*, organizations!inner(*))") \
            .eq("meeting_id", meeting_id) \
            .execute()
        
        if not meeting_response.data:
            raise HTTPException(status_code=404, detail="Meeting not found")
        
        meeting = meeting_response.data[0]
        bot_id = meeting.get("bot_id")
        
        if not bot_id:
            raise HTTPException(status_code=400, detail="No bot ID found for this meeting")
        
        # Update meeting status to indicate processing
        supabase.table("meetings") \
            .update({"meeting_status": "processing"}) \
            .eq("meeting_id", meeting_id) \
            .execute()
        
        # Process structured summary
        summary_result = await ai_summary_pipeline.process_meeting_summary(
            meeting_id=meeting_id,
            bot_id=bot_id,
            user_id=user_id,
            supabase=supabase
        )
        
        if summary_result["status"] == "success":
            # Update meeting status to completed
            supabase.table("meetings") \
                .update({"meeting_status": "completed"}) \
                .eq("meeting_id", meeting_id) \
                .execute()
            
            # Get context group from summary
            structured_summary = summary_result.get("structured_summary", {})
            context_group = structured_summary.get("context_group", "general")
            
            return {
                "status": "success",
                "message": "Meeting processed successfully",
                "summary_id": summary_result["summary_id"],
                "context_group": context_group,
                "meeting_title": meeting["title"],
                "project_name": meeting["projects"]["project_name"],
                "organization_name": meeting["projects"]["organizations"]["org_name"],
                "processed_at": summary_result["processed_at"]
            }
        else:
            # Update meeting status to error
            supabase.table("meetings") \
                .update({"meeting_status": "error"}) \
                .eq("meeting_id", meeting_id) \
                .execute()
            
            raise HTTPException(status_code=500, detail=summary_result.get("error", "Unknown error"))
        
    except Exception as e:
        print(f"Error auto-processing meeting: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to auto-process meeting: {str(e)}")

@router.get("/meeting-summaries/{meeting_id}")
async def get_meeting_summaries_without_bot_id(
    meeting_id: str,
    supabase: Client = Depends(get_supabase)
):
    """
    Get all meeting summaries for a meeting, excluding the bot_id field.
    Returns a list of summaries with fields: summary_id, meeting_id, summary_type, content (as JSON), created_at, created_by, context_group.
    The 'content' field is always a JSON object, never a string.
    """
    fallback_content = {
        "overview": "",
        "action_items": [],
        "key_decisions": [],
        "key_takeaways": [],
        "discussion_points": [],
        "jargon_clarifications": [],
        "themes": [],
        "context_group": ""
    }
    try:
        summaries_response = supabase.table("meeting_summaries") \
            .select("summary_id, meeting_id, summary_type, content, created_at, created_by, context_group") \
            .eq("meeting_id", meeting_id) \
            .order("created_at", desc=False) \
            .execute()
        summaries = summaries_response.data if summaries_response.data else []
        for summary in summaries:
            try:
                summary['content'] = json.loads(summary['content'])
                if not isinstance(summary['content'], dict):
                    summary['content'] = fallback_content
            except Exception:
                summary['content'] = fallback_content
        return {"summaries": summaries}
    except Exception as e:
        print(f"Error getting meeting summaries: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get meeting summaries: {str(e)}") 

@router.get("/meeting-transcript/{meeting_id}")
async def get_meeting_transcript(
    meeting_id: str,
    supabase: Client = Depends(get_supabase)
):
    """
    Get meeting transcript by meeting ID.
    
    Args:
        meeting_id (str): ID of the meeting
        supabase (Client): Supabase client
        
    Returns:
        dict: Meeting transcript data
            {
                "status": str,
                "transcript": list,
                "meeting_info": dict
            }
    """
    try:
        print(f"Getting transcript for meeting: {meeting_id}")
        
        # First, get the meeting details
        meeting_response = supabase.table("meetings") \
            .select("*") \
            .eq("meeting_id", meeting_id) \
            .execute()
        
        if not meeting_response.data:
            print(f"Meeting not found: {meeting_id}")
            raise HTTPException(status_code=404, detail="Meeting not found")
        
        meeting = meeting_response.data[0]
        print(f"Meeting found: {meeting['title']}")
        
        # Get transcripts directly by meeting_id
        transcript_response = supabase.table("meeting_transcripts") \
            .select("*") \
            .eq("meeting_id", meeting_id) \
            .order("created_at", desc=False) \
            .execute()
        
        transcripts = transcript_response.data if transcript_response.data else []
        print(f"Found {len(transcripts)} transcript entries")
        
        if not transcripts:
            return {
                "status": "not_found",
                "message": "No transcript data available for this meeting",
                "meeting_info": {
                    "meeting_id": meeting_id,
                    "title": meeting["title"],
                    "scheduled_at": meeting["scheduled_at"]
                }
            }
        
        # Process transcript data to make it more readable
        processed_transcript = []
        for transcript in transcripts:
            transcript_data = transcript["transcript_data"]
            
            # Handle different transcript data formats
            if isinstance(transcript_data, dict):
                # If it's a single transcript entry
                if "words" in transcript_data:
                    # Process word-level transcript
                    words = transcript_data.get("words", [])
                    
                    # Handle speaker information - check both 'speaker' and 'participant' fields
                    speaker = "Unknown"
                    if "speaker" in transcript_data:
                        speaker = transcript_data.get("speaker", "Unknown")
                    elif "participant" in transcript_data:
                        participant = transcript_data.get("participant", {})
                        if isinstance(participant, dict):
                            speaker = participant.get("name", "Unknown")
                        else:
                            speaker = str(participant)
                    
                    # Extract timestamp - use first word's start timestamp if available
                    timestamp = "00:00"
                    if words and len(words) > 0:
                        first_word = words[0]
                        if "start_timestamp" in first_word:
                            start_ts = first_word["start_timestamp"]
                            if isinstance(start_ts, dict) and "relative" in start_ts:
                                # Convert relative timestamp (seconds) to MM:SS format
                                seconds = start_ts["relative"]
                                minutes = int(seconds // 60)
                                secs = int(seconds % 60)
                                timestamp = f"{minutes:02d}:{secs:02d}"
                            elif isinstance(start_ts, dict) and "absolute" in start_ts:
                                # Use absolute timestamp as fallback
                                timestamp = start_ts["absolute"]
                    elif "timestamp" in transcript_data:
                        timestamp = transcript_data.get("timestamp", "00:00")
                    
                    if words:
                        text = " ".join([word.get("text", "") for word in words])
                        processed_transcript.append({
                            "speaker": speaker,
                            "text": text,
                            "timestamp": timestamp,
                            "created_at": transcript["created_at"],
                            "word_count": len(words)
                        })
                else:
                    # If it's a different format, try to extract what we can
                    processed_transcript.append({
                        "speaker": transcript_data.get("speaker", "Unknown"),
                        "text": str(transcript_data),
                        "timestamp": transcript_data.get("timestamp", "00:00"),
                        "created_at": transcript["created_at"]
                    })
            elif isinstance(transcript_data, list):
                # If it's a list of transcript entries
                for entry in transcript_data:
                    if isinstance(entry, dict):
                        speaker = entry.get("speaker", "Unknown")
                        text = entry.get("text", str(entry))
                        timestamp = entry.get("timestamp", "00:00")
                        processed_transcript.append({
                            "speaker": speaker,
                            "text": text,
                            "timestamp": timestamp,
                            "created_at": transcript["created_at"]
                        })
        
        return {
            "status": "success",
            "transcript": processed_transcript,
            "meeting_info": {
                "meeting_id": meeting_id,
                "title": meeting["title"],
                "scheduled_at": meeting["scheduled_at"],
                "bot_id": transcripts[0].get("bot_id") if transcripts else None
            }
        }
        
    except Exception as e:
        print(f"Error retrieving meeting transcript: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve meeting transcript: {str(e)}") 