from fastapi import APIRouter, Body, Depends, HTTPException, Request
from sqlalchemy.orm import Session
import uuid

from app.controllers.project_member_controller import ProjectMemberController
from app.core.config import settings
from app.database import get_db
from app.schemas.project_member import MemberRoleUpdate, ProjectMemberResponse, ProjectMemberDetailResponse, MemberRemoveRequest, MemberLeaveRequest


router = APIRouter()

@router.get("/project-member/{project_id}", status_code=200, description="Get all project members")
def get_all_project_member(request: Request, project_id: uuid.UUID, db: Session = Depends(get_db)):
    controller = ProjectMemberController(db)
    token: str | None = None

    token = request.cookies.get(settings.ACCESS_TOKEN_COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=401, detail="Missing access token")

    try:
        members_data = controller.get_project_members(token, str(project_id))
        members_out = [ProjectMemberDetailResponse.model_validate(member) for member in members_data]
        return {
            "success": True,
            "message": "Get project members successfully",
            "data": [member.model_dump(mode="json") for member in members_out]
        }
    except ValueError as e:
        error_message = str(e)
        if "not found" in error_message.lower():
            raise HTTPException(status_code=404, detail=error_message)
        elif "access denied" in error_message.lower():
            raise HTTPException(status_code=403, detail=error_message)
        else:
            raise HTTPException(status_code=401, detail=error_message)

@router.patch("/project-member/role", status_code=200, description="Update a member's role in a project")
def update_member_role(request: Request, payload: MemberRoleUpdate = Body(...), db: Session = Depends(get_db)):
    controller = ProjectMemberController(db)
    token: str | None = None

    token = request.cookies.get(settings.ACCESS_TOKEN_COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=401, detail="Missing access token")

    try:
        member_data = controller.update_member_role(payload, token)
        member_out = ProjectMemberResponse.model_validate(member_data)
        return {
            "success": True,
            "message": "Member role updated successfully",
            "data": member_out.model_dump(mode="json")
        }
    except ValueError as e:
        error_message = str(e)
        if "not found" in error_message.lower():
            raise HTTPException(status_code=404, detail=error_message)
        elif "access denied" in error_message.lower() or "cannot" in error_message.lower():
            raise HTTPException(status_code=403, detail=error_message)
        else:
            raise HTTPException(status_code=401, detail=error_message)

@router.delete("/project-member", status_code=200, description="Remove a member from a project")
def remove_member(request: Request, payload: MemberRemoveRequest = Body(...), db: Session = Depends(get_db)):
    controller = ProjectMemberController(db)
    token: str | None = None

    token = request.cookies.get(settings.ACCESS_TOKEN_COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=401, detail="Missing access token")

    try:
        member_data = controller.remove_member(payload, token)
        member_out = ProjectMemberResponse.model_validate(member_data)
        return {
            "success": True,
            "message": "Member removed from project successfully",
            "data": member_out.model_dump(mode="json")
        }
    except ValueError as e:
        error_message = str(e)
        if "not found" in error_message.lower():
            raise HTTPException(status_code=404, detail=error_message)
        elif "access denied" in error_message.lower() or "cannot" in error_message.lower():
            raise HTTPException(status_code=403, detail=error_message)
        else:
            raise HTTPException(status_code=401, detail=error_message)

@router.post("/project-member/leave", status_code=200, description="Leave a project")
def leave_project(request: Request, payload: MemberLeaveRequest = Body(...), db: Session = Depends(get_db)):
    controller = ProjectMemberController(db)
    token: str | None = None

    token = request.cookies.get(settings.ACCESS_TOKEN_COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=401, detail="Missing access token")

    try:
        member_data = controller.leave_project(payload, token)
        member_out = ProjectMemberResponse.model_validate(member_data)
        return {
            "success": True,
            "message": "Left project successfully",
            "data": member_out.model_dump(mode="json")
        }
    except ValueError as e:
        error_message = str(e)
        if "not found" in error_message.lower() or "not an active member" in error_message.lower():
            raise HTTPException(status_code=404, detail=error_message)
        elif "access denied" in error_message.lower() or "cannot" in error_message.lower():
            raise HTTPException(status_code=403, detail=error_message)
        else:
            raise HTTPException(status_code=400, detail=error_message)

