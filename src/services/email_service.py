# src/utils/email_utils.py - Fixed version from your original
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel

class MeetingInviteData(BaseModel):
    meeting_title: str
    meeting_date: str
    meeting_time: str
    meeting_platform: str
    meeting_link: str
    agenda_items: List[str]
    recipient_email: str
    recipient_name: str
    organizer_name: str
    organizer_email: str
    organization_name: str
    project_name: str

class EmailService:
    def __init__(self):
        self.smtp_server = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
        self.smtp_port = int(os.getenv('SMTP_PORT', 587))
        self.email_user = os.getenv('SMTP_USERNAME')
        self.email_password = os.getenv('SMTP_PASSWORD')
        self.from_email = os.getenv('FROM_EMAIL')

        # Debug logging
        print(f"Email service initialized:")
        print(f"SMTP Server: {self.smtp_server}")
        print(f"Email User: {self.email_user}")
        print(f"Password configured: {'Yes' if self.email_password else 'No'}")

    def send_email(self, to_email: str, subject: str, html_content: str, text_content: Optional[str] = None):
        """Send an email with both HTML and plain text content"""
        try:
            msg = MIMEMultipart('alternative')
            msg['From'] = self.from_email
            msg['To'] = to_email
            msg['Subject'] = subject

            # Create plain text version if not provided
            if not text_content:
                # Fix for f-string issue - use format instead of f-string with backslash
                newline = '\n'
                text_content = f"{subject}{newline}{newline}{html_content.replace('<br>', newline).replace('<p>', newline).replace('</p>', newline)}"

            # Attach both versions
            part1 = MIMEText(text_content, 'plain')
            part2 = MIMEText(html_content, 'html')
            msg.attach(part1)
            msg.attach(part2)

            # Send email
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.email_user, self.email_password)
                server.sendmail(self.from_email, to_email, msg.as_string())

            return True

        except Exception as e:
            print(f"Error sending email: {str(e)}")
            print(f"Error type: {type(e).__name__}")
            import traceback
            traceback.print_exc()
            return False

    def generate_meeting_invite_html(self, meeting_data: MeetingInviteData) -> str:
        """Generate HTML email template for meeting invite"""
        
        # Generate agenda items HTML
        agenda_html = ""
        if meeting_data.agenda_items:
            agenda_html = "<ul style='margin: 15px 0; padding-left: 20px;'>"
            for item in meeting_data.agenda_items:
                agenda_html += f"<li style='margin: 5px 0; color: #555;'>{item}</li>"
            agenda_html += "</ul>"
        else:
            agenda_html = "<p style='color: #888; font-style: italic;'>No agenda items specified</p>"
        
        html_template = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Meeting Invitation</title>
        </head>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
            <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; text-align: center; border-radius: 10px 10px 0 0;">
                <h1 style="color: white; margin: 0; font-size: 28px;">📅 Meeting Invitation</h1>
            </div>
            
            <div style="background: #fff; padding: 30px; border: 1px solid #ddd; border-top: none; border-radius: 0 0 10px 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
                <div style="margin-bottom: 25px;">
                    <h2 style="color: #333; margin: 0 0 10px 0; font-size: 24px;">Hi {meeting_data.recipient_name}! 👋</h2>
                    <p style="margin: 0; color: #666; font-size: 16px;">You're invited to join an upcoming meeting.</p>
                    <p style="margin: 5px 0; font-size: 14px; color: #666;"><strong>Organized by:</strong> {meeting_data.organizer_name} ({meeting_data.organizer_email})</p>
                    <div style="margin: 10px 0; padding: 10px; background: #e3f2fd; border-radius: 5px; border-left: 4px solid #2196f3;">
                        <p style="margin: 0; font-size: 14px; color: #1565c0;"><strong>🏢 Organization:</strong> {meeting_data.organization_name}</p>
                        <p style="margin: 5px 0 0 0; font-size: 14px; color: #1565c0;"><strong>📁 Project:</strong> {meeting_data.project_name}</p>
                    </div>
                </div>
                
                <div style="background: #f8f9fa; padding: 25px; border-radius: 8px; margin: 25px 0; border-left: 4px solid #667eea;">
                    <h3 style="color: #333; margin: 0 0 20px 0; font-size: 22px; display: flex; align-items: center;">
                        🏢 {meeting_data.meeting_title}
                    </h3>
                    
                    <div style="margin: 15px 0;">
                        <div style="display: inline-block; margin: 8px 0; padding: 8px 12px; background: #e3f2fd; border-radius: 20px; font-size: 14px;">
                            <strong>📅 Date:</strong> {meeting_data.meeting_date} {meeting_data.meeting_time}
                        </div>
                        <p style="margin: 5px 0; font-size: 14px; color: #666;"><strong>Meeting Link:</strong> <a href="{meeting_data.meeting_link}" style="color: #667eea; text-decoration: none;">{meeting_data.meeting_link}</a></p>
                    </div>

                    <div style="margin: 30px 0;">
                        <h4 style="color: #333; margin: 0 0 15px 0; font-size: 18px; display: flex; align-items: center;">
                            📋 Meeting Agenda
                        </h4>
                        {agenda_html}
                    </div>
                    
                    <div style="margin: 15px 0;">
                        <div style="display: inline-block; margin: 8px 0; padding: 8px 12px; background: #e8f5e8; border-radius: 20px; font-size: 14px;">
                            <strong>💻 Platform:</strong> {meeting_data.meeting_platform}
                        </div>
                    </div>
                </div>
                
                <div style="text-align: center; margin: 30px 0;">
                    <a href="{meeting_data.meeting_link}" 
                       style="display: inline-block; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; text-decoration: none; padding: 15px 30px; border-radius: 25px; font-weight: bold; font-size: 16px; box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4); transition: transform 0.2s;">
                        🚀 Join Meeting
                    </a>
                </div>
                
                <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #eee; text-align: center;">
                    <p style="margin: 0; color: #888; font-size: 14px;">
                        Can't attend? Please let the organizer know as soon as possible.
                    </p>
                    <p style="margin: 10px 0 0 0; color: #888; font-size: 12px;">
                        This invitation was sent via Momentum AI Meeting Platform
                    </p>
                </div>
            </div>
        </body>
        </html>
        """
        
        return html_template

    def send_meeting_invite(self, meeting_data: MeetingInviteData) -> bool:
        """Send meeting invite email"""
        try:
            # Generate HTML content
            html_content = self.generate_meeting_invite_html(meeting_data)
            
            # Create plain text version
            # Fix for f-string issue - use join instead of f-string with backslash
            newline = '\n'
            agenda_text = newline.join(f"• {item}" for item in meeting_data.agenda_items) if meeting_data.agenda_items else "No agenda items specified"
            
            text_content = (
                f"Meeting Invitation{newline}{newline}"
                f"Hi {meeting_data.recipient_name}!{newline}{newline}"
                f"You're invited to join: {meeting_data.meeting_title}{newline}{newline}"
                f"Organization: {meeting_data.organization_name}{newline}"
                f"Project: {meeting_data.project_name}{newline}{newline}"
                f"Details:{newline}"
                f"📅 Date: {meeting_data.meeting_date}{newline}"
                f"🕐 Time: {meeting_data.meeting_time}{newline}"
                f"💻 Platform: {meeting_data.meeting_platform}{newline}{newline}"
                f"Join here: {meeting_data.meeting_link}{newline}{newline}"
                f"Agenda:{newline}{agenda_text}{newline}{newline}"
                f"Organized by: {meeting_data.organizer_name} ({meeting_data.organizer_email}){newline}{newline}"
                f"Can't attend? Please let the organizer know as soon as possible."
            )
            
            return self.send_email(
                to_email=meeting_data.recipient_email,
                subject=f"Meeting Invitation: {meeting_data.meeting_title}",
                html_content=html_content,
                text_content=text_content
            )
            
        except Exception as e:
            print(f"Error sending meeting invite: {str(e)}")
            return False

    def send_participant_invite(self, to_email: str, project_name: str, inviter_name: str):
        """Send project invitation email"""
        subject = f"You've been invited to join the project '{project_name}'"
        html_content = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
            <h2 style="color: #333;">Project Invitation</h2>
            <p>Hello,</p>
            <p>{inviter_name} has invited you to join the project <b>{project_name}</b>.</p>
            <p>Please log in to your account to accept the invitation.</p>
        </div>
        """
        return self.send_email(to_email, subject, html_content)

    def send_role_update(self, to_email: str, project_name: str, new_role: str):
        """Send role update notification email"""
        subject = f"Your role in '{project_name}' has been updated"
        html_content = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
            <h2 style="color: #333;">Role Updated</h2>
            <p>Hello,</p>
            <p>Your role in the project <b>{project_name}</b> has been changed to <b>{new_role}</b>.</p>
            <p>Please log in to see your new permissions.</p>
        </div>
        """
        return self.send_email(to_email, subject, html_content)

    def send_removal_notification(self, to_email: str, project_name: str):
        """Send project removal notification email"""
        subject = f"You have been removed from '{project_name}'"
        html_content = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
            <h2 style="color: #333;">Removed from Project</h2>
            <p>Hello,</p>
            <p>You have been removed from the project <b>{project_name}</b>.</p>
            <p>If you believe this is a mistake, please contact your project admin.</p>
        </div>
        """
        return self.send_email(to_email, subject, html_content)