from jose import JWTError, jwt
from sqlalchemy.orm import Session
from sqlalchemy import and_
from datetime import datetime, timedelta
import secrets
import uuid
from datetime import timezone

from app.core.config import settings
from app.models import ProjectInvite, ProjectMember, User, Project
from app.models.project_invite import InviteStatus
from app.models.project_member import MemberStatus
from app.core.email import sent_email_brevo

class ProjectInviteController:
    def __init__(self, db: Session):
        self.db = db

    def invite_user_by_email(self, project_id: str, email: str, invited_by_user_id: str) -> ProjectInvite:
        """Invite a user to a project by email."""
        
        # Validate project exists and inviter has permission
        project = self.db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise ValueError("Project not found")
        
        # Check if user is already a member
        existing_member = (
            self.db.query(ProjectMember)
            .join(User, ProjectMember.user_id == User.id)
            .filter(
                and_(
                    ProjectMember.project_id == project_id,
                    User.email == email,
                    ProjectMember.status == MemberStatus.active
                )
            )
            .first()
        )
        if existing_member:
            raise ValueError("User is already a member of this project")
        
        # Check if there's a pending invite for this email
        existing_invite = (
            self.db.query(ProjectInvite)
            .filter(
                and_(
                    ProjectInvite.project_id == project_id,
                    ProjectInvite.email == email,
                    ProjectInvite.status == InviteStatus.pending
                )
            )
            .first()
        )
        if existing_invite:
            # Check if expired
            if existing_invite.expired_at and existing_invite.expired_at < datetime.utcnow().replace(tzinfo=timezone.utc):
                existing_invite.status = InviteStatus.expired
                self.db.commit()
            else:
                raise ValueError("Invitation already sent and pending")
        
        # Generate secure token
        token = secrets.token_urlsafe(32)
        
        # Create invitation (expires in 7 days)
        expired_at = datetime.utcnow() + timedelta(days=7)
        
        invite = ProjectInvite(
            project_id=project_id,
            email=email,
            invited_by=invited_by_user_id,
            status=InviteStatus.pending,
            token=token,
            expired_at=expired_at
        )
        
        self.db.add(invite)
        self.db.commit()
        self.db.refresh(invite)
        
        # Send invitation email
        self._send_invitation_email(invite, project)
        
        return invite

    def _send_invitation_email(self, invite: ProjectInvite, project: Project):
        """Send invitation email to user."""
        inviter = self.db.query(User).filter(User.id == invite.invited_by).first()
        inviter_name = inviter.full_name or inviter.username
        
        # Check if user exists
        user_exists = self.db.query(User).filter(User.email == invite.email).first() is not None
        
        # must be modify when working with front-end project
        accept_url = f"{settings.FRONTEND_URL}/accept-invite?token={invite.token}"
        
        if user_exists:
            # User has account - direct accept link
            html_content = f"""
            <h2>You've been invited to join a project!</h2>
            <p>{inviter_name} has invited you to join the project <strong>{project.name}</strong>.</p>
            <p><a href="{accept_url}">Accept Invitation</a></p>
            <p>This invitation expires on {invite.expired_at.strftime('%Y-%m-%d %H:%M') if invite.expired_at else 'N/A'}.</p>
            """
        else:
            # User doesn't have account - signup + accept flow
            signup_url = f"{settings.FRONTEND_URL}/signup?invite_token={invite.token}"
            html_content = f"""
            <h2>You've been invited to join a project!</h2>
            <p>{inviter_name} has invited you to join the project <strong>{project.name}</strong>.</p>
            <p>To accept this invitation, please create an account:</p>
            <p><a href="{signup_url}">Create Account & Accept Invitation</a></p>
            <p>This invitation expires on {invite.expired_at.strftime('%Y-%m-%d %H:%M') if invite.expired_at else 'N/A'}.</p>
            """
        
        sent_email_brevo(
            to_email=invite.email,
            subject=f"Invitation to join {project.name}",
            html_content=html_content
        )