from fastapi import APIRouter, Body, Depends, HTTPException, Request
from sqlalchemy.orm import Session
import uuid

from app.controllers.comment_controller import CommentController
from app.core.config import settings
from app.database import get_db
from app.schemas.comment import CommentCreate, CommentResponse, CommentUpdate


router = APIRouter()

@router.post("/tasks/{task_id}/comments", status_code=201, description="Create a new comment")
def create_comment(request: Request, task_id: uuid.UUID, payload: CommentCreate = Body(...), db: Session = Depends(get_db)):
    controller = CommentController(db)
    token: str | None = None

    token = request.cookies.get(settings.ACCESS_TOKEN_COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=401, detail="Missing access token")
    
    # Ensure the task_id in path matches the payload
    if payload.tasks_id != task_id:
        raise HTTPException(status_code=400, detail="Task ID in path does not match payload")

    try:
        comment_data = controller.create_comment(payload, token)
        comment_out = CommentResponse.model_validate(comment_data)
        return {
            "success": True,
            "message": "Create comment successfully",
            "data": comment_out.model_dump(mode="json")
        }
    except ValueError as e:
        error_message = str(e)
        if "not found" in error_message.lower():
            raise HTTPException(status_code=404, detail=error_message)
        elif "access denied" in error_message.lower() or "must be a project member" in error_message.lower():
            raise HTTPException(status_code=403, detail=error_message)
        else:
            raise HTTPException(status_code=401, detail=error_message)

@router.get("/tasks/{task_id}/comments", status_code=200, description="Get all comments for a task")
def get_comments_by_task(request: Request, task_id: uuid.UUID, db: Session = Depends(get_db)):
    controller = CommentController(db)
    token: str | None = None

    token = request.cookies.get(settings.ACCESS_TOKEN_COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=401, detail="Missing access token")

    try:
        comments_data = controller.get_comments_by_task(str(task_id), token)
        comments_out = [CommentResponse.model_validate(comment) for comment in comments_data]
        return {
            "success": True,
            "message": "Get comments successfully",
            "data": comments_out
        }
    except ValueError as e:
        error_message = str(e)
        if "not found" in error_message.lower():
            raise HTTPException(status_code=404, detail=error_message)
        elif "access denied" in error_message.lower() or "must be a project member" in error_message.lower():
            raise HTTPException(status_code=403, detail=error_message)
        else:
            raise HTTPException(status_code=401, detail=error_message)

@router.patch("/comments/{comment_id}", status_code=200, description="Update a comment")
def update_comment(request: Request, comment_id: uuid.UUID, payload: CommentUpdate = Body(...), db: Session = Depends(get_db)):
    controller = CommentController(db)
    token: str | None = None

    token = request.cookies.get(settings.ACCESS_TOKEN_COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=401, detail="Missing access token")

    try:
        comment_data = controller.update_comment(str(comment_id), payload, token)
        comment_out = CommentResponse.model_validate(comment_data)
        return {
            "success": True,
            "message": "Update comment successfully",
            "data": comment_out.model_dump(mode="json")
        }
    except ValueError as e:
        error_message = str(e)
        if "not found" in error_message.lower():
            raise HTTPException(status_code=404, detail=error_message)
        elif "can only update" in error_message.lower() or "only" in error_message.lower():
            raise HTTPException(status_code=403, detail=error_message)
        else:
            raise HTTPException(status_code=401, detail=error_message)

@router.delete("/comments/{comment_id}", status_code=200, description="Delete a comment")
def delete_comment(request: Request, comment_id: uuid.UUID, db: Session = Depends(get_db)):
    controller = CommentController(db)
    token: str | None = None

    token = request.cookies.get(settings.ACCESS_TOKEN_COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=401, detail="Missing access token")

    try:
        result = controller.delete_comment(str(comment_id), token)
        return {
            "success": True,
            "message": result["message"],
            "data": result["deleted_comment"]
        }
    except ValueError as e:
        error_message = str(e)
        if "not found" in error_message.lower():
            raise HTTPException(status_code=404, detail=error_message)
        elif "can only delete" in error_message.lower() or "only" in error_message.lower():
            raise HTTPException(status_code=403, detail=error_message)
        else:
            raise HTTPException(status_code=401, detail=error_message)
