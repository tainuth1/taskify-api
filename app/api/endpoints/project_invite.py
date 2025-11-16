from fastapi import APIRouter, Body, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from jose import jwt
from app.core.config import settings
from app.database import get_db
from app.controllers.project_invite_controller import ProjectInviteController
from app.models import User
from app.schemas.project_invite import ProjectInviteCreate, ProjectInviteResponse

router = APIRouter()

@router.post("/projects/{project_id}/invite", status_code=201, response_model=dict)
def invite_user(request: Request, project_id: str, payload: ProjectInviteCreate = Body(...), db: Session = Depends(get_db)):
    """Invite a user to a project by email."""
    controller = ProjectInviteController(db)
    
    # Get authenticated user
    token = request.cookies.get(settings.ACCESS_TOKEN_COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=401, detail="Missing access token")
    
    try:
        jwt_payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        inviter_id = jwt_payload.get("sub")
    except:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    try:
        invite = controller.invite_user_by_email(project_id, payload.email, inviter_id)
        invite_response = ProjectInviteResponse.model_validate(invite)
        return {
            "success": True,
            "message": "Invitation sent successfully",
            "data": invite_response.model_dump(mode="json")
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
@router.post("/invites/{token}/accept", status_code=200)
def accept_invitation(request: Request, token: str, db: Session = Depends(get_db)):
    """Accept a project invitation."""
    controller = ProjectInviteController(db)

    # Get authenticated user
    token_cookie = request.cookies.get(settings.ACCESS_TOKEN_COOKIE_NAME)
    if not token_cookie:
        raise HTTPException(status_code=401, detail="Missing access token")
    
    try:
        jwt_payload = jwt.decode(token_cookie, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id = jwt_payload.get("sub")
    except:
        raise HTTPException(status_code=401, detail="Invalid token")

    try:
        member = controller.accept_invite(token, user_id)
        return {
            "success": True,
            "message": "Invitation accepted successfully",
            "data": {
                "project_id": str(member.project_id),
                "user_id": str(member.user_id),
                "role": member.role.value
            }
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/invites/{token}/reject", status_code=200)
def reject_invitation(request: Request, token: str, db: Session = Depends(get_db)):
    controller = ProjectInviteController(db)
    
    # Get authenticated user
    token_cookie = request.cookies.get(settings.ACCESS_TOKEN_COOKIE_NAME)
    if not token_cookie:
        raise HTTPException(status_code=401, detail="Missing access token")

    try:
        payload = jwt.decode(token_cookie, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id = payload.get("sub")
    except:
        raise HTTPException(status_code=401, detail="Invalid token")

    try:
        invite = controller.reject_invite(token, user_id)
        return {
            "success": True,
            "message": "Invitation rejected",
            "data": {"status": invite.status.value}
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/invites/{token}", status_code=200)
def get_invitation_details(token: str, db: Session = Depends(get_db)):
    """Get invitation details (public endpoint for unauthenticated users)."""
    controller = ProjectInviteController(db)
    
    try:
        invite_data = controller.get_invite_by_token(token)
        
        return {
            "success": True,
            "message": "Get invitation details successfully",
            "data": invite_data
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.get("/invitations/pending", status_code=200)
def get_pending_invitaions_for_user(request: Request, db: Session = Depends(get_db)):
    """Get all pending invitations for the authenticated user."""
    controller = ProjectInviteController(db)
    
    token = request.cookies.get(settings.ACCESS_TOKEN_COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=401, detail="Missing access token")
    
    try:
        jwt_payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id = jwt_payload.get("sub")
        user = db.query(User).filter(User.id == user_id).first()

        invite_data = controller.get_pending_invite_for_user(user.email)
        return {
            "success": True,
            "message": "Get pending invitations successfully",
            "data": invite_data
        }
    except Exception as e:
        raise HTTPException(status_code=401, detail=str(e))

@router.get("/projects/{project_id}/invites/pending", status_code=200)
def get_pending_invites_for_project(request: Request, project_id: str, db: Session = Depends(get_db)):
    """Get all pending invitations for a project."""
    controller = ProjectInviteController(db)
    
    token = request.cookies.get(settings.ACCESS_TOKEN_COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=401, detail="Missing access token")
    
    try:
        jwt_payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id = jwt_payload.get("sub")
    except:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    try:
        invites = controller.get_pending_invites_for_project(project_id, user_id)
        return {
            "success": True,
            "message": "Get pending invitations for project successfully",
            "data": invites
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))