import uuid
from fastapi import APIRouter, Body, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.controllers.subtask_controller import SubTaskController
from app.core.config import settings
from app.database import get_db
from app.schemas.subtask import SubTaskCreate, SubTaskResponse, SubTaskStatusUpdate, SubTaskUpdate


router = APIRouter()

@router.post("/tasks/subtasks", status_code=201, description="Create a new sub task")
def create_task(request: Request, payload: SubTaskCreate = Body(...), db: Session = Depends(get_db)):
    controller = SubTaskController(db)
    token: str | None = None

    token = request.cookies.get(settings.ACCESS_TOKEN_COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=401, detail="Missing access token")
    
    try:
        subtask_data = controller.create_subtask(payload, token)
        subtask_out = SubTaskResponse.model_validate(subtask_data)
        return {
            "success": True,
            "message": "Create subtask successfully",
            "data": subtask_out.model_dump(mode="json")
        }
    except ValueError as e:
        error_message = str(e)
        if "not found" in error_message.lower():
            raise HTTPException(status_code=404, detail=error_message)
        elif "access denied" in error_message.lower() or "only" in error_message.lower():
            raise HTTPException(status_code=403, detail=error_message)
        else:
            raise HTTPException(status_code=401, detail=error_message)

@router.get("/tasks/{task_id}/subtasks", status_code=200, description="Get all subtasks for a task")
def get_subtasks_by_task(request: Request, task_id: uuid.UUID, db: Session = Depends(get_db)):
    controller = SubTaskController(db)
    token: str | None = None

    token = request.cookies.get(settings.ACCESS_TOKEN_COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=401, detail="Missing access token")

    try:
        subtasks_data = controller.get_subtasks_by_task(str(task_id), token)
        subtasks_out = [SubTaskResponse.model_validate(subtask) for subtask in subtasks_data]
        return {
            "success": True,
            "message": "Get subtasks successfully",
            "data": subtasks_out
        }
    except ValueError as e:
        error_message = str(e)
        if "not found" in error_message.lower():
            raise HTTPException(status_code=404, detail=error_message)
        elif "access denied" in error_message.lower() or "must be a project member" in error_message.lower():
            raise HTTPException(status_code=403, detail=error_message)
        else:
            raise HTTPException(status_code=401, detail=error_message)

@router.patch("/tasks/subtasks/{subtask_id}", status_code=200, description="Update a subtask (partial)")
def update_subtask(request: Request, subtask_id: uuid.UUID, payload: SubTaskUpdate = Body(...), db: Session = Depends(get_db)):
    controller = SubTaskController(db)
    token: str | None = None

    token = request.cookies.get(settings.ACCESS_TOKEN_COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=401, detail="Missing access token")
    
    # Ensure the subtask_id in path matches the payload
    if payload.id != subtask_id:
        raise HTTPException(status_code=400, detail="Subtask ID in path does not match payload")
    
    try:
        subtask_data = controller.update_subtask(payload, token)
        subtask_out = SubTaskResponse.model_validate(subtask_data)
        return {
            "success": True,
            "message": "Update subtask successfully",
            "data": subtask_out.model_dump(mode="json")
        }
    except ValueError as e:
        error_message = str(e)
        if "not found" in error_message.lower():
            raise HTTPException(status_code=404, detail=error_message)
        elif "access denied" in error_message.lower() or "only" in error_message.lower():
            raise HTTPException(status_code=403, detail=error_message)
        else:
            raise HTTPException(status_code=401, detail=error_message)

@router.patch("/tasks/subtasks/{subtask_id}/status", status_code=200, description="Update subtask status only")
def update_subtask_status(request: Request, subtask_id: uuid.UUID, payload: SubTaskStatusUpdate = Body(...), db: Session = Depends(get_db)):
    controller = SubTaskController(db)
    token: str | None = None

    token = request.cookies.get(settings.ACCESS_TOKEN_COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=401, detail="Missing access token")
    
    # Ensure the subtask_id in path matches the payload
    if payload.subtask_id != subtask_id:
        raise HTTPException(status_code=400, detail="Subtask ID in path does not match payload")

    try:
        subtask_data = controller.update_subtask_status(str(subtask_id), payload.status, token)
        subtask_out = SubTaskResponse.model_validate(subtask_data)
        return {
            "success": True,
            "message": "Subtask status updated successfully",
            "data": subtask_out.model_dump(mode="json")
        }
    except ValueError as e:
        error_message = str(e)
        if "not found" in error_message.lower():
            raise HTTPException(status_code=404, detail=error_message)
        elif "access denied" in error_message.lower() or "only" in error_message.lower() or "can only update" in error_message.lower() or "members can only" in error_message.lower() or "viewers cannot" in error_message.lower():
            raise HTTPException(status_code=403, detail=error_message)
        else:
            raise HTTPException(status_code=401, detail=error_message)

@router.delete("/tasks/subtasks/{subtask_id}", status_code=200, description="Delete a subtask")
def delete_subtask(request: Request, subtask_id: uuid.UUID, db: Session = Depends(get_db)):
    controller = SubTaskController(db)
    token: str | None = None

    token = request.cookies.get(settings.ACCESS_TOKEN_COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=401, detail="Missing access token")

    try:
        result = controller.delete_subtask(token, str(subtask_id))
        return {
            "success": True,
            "message": result["message"],
            "data": result["deleted_subtask"]
        }
    except ValueError as e:
        error_message = str(e)
        if "not found" in error_message.lower():
            raise HTTPException(status_code=404, detail=error_message)
        elif "access denied" in error_message.lower() or "only" in error_message.lower() or "can only delete" in error_message.lower():
            raise HTTPException(status_code=403, detail=error_message)
        else:
            raise HTTPException(status_code=401, detail=error_message)

