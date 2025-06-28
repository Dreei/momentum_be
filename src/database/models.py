from sqlalchemy import Column, String, Text, Enum, ForeignKey, DateTime, Boolean, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB, INET
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime
from .base import Base

class User(Base):
    __tablename__ = "users"
    
    user_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    first_name = Column(Text, nullable=False)
    last_name = Column(Text, nullable=False)
    email = Column(Text, unique=True, nullable=False, index=True)
    status = Column(Enum('active', 'inactive', 'pending', name='user_status'), default='active')
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = Column(DateTime)
    timezone = Column(String(50))
    last_active_org_id = Column(UUID(as_uuid=True), ForeignKey("organizations.org_id"), nullable=True)
    last_active_project_id = Column(UUID(as_uuid=True), ForeignKey("projects.project_id"), nullable=True)

class Organization(Base):
    __tablename__ = "organizations"

    org_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_name = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    status = Column(Enum("active", "inactive", name="org_status"), default="active")

class OrganizationMember(Base):
    __tablename__ = "organization_members"
    
    org_member_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False)
    org_id = Column(UUID(as_uuid=True), ForeignKey("organizations.org_id"), nullable=False)
    role = Column(Enum("org_admin", "org_member", name="org_role"), nullable=False)
    joined_at = Column(DateTime, default=datetime.utcnow)


class Project(Base):
    __tablename__ = "projects"

    project_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_name = Column(Text, nullable=False)
    profile_url = Column(Text)
    description = Column(Text)
    org_id = Column(UUID(as_uuid=True), ForeignKey("organizations.org_id"), nullable=False)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    status = Column(Enum("active", "inactive", name="project_status"), default="active")
    

class ProjectMember(Base):
    __tablename__ = "project_members"

    project_member_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.project_id"), nullable=False)
    role = Column(Enum("project_admin", "member", "viewer", name="project_role"), nullable=False, default="member")
    joined_at = Column(DateTime, default=datetime.utcnow)
    org_id=Column(UUID(as_uuid=True), ForeignKey("organizations.org_id"), nullable=False)

class Meeting(Base):
    __tablename__ = "meetings"

    meeting_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.project_id"), nullable=False)
    description = Column(Text)
    title = Column(Text, nullable=False)
    scheduled_at = Column(DateTime, nullable=False)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    agenda_generated = Column(Boolean, default=False)
    meeting_status = Column(Enum("scheduled", "started", "processing", "completed", "cancelled", "error", name="meeting_status"), default="scheduled")
    manual_meeting_link = Column(Text)
    bot_id = Column(Text, nullable=True)  # Recall.ai bot ID
    ai_processing_enabled = Column(Boolean, default=False)
    ai_processing_status = Column(Enum("pending", "processing", "completed", "error", name="ai_processing_status"), default="pending")
    summary_id = Column(UUID(as_uuid=True), ForeignKey("meeting_summaries.summary_id"), nullable=True)
    started_at = Column(DateTime, nullable=True)
    ended_at = Column(DateTime, nullable=True)

class MeetingLink(Base):
    __tablename__ = "meeting_links"

    meeting_link_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    meeting_id = Column(UUID(as_uuid=True), ForeignKey("meetings.meeting_id"), nullable=False)
    platform = Column(Enum("zoom", "google_meet", "teams", name="meeting_platform"), nullable=False)
    link_url = Column(Text, nullable=False)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class Summaries(Base):
    __tablename__ = "summaries"

    summary_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    meeting_id = Column(UUID(as_uuid=True), ForeignKey("meetings.meeting_id"), nullable=False)
    content = Column(Text, nullable=False)
    ai_topic = Column(Text)
    embedding_vector = Column(JSONB, nullable=True)  # Store vector as JSON array or use pgvector if available
    created_at = Column(DateTime, default=datetime.utcnow)

class ActionItem(Base):
    __tablename__ = "action_items"

    action_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    summary_id = Column(UUID(as_uuid=True), ForeignKey("summaries.summary_id"), nullable=False)
    description = Column(Text, nullable=False)
    status = Column(Enum("pending", "in_progress", "completed", name="action_status"), default="pending")
    assigned_to = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=True)
    due_date = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)

class Agenda(Base):
    __tablename__ = "agendas"

    agenda_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    meeting_id = Column(UUID(as_uuid=True), ForeignKey("meetings.meeting_id"), nullable=False)
    generated_by_ai = Column(Boolean)
    agenda_items = Column(JSONB, nullable=False)  # Store agenda items as a JSON array
    created_at = Column(DateTime, default=datetime.utcnow)


class Audit(Base):
    __tablename__ = "audit_table"

    audit_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    timestamp = Column(DateTime, default=datetime.utcnow)
    org_id = Column(UUID(as_uuid=True), ForeignKey("organizations.org_id"), nullable=True)
    proj_id = Column(UUID(as_uuid=True), ForeignKey("projects.project_id"), nullable=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False)
    action = Column(Text, nullable=False)
    changes = Column(JSONB)
    ip_address = Column(INET)
    status = Column(Text, default="success")

