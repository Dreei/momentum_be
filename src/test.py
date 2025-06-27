# This is a test file for the User Management API
# If any issues with connecting to Supabase, 
# check this file for reference
#
#

from fastapi import FastAPI, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr, Field
from typing import Optional
import os
from datetime import datetime
import uuid

# Initialize FastAPI app
app = FastAPI(title="User Management API", version="1.0.0")

# Supabase configuration
SUPABASE_URL = "https://clpsxwgujflkbqtnxdca.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImNscHN4d2d1amZsa2JxdG54ZGNhIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDkwNDcwMjIsImV4cCI6MjA2NDYyMzAyMn0.FU6LugpZ1T5Dvbc49lj5kWa8rb31uIFCydtlHAibEAg"


if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("SUPABASE_URL and SUPABASE_ANON_KEY environment variables are required")

# Initialize Supabase client with error handling
try:
    from supabase import create_client, Client
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
except Exception as e:
    print(f"Error initializing Supabase client: {e}")
    print("Trying alternative initialization...")
    try:
        # Alternative approach for older versions
        from supabase._sync.client import SyncClient
        supabase = SyncClient(SUPABASE_URL, SUPABASE_KEY)
    except Exception as e2:
        print(f"Alternative initialization also failed: {e2}")
        raise ValueError("Failed to initialize Supabase client. Please check your supabase-py version.")

# Pydantic models
class UserCreate(BaseModel):
    first_name: str = Field(..., min_length=1, max_length=100, description="User's first name")
    last_name: str = Field(..., min_length=1, max_length=100, description="User's last name")
    email: EmailStr = Field(..., description="User's email address")
    timezone: Optional[str] = Field(default="UTC", description="User's timezone")

class UserResponse(BaseModel):
    user_id: str
    first_name: str
    last_name: str
    email: str
    created_at: str
    updated_at: str
    status: str
    last_login: Optional[str]
    timezone: str

# Sample user data
SAMPLE_USERS = [
    {
        "first_name": "Jane",
        "last_name": "Smith",
        "email": "jane.smith@example.com", 
        "timezone": "America/Los_Angeles"
    },
    {
        "first_name": "Alice",
        "last_name": "Johnson",
        "email": "alice.johnson@example.com",
        "timezone": "Europe/London"
    }
]

# Function to add sample users
async def add_sample_users():
    """Add sample users to the database on startup"""
    print("Adding sample users to the database...")
    
    for user_data in SAMPLE_USERS:
        try:
            # Create UserCreate instance
            user_create = UserCreate(**user_data)
            
            # Check if user already exists
            existing_user = supabase.table("users").select("email").eq("email", user_create.email).execute()
            
            if existing_user.data:
                print(f"User {user_create.email} already exists, skipping...")
                continue
            
            # Prepare user data for insertion
            user_dict = {
                "first_name": user_create.first_name.strip(),
                "last_name": user_create.last_name.strip(),
                "email": user_create.email.lower().strip(),
                "timezone": user_create.timezone
            }
            
            # Insert user into database
            result = supabase.table("users").insert(user_dict).execute()
            
            if result.data:
                created_user = result.data[0]
                print(f"✓ Successfully added user: {created_user['first_name']} {created_user['last_name']} ({created_user['email']})")
            else:
                print(f"✗ Failed to add user: {user_create.email}")
                
        except Exception as e:
            if "duplicate key value violates unique constraint" in str(e):
                print(f"User {user_data['email']} already exists, skipping...")
            else:
                print(f"✗ Error adding user {user_data['email']}: {str(e)}")
    
    print("Sample user addition completed!\n")

# Startup event to add sample users
@app.on_event("startup")
async def startup_event():
    """Run on application startup"""
    await add_sample_users()

# API endpoint for creating a user
@app.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(user_data: UserCreate):
    """
    Create a new user in the database.
    
    - **first_name**: User's first name (required)
    - **last_name**: User's last name (required)
    - **email**: User's email address (required, must be unique)
    - **timezone**: User's timezone (optional, defaults to UTC)
    """
    try:
        # Prepare user data for insertion
        user_dict = {
            "first_name": user_data.first_name.strip(),
            "last_name": user_data.last_name.strip(),
            "email": user_data.email.lower().strip(),
            "timezone": user_data.timezone
        }
        
        # Insert user into database
        result = supabase.table("users").insert(user_dict).execute()
        
        if not result.data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to create user"
            )
        
        created_user = result.data[0]
        
        # Convert UUID to string and format response
        user_response = UserResponse(
            user_id=str(created_user["user_id"]),
            first_name=created_user["first_name"],
            last_name=created_user["last_name"],
            email=created_user["email"],
            created_at=created_user["created_at"],
            updated_at=created_user["updated_at"],
            status=created_user["status"],
            last_login=created_user.get("last_login"),
            timezone=created_user["timezone"]
        )
        
        return user_response
        
    except Exception as e:
        # Handle duplicate email error
        if "duplicate key value violates unique constraint" in str(e):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A user with this email already exists"
            )
        
        # Handle other database errors
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}"
        )

# Endpoint to manually add sample users
@app.post("/add-sample-users")
async def add_sample_users_endpoint():
    """Manually trigger adding sample users"""
    try:
        await add_sample_users()
        return {"message": "Sample users processing completed", "status": "success"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error adding sample users: {str(e)}"
        )

# Endpoint to get all users
@app.get("/users")
async def get_all_users():
    """Get all users from the database"""
    try:
        result = supabase.table("users").select("*").execute()
        
        if result.data:
            users = []
            for user in result.data:
                user_response = UserResponse(
                    user_id=str(user["user_id"]),
                    first_name=user["first_name"],
                    last_name=user["last_name"],
                    email=user["email"],
                    created_at=user["created_at"],
                    updated_at=user["updated_at"],
                    status=user["status"],
                    last_login=user.get("last_login"),
                    timezone=user["timezone"]
                )
                users.append(user_response)
            return {"users": users, "count": len(users)}
        else:
            return {"users": [], "count": 0}
            
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}"
        )

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint to verify API is running"""
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}

# Root endpoint
@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "message": "User Management API",
        "version": "1.0.0",
        "endpoints": {
            "create_user": "POST /users",
            "get_users": "GET /users", 
            "add_sample_users": "POST /add-sample-users",
            "health_check": "GET /health"
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)