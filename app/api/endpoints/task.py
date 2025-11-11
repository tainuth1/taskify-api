from fastapi import APIRouter, Body, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.controllers.task_controller import TaskController
from app.core.config import settings
from app.database import get_db
from app.schemas.task import TaskCreate, TaskResponse, TaskUpdate
import uuid

from app.schemas.task_assignee import TaskAssignRequest, TaskAssigneeResponse


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

@router.patch("/tasks/{task_id}", status_code=200, description="Update a task (partial)")
def update_task(request: Request, task_id: uuid.UUID, payload: TaskUpdate = Body(...), db: Session = Depends(get_db)):
    controller = TaskController(db)
    token: str | None = None

    token = request.cookies.get(settings.ACCESS_TOKEN_COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=401, detail="Missing access token")
    
    # Ensure the task_id in path matches the payload
    if payload.id != task_id:
        raise HTTPException(status_code=400, detail="Task ID in path does not match payload")

    try:
        task_data = controller.update_task(payload, token)
        task_out = TaskResponse.model_validate(task_data)
        return {
            "success": True,
            "message": "Update task successfully",
            "data": task_out.model_dump(mode="json")
        }
    except ValueError as e:
        error_message = str(e)
        if "not found" in error_message.lower():
            raise HTTPException(status_code=404, detail=error_message)
        elif "access denied" in error_message.lower() or "only" in error_message.lower() or "can only update" in error_message.lower():
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

@router.post("/tasks/{task_id}/assign", status_code=201, description="Assign a task to a user")
def assign_task(request: Request, task_id: uuid.UUID, payload: TaskAssignRequest = Body(...), db: Session = Depends(get_db)):
    controller = TaskController(db)
    token: str | None = None

    token = request.cookies.get(settings.ACCESS_TOKEN_COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=401, detail="Missing access token")

    try:
        assignment_data = controller.assign_task_to_user(token, str(task_id), str(payload.user_id))
        assignment_out = TaskAssigneeResponse.model_validate(assignment_data)
        return {
            "success": True,
            "message": "Task assigned successfully",
            "data": assignment_out.model_dump(mode="json")
        }
    except ValueError as e:
        error_message = str(e)
        if "not found" in error_message.lower():
            raise HTTPException(status_code=404, detail=error_message)
        elif "access denied" in error_message.lower() or "only" in error_message.lower() or "cannot assign" in error_message.lower():
            raise HTTPException(status_code=403, detail=error_message)
        elif "already assigned" in error_message.lower():
            raise HTTPException(status_code=400, detail=error_message)
        else:
            raise HTTPException(status_code=401, detail=error_message)

@router.delete("/tasks/{task_id}/assign/{user_id}", status_code=200, description="Unassign a task from a user")
def unassign_task(request: Request, task_id: uuid.UUID, user_id: uuid.UUID, db: Session = Depends(get_db)):
    controller = TaskController(db)
    token: str | None = None

    token = request.cookies.get(settings.ACCESS_TOKEN_COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=401, detail="Missing access token")

    try:
        result = controller.unassign_task_from_user(token, str(task_id), str(user_id))
        return {
            "success": True,
            "message": result["message"],
            "data": result["unassigned"]
        }
    except ValueError as e:
        error_message = str(e)
        if "not found" in error_message.lower() or "not assigned" in error_message.lower():
            raise HTTPException(status_code=404, detail=error_message)
        elif "access denied" in error_message.lower() or "only" in error_message.lower() or "cannot unassign" in error_message.lower():
            raise HTTPException(status_code=403, detail=error_message)
        else:
            raise HTTPException(status_code=401, detail=error_message)