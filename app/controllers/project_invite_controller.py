from sqlalchemy.orm import Session, aliased
from sqlalchemy import and_
from datetime import datetime, timedelta
import secrets
from datetime import timezone

from app.core.config import settings
from app.models import ProjectInvite, ProjectMember, User, Project
from app.models.project_invite import InviteStatus
from app.models.project_member import MemberRole, MemberStatus
from app.core.email import sent_email_brevo
from app.schemas.user import User as UserSchema
from app.schemas.project import Project as ProjectSchema

class ProjectInviteController:
    def __init__(self, db: Session):
        self.db = db

    def invite_user_by_email(self, project_id: str, email: str, invited_by_user_id: str) -> ProjectInvite:
        """Invite a user to a project by email. Only owners and admins can invite."""
        
        # Validate project exists
        project = self.db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise ValueError("Project not found")
        
        # Check if inviter is an active member with owner or admin role
        inviter_member = (
            self.db.query(ProjectMember)
            .filter(
                and_(
                    ProjectMember.project_id == project_id,
                    ProjectMember.user_id == invited_by_user_id,
                    ProjectMember.status == MemberStatus.active
                )
            )
            .first()
        )
        
        if not inviter_member:
            raise ValueError("You are not a member of this project")
        
        if inviter_member.role not in [MemberRole.owner, MemberRole.admin]:
            raise ValueError("Only owners and admins can invite new members")
        
        # Check if user is already an active member
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

    def accept_invite(self, token: str, user_id: str) -> ProjectMember:
        """Accept an invitation. User must be authenticated."""
        
        invite = (
            self.db.query(ProjectInvite)
            .filter(ProjectInvite.token == token)
            .first()
        )

        if not invite:
            raise ValueError("Invalid invitation token")

        if invite.status != InviteStatus.pending:
            raise ValueError(f"Invitation already {invite.status.value}")
        
        if invite.expired_at and invite.expired_at.replace(tzinfo=None) < datetime.utcnow():
            invite.status = InviteStatus.expired
            self.db.commit()
            raise ValueError("Invitation has expired")

        # Verify user email matches invite email
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError("User not found")
        
        # Validate that the authenticated user's email matches the invite email
        if user.email.lower() != invite.email.lower():
            raise ValueError("This invitation is for a different email address")

        # Check if user has ANY existing membership record (regardless of status)
        existing_member = (
            self.db.query(ProjectMember)
            .filter(
                and_(
                    ProjectMember.project_id == invite.project_id,
                    ProjectMember.user_id == user_id
                )
            )
            .first()
        )
        
        if existing_member:
            # If already active, just return it
            if existing_member.status == MemberStatus.active:
                invite.status = InviteStatus.accepted
                self.db.commit()
                return existing_member
            
            # If status is 'remove' or 'left', reactivate the member
            if existing_member.status in [MemberStatus.remove, MemberStatus.left]:
                existing_member.status = MemberStatus.active
                existing_member.left_at = None  # Clear the left_at timestamp
                # Optionally update join_at to current time, or keep original
                # existing_member.join_at = datetime.utcnow().replace(tzinfo=timezone.utc)
                
                invite.status = InviteStatus.accepted
                self.db.commit()
                self.db.refresh(existing_member)
                return existing_member

        # No existing record found, create new project member
        project_member = ProjectMember(
            user_id=user_id,
            project_id=invite.project_id,
            role=MemberRole.member,
            status=MemberStatus.active
        )
        self.db.add(project_member)

        # Update invite status
        invite.status = InviteStatus.accepted

        self.db.commit()
        self.db.refresh(project_member)
        
        return project_member

    def reject_invite(self, token: str, user_id: str) -> ProjectInvite:
        """Reject an invitation. User must be authenticated."""

        invite = (
            self.db.query(ProjectInvite)
            .filter(ProjectInvite.token == token)
            .first()
        )
        if not invite:
            raise ValueError("Invalid invitation token")

        if invite.status != InviteStatus.pending:
            raise ValueError(f"Invitation already {invite.status.value}")

        # Verify user email matches invite email
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError("User not found")

        if user.email.lower() != invite.email.lower():
            raise ValueError("This invitation is for a different email address")

        invite.status = InviteStatus.rejected
        self.db.commit()
        self.db.refresh(invite)
        
        return invite

    def get_invite_by_token(self, token: str) -> dict:
        """Get invitation details by token (for unauthenticated users).
        Returns a dictionary with invite details, project info, and inviter info.
        """
        Inviter = aliased(User)
        ProjectOwner = aliased(User)
        
        result = (
            self.db.query(ProjectInvite, Project, Inviter, ProjectOwner)
            .join(Project, ProjectInvite.project_id == Project.id)
            .join(Inviter, ProjectInvite.invited_by == Inviter.id)
            .join(ProjectOwner, Project.owner_id == ProjectOwner.id)
            .filter(ProjectInvite.token == token)
            .first()
        )
        
        if not result:
            raise ValueError("Invalid invitation token")
        
        invite, project, inviter, project_owner = result
        
        # Check if the invited email already has an account
        invited_user = self.db.query(User).filter(User.email == invite.email).first()
        user_exists = invited_user is not None
        
        return {
            "id": str(invite.id),
            "token": invite.token,
            "email": invite.email,
            "status": invite.status.value,
            "expired_at": invite.expired_at.isoformat() if invite.expired_at else None,
            "created_at": invite.created_at.isoformat() if invite.created_at else None,
            "updated_at": invite.updated_at.isoformat() if invite.updated_at else None,
            "project": {
                "id": str(project.id),
                "name": project.name,
                "description": project.description,
                "type": project.type.value if hasattr(project.type, 'value') else str(project.type),
                "owner_id": str(project.owner_id),
                "owner": {
                    "id": str(project_owner.id) if project_owner else None,
                    "username": project_owner.username if project_owner else None,
                    "full_name": project_owner.full_name if project_owner else None,
                    "profile": project_owner.profile if project_owner else None,
                } if project_owner else None,
                "created_at": project.created_at.isoformat() if project.created_at else None,
            },
            "invited_by": {
                "id": str(inviter.id),
                "username": inviter.username,
                "full_name": inviter.full_name,
                "profile": inviter.profile,
                "email": inviter.email,
            },
            "user_exists": user_exists,
        }

    def get_pending_invite_for_user(self, email: str):
        """Get a pending invitation by project ID and email."""
        invites = (
            self.db.query(ProjectInvite)
            .join(Project, ProjectInvite.project_id == Project.id)
            .join(User, ProjectInvite.invited_by == User.id)
            .filter(
                and_(
                    ProjectInvite.email == email,
                    ProjectInvite.status == InviteStatus.pending
                )
            )
            .all()
        )
        
        result = []
        for invite in invites:
            project = self.db.query(Project).filter(Project.id == invite.project_id).first()
            inviter = self.db.query(User).filter(User.id == invite.invited_by).first()
            
            result.append({
                "id": str(invite.id),
                "token": invite.token,
                "project": ProjectSchema.model_validate(project).model_dump(mode="json"),
                "invited_by": UserSchema.model_validate(inviter).model_dump(mode="json"),
                "status": invite.status.value,
                "expired_at": invite.expired_at.isoformat() if invite.expired_at else None,
                "created_at": invite.created_at.isoformat() if invite.created_at else None,
            })
        
        return result

    def get_pending_invites_for_project(self, project_id: str, user_id: str) -> list:
        """Get all pending invitations for a project. User must be a member of the project."""
        
        # Validate project exists
        project = self.db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise ValueError("Project not found")
        
        # Check if user is a member of the project (active status)
        member = (
            self.db.query(ProjectMember)
            .filter(
                and_(
                    ProjectMember.project_id == project_id,
                    ProjectMember.user_id == user_id,
                    ProjectMember.status == MemberStatus.active
                )
            )
            .first()
        )
        if not member:
            raise ValueError("You are not a member of this project")
        
        # Get all pending invites for the project
        Inviter = aliased(User)
        invites = (
            self.db.query(ProjectInvite, Inviter)
            .join(Inviter, ProjectInvite.invited_by == Inviter.id)
            .filter(
                and_(
                    ProjectInvite.project_id == project_id,
                    ProjectInvite.status == InviteStatus.pending
                )
            )
            .order_by(ProjectInvite.created_at.desc())
            .all()
        )
        
        result = []
        for invite, inviter in invites:
            # Check if invite is expired
            is_expired = False
            if invite.expired_at and invite.expired_at < datetime.utcnow().replace(tzinfo=timezone.utc):
                is_expired = True
            
            result.append({
                "id": str(invite.id),
                "email": invite.email,
                "token": invite.token,
                "status": invite.status.value,
                "expired_at": invite.expired_at.isoformat() if invite.expired_at else None,
                "created_at": invite.created_at.isoformat() if invite.created_at else None,
                "updated_at": invite.updated_at.isoformat() if invite.updated_at else None,
                "is_expired": is_expired,
                "invited_by": {
                    "id": str(inviter.id),
                    "username": inviter.username,
                    "full_name": inviter.full_name,
                    "email": inviter.email,
                    "profile": inviter.profile,
                }
            })
        
        return result