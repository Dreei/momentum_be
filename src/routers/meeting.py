from fastapi import APIRouter, Depends, HTTPException, Query
from database.base import get_supabase
from supabase import Client
import uuid
from typing import List
from datetime import datetime
from pydantic import BaseModel
from services.email_service import EmailService, MeetingInviteData
from schemas import MeetingBotUpdateRequest

router = APIRouter()
email_service = EmailService()

class MeetingParticipant(BaseModel):
    email: str
    role: str = "participant"
    user_id: uuid.UUID

class MeetingCreate(BaseModel):
    title: str
    scheduled_at: datetime
    duration_minutes: int
    project_id: uuid.UUID
    platform_type: str
    participants: List[MeetingParticipant]
    description: str = None
    agenda: List[str]
    meeting_link: str
    bot_id: str = None  # Optional bot ID for recall.ai integration


"""
[POST]
/meetings/:
Create a new meeting with metadata and participants.
The meeting is associated with a project and stored with draft status.
No meeting_id is returned at this stage.

Args:
    meeting: {
    title: str
    scheduled_at: datetime
    duration_minutes: int
    project_id: uuid.UUID
    platform_type: str
    participants: List[MeetingParticipant]
    description: str = None 
    }

    user_id (uuid.UUID): User ID of the requester.
    supabase (Client): Supabase client (injected).

Returns:
    dict: Status message.
"""



