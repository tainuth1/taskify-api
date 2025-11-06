from fastapi import APIRouter, Body, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from jose import jwt
from app.core.config import settings
from app.database import get_db
from app.controllers.project_invite_controller import ProjectInviteController
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