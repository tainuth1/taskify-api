from fastapi import APIRouter, Body, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.controllers.task_controller import TaskController
from app.core.config import settings
from app.database import get_db
from app.schemas.task import TaskCreate, TaskResponse
import uuid


router = APIRouter()

@router.post("/tasks", status_code=201, description="Create a new task")
def create_task(request: Request, payload: TaskCreate = Body(...), db: Session = Depends(get_db)):
    controller = TaskController(db)
    token: str | None = None

    token = request.cookies.get(settings.ACCESS_TOKEN_COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=401, detail="Missing access token")

    try:
        task_data = controller.create_task(payload, token)
        task_out = TaskResponse.model_validate(task_data)
        return {
            "success": True,
            "message": "Create task successfully",
            "data": task_out.model_dump(mode="json")
        }
    except ValueError as e:
        error_message = str(e)
        if "not found" in error_message.lower():
            raise HTTPException(status_code=404, detail=error_message)
        elif "access denied" in error_message.lower() or "only" in error_message.lower():
            raise HTTPException(status_code=403, detail=error_message)
        else:
            raise HTTPException(status_code=401, detail=error_message)

@router.get("/tasks", status_code=200, description="Get all tasks accessible to the user")
def get_all_tasks(request: Request, db: Session = Depends(get_db)):
    controller = TaskController(db)
    token: str | None = None

    token = request.cookies.get(settings.ACCESS_TOKEN_COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=401, detail="Missing access token")

    try:
        tasks_data = controller.get_all_tasks(token)
        tasks_out = [TaskResponse.model_validate(task) for task in tasks_data]
        return {
            "success": True,
            "message": "Get all tasks successfully",
            "data": tasks_out
        }
    except ValueError as e:
        error_message = str(e)
        if "not found" in error_message.lower():
            raise HTTPException(status_code=404, detail=error_message)
        elif "access denied" in error_message.lower():
            raise HTTPException(status_code=403, detail=error_message)
        else:
            raise HTTPException(status_code=401, detail=error_message)

@router.get("/tasks/project/{project_id}", status_code=200, description="Get all tasks for a specific project")
def get_tasks_by_project(request: Request, project_id: uuid.UUID, db: Session = Depends(get_db)):
    controller = TaskController(db)
    token: str | None = None

    token = request.cookies.get(settings.ACCESS_TOKEN_COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=401, detail="Missing access token")

    try:
        tasks_data = controller.get_tasks_by_project(token, str(project_id))
        tasks_out = [TaskResponse.model_validate(task) for task in tasks_data]
        return {
            "success": True,
            "message": "Get project tasks successfully",
            "data": tasks_out
        }
    except ValueError as e:
        error_message = str(e)
        if "not found" in error_message.lower():
            raise HTTPException(status_code=404, detail=error_message)
        elif "access denied" in error_message.lower():
            raise HTTPException(status_code=403, detail=error_message)
        else:
            raise HTTPException(status_code=401, detail=error_message)

@router.get("/tasks/{task_id}", status_code=200, description="Get a task by ID")
def get_task_by_id(request: Request, task_id: uuid.UUID, db: Session = Depends(get_db)):
    controller = TaskController(db)
    token: str | None = None

    token = request.cookies.get(settings.ACCESS_TOKEN_COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=401, detail="Missing access token")

    try:
        task_data = controller.get_task_by_id(token, str(task_id))
        task_out = TaskResponse.model_validate(task_data)
        return {
            "success": True,
            "message": "Get task successfully",
            "data": task_out.model_dump(mode="json")
        }
    except ValueError as e:
        error_message = str(e)
        if "not found" in error_message.lower():
            raise HTTPException(status_code=404, detail=error_message)
        elif "access denied" in error_message.lower():
            raise HTTPException(status_code=403, detail=error_message)
        else:
            raise HTTPException(status_code=401, detail=error_message)

@router.delete("/tasks/{task_id}", status_code=200, description="Delete a task")
def delete_task(request: Request, task_id: uuid.UUID, db: Session = Depends(get_db)):
    controller = TaskController(db)
    token: str | None = None

    token = request.cookies.get(settings.ACCESS_TOKEN_COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=401, detail="Missing access token")

    try:
        result = controller.delete_task(token, str(task_id))
        return {
            "success": True,
            "message": result["message"],
            "data": result["deleted_task"]
        }
    except ValueError as e:
        error_message = str(e)
        if "not found" in error_message.lower():
            raise HTTPException(status_code=404, detail=error_message)
        elif "access denied" in error_message.lower() or "only" in error_message.lower() or "can only delete" in error_message.lower():
            raise HTTPException(status_code=403, detail=error_message)
        else:
            raise HTTPException(status_code=401, detail=error_message)