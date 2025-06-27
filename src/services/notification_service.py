# src/services/notification_service.py - Meeting notification service
from typing import List, Dict, Any
from datetime import datetime
from supabase import Client
import logging

from src.services.email_service import email_service, MeetingInviteData
from src.core.exceptions import NotFoundError, ServiceError

logger = logging.getLogger(__name__)

class NotificationService:
    """Service for handling meeting notifications and logging"""
    
    def __init__(self):
        self.email_service = email_service

    async def log_notification(
        self, 
        meeting_id: str, 
        recipient_email: str, 
        recipient_name: str,
        notification_type: str, 
        status: str, 
        error_message: str = None,
        supabase: Client = None
    ) -> dict:
        """Log notification attempt to database"""
        try:
            log_data = {
                'meeting_id': meeting_id,
                'recipient_email': recipient_email,
                'recipient_name': recipient_name,
                'notification_type': notification_type,
                'status': status,
                'sent_at': datetime.utcnow().isoformat(),
                'error_message': error_message
            }
            
            if supabase:
                # Check if notification_logs table exists, if not skip logging
                try:
                    response = supabase.table('notification_logs').insert(log_data).execute()
                    logger.info(f"Notification logged: {log_data}")
                except Exception as e:
                    logger.warning(f"Could not log notification (table may not exist): {str(e)}")
            
            return log_data
        except Exception as e:
            logger.error(f"Error logging notification: {str(e)}")
            return log_data

    async def get_meeting_details(self, meeting_id: str, supabase: Client) -> Dict[str, Any]:
        """Get complete meeting details with project and organization info"""
        meeting_response = supabase.table('meetings') \
            .select('*') \
            .eq('meeting_id', meeting_id) \
            .execute()
        
        if not meeting_response.data:
            raise NotFoundError("Meeting", meeting_id)
        
        meeting = meeting_response.data[0]
        
        # Get project details
        project_response = supabase.table('projects') \
            .select('*') \
            .eq('project_id', meeting['project_id']) \
            .execute()
        
        if not project_response.data:
            raise NotFoundError("Project", meeting['project_id'])
        
        project = project_response.data[0]
        
        # Get organization details
        org_response = supabase.table('organizations') \
            .select('*') \
            .eq('org_id', project['org_id']) \
            .execute()
        
        org_name = org_response.data[0]['org_name'] if org_response.data else "Unknown Organization"
        
        return {
            'meeting': meeting,
            'project': project,
            'organization_name': org_name
        }

    async def get_meeting_participants(self, meeting_id: str, supabase: Client) -> List[Dict[str, Any]]:
        """Get all participants for a meeting"""
        # Try meeting_participants table first (if it exists)
        try:
            participants_response = supabase.table('meeting_participants') \
                .select('*, users(*)') \
                .eq('meeting_id', meeting_id) \
                .execute()
            
            if participants_response.data:
                return [
                    {
                        'user_id': p['user_id'],
                        'email': p['email'],
                        'first_name': p['users']['first_name'] if p.get('users') else '',
                        'last_name': p['users']['last_name'] if p.get('users') else '',
                        'role': p.get('role', 'participant')
                    }
                    for p in participants_response.data
                ]
        except Exception as e:
            logger.debug(f"meeting_participants table not found or error: {str(e)}")
        
        # Fallback to project members
        meeting_details = await self.get_meeting_details(meeting_id, supabase)
        project_id = meeting_details['meeting']['project_id']
        
        project_members_response = supabase.table('project_members') \
            .select('*, users(*)') \
            .eq('project_id', project_id) \
            .execute()
        
        if not project_members_response.data:
            logger.warning(f"No participants found for meeting {meeting_id}")
            return []
        
        return [
            {
                'user_id': member['user_id'],
                'email': member['users']['email'],
                'first_name': member['users']['first_name'],
                'last_name': member['users']['last_name'],
                'role': member['role']
            }
            for member in project_members_response.data
            if member.get('users')
        ]

    async def get_meeting_creator(self, meeting_id: str, supabase: Client) -> Dict[str, Any]:
        """Get meeting creator details"""
        meeting_details = await self.get_meeting_details(meeting_id, supabase)
        creator_id = meeting_details['meeting']['created_by']
        
        creator_response = supabase.table('users') \
            .select('*') \
            .eq('user_id', creator_id) \
            .execute()
        
        if not creator_response.data:
            raise NotFoundError("Meeting creator", creator_id)
        
        return creator_response.data[0]

    async def get_meeting_agenda(self, meeting_id: str, supabase: Client) -> List[str]:
        """Get meeting agenda items"""
        try:
            agenda_response = supabase.table('agendas') \
                .select('agenda_items') \
                .eq('meeting_id', meeting_id) \
                .execute()
            
            if agenda_response.data and agenda_response.data[0]['agenda_items']:
                agenda_items = agenda_response.data[0]['agenda_items']
                
                # Handle different agenda storage formats
                if isinstance(agenda_items, list):
                    return agenda_items
                elif isinstance(agenda_items, str):
                    import json
                    try:
                        return json.loads(agenda_items)
                    except json.JSONDecodeError:
                        return [agenda_items]
                else:
                    return []
            
            return []
        except Exception as e:
            logger.debug(f"Could not retrieve agenda for meeting {meeting_id}: {str(e)}")
            return []

    async def send_meeting_notifications(
        self, 
        meeting_id: str, 
        link_url: str, 
        platform: str, 
        current_user_email: str,
        supabase: Client
    ) -> List[Dict[str, Any]]:
        """Send notifications to all meeting participants"""
        try:
            logger.info(f"🚀 Starting notification process for meeting {meeting_id}")
            
            # Get meeting details
            meeting_details = await self.get_meeting_details(meeting_id, supabase)
            meeting = meeting_details['meeting']
            project = meeting_details['project']
            org_name = meeting_details['organization_name']
            
            # Get meeting creator
            creator = await self.get_meeting_creator(meeting_id, supabase)
            creator_name = f"{creator['first_name']} {creator['last_name']}"
            
            # Get participants
            participants = await self.get_meeting_participants(meeting_id, supabase)
            
            if not participants:
                logger.warning(f"No participants found for meeting {meeting_id}")
                return []
            
            # Get agenda items
            agenda_items = await self.get_meeting_agenda(meeting_id, supabase)
            
            # Prepare email data
            try:
                meeting_date = datetime.fromisoformat(meeting['scheduled_at'].replace('Z', '+00:00')).strftime('%B %d, %Y')
                meeting_time = datetime.fromisoformat(meeting['scheduled_at'].replace('Z', '+00:00')).strftime('%I:%M %p UTC')
            except Exception as e:
                logger.warning(f"Error parsing meeting date: {str(e)}")
                meeting_date = meeting['scheduled_at']
                meeting_time = ""
            
            # Send notifications to all participants
            notification_results = []
            
            for participant in participants:
                participant_email = participant['email']
                participant_name = f"{participant['first_name']} {participant['last_name']}".strip()
                
                if not participant_name:
                    participant_name = participant_email.split('@')[0]
                
                logger.info(f"Sending notification to: {participant_name} ({participant_email})")
                
                try:
                    # Create meeting data for email
                    meeting_data = MeetingInviteData(
                        meeting_title=meeting['title'],
                        meeting_date=meeting_date,
                        meeting_time=meeting_time,
                        meeting_platform=platform,
                        meeting_link=link_url,
                        agenda_items=agenda_items,
                        recipient_email=participant_email,
                        recipient_name=participant_name,
                        organizer_name=creator_name,
                        organizer_email=creator['email'],
                        organization_name=org_name,
                        project_name=project['project_name']
                    )
                    
                    # Send email notification
                    email_sent = self.email_service.send_meeting_invite(meeting_data)
                    
                    if email_sent:
                        # Log successful notification
                        await self.log_notification(
                            meeting_id=meeting_id,
                            recipient_email=participant_email,
                            recipient_name=participant_name,
                            notification_type='meeting_link_shared',
                            status='sent',
                            supabase=supabase
                        )
                        
                        notification_results.append({
                            'recipient': participant_email,
                            'status': 'sent',
                            'message': 'Email notification sent successfully'
                        })
                        logger.info(f"✅ Notification sent to {participant_email}")
                    else:
                        # Log failed notification
                        await self.log_notification(
                            meeting_id=meeting_id,
                            recipient_email=participant_email,
                            recipient_name=participant_name,
                            notification_type='meeting_link_shared',
                            status='failed',
                            error_message='Email service returned False',
                            supabase=supabase
                        )
                        
                        notification_results.append({
                            'recipient': participant_email,
                            'status': 'failed',
                            'error': 'Email service returned False'
                        })
                        logger.warning(f"❌ Failed to send notification to {participant_email}")
                        
                except Exception as e:
                    error_message = f"Error sending notification: {str(e)}"
                    logger.error(f"❌ Error sending notification to {participant_email}: {error_message}")
                    
                    # Log failed notification
                    await self.log_notification(
                        meeting_id=meeting_id,
                        recipient_email=participant_email,
                        recipient_name=participant_name,
                        notification_type='meeting_link_shared',
                        status='failed',
                        error_message=error_message,
                        supabase=supabase
                    )
                    
                    notification_results.append({
                        'recipient': participant_email,
                        'status': 'failed',
                        'error': error_message
                    })
            
            successful_count = len([r for r in notification_results if r['status'] == 'sent'])
            logger.info(f"✅ Notification process complete: {successful_count}/{len(notification_results)} sent successfully")
            
            return notification_results
            
        except Exception as e:
            logger.error(f"❌ Error in send_meeting_notifications: {str(e)}")
            raise ServiceError("Notification", str(e))

    async def get_notification_logs(
        self, 
        meeting_id: str = None, 
        user_id: str = None,
        supabase: Client = None
    ) -> List[Dict[str, Any]]:
        """Get notification logs, optionally filtered by meeting or user"""
        try:
            if not supabase:
                return []
            
            query = supabase.table('notification_logs').select('*')
            
            if meeting_id:
                query = query.eq('meeting_id', meeting_id)
            
            if user_id:
                # Get meetings the user has access to
                accessible_meetings = supabase.table('meetings') \
                    .select('meeting_id, projects!inner(project_members!inner(user_id))') \
                    .eq('projects.project_members.user_id', user_id) \
                    .execute()
                
                meeting_ids = [m['meeting_id'] for m in accessible_meetings.data]
                if meeting_ids:
                    query = query.in_('meeting_id', meeting_ids)
                else:
                    return []
            
            response = query.order('sent_at', desc=True).execute()
            return response.data
            
        except Exception as e:
            logger.error(f"Error retrieving notification logs: {str(e)}")
            return []

# Create global notification service instance
notification_service = NotificationService()