from fastapi import APIRouter, Body, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.controllers.task_controller import TaskController
from app.core.config import settings
from app.database import get_db
from app.schemas.task import TaskCreate, TaskResponse


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