# Recall.ai Integration

This document describes the Recall.ai integration for automated meeting recording, transcription, and AI-powered summarization.

## Overview

The Recall.ai integration allows you to:
- Automatically join Zoom meetings with a bot
- Record and transcribe meetings in real-time
- Generate AI-powered summaries of meetings
- Store all data in your Supabase database

## Configuration

Add the following environment variables to your `.env` file:

```env
# Recall.ai Configuration
RECALL_API_TOKEN=your_recall_api_token_here
RECALL_BOT_NAME=Momentum Notetaker
RECALL_WEBHOOK_SECRET=your_webhook_secret_here

# AI Configuration (for summarization)
GEMINI_API_KEY=your_gemini_api_key_here
```

## API Endpoints

### Recall.ai Management

#### Start Recording
```http
POST /recall/start-recording
```

Start a Recall.ai bot recording for a meeting.

**Query Parameters:**
- `meeting_url` (string): The meeting URL to join
- `meeting_id` (string): ID of the meeting
- `user_id` (string): ID of the user starting the recording
- `webhook_url` (string): URL for receiving transcription webhooks

**Response:**
```json
{
  "botId": "bot_123456",
  "status": "started"
}
```

#### Stop Recording
```http
POST /recall/stop-recording
```

Stop a Recall.ai bot recording.

**Query Parameters:**
- `bot_id` (string): ID of the bot to stop
- `meeting_id` (string): ID of the meeting

**Response:**
```json
{
  "status": "stopped"
}
```

#### Get Recording State
```http
GET /recall/recording-state
```

Get the current state of a Recall.ai bot recording.

**Query Parameters:**
- `bot_id` (string): ID of the bot to check

**Response:**
```json
{
  "state": "in_meeting",
  "transcript": [...]
}
```

#### Handle Transcription Webhook
```http
POST /recall/transcription
```

Handle transcription webhook from Recall.ai.

**Query Parameters:**
- `secret` (string): Webhook secret for verification

**Request Body:** (from Recall.ai)
```json
{
  "event": "transcript.data",
  "data": {
    "bot": {
      "id": "bot_123456"
    },
    "data": {
      "participant": {
        "name": "John Doe"
      },
      "words": [...],
      "is_final": true
    }
  }
}
```

#### Generate Summary
```http
POST /recall/summarize
```

Generate a summary of the meeting transcript using AI.

**Query Parameters:**
- `bot_id` (string): ID of the bot whose transcript to summarize
- `prompt_type` (string): Type of summary (general_summary, action_items, decisions, next_steps, key_takeaways)

**Response:**
```json
{
  "summary": "The meeting covered several key topics..."
}
```

#### Get Meeting Sessions
```http
GET /recall/sessions/{meeting_id}
```

Get all recording sessions for a meeting.

**Response:**
```json
{
  "sessions": [
    {
      "session_id": "uuid",
      "meeting_id": "uuid",
      "user_id": "uuid",
      "bot_id": "bot_123456",
      "status": "active",
      "created_at": "2024-01-01T00:00:00Z"
    }
  ]
}
```

### Zoom Integration

#### Generate Meeting Link with Recording
```http
POST /meeting-platform/zoom/generate-link-with-recording/{meeting_id}
```

Generate a Zoom meeting link and automatically start Recall.ai recording.

**Query Parameters:**
- `user_id` (string): ID of the user generating the link
- `webhook_url` (string): URL for receiving transcription webhooks

**Response:**
```json
{
  "status": "success",
  "meeting_link": "https://zoom.us/j/123456789",
  "recording": {
    "botId": "bot_123456",
    "status": "started"
  }
}
```

## Database Tables

The integration creates the following tables:

### recall_sessions
Stores active recording sessions.

```sql
CREATE TABLE recall_sessions (
  session_id UUID PRIMARY KEY,
  meeting_id UUID REFERENCES meetings(meeting_id),
  user_id UUID REFERENCES users(user_id),
  bot_id TEXT UNIQUE NOT NULL,
  status TEXT CHECK (status IN ('active', 'stopped', 'error')),
  created_at TIMESTAMP DEFAULT NOW(),
  ended_at TIMESTAMP
);
```

### meeting_transcripts
Stores raw transcript data from Recall.ai.

```sql
CREATE TABLE meeting_transcripts (
  transcript_id UUID PRIMARY KEY,
  bot_id TEXT NOT NULL,
  transcript_data JSONB NOT NULL,
  created_at TIMESTAMP DEFAULT NOW()
);
```

### meeting_summaries
Stores AI-generated meeting summaries.

```sql
CREATE TABLE meeting_summaries (
  summary_id UUID PRIMARY KEY,
  meeting_id UUID REFERENCES meetings(meeting_id),
  bot_id TEXT NOT NULL,
  summary_type TEXT CHECK (summary_type IN ('general_summary', 'action_items', 'decisions', 'next_steps', 'key_takeaways')),
  content TEXT NOT NULL,
  created_at TIMESTAMP DEFAULT NOW(),
  created_by UUID REFERENCES users(user_id)
);
```

## Usage Example

1. **Start a meeting with recording:**
   ```bash
   curl -X POST "http://localhost:8000/meeting-platform/zoom/generate-link-with-recording/meeting-uuid" \
     -H "Content-Type: application/json" \
     -d '{
       "user_id": "user-uuid",
       "webhook_url": "https://your-domain.com/recall/transcription"
     }'
   ```

2. **Check recording status:**
   ```bash
   curl "http://localhost:8000/recall/recording-state?bot_id=bot_123456"
   ```

3. **Generate a summary:**
   ```bash
   curl -X POST "http://localhost:8000/recall/summarize" \
     -H "Content-Type: application/json" \
     -d '{
       "bot_id": "bot_123456",
       "prompt_type": "action_items"
     }'
   ```

4. **Stop recording:**
   ```bash
   curl -X POST "http://localhost:8000/recall/stop-recording" \
     -H "Content-Type: application/json" \
     -d '{
       "bot_id": "bot_123456",
       "meeting_id": "meeting-uuid"
     }'
   ```

## Webhook Setup

To receive transcription data from Recall.ai, you need to:

1. Set up a public endpoint at `/recall/transcription`
2. Configure the webhook URL in your Recall.ai bot creation
3. Ensure the webhook secret matches your `RECALL_WEBHOOK_SECRET`

The webhook will receive real-time transcription data as participants speak during the meeting.

## Security

- All webhook requests are verified using the `RECALL_WEBHOOK_SECRET`
- Bot sessions are tied to specific users and meetings
- Transcript data is stored securely in your Supabase database

## Error Handling

The integration includes comprehensive error handling:
- Invalid meeting/user IDs return 404 errors
- Missing API tokens return 401 errors
- Recall.ai API errors are logged and returned as 500 errors
- Webhook verification failures return 401 errors

## Troubleshooting

1. **Bot not joining meeting:** Check that the meeting URL is valid and accessible
2. **No transcriptions:** Verify webhook URL is publicly accessible and secret matches
3. **Summary generation fails:** Ensure `GEMINI_API_KEY` is set correctly
4. **Database errors:** Check that all required tables exist in your Supabase database 