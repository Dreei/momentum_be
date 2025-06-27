import os
from fastapi import APIRouter, Depends, HTTPException
from database.base import get_supabase
from supabase import Client
import uuid
from typing import List, Dict, Any
from pydantic import BaseModel
import google.generativeai as genai
import re

router = APIRouter()

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

class AgendaStore(BaseModel):
    agenda_items: List[str]
    generated_by_ai: bool 


"""
[POST]
/agenda/store-agenda:
Stores multiple agenda items tied to a meeting_id.
Supports AI-generated, manual, or versioned agendas.

Args:
    meeting_id: uuid.UUID
    agenda_data: {
        agenda_items: List[str]
        generated_by_ai: bool 
    }

Returns:
    dict: Status message.
"""
@router.post("/store-agenda/{meeting_id}")
def store_agenda(meeting_id: uuid.UUID, agenda_data: AgendaStore, supabase: Client = Depends(get_supabase)):
    # Verify meeting exists
    meeting_response = supabase.table("meetings") \
        .select("*") \
        .eq("meeting_id", str(meeting_id)) \
        .execute()
    
    if not meeting_response.data:
        raise HTTPException(status_code=404, detail="Meeting not found")

    # Create a new agenda record
    agenda_data = {
        "meeting_id": str(meeting_id),
        "agenda_items": agenda_data.agenda_items,
        "generated_by_ai": agenda_data.generated_by_ai
    }
    supabase.table("agendas").insert(agenda_data).execute()

    # Update meeting status to indicate agenda is saved
    supabase.table("meetings") \
        .update({"agenda_generated": True}) \
        .eq("meeting_id", str(meeting_id)) \
        .execute()

    return {"status": "success", "message": "Agenda stored successfully"}


class GenerateContext(BaseModel):
    title: str
    description: str
    generate_via_summary: bool

"""
[POST]
/agenda/generate:
Generates an agenda based on previous meeting summaries or provided title and description.
Args:
    context:{title: str
    description: str
    project_id: uuid.UUID}
    db (Session): SQLAlchemy session (injected).

Returns:
    dict: Generated agenda as a list of items.
"""

@router.post("/generate-agenda/{project_id}")
def generate_agenda(project_id: uuid.UUID, agenda_context: GenerateContext, supabase: Client = Depends(get_supabase)):
    print(f"Generating agenda for context: {agenda_context}")
    
    if agenda_context.generate_via_summary:
        # Fetch previous meeting summaries for the project
        summaries_response = supabase.table("summaries") \
            .select("*, meetings!inner(*)") \
            .eq("meetings.project_id", str(project_id)) \
            .order("created_at", desc=True) \
            .limit(3) \
            .execute()
        
        summaries = summaries_response.data

        if summaries:
            # Use Gemini Flash to generate a summary from the last 3 summaries
            context = "\n\n".join([s["content"] for s in summaries])
            prompt = (
                "Given the past meeting summaries, generate a detailed agenda as a list of items for the meeting. "
                f"Return only the agenda items as a numbered or bulleted list.\n\n"
                f"{context}\n\nSummary:"
            )
            model = genai.GenerativeModel("gemini-1.5-flash")
            response = model.generate_content(prompt)
            agenda_text = response.text.strip()
            # Clean and split agenda into list items
            agenda = []
            for line in agenda_text.splitlines():
                # More robust regex to remove any leading non-word characters (like *, -) or numbers followed by a dot
                cleaned_line = re.sub(r"^\W*(\d*\.)?\s*", "", line.strip()).strip()
                if cleaned_line:
                    agenda.append(cleaned_line)
            return {"agenda": agenda}

    # No context or no summaries, use Gemini Flash to generate an agenda from title and description
    prompt = (
        f"Given the following meeting title and description, generate 5 detailed agenda as a list of items for the meeting. "
        f"Return only the agenda items as a numbered or bulleted list.\n\n"
        f"Title: {agenda_context.title}\nDescription: {agenda_context.description}\n\nAgenda:"
    )
    model = genai.GenerativeModel("gemini-1.5-flash")
    response = model.generate_content(prompt)
    agenda_text = response.text.strip()
    # Clean and split agenda into list items
    agenda = []
    for line in agenda_text.splitlines():
        # More robust regex to remove any leading non-word characters (like *, -) or numbers followed by a dot
        cleaned_line = re.sub(r"^\W*(\d*\.)?\s*", "", line.strip()).strip()
        if cleaned_line:
            agenda.append(cleaned_line)
    return {"agenda": agenda}

