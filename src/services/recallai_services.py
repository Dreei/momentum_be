import requests
import json
import hmac
import hashlib
import re
from typing import Dict, List, Optional, Any
from datetime import datetime
import uuid
from core.config import RECALL_API_TOKEN, RECALL_BOT_NAME, RECALL_WEBHOOK_SECRET, RECALL_WEBHOOK_URL, RECALL_BASE_URL, GEMINI_API_KEY
from database.base import get_supabase
from supabase import Client

class RecallAIService:
    """Service for managing Recall.ai bots and transcriptions"""
    
    def __init__(self):
        self.base_url = RECALL_BASE_URL
        self.api_token = RECALL_API_TOKEN
        self.bot_name = RECALL_BOT_NAME
        self.webhook_secret = RECALL_WEBHOOK_SECRET
        self.webhook_url = RECALL_WEBHOOK_URL
        
    def _get_headers(self) -> Dict[str, str]:
        """Get headers for Recall.ai API requests"""
        return {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'Authorization': f'Token {self.api_token}'
        }
    
    async def recall_fetch(self, path: str, options: Dict[str, Any] = None) -> Dict[str, Any]:
        """Make a request to the Recall.ai API"""
        if options is None:
            options = {}
            
        url = f"{self.base_url}{path}"
        
        # Merge headers
        headers = self._get_headers()
        if 'headers' in options:
            headers.update(options['headers'])
        
        # Prepare request
        request_options = {
            'headers': headers,
            **options
        }
        
        # Remove headers from options to avoid duplication
        if 'headers' in request_options:
            del request_options['headers']
        
        response = requests.request(
            method=request_options.get('method', 'GET'),
            url=url,
            headers=headers,
            json=request_options.get('json'),
            data=request_options.get('data')
        )
        
        if response.status_code > 299:
            print(f"Recall API returned {response.url}: {response.status_code}")
            print(f"Response: {response.text}")
            raise Exception(f"Recall API Error: {response.status_code}")
        
        return response.json()
    
    async def start_recording(self, meeting_url: str, meeting_id: str, user_id: str, webhook_url: str) -> Dict[str, Any]:
        """Start a Recall.ai bot recording for a meeting"""
        try:
            bot_data = {
                "bot_name": f"{self.bot_name}",
                "meeting_url": meeting_url,
                "recording_config": {
                    "realtime_endpoints": [
                        {
                            "type": "webhook",
                            "url": f"{self.webhook_url}?secret={self.webhook_secret}",
                            "events": [
                                "transcript.partial_data",
                                "transcript.data",
                                "participant_events.chat_message",
                            ],
                        },
                    ],
                    "transcript": {
                        "provider": {
                            "gladia_v2_streaming": {}
                        },
                    },
                },
                "zoom": {
                    "request_recording_permission_on_host_join": True,
                    "require_recording_permission": True,
                },
            }
            
            bot = await self.recall_fetch('/api/v1/bot', {
                'method': 'POST',
                'json': bot_data
            })
            
            # Store bot session in database
            supabase = get_supabase()
            session_data = {
                "meeting_id": meeting_id,
                "user_id": user_id,
                "bot_id": bot["id"],
                "status": "active",
                "created_at": datetime.utcnow().isoformat()
            }
            
            supabase.table("recall_sessions").insert(session_data).execute()
            
            return {
                "botId": bot["id"],
                "status": "started"
            }
            
        except Exception as e:
            print(f"Error starting recording: {str(e)}")
            raise
    
    async def stop_recording(self, bot_id: str, meeting_id: str) -> Dict[str, Any]:
        """Stop a Recall.ai bot recording"""
        try:
            await self.recall_fetch(f'/api/v1/bot/{bot_id}/leave_call', {
                'method': 'POST'
            })
            
            # Update session status in database
            supabase = get_supabase()
            supabase.table("recall_sessions") \
                .update({"status": "stopped", "ended_at": datetime.utcnow().isoformat()}) \
                .eq("bot_id", bot_id) \
                .execute()
            
            return {"status": "stopped"}
            
        except Exception as e:
            print(f"Error stopping recording: {str(e)}")
            raise
    
    async def get_recording_state(self, bot_id: str) -> Dict[str, Any]:
        """Get the current state of a Recall.ai bot"""
        try:
            bot = await self.recall_fetch(f'/api/v1/bot/{bot_id}', {
                'method': 'GET'
            })
            
            latest_status = bot["status_changes"][-1]["code"] if bot["status_changes"] else "unknown"
            
            # Get transcripts from database
            supabase = get_supabase()
            transcript_response = supabase.table("meeting_transcripts") \
                .select("*") \
                .eq("bot_id", bot_id) \
                .order("created_at", desc=False) \
                .execute()
            
            transcripts = transcript_response.data if transcript_response.data else []
            
            return {
                "state": latest_status,
                "transcript": transcripts
            }
            
        except Exception as e:
            print(f"Error getting recording state: {str(e)}")
            raise
    
    def verify_webhook_signature(self, secret: str) -> bool:
        """Verify webhook signature for security"""
        return hmac.compare_digest(secret, self.webhook_secret)
    
    async def save_transcript(self, bot_id: str, transcript_data: Dict[str, Any], meeting_id: str = None) -> None:
        """Save transcript data to database"""
        try:
            supabase = get_supabase()
            
            # If meeting_id is not provided, try to find it from the bot_id
            if not meeting_id:
                session_response = supabase.table("recall_sessions") \
                    .select("meeting_id") \
                    .eq("bot_id", bot_id) \
                    .execute()
                
                if session_response.data:
                    meeting_id = session_response.data[0]["meeting_id"]
                else:
                    print(f"Warning: Could not find meeting_id for bot_id: {bot_id}")
                    # Still save the transcript without meeting_id for backward compatibility
                    meeting_id = None
            
            transcript_entry = {
                "bot_id": bot_id,
                "transcript_data": transcript_data,
                "created_at": datetime.utcnow().isoformat()
            }
            
            # Add meeting_id if available
            if meeting_id:
                transcript_entry["meeting_id"] = meeting_id
            
            supabase.table("meeting_transcripts").insert(transcript_entry).execute()
            
        except Exception as e:
            print(f"Error saving transcript: {str(e)}")
            raise