@router.post("/")
def create_meeting(meeting: MeetingCreate, user_id: uuid.UUID = Query(...), supabase: Client = Depends(get_supabase)):
    try:
        print(f"Creating meeting: {meeting.title}")
        print(f"Project ID: {meeting.project_id}")
        print(f"User ID: {user_id}")
        
        # Verify project exists
        project_response = supabase.table("projects").select("*").eq("project_id", str(meeting.project_id)).execute()
        if not project_response.data:
            raise HTTPException(status_code=404, detail=f"Project not found with ID: {meeting.project_id}")
        
        print(f"Project found: {project_response.data[0]['project_name']}")
        
        # Create meeting record
        meeting_data = {
            "project_id": str(meeting.project_id),
            "title": meeting.title,
            "description": meeting.description,
            "scheduled_at": meeting.scheduled_at.isoformat(),
            "created_by": str(user_id),
            "meeting_status": "scheduled",
            "agenda_generated": False,
            "manual_meeting_link": meeting.meeting_link,
            "bot_id": meeting.bot_id,  # Store bot ID if provided
        }
        
        
        meeting_response = supabase.table("meetings").insert(meeting_data).execute()
        new_meeting = meeting_response.data[0]
        print(f"Meeting created with ID: {new_meeting['meeting_id']}")
        print("meeting agenda",meeting.agenda)

        # Add participants
        participants_data = []
        for participant in meeting.participants:
            if not participant.email or not participant.email.strip():
                continue  # Skip empty emails
            # If user_id is empty or not found in users table, set as None
            user_id_to_use = None
            if participant.user_id:
                user_resp = supabase.table("users").select("*").eq("user_id", str(participant.user_id)).execute()
                if user_resp.data:
                    user_id_to_use = str(participant.user_id)
            participants_data.append({
                "meeting_id": new_meeting["meeting_id"],
                "user_id": user_id_to_use,
                "email": participant.email,
                "role": participant.role,
                "status": "invited"
            })
        print(f"Inserting participants data: {participants_data}")
        supabase.table("meeting_participants").insert(participants_data).execute()
        print("Participants added successfully")

        # Add meeting link if platform type is provided
        if meeting.platform_type:
            link_data = {
                "meeting_id": new_meeting["meeting_id"],
                "platform": meeting.platform_type,
                "link_url": meeting.meeting_link,
                "created_by": str(user_id)
            }
            print(f"Inserting meeting link data: {link_data}")
            supabase.table("meeting_links").insert(link_data).execute()
            print("Meeting link added successfully")

        # Get project and organization details for email
        project = project_response.data[0]
        org_response = supabase.table("organizations").select("*").eq("org_id", project["org_id"]).execute()
        org = org_response.data[0] if org_response.data else None
        
        # Get creator details
        creator_response = supabase.table("users").select("*").eq("user_id", str(user_id)).execute()
        creator = creator_response.data[0] if creator_response.data else None
        

        # Send meeting invites to participants
        if creator and org:
            for participant in meeting.participants:
                if not participant.email or not participant.email.strip():
                    continue  # Skip empty emails
                # Try to get user details if user_id is present
                theparticipant = None
                if participant.user_id:
                    theparticipant_response = supabase.table("users").select("*").eq("user_id", str(participant.user_id)).execute()
                    if theparticipant_response.data:
                        theparticipant = theparticipant_response.data[0]
                # If not found, use email only
                recipient_email = participant.email
                recipient_name = f"{theparticipant['first_name']} {theparticipant['last_name']}" if theparticipant else participant.email
                meeting_invite_data = MeetingInviteData(
                    meeting_title=meeting.title,
                    meeting_date=meeting.scheduled_at.strftime("%B %d, %Y"),
                    meeting_time=meeting.scheduled_at.strftime("%I:%M %p"),
                    meeting_platform=meeting.platform_type or "TBD",
                    meeting_link=meeting.meeting_link, 
                    agenda_items=meeting.agenda, 
                    recipient_email=recipient_email,
                    recipient_name=recipient_name,
                    organizer_name=f"{creator['first_name']} {creator['last_name']}",
                    organizer_email=creator["email"],
                    organization_name=org["org_name"],
                    project_name=project["project_name"]
                )
                email_service.send_meeting_invite(meeting_invite_data)

        print("Meeting creation completed successfully")

        # Call notify_meeting_link to send meeting link notifications
        try:
            from crud import notify_meeting_link
            notify_meeting_link({
                "meeting_id": new_meeting["meeting_id"],
                "meeting_link": meeting.meeting_link,
                "participants": meeting.participants,
                "title": meeting.title,
                "scheduled_at": meeting.scheduled_at.isoformat(),
                "project_id": str(meeting.project_id),
                "platform_type": meeting.platform_type
            })
        except Exception as e:
            print(f"Warning: Failed to send meeting link notification: {e}")

        return {"status": "success", "message": "Meeting created successfully","meeting_id":new_meeting['meeting_id']}
        
    except Exception as e:
        print(f"Error creating meeting: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


"""
[GET]
/meetings/{meeting_id}/participants:
Get all participants for a specific meeting.

Args:
    meeting_id (uuid.UUID): Meeting ID.
    supabase (Client): Supabase client (injected).

Returns:
    list: List of meeting participants with their details.
"""
@router.get("/participants")
def get_meeting_participants(meeting_id: uuid.UUID, supabase: Client = Depends(get_supabase)):
    # Verify meeting exists
    meeting_response = supabase.table("meetings").select("*").eq("meeting_id", str(meeting_id)).execute()
    if not meeting_response.data:
        raise HTTPException(status_code=404, detail="Meeting not found")
    
    # Get all participants for the meeting
    participants_response = supabase.table("meeting_participants") \
        .select("*") \
        .eq("meeting_id", str(meeting_id)) \
        .execute()
    
    return [{
        "email": p["email"],
        "role": p["role"],
        "status": p["status"],
        "joined_at": p["joined_at"]
    } for p in participants_response.data]







"""
[GET]
/meetings/project/{project_id}:
Get all meetings for a specific project.

Args:
    project_id (uuid.UUID): Project ID.
    supabase (Client): Supabase client (injected).

Returns:
    list: List of meetings with their details.
"""
@router.get("/project")
def get_project_meetings(project_id: uuid.UUID, supabase: Client = Depends(get_supabase)):
    # Verify project exists
    project_response = supabase.table("projects").select("*").eq("project_id", str(project_id)).execute()
    if not project_response.data:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Get all meetings for the project
    meetings_response = supabase.table("meetings") \
        .select("*") \
        .eq("project_id", str(project_id)) \
        .execute()
    
    return [{
        "meeting_id": m["meeting_id"],
        "title": m["title"],
        "description": m["description"],
        "scheduled_at": m["scheduled_at"],
        "meeting_status": m["meeting_status"],
        "created_at": m["created_at"],
        "created_by": m["created_by"],
        "bot_id": m["bot_id"]  # Include bot ID in response
    } for m in meetings_response.data]





"""
[GET]
/meetings/project-meetings/{project_id}:
Get all meetings in a project with their participants for a specific project.

Args:
    project_id (uuid.UUID): Project ID.
    supabase (Client): Supabase client (injected).

Returns:
    list: List of meetings with their details and participants.
"""
@router.get("/project-meetings/{project_id}")
def get_project_meetings_with_participants(project_id: uuid.UUID, supabase: Client = Depends(get_supabase)):
    # Verify project exists
    project_response = supabase.table("projects").select("*").eq("project_id", str(project_id)).execute()
    if not project_response.data:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Get all meetings for the project with their participants
    meetings_response = supabase.table("meetings") \
        .select("*, meeting_participants(*)") \
        .eq("project_id", str(project_id)) \
        .execute()
    
    return meetings_response.data




"""
[GET]
/meetings/{meeting_id}:
Get detailed information about a specific meeting including participants and meeting links.

Args:
    meeting_id (uuid.UUID): Meeting ID.
    supabase (Client): Supabase client (injected).

Returns:
    dict: Detailed meeting information including participants and meeting links.
"""
@router.get("/{meeting_id}")
def get_meeting_details(meeting_id: uuid.UUID, supabase: Client = Depends(get_supabase)):
    # Get meeting details
    meeting_response = supabase.table("meetings").select("*").eq("meeting_id", str(meeting_id)).execute()
    if not meeting_response.data:
        raise HTTPException(status_code=404, detail="Meeting not found")
    
    meeting = meeting_response.data[0]
    
    # Get participants
    participants_response = supabase.table("meeting_participants") \
        .select("*") \
        .eq("meeting_id", str(meeting_id)) \
        .execute()
    
    participants = participants_response.data
    
    # Get meeting links
    meeting_links_response = supabase.table("meeting_links").select("*").eq("meeting_id", str(meeting_id)).execute()
    
    meeting_links = meeting_links_response.data
    
    # Get summaries
    summaries_response = supabase.table("summaries").select("*").eq("meeting_id", str(meeting_id)).execute()
    
    summaries = summaries_response.data

    # Get agendas
    agendas_response = supabase.table("agendas").select("*").eq("meeting_id", str(meeting_id)).execute()
    
    agendas = agendas_response.data
    
    # Get creator details
    creator_response = supabase.table("users").select("*").eq("user_id", meeting["created_by"]).execute()
    
    creator = creator_response.data[0] if creator_response.data else None
    
    return {
        "meeting_id": str(meeting["meeting_id"]),
        "project_id": str(meeting["project_id"]),
        "title": meeting["title"],
        "description": meeting["description"],
        "scheduled_at": meeting["scheduled_at"],
        "meeting_status": meeting["meeting_status"],
        "created_at": meeting["created_at"],
        "agenda_generated": meeting["agenda_generated"],
        "manual_meeting_link": meeting["manual_meeting_link"],
        "bot_id": meeting["bot_id"],  # Include bot ID in response
        "creator": {
            "user_id": str(creator["user_id"]),
            "first_name": creator["first_name"],
            "last_name": creator["last_name"],
            "email": creator["email"]
        } if creator else None,
        "participants": [{
            "email": p["email"],
            "role": p["role"],
            "status": p["status"],
            "joined_at": p["joined_at"]
        } for p in participants],
        "meeting_links": [{
            "platform": link["platform"],
            "link_url": link["link_url"],
            "created_at": link["created_at"]
        } for link in meeting_links],
        "summaries": [{
            "summary_id": str(s["summary_id"]),
            "content": s["content"],
            "ai_topic": s["ai_topic"],
            "created_at": s["created_at"]
        } for s in summaries],
        "agendas": [{
            "agenda_id": str(a["agenda_id"]),
            "agenda_items": a["agenda_items"],
            "generated_by_ai": a["generated_by_ai"],
            "created_at": a["created_at"]
        } for a in agendas]
    }


"""
[PUT]
/meetings/{meeting_id}/bot:
Update the bot_id for an existing meeting.

Args:
    meeting_id (uuid.UUID): Meeting ID.
    bot_update (MeetingBotUpdateRequest): Bot update data containing bot_id.
    supabase (Client): Supabase client (injected).

Returns:
    dict: Status message and updated meeting info.
"""
@router.put("/{meeting_id}/bot")
def update_meeting_bot_id(
    meeting_id: uuid.UUID, 
    bot_update: MeetingBotUpdateRequest, 
    supabase: Client = Depends(get_supabase)
):
    try:
        # Verify meeting exists
        meeting_response = supabase.table("meetings").select("*").eq("meeting_id", str(meeting_id)).execute()
        if not meeting_response.data:
            raise HTTPException(status_code=404, detail="Meeting not found")
        
        # Update the meeting with the bot_id
        update_data = {"bot_id": bot_update.bot_id}
        update_response = supabase.table("meetings") \
            .update(update_data) \
            .eq("meeting_id", str(meeting_id)) \
            .execute()
        
        if not update_response.data:
            raise HTTPException(status_code=500, detail="Failed to update meeting bot_id")
        
        return {
            "status": "success", 
            "message": "Meeting bot_id updated successfully",
            "meeting_id": str(meeting_id),
            "bot_id": bot_update.bot_id
        }
        
    except Exception as e:
        print(f"Error updating meeting bot_id: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


"""
[GET]
/meetings/{meeting_id}/bot:
Get the bot_id for a specific meeting.

Args:
    meeting_id (uuid.UUID): Meeting ID.
    supabase (Client): Supabase client (injected).

Returns:
    dict: Bot ID information for the meeting.
"""
@router.get("/{meeting_id}/bot")
def get_meeting_bot_id(meeting_id: uuid.UUID, supabase: Client = Depends(get_supabase)):
    try:
        # Get meeting details
        meeting_response = supabase.table("meetings") \
            .select("meeting_id, title, bot_id") \
            .eq("meeting_id", str(meeting_id)) \
            .execute()
        
        if not meeting_response.data:
            raise HTTPException(status_code=404, detail="Meeting not found")
        
        meeting = meeting_response.data[0]
        
        return {
            "meeting_id": str(meeting["meeting_id"]),
            "title": meeting["title"],
            "bot_id": meeting["bot_id"]
        }
        
    except Exception as e:
        print(f"Error getting meeting bot_id: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


"""
[GET]
/meetings/{meeting_id}/transcript:
Get the transcript for a specific meeting.

Args:
    meeting_id (uuid.UUID): Meeting ID.
    supabase (Client): Supabase client (injected).

Returns:
    dict: Meeting transcript data with processed entries.
"""
@router.get("/{meeting_id}/transcript")
def get_meeting_transcript(meeting_id: uuid.UUID, supabase: Client = Depends(get_supabase)):
    try:
        # Verify meeting exists
        meeting_response = supabase.table("meetings").select("*").eq("meeting_id", str(meeting_id)).execute()
        if not meeting_response.data:
            raise HTTPException(status_code=404, detail="Meeting not found")
        
        meeting = meeting_response.data[0]
        
        # Get transcripts for the meeting
        transcript_response = supabase.table("meeting_transcripts") \
            .select("*") \
            .eq("meeting_id", str(meeting_id)) \
            .order("created_at", desc=False) \
            .execute()
        
        transcripts = transcript_response.data if transcript_response.data else []
        
        if not transcripts:
            return {
                "status": "not_found",
                "message": "No transcript data available for this meeting",
                "meeting_info": {
                    "meeting_id": str(meeting_id),
                    "title": meeting["title"],
                    "scheduled_at": meeting["scheduled_at"],
                    "meeting_status": meeting["meeting_status"]
                },
                "transcript": []
            }
        
        # Process transcript data into a readable format
        processed_transcript = []
        total_entries = 0
        
        for transcript_entry in transcripts:
            transcript_data = transcript_entry["transcript_data"]
            bot_id = transcript_entry.get("bot_id")
            created_at = transcript_entry["created_at"]
            
            # Handle different transcript data formats from Recall.ai
            if isinstance(transcript_data, dict):
                # Single transcript entry
                if "words" in transcript_data:
                    # Word-level transcript data
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
                        text = " ".join([word.get("text", "") for word in words if word.get("text")])
                        if text.strip():  # Only add non-empty text
                            processed_transcript.append({
                                "speaker": speaker,
                                "text": text.strip(),
                                "timestamp": timestamp,
                                "created_at": created_at,
                                "entry_type": "speech",
                                "word_count": len(words)
                            })
                            total_entries += 1
                elif "text" in transcript_data:
                    # Direct text format
                    text = transcript_data.get("text", "").strip()
                    if text:
                        processed_transcript.append({
                            "speaker": transcript_data.get("speaker", "Unknown"),
                            "text": text,
                            "timestamp": transcript_data.get("timestamp", "00:00"),
                            "created_at": created_at,
                            "entry_type": "speech"
                        })
                        total_entries += 1
                        
            elif isinstance(transcript_data, list):
                # Multiple transcript entries in one record
                for entry in transcript_data:
                    if isinstance(entry, dict):
                        text = entry.get("text", "").strip()
                        if text:
                            processed_transcript.append({
                                "speaker": entry.get("speaker", "Unknown"),
                                "text": text,
                                "timestamp": entry.get("timestamp", "00:00"),
                                "created_at": created_at,
                                "entry_type": "speech"
                            })
                            total_entries += 1
        
        # Sort by timestamp if available, otherwise by created_at
        processed_transcript.sort(key=lambda x: (x["created_at"], x["timestamp"]))
        
        return {
            "status": "success",
            "message": f"Retrieved {total_entries} transcript entries",
            "meeting_info": {
                "meeting_id": str(meeting_id),
                "title": meeting["title"],
                "scheduled_at": meeting["scheduled_at"],
                "meeting_status": meeting["meeting_status"],
                "bot_id": meeting.get("bot_id")
            },
            "transcript": processed_transcript,
            "metadata": {
                "total_entries": total_entries,
                "transcript_sources": len(transcripts),
                "has_transcript": total_entries > 0
            }
        }
        
    except Exception as e:
        print(f"Error getting meeting transcript: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


"""
[GET]
/meetings/{meeting_id}/transcript/raw:
Get the raw transcript data for a specific meeting (for debugging/advanced use).

Args:
    meeting_id (uuid.UUID): Meeting ID.
    supabase (Client): Supabase client (injected).

Returns:
    dict: Raw meeting transcript data as stored in the database.
"""
@router.get("/{meeting_id}/transcript/raw")
def get_meeting_transcript_raw(meeting_id: uuid.UUID, supabase: Client = Depends(get_supabase)):
    try:
        # Verify meeting exists
        meeting_response = supabase.table("meetings").select("*").eq("meeting_id", str(meeting_id)).execute()
        if not meeting_response.data:
            raise HTTPException(status_code=404, detail="Meeting not found")
        
        meeting = meeting_response.data[0]
        
        # Get raw transcripts for the meeting
        transcript_response = supabase.table("meeting_transcripts") \
            .select("*") \
            .eq("meeting_id", str(meeting_id)) \
            .order("created_at", desc=False) \
            .execute()
        
        transcripts = transcript_response.data if transcript_response.data else []
        
        return {
            "status": "success",
            "meeting_info": {
                "meeting_id": str(meeting_id),
                "title": meeting["title"],
                "scheduled_at": meeting["scheduled_at"],
                "meeting_status": meeting["meeting_status"],
                "bot_id": meeting.get("bot_id")
            },
            "raw_transcripts": transcripts,
            "metadata": {
                "transcript_count": len(transcripts),
                "has_transcript": len(transcripts) > 0
            }
        }
        
    except Exception as e:
        print(f"Error getting raw meeting transcript: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

