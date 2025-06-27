from core.config import SUPABASE_URL, SUPABASE_KEY
from supabase import create_client, Client
from fastapi import HTTPException

# Initialize Supabase client with error handling
supabase: Client = None

try:
    if SUPABASE_URL and SUPABASE_KEY:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        print("✅ Database connection established")
    else:
        print("⚠️  Supabase credentials not configured")
        supabase = None
except Exception as e:
    print(f"❌ Failed to connect to database: {e}")
    supabase = None

def get_supabase():
    if supabase is None:
        raise HTTPException(
            status_code=503, 
            detail="Database connection not available. Please check your configuration."
        )
    return supabase

# We'll keep SQLAlchemy for type definitions and migrations

# def get_db():
#     db = SessionLocal()
#     try:
#         yield db
#     finally:
#         db.close()