import json
import requests
import os
from typing import Dict, List, Any, Optional
from datetime import datetime
from core.config import GEMINI_API_KEY
from database.base import get_supabase
from supabase import Client
import google.generativeai as genai
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))


class AISummaryPipeline:
    """AI-powered meeting summary pipeline that processes transcripts and generates structured summaries"""
    
    def __init__(self):
        self.api_key = GEMINI_API_KEY
        self.base_url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent"
        
    def _call_gemini_api(self, prompt: str) -> str:
        """Make a call to the Gemini API"""
        try:
            if not self.api_key:
                raise Exception("Gemini API key not configured")
            
            # response = requests.post(
            #     f"{self.base_url}?key={self.api_key}",
            #     json={
            #         "contents": [{
            #             "parts": [{"text": prompt}]
            #         }]
            #     },
            #     timeout=30
            # )
            model = genai.GenerativeModel("gemini-1.5-flash")
            response = model.generate_content(prompt)
            
            # The response from Gemini SDK is an object, not a requests.Response
            # Extract the text from the response structure
            if hasattr(response, "text"):
                return response.text
            elif hasattr(response, "candidates") and response.candidates:
                # For some SDK versions, candidates may be present
                return response.candidates[0].content.parts[0].text
            else:
                raise Exception("Unexpected Gemini API response format")
            
        except Exception as e:
            print(f"Error calling Gemini API: {str(e)}")
            raise
    
    def _extract_structured_summary(self, transcript_text: str) -> Dict[str, Any]:
        """Extract structured summary from transcript using AI"""
        
        prompt = f"""
You are an expert meeting analyst. Analyze the following meeting transcript and extract structured information.

TRANSCRIPT:
{transcript_text}

Please provide a structured analysis in the following JSON format:

{{
    "overview": "Brief overview of the meeting",
    "action_items": [
        {{
            "description": "Action item description",
            "owner": "Person responsible",
            "due_date": "Due date if mentioned (YYYY-MM-DD format)",
            "priority": "high/medium/low",
            "status": "pending"
        }}
    ],
    "key_decisions": [
        {{
            "decision": "Decision made",
            "context": "Context around the decision",
            "impact": "Impact of the decision"
        }}
    ],
    "key_takeaways": [
        "Key takeaway 1",
        "Key takeaway 2"
    ],
    "discussion_points": [
        {{
            "topic": "Discussion topic",
            "summary": "Summary of discussion",
            "participants": ["Participant names"]
        }}
    ],
    "jargon_clarifications": [
        {{
            "term": "Jargon or acronym",
            "clarification": "Explanation of the term"
        }}
    ],
    "themes": [
        "Theme 1",
        "Theme 2"
    ],
    "context_group": "Suggested context group identifier (e.g., 'product-development', 'sales-review', 'team-sync')"
}}

Return ONLY the JSON object, no additional text.
"""
        
        try:
            response = self._call_gemini_api(prompt)
            
            # Clean the response to extract JSON
            response = response.strip()
            if response.startswith("```json"):
                response = response[7:]
            if response.endswith("```"):
                response = response[:-3]
            
            # Parse JSON
            structured_data = json.loads(response.strip())
            print(structured_data)
            return structured_data
            
        except Exception as e:
            print(f"Error extracting structured summary: {str(e)}")
            # Return fallback structure
            return {
                "overview": "Error processing transcript",
                "action_items": [],
                "key_decisions": [],
                "key_takeaways": [],
                "discussion_points": [],
                "jargon_clarifications": [],
                "themes": [],
                "context_group": "general"
            }
    
    def _process_transcript_data(self, transcripts: List[Dict[str, Any]]) -> str:
        """Process raw transcript data into readable text"""
        all_words = []
        for utterance in transcripts:
            # Handle both utterance-level and word-level speaker info
            speaker_name = None
            if 'participant' in utterance["transcript_data"] and utterance["transcript_data"]["participant"]:
                speaker_name = utterance["transcript_data"]["participant"]['name']
            # If the utterance itself is a word (flat list)
            if 'words' in utterance["transcript_data"] and isinstance(utterance["transcript_data"]["words"], list) and utterance["transcript_data"]["words"]:
                for word in utterance["transcript_data"]["words"]:
                    
                    all_words.append({
                        "text": word["text"],
                        "speaker": speaker_name,
                        "timestamp": word["start_timestamp"]["relative"] if "start_timestamp" in word else utterance["transcript_data"].get("start_timestamp", {}).get("relative", 0),
                        "is_final": word["is_final"] if "is_final" in word else utterance.get("is_final", False),
                    })
            # If the utterance itself is a word (no 'words' key)
            
        # Sort by timestamp for chronological order
        all_words.sort(key=lambda x: x["timestamp"])

        # Use final words if available, otherwise use all words
        final_words = [word for word in all_words if word["is_final"] is True]
        words_to_process = final_words if final_words else all_words

        # Group consecutive words from same speaker
        grouped_transcript = []
        current_speaker = None
        for word in words_to_process:
            if word["speaker"] != current_speaker:
                current_speaker = word["speaker"]
                grouped_transcript.append({
                    "speaker": current_speaker,
                    "words": [word["text"]],
                })
            else:
                grouped_transcript[-1]["words"].append(word["text"])

        # Format for AI processing
        transcript_text = "\n".join([
            f"{item['speaker']}: {' '.join(item['words'])}"
            for item in grouped_transcript
        ])
        return transcript_text
    
    async def process_meeting_summary(
        self, 
        meeting_id: str, 
        bot_id: str, 
        user_id: str,
        supabase: Client = None
    ) -> Dict[str, Any]:
        """Process meeting transcript and generate structured summary"""
        
        if supabase is None:
            supabase = get_supabase()
        
        try:
            # Get transcripts from database
            transcript_response = supabase.table("meeting_transcripts") \
                .select("*") \
                .eq("bot_id", bot_id) \
                .order("created_at", desc=False) \
                .execute()
            
            transcripts = transcript_response.data if transcript_response.data else []
            
            if not transcripts:
                raise Exception("No transcript data available")
            
            # Process transcript data
            transcript_text = self._process_transcript_data(transcripts)
            
            if not transcript_text.strip():
                raise Exception("No meaningful transcript content found")
            
            # Extract structured summary
            structured_summary = self._extract_structured_summary(transcript_text)
            
            # Save structured summary to database
            summary_data = {
                "meeting_id": meeting_id,
                "bot_id": bot_id,
                "summary_type": "structured_summary",
                "content": json.dumps(structured_summary),
                "created_at": datetime.utcnow().isoformat(),
                "created_by": user_id,
                "context_group": structured_summary.get("context_group", "general")
            }
            
            # Insert into meeting_summaries table
            summary_response = supabase.table("meeting_summaries").insert(summary_data).execute()
            
            # Save individual components to separate tables
            await self._save_summary_components(meeting_id, structured_summary, supabase)
            
            return {
                "status": "success",
                "summary_id": summary_response.data[0]["summary_id"] if summary_response.data else None,
                "structured_summary": structured_summary,
                "transcript_length": len(transcript_text),
                "processed_at": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            print(f"Error processing meeting summary: {str(e)}")
            return {
                "status": "error",
                "error": str(e),
                "processed_at": datetime.utcnow().isoformat()
            }
    
    async def _save_summary_components(
        self, 
        meeting_id: str, 
        structured_summary: Dict[str, Any], 
        supabase: Client
    ):
        """Save individual summary components to separate tables"""
        
        try:
            # Save action items
            for action_item in structured_summary.get("action_items", []):
                action_data = {
                    "meeting_id": meeting_id,
                    "description": action_item.get("description", ""),
                    "owner": action_item.get("owner", ""),
                    "due_date": action_item.get("due_date"),
                    "priority": action_item.get("priority", "medium"),
                    "status": action_item.get("status", "pending"),
                    "created_at": datetime.utcnow().isoformat()
                }
                supabase.table("action_items").insert(action_data).execute()
            
            # Save key decisions
            for decision in structured_summary.get("key_decisions", []):
                decision_data = {
                    "meeting_id": meeting_id,
                    "decision": decision.get("decision", ""),
                    "context": decision.get("context", ""),
                    "impact": decision.get("impact", ""),
                    "created_at": datetime.utcnow().isoformat()
                }
                supabase.table("meeting_decisions").insert(decision_data).execute()
            
            # Save discussion points
            for discussion in structured_summary.get("discussion_points", []):
                discussion_data = {
                    "meeting_id": meeting_id,
                    "topic": discussion.get("topic", ""),
                    "summary": discussion.get("summary", ""),
                    "participants": json.dumps(discussion.get("participants", [])),
                    "created_at": datetime.utcnow().isoformat()
                }
                supabase.table("meeting_discussions").insert(discussion_data).execute()
            
            # Save jargon clarifications
            for jargon in structured_summary.get("jargon_clarifications", []):
                jargon_data = {
                    "meeting_id": meeting_id,
                    "term": jargon.get("term", ""),
                    "clarification": jargon.get("clarification", ""),
                    "created_at": datetime.utcnow().isoformat()
                }
                supabase.table("meeting_jargon").insert(jargon_data).execute()
            
            # Save themes
            themes_data = {
                "meeting_id": meeting_id,
                "themes": json.dumps(structured_summary.get("themes", [])),
                "context_group": structured_summary.get("context_group", "general"),
                "created_at": datetime.utcnow().isoformat()
            }
            supabase.table("meeting_themes").insert(themes_data).execute()
            
        except Exception as e:
            print(f"Error saving summary components: {str(e)}")
            raise
    
    async def get_meeting_summary(self, meeting_id: str, supabase: Client = None) -> Dict[str, Any]:
        """Retrieve structured summary for a meeting"""
        
        if supabase is None:
            supabase = get_supabase()
        
        try:
            # Get main summary
            summary_response = supabase.table("meeting_summaries") \
                .select("*") \
                .eq("meeting_id", meeting_id) \
                .eq("summary_type", "structured_summary") \
                .order("created_at", desc=True) \
                .limit(1) \
                .execute()
            
            if not summary_response.data:
                return {"status": "not_found", "message": "No summary found for this meeting"}
            
            summary = summary_response.data[0]
            structured_summary = json.loads(summary["content"])
            
            # Get additional components
            action_items_response = supabase.table("action_items") \
                .select("*") \
                .eq("meeting_id", meeting_id) \
                .execute()
            
            decisions_response = supabase.table("meeting_decisions") \
                .select("*") \
                .eq("meeting_id", meeting_id) \
                .execute()
            
            discussions_response = supabase.table("meeting_discussions") \
                .select("*") \
                .eq("meeting_id", meeting_id) \
                .execute()
            
            # Return structure that matches frontend's StructuredSummaryFromAPI interface
            return {
                "status": "success",
                "summary": {
                    "summary_id": summary["summary_id"],
                    "meeting_id": summary["meeting_id"],
                    "summary_type": summary["summary_type"],
                    "content": structured_summary,
                    "created_at": summary["created_at"],
                    "created_by": summary["created_by"]
                },
                "action_items": action_items_response.data if action_items_response.data else [],
                "decisions": decisions_response.data if decisions_response.data else [],
                "discussions": discussions_response.data if discussions_response.data else [],
                "created_at": summary["created_at"]
            }
            
        except Exception as e:
            print(f"Error retrieving meeting summary: {str(e)}")
            return {"status": "error", "error": str(e)}

# Create global instance
ai_summary_pipeline = AISummaryPipeline() 