class AISummarizationService:
    """Service for AI-powered meeting summarization"""
    
    def __init__(self):
        self.api_key = GEMINI_API_KEY
        self.base_url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent"
    
    PROMPTS = {
        "_template": """You are a virtual assistant taking notes for a meeting. You are diligent, polite and slightly humorous at times.

Here is the transcript of the meeting, including the speaker's name:

<transcript>
{transcript}
</transcript>

Only answer the following question directly, do not add any additional comments or information.
{prompt}""",
        "general_summary": "Can you summarize the meeting? Please be concise.",
        "action_items": "What are the action items from the meeting?",
        "decisions": "What decisions were made in the meeting?",
        "next_steps": "What are the next steps?",
        "key_takeaways": "What are the key takeaways?",
    }
    
    async def summarize_transcript(self, transcripts: List[Dict[str, Any]], prompt_type: str = "general_summary") -> str:
        """Generate a summary of the transcript using AI"""
        try:
            if not self.api_key:
                raise Exception("Gemini API key not configured")
            
            # Process transcript chronologically using timestamps
            all_words = []
            
            for utterance in transcripts:
                speaker_name = utterance.get("participant", {}).get("name", "Unknown")
                words = utterance.get("words", [])
                
                for word in words:
                    all_words.append({
                        "text": word.get("text", ""),
                        "speaker": speaker_name,
                        "timestamp": word.get("start_timestamp", {}).get("relative", 0),
                        "is_final": utterance.get("is_final", False),
                    })
            
            # Sort by timestamp for chronological order
            all_words.sort(key=lambda x: x["timestamp"])
            
            # Handle case where is_final might be undefined
            # Use all words if no final words are available, otherwise use only final words
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
            
            # Check if we have any transcript data
            if not grouped_transcript:
                return "No transcript data available to summarize."
            
            # Format for AI prompt
            final_transcript = "\n".join([
                f"{item['speaker']}: {' '.join(item['words'])}"
                for item in grouped_transcript
            ])
            
            # Additional check for empty transcript
            if not final_transcript.strip():
                return "No meaningful transcript content found to summarize."
            
            prompt = self.PROMPTS.get(prompt_type, self.PROMPTS["general_summary"])
            complete_prompt = self.PROMPTS["_template"].format(
                transcript=final_transcript,
                prompt=prompt
            )
            
            # Call Gemini API
            response = requests.post(
                f"{self.base_url}?key={self.api_key}",
                json={
                    "contents": [{
                        "parts": [{"text": complete_prompt}]
                    }]
                }
            )
            
            if response.status_code != 200:
                raise Exception(f"Gemini API error: {response.status_code}")
            
            result = response.json()
            summary = result["candidates"][0]["content"]["parts"][0]["text"]
            
            # Clean up the response
            clean_summary = summary.replace(complete_prompt, "").strip()
            clean_summary = re.sub(r'<think>.*?</think>', '', clean_summary, flags=re.DOTALL | re.IGNORECASE).strip()
            clean_summary = re.sub(r'^\s+|\s+$', '', clean_summary, flags=re.MULTILINE)
            
            return clean_summary
            
        except Exception as e:
            print(f"Error summarizing transcript: {str(e)}")
            return f"Error generating summary: {str(e)}"

# Create service instances
recall_service = RecallAIService()
ai_summarization_service = AISummarizationService()
