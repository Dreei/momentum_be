
#!/usr/bin/env python3
"""
Test script for Recall.ai integration
"""

import requests
import json
import os
from datetime import datetime

# Configuration
BASE_URL = "http://localhost:8000"
TEST_MEETING_ID = "test-meeting-uuid"
TEST_USER_ID = "test-user-uuid"
WEBHOOK_URL = "https://your-domain.com/recall/transcription"

def test_recall_endpoints():
    """Test all Recall.ai endpoints"""
    
    print("🧪 Testing Recall.ai Integration")
    print("=" * 50)
    
    # Test 1: Start recording
    print("\n1. Testing start recording...")
    try:
        response = requests.post(
            f"{BASE_URL}/recall/start-recording",
            params={
                "meeting_url": "https://zoom.us/j/test123",
                "meeting_id": TEST_MEETING_ID,
                "user_id": TEST_USER_ID,
                "webhook_url": WEBHOOK_URL
            }
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Start recording successful: {data}")
            bot_id = data.get("botId")
        else:
            print(f"❌ Start recording failed: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Start recording error: {str(e)}")
        return False
    
    # Test 2: Get recording state
    print("\n2. Testing get recording state...")
    try:
        response = requests.get(
            f"{BASE_URL}/recall/recording-state",
            params={"bot_id": bot_id}
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Get recording state successful: {data}")
        else:
            print(f"❌ Get recording state failed: {response.status_code} - {response.text}")
            
    except Exception as e:
        print(f"❌ Get recording state error: {str(e)}")
    
    # Test 3: Generate summary
    print("\n3. Testing generate summary...")
    try:
        response = requests.post(
            f"{BASE_URL}/recall/summarize",
            params={
                "bot_id": bot_id,
                "prompt_type": "general_summary"
            }
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Generate summary successful: {data}")
        else:
            print(f"❌ Generate summary failed: {response.status_code} - {response.text}")
            
    except Exception as e:
        print(f"❌ Generate summary error: {str(e)}")
    
    # Test 4: Get meeting sessions
    print("\n4. Testing get meeting sessions...")
    try:
        response = requests.get(
            f"{BASE_URL}/recall/sessions/{TEST_MEETING_ID}"
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Get meeting sessions successful: {data}")
        else:
            print(f"❌ Get meeting sessions failed: {response.status_code} - {response.text}")
            
    except Exception as e:
        print(f"❌ Get meeting sessions error: {str(e)}")
    
    # Test 5: Stop recording
    print("\n5. Testing stop recording...")
    try:
        response = requests.post(
            f"{BASE_URL}/recall/stop-recording",
            params={
                "bot_id": bot_id,
                "meeting_id": TEST_MEETING_ID
            }
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Stop recording successful: {data}")
        else:
            print(f"❌ Stop recording failed: {response.status_code} - {response.text}")
            
    except Exception as e:
        print(f"❌ Stop recording error: {str(e)}")
    
    # Test 6: Zoom integration
    print("\n6. Testing Zoom integration...")
    try:
        response = requests.post(
            f"{BASE_URL}/meeting-platform/zoom/generate-link-with-recording/{TEST_MEETING_ID}",
            params={
                "user_id": TEST_USER_ID,
                "webhook_url": WEBHOOK_URL
            }
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Zoom integration successful: {data}")
        else:
            print(f"❌ Zoom integration failed: {response.status_code} - {response.text}")
            
    except Exception as e:
        print(f"❌ Zoom integration error: {str(e)}")
    
    print("\n" + "=" * 50)
    print("🏁 Testing completed!")
    
    return True

def test_webhook_simulation():
    """Simulate a webhook call from Recall.ai"""
    
    print("\n🧪 Testing Webhook Simulation")
    print("=" * 50)
    
    # Simulate webhook data
    webhook_data = {
        "event": "transcript.data",
        "data": {
            "bot": {
                "id": "test_bot_123"
            },
            "data": {
                "participant": {
                    "name": "Test User"
                },
                "words": [
                    {
                        "text": "Hello",
                        "start_timestamp": {"relative": 0.0}
                    },
                    {
                        "text": "world",
                        "start_timestamp": {"relative": 0.5}
                    }
                ],
                "is_final": True
            }
        }
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/recall/transcription",
            params={"secret": "test_secret"},
            json=webhook_data
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Webhook simulation successful: {data}")
        else:
            print(f"❌ Webhook simulation failed: {response.status_code} - {response.text}")
            
    except Exception as e:
        print(f"❌ Webhook simulation error: {str(e)}")

def check_environment():
    """Check if required environment variables are set"""
    
    print("🔧 Checking Environment Configuration")
    print("=" * 50)
    
    required_vars = [
        "RECALL_API_TOKEN",
        "RECALL_BOT_NAME", 
        "RECALL_WEBHOOK_SECRET",
        "GEMINI_API_KEY"
    ]
    
    missing_vars = []
    
    for var in required_vars:
        value = os.getenv(var)
        if value:
            print(f"✅ {var}: {'*' * len(value)} (set)")
        else:
            print(f"❌ {var}: Not set")
            missing_vars.append(var)
    
    if missing_vars:
        print(f"\n⚠️  Missing environment variables: {', '.join(missing_vars)}")
        print("Please set these in your .env file")
        return False
    else:
        print("\n✅ All required environment variables are set")
        return True

if __name__ == "__main__":
    print("🚀 Recall.ai Integration Test Suite")
    print("=" * 50)
    
    # Check environment first
    if not check_environment():
        print("\n❌ Environment check failed. Please configure your environment variables.")
        exit(1)
    
    # Test endpoints
    test_recall_endpoints()
    
    # Test webhook simulation
    test_webhook_simulation()
    
    print("\n📝 Test Summary:")
    print("- Environment variables: Checked")
    print("- API endpoints: Tested")
    print("- Webhook simulation: Tested")
    print("\n💡 Note: Some tests may fail if the server is not running or if")
    print("   the database tables don't exist yet.") 