from fastapi import APIRouter, Body, Depends, HTTPException, Request
from sqlalchemy.orm import Session
import uuid

from app.controllers.project_controller import ProjectController
from app.core.config import settings
from app.database import get_db
from app.schemas.project import Project, ProjectCreate, ProjectResponse, ProjectDetailResponse

router = APIRouter()

@router.post("/projects", status_code=201, description="Create a new project")
def create_project(request: Request, payload: ProjectCreate = Body(...), db: Session = Depends(get_db)):
    controller = ProjectController(db)
    token: str | None = None

    token = request.cookies.get(settings.ACCESS_TOKEN_COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=401, detail="Missing access token")

    try:
        project_data = controller.create_project(payload, token)
        project_out = ProjectResponse.model_validate(project_data)
        return {
            "success": True,
            "message": "Create project successfully",
            "data": project_out.model_dump(mode="json")
        }
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))
        
@router.get("/projects", status_code=200, description="Get all projects")
def get_all_projects(request: Request, db: Session = Depends(get_db)):
    controller = ProjectController(db)
    token: str | None = None

    token = request.cookies.get(settings.ACCESS_TOKEN_COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=401, detail="Missing access token")

    try:
        projects_data = controller.get_all_projects(token)
        projects_out = [ProjectResponse.model_validate(project) for project in projects_data]
        return {
            "success": True,
            "message": "Get all projects successfully",
            "data": projects_out
        }
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))

@router.get("/projects/{project_id}", status_code=200, description="Get project by ID")
def get_project_by_id(request: Request, project_id: uuid.UUID, db: Session = Depends(get_db)):
    controller = ProjectController(db)
    token: str | None = None

    token = request.cookies.get(settings.ACCESS_TOKEN_COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=401, detail="Missing access token")

    try:
        project_data = controller.get_project_by_id(token, str(project_id))
        project_out = ProjectDetailResponse.model_validate(project_data)
        return {
            "success": True,
            "message": "Get project successfully",
            "data": project_out.model_dump(mode="json")
        }
    except ValueError as e:
        error_message = str(e)
        if "not found" in error_message.lower():
            raise HTTPException(status_code=404, detail=error_message)
        elif "access denied" in error_message.lower():
            raise HTTPException(status_code=403, detail=error_message)
        else:
            raise HTTPException(status_code=401, detail=error_message)