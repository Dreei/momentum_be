# src/core/config.py - Compatible with existing routers
import os
from typing import List
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()

ML_AVAILABLE = False
GEMINI_AVAILABLE = False

try:
    import sklearn
    import numpy
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False

try:
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    if GEMINI_API_KEY:
        genai.configure(api_key=GEMINI_API_KEY)
        GEMINI_AVAILABLE = True
    else:
        GEMINI_AVAILABLE = False
except ImportError:
    GEMINI_AVAILABLE = False

class Settings:
    """Simple settings class without pydantic validation"""
    
    # Application Settings
    PROJECT_NAME: str = "Meeting Management API"
    VERSION: str = "1.0.0"
    DESCRIPTION: str = "API for managing meetings, organizations, and projects with automated notifications"
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    DEBUG: bool = os.getenv("DEBUG", "True").lower() == "true"
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    
    # CORS Settings - simple list, no complex parsing
    ALLOWED_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
        "https://79a6-136-158-33-250.ngrok-free.app"
    ]
    
    # Security Settings with defaults
    SECRET_KEY: str = os.getenv("SECRET_KEY", "development-secret-key-change-in-production")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # Supabase Configuration - with safe defaults
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
    SUPABASE_KEY: str = os.getenv("SUPABASE_KEY", "")
    SUPABASE_JWT_SECRET: str = os.getenv("SUPABASE_JWT_SECRET", "")
    
    # Google OAuth Configuration
    GOOGLE_CLIENT_ID: str = os.getenv("GOOGLE_CLIENT_ID", "")
    
    # Zoom OAuth Configuration
    ZOOM_CLIENT_ID: str = os.getenv("ZOOM_CLIENT_ID", "")
    ZOOM_CLIENT_SECRET: str = os.getenv("ZOOM_CLIENT_SECRET", "")
    ZOOM_REDIRECT_URI: str = os.getenv("ZOOM_REDIRECT_URI", "http://localhost:5173/zoom/callback")
    
    # Email Configuration
    SMTP_SERVER: str = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USERNAME: str = os.getenv("SMTP_USERNAME", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
    FROM_EMAIL: str = os.getenv("FROM_EMAIL", "")
    
    # AI Configuration
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    
    # Recall.ai Configuration
    RECALL_API_TOKEN: str = os.getenv("RECALL_API_TOKEN", "")
    RECALL_BOT_NAME: str = os.getenv("RECALL_BOT_NAME", "Momentum Notetaker")
    RECALL_WEBHOOK_SECRET: str = os.getenv("RECALL_WEBHOOK_SECRET", "")
    RECALL_BASE_URL: str = "https://us-west-2.recall.ai"
    RECALL_WEBHOOK_URL: str = os.getenv("RECALL_WEBHOOK_URL", "")
    
    # Logging Configuration
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    
    def __init__(self):
        """Initialize and validate critical settings"""
        if not self.SUPABASE_URL:
            print("⚠️  Warning: SUPABASE_URL not set")
        if not self.SUPABASE_KEY:
            print("⚠️  Warning: SUPABASE_KEY not set")
        if not self.SMTP_USERNAME:
            print("⚠️  Warning: Email functionality disabled (SMTP_USERNAME not set)")
        
        # Show configuration status
        print(f"🔧 Configuration loaded:")
        print(f"   - Environment: {self.ENVIRONMENT}")
        print(f"   - Debug mode: {self.DEBUG}")
        print(f"   - Supabase: {'✅ Configured' if self.SUPABASE_URL else '❌ Not configured'}")
        print(f"   - Email: {'✅ Configured' if self.SMTP_USERNAME else '❌ Not configured'}")
        print(f"   - Google Auth: {'✅ Configured' if self.GOOGLE_CLIENT_ID else '❌ Not configured'}")
        print(f"   - Zoom: {'✅ Configured' if self.ZOOM_CLIENT_ID else '❌ Not configured'}")
        print(f"   - Recall.ai: {'✅ Configured' if self.RECALL_API_TOKEN else '❌ Not configured'}")

# Create global settings instance
settings = Settings()

# Export individual constants for backward compatibility with existing routers
SUPABASE_URL = settings.SUPABASE_URL
SUPABASE_KEY = settings.SUPABASE_KEY
SUPABASE_JWT_SECRET = settings.SUPABASE_JWT_SECRET
ZOOM_CLIENT_ID = settings.ZOOM_CLIENT_ID
ZOOM_CLIENT_SECRET = settings.ZOOM_CLIENT_SECRET
ZOOM_REDIRECT_URI = settings.ZOOM_REDIRECT_URI
SECRET_KEY = settings.SECRET_KEY
ALGORITHM = settings.ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES
GOOGLE_CLIENT_ID = settings.GOOGLE_CLIENT_ID
RECALL_API_TOKEN = settings.RECALL_API_TOKEN
RECALL_BOT_NAME = settings.RECALL_BOT_NAME
RECALL_WEBHOOK_SECRET = settings.RECALL_WEBHOOK_SECRET
RECALL_BASE_URL = settings.RECALL_BASE_URL
RECALL_WEBHOOK_URL= settings.RECALL_WEBHOOK_URL
GEMINI_API_KEY = settings.GEMINI_API_KEY