class MeetingParticipant(Base):
    __tablename__ = "meeting_participants"

    meeting_participant_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    meeting_id = Column(UUID(as_uuid=True), ForeignKey("meetings.meeting_id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False)
    role = Column(Enum("Creator", "participant", name="participant_role"), default="participant")
    email = Column(Text, nullable=False)  # Email of the participant
    status = Column(Enum("invited", "accepted", "declined", name="participant_status"), default="invited")
    joined_at = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)

class OAuthToken(Base):
    __tablename__ = "oauth_tokens"

    token_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False)
    platform = Column(Enum("zoom", "google", "teams", name="platform_type"), nullable=False)
    access_token = Column(Text, nullable=False)
    refresh_token = Column(Text, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Ensure one token per user per platform
    __table_args__ = (
        UniqueConstraint('user_id', 'platform', name='uix_user_platform'),
    )

class RecallSession(Base):
    __tablename__ = "recall_sessions"

    session_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    meeting_id = Column(UUID(as_uuid=True), ForeignKey("meetings.meeting_id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False)
    bot_id = Column(Text, nullable=False, unique=True)  # Recall.ai bot ID
    status = Column(Enum("active", "stopped", "error", name="recall_session_status"), default="active")
    created_at = Column(DateTime, default=datetime.utcnow)
    ended_at = Column(DateTime, nullable=True)

class MeetingTranscript(Base):
    __tablename__ = "meeting_transcripts"

    transcript_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    meeting_id = Column(UUID(as_uuid=True), ForeignKey("meetings.meeting_id"), nullable=False)  # Direct reference to meeting
    bot_id = Column(Text, nullable=False)  # Recall.ai bot ID
    transcript_data = Column(JSONB, nullable=False)  # Raw transcript data from Recall.ai
    created_at = Column(DateTime, default=datetime.utcnow)

class MeetingSummary(Base):
    __tablename__ = "meeting_summaries"

    summary_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    meeting_id = Column(UUID(as_uuid=True), ForeignKey("meetings.meeting_id"), nullable=False)
    bot_id = Column(Text, nullable=False)  # Recall.ai bot ID
    summary_type = Column(Enum("general_summary", "action_items", "decisions", "next_steps", "key_takeaways", "structured_summary", name="summary_type"), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False)
    context_group = Column(Text, nullable=True)  # For grouping related meetings

class MeetingDecision(Base):
    __tablename__ = "meeting_decisions"

    decision_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    meeting_id = Column(UUID(as_uuid=True), ForeignKey("meetings.meeting_id"), nullable=False)
    decision = Column(Text, nullable=False)
    context = Column(Text, nullable=True)
    impact = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class MeetingDiscussion(Base):
    __tablename__ = "meeting_discussions"

    discussion_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    meeting_id = Column(UUID(as_uuid=True), ForeignKey("meetings.meeting_id"), nullable=False)
    topic = Column(Text, nullable=False)
    summary = Column(Text, nullable=True)
    participants = Column(JSONB, nullable=True)  # Array of participant names
    created_at = Column(DateTime, default=datetime.utcnow)

class MeetingJargon(Base):
    __tablename__ = "meeting_jargon"

    jargon_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    meeting_id = Column(UUID(as_uuid=True), ForeignKey("meetings.meeting_id"), nullable=False)
    term = Column(Text, nullable=False)
    clarification = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

class MeetingThemes(Base):
    __tablename__ = "meeting_themes"

    theme_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    meeting_id = Column(UUID(as_uuid=True), ForeignKey("meetings.meeting_id"), nullable=False)
    themes = Column(JSONB, nullable=False)  # Array of themes
    context_group = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class SummaryEditRequest(Base):
    __tablename__ = "summary_edit_requests"

    edit_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    meeting_id = Column(UUID(as_uuid=True), ForeignKey("meetings.meeting_id"), nullable=False)
    proposed_by = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False)
    proposed_changes = Column(JSONB, nullable=False)
    status = Column(Enum('draft', 'pending_approval', 'approved', 'rejected', name='edit_status'), default='pending_approval')
    reviewed_by = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class SummaryRevisionHistory(Base):
    __tablename__ = "summary_revision_history"

    revision_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    edit_id = Column(UUID(as_uuid=True), ForeignKey("summary_edit_requests.edit_id"), nullable=False)
    editor_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False)
    reviewer_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=True)
    content = Column(JSONB, nullable=False)
    status = Column(Enum('approved', 'rejected', name='revision_status'), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)

class Notification(Base):
    __tablename__ = "notifications"

    notification_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id"), nullable=False)
    meeting_id = Column(UUID(as_uuid=True), ForeignKey("meetings.meeting_id"), nullable=False)
    edit_request_id = Column(UUID(as_uuid=True), ForeignKey("summary_edit_requests.edit_id"), nullable=False)
    type = Column(Enum('edit_pending', name='notification_type'), nullable=False)
    status = Column(Enum('unread', 'read', name='notification_status'), default='unread')
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)







