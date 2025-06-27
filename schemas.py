
from typing import List, Optional, Dict
from pydantic import BaseModel, EmailStr, Field
from enum import Enum

class UserRole(str, Enum):
    admin = "project_admin"
    member = "member"

class UserInvite(BaseModel):
    email: EmailStr
    role: UserRole

class ProjectInviteRequest(BaseModel):
    project_id: str
    org_id: Optional[str] = None
    add_to_org: bool = False
    users: List[UserInvite]

class ProjectCreateRequest(BaseModel):
    project_id: Optional[str] = None  # let Supabase generate one if not provided
    project_name: str
    description: str
    org_id: str

class MeetingLinkRequest(BaseModel):
    meeting_id: str = Field(..., description="Unique ID for the meeting")
    project_id: str = Field(..., description="Associated project ID")
    link: str = Field(..., description="Zoom/Meet/etc. meeting URL")
    participants: List[EmailStr] = Field(..., description="List of participant emails to notify")

class SaveAgendaRequest(BaseModel):
    project_id: str
    agenda: str
    meeting_id: Optional[str] = None

class MeetingAgendaRequest(BaseModel):
    project_id: str
    created_by: str
    title: str
    scheduled_at: str
    agenda: str
    agenda_items: dict  # this should match JSONB schema in Supabase

class SaveLinkRequest(BaseModel):
    meeting_id: str
    project_id: str
    platform: str
    link: str
    created_by: str
    participants: List[str]

class GenerateContextGroupsRequest(BaseModel):
    user_id: str = Field(..., description="ID of the user triggering the grouping")


