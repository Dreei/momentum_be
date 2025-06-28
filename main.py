# main.py - Working with existing routers
import os
import sys
from pathlib import Path
import uvicorn
import traceback
import google.generativeai as genai
from contextlib import asynccontextmanager
from src.core.config import GEMINI_API_KEY
from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware

from schemas import ProjectInviteRequest, ProjectCreateRequest, SaveAgendaRequest, SaveLinkRequest, MeetingAgendaRequest
from crud import invite_users_to_project, generate_context_groups
from email_utils import EmailService, MeetingInviteData
from supabase import create_client, Client
import uuid
import asyncio  

# Import configuration
from src.core.config import settings, SUPABASE_URL, SUPABASE_KEY

# Add both src and routers directories to Python path
current_dir = Path(__file__).parent
src_dir = current_dir / "src"
routers_dir = current_dir / "src" / "routers"

# Add all possible paths
sys.path.insert(0, str(current_dir))
sys.path.insert(0, str(src_dir))
sys.path.insert(0, str(routers_dir))


# Import ML and AI libraries with error handling
ML_AVAILABLE = False
GEMINI_AVAILABLE = False

try:
    import sklearn
    ML_AVAILABLE = True
    print("✅ ML libraries (sklearn, numpy) loaded successfully")
except ImportError as e:
    print(f"⚠️  ML libraries not available: {e}")
    print("   Context grouping features will be disabled")

try:

    if GEMINI_API_KEY:
        genai.configure(api_key=GEMINI_API_KEY)
        GEMINI_AVAILABLE = True
        print("✅ Gemini AI library loaded successfully")
    else:
        print("⚠️  Gemini API key not configured")
        GEMINI_AVAILABLE = False
except ImportError as e:
    print(f"⚠️  Gemini AI library not available: {e}")
    print("   AI features will be disabled")
    GEMINI_AVAILABLE = False

from schemas import (
    ProjectInviteRequest,
    ProjectCreateRequest,
    SaveLinkRequest,
    SaveAgendaRequest,
    MeetingAgendaRequest,
)

# Initialize Supabase client with error handling
supabase = None
try:
    if SUPABASE_URL and SUPABASE_KEY:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        print("✅ Supabase client initialized successfully")
    else:
        print("⚠️  Supabase credentials not configured - some features may not work")
except Exception as e:
    print(f"❌ Failed to initialize Supabase client: {e}")
    supabase = None

# Create app
app = FastAPI(
    title="Meeting Management API",
    version="1.0.0",
    description="API for managing meetings, organizations, and projects with automated notifications",
    lifespan=lifespan,
)

# Simple CORS setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Basic health check routes
@app.get("/")
async def root():
    return {
        "message": "Meeting Management API",
        "version": "1.0.0", 
        "status": "healthy",
        "docs_url": "/docs",
        "ml_available": ML_AVAILABLE,
        "gemini_available": GEMINI_AVAILABLE
    }

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "Meeting Management API",
        "version": "1.0.0",
        "ml_available": ML_AVAILABLE,
        "gemini_available": GEMINI_AVAILABLE
    }

@app.get("/webhook/health")
async def webhook_health_check():
    """Check webhook configuration and availability"""
    try:
        from src.core.config import RECALL_WEBHOOK_URL, RECALL_WEBHOOK_SECRET, RECALL_API_TOKEN
        
        webhook_status = {
            "status": "healthy",
            "webhook_url": RECALL_WEBHOOK_URL or "Not configured",
            "webhook_secret": "Configured" if RECALL_WEBHOOK_SECRET else "Not configured",
            "recall_api_token": "Configured" if RECALL_API_TOKEN else "Not configured",
            "endpoint_available": True,
            "endpoint_path": "/recall/transcription"
        }
        
        # Check if recall router is loaded
        if "recall" in routers_loaded:
            webhook_status["router_loaded"] = True
        else:
            webhook_status["router_loaded"] = False
            webhook_status["status"] = "warning"
            
        return webhook_status
        
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "endpoint_available": False
        }

@app.post("/webhook/test")
async def test_webhook():
    """Test webhook functionality with sample data"""
    try:
        from src.services.recallai_services import recall_service
        from src.core.config import RECALL_WEBHOOK_SECRET
        
        # Sample webhook data
        test_data = {
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
        
        # Test webhook verification
        if recall_service.verify_webhook_signature(RECALL_WEBHOOK_SECRET):
            verification_status = "✅ Webhook secret verification works"
        else:
            verification_status = "❌ Webhook secret verification failed"
        
        return {
            "status": "success",
            "message": "Webhook test completed",
            "verification": verification_status,
            "test_data": test_data,
            "webhook_endpoint": "/recall/transcription",
            "note": "Use this endpoint to test webhook functionality"
        }
        
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "message": "Webhook test failed"
        }

# Track loaded routers
routers_loaded = []
router_errors = []

# Try to import routers with better error handling
def safe_import_router(module_name, router_name, url_prefix, tags):
    """Safely import and include a router"""
    try:
        # Import the module
        module = __import__(module_name, fromlist=[router_name])
        
        # Look for router attribute
        if hasattr(module, 'router'):
            app.include_router(module.router, prefix=url_prefix, tags=tags)
            routers_loaded.append(router_name)
            print(f"✅ Loaded router: {router_name}")
            return True
        else:
            # Debug: show what attributes the module has
            attrs = [attr for attr in dir(module) if not attr.startswith('_')]
            router_errors.append(f"{router_name}: No 'router' attribute. Found: {attrs}")
            print(f"❌ Failed to load router: {router_name} - No 'router' attribute")
            return False
    except Exception as e:
        router_errors.append(f"{router_name}: Import error - {str(e)}")
        print(f"❌ Failed to load router: {router_name} - {str(e)}")
        return False

# Import and include routers - simplified to avoid duplicates
print("🔧 Loading routers...")

# Define router configurations
router_configs = [
    ("src.routers.auth", "auth", "/auth", ["Authentication"]),
    ("src.routers.user", "user", "/users", ["Users"]),
    ("src.routers.organization", "organization", "/org", ["Organizations"]),
    ("src.routers.project", "project", "/proj", ["Projects"]),
    ("src.routers.meeting", "meeting", "/meetings", ["Meetings"]),
    ("src.routers.agenda", "agenda", "/agenda", ["Agenda"]),
    ("src.routers.action_items", "action_items", "/action-items", ["Action Items"]),
    ("src.routers.search", "search", "/search", ["Search"]),
    ("src.routers.zoom", "zoom", "/meeting-platform/zoom", ["Zoom Integration"]),
    ("src.routers.recall", "recall", "/recall", ["Recall AI"]),
    ("src.routers.summary", "summary", "/summary", ["Summary"]),
    ("src.routers.notification", "notification", "/notifications", ["Notifications"]),
]

# Load all routers using the safe import function
for module_name, router_name, url_prefix, tags in router_configs:
    safe_import_router(module_name, router_name, url_prefix, tags)

# Add debug routes
@app.get("/status")
async def status():
    """Get API status and loaded routers"""
    return {
        "status": "running",
        "loaded_routers": routers_loaded,
        "router_errors": router_errors,
        "ml_available": ML_AVAILABLE,
        "gemini_available": GEMINI_AVAILABLE,
        "total_routers": len(routers_loaded),
        "total_errors": len(router_errors)
    }

@app.get("/test-import")
async def test_import():
    """Test import functionality"""
    return {
        "message": "Import test successful",
        "loaded_routers": routers_loaded,
        "errors": router_errors
          }
  
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize services on startup and cleanup on shutdown"""
    # Startup
    print("🚀 Starting Momentum AI API...")
    print(f"📊 Loaded routers: {routers_loaded}")
    if router_errors:
        print(f"⚠️  Router errors: {router_errors}")
    print(f"🤖 ML available: {ML_AVAILABLE}")
    print(f"🧠 Gemini available: {GEMINI_AVAILABLE}")
    print(f"📖 Documentation: http://localhost:8000/docs")
    print(f"🔍 Status: http://localhost:8000/status")
    
    yield
    
    # Shutdown
    print("🛑 Shutting down Momentum AI API...")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
    
