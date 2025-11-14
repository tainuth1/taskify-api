from fastapi import APIRouter
from app.api.endpoints import auth
from app.api.endpoints import project
from app.api.endpoints import project_member
from app.api.endpoints import project_invite
from app.api.endpoints import task
from app.api.endpoints import subtask
from app.api.endpoints import comment

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(project.router, tags=["Projects"])
api_router.include_router(project_member.router, tags=["Project Members"])
api_router.include_router(project_invite.router, tags=["Project Invites"])
api_router.include_router(task.router, tags=["Tasks"])
api_router.include_router(subtask.router, tags=["SubTask"])
api_router.include_router(comment.router, tags=["Comments"])