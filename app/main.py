from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from app.api.route import api_router
from app.core.limiter import limiter, rate_limit_handler
from app.core.config import settings
from app.database import engine, Base
from sqlalchemy import text
from fastapi.middleware.cors import CORSMiddleware
import cloudinary

# Import models to register them with SQLAlchemy
from app.models.user import User
from app.models.otp import OTP
from app.models.project import Project
from app.models.project_invite import ProjectInvite
from app.models.project_member import ProjectMember
from app.models.task import Task
from app.models.subtask import SubTask
from app.models.comment import Comment
from app.models.task_assignee import TaskAssignee
from app.models.notification import Notification

# This will migrate model into database
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title = settings.PROJECT_NAME,
    description = settings.DESCRIBTION,
    version = settings.VERSION
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_handler)

cloudinary.config(
    cloud_name=settings.CLOUDINARY_CLOUD_NAME,
    api_key=settings.CLOUDINARY_API_KEY,
    api_secret=settings.CLOUDINARY_API_SECRET,
    secure=True
)

app.include_router(api_router, prefix=settings.API_V1_STR)

# CORS Configuration - Only allow your frontend domain
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL],  # Use your frontend URL from settings
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],  # Specify methods instead of "*"
    allow_headers=["Content-Type", "Authorization", "Accept"],  # Specify headers instead of "*"
    expose_headers=["*"],  # Headers your frontend can read
    max_age=3600,  # Cache preflight requests for 1 hour
)

@app.exception_handler(HTTPException)
async def custome_http_exception_error(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "message": exc.detail,
            "data": None,
        }
    )

@app.get("/", tags=["Greet"])
async def root():
    return {"message": "Welcome to Note App"}

@app.get("/health/db", tags=["Check Database Connection"])
async def check_database_connction():
    try:
        with engine.connect() as connection:
            result = connection.execute(text("SELECT 1"))
            result.fetchone()
        return {"status": "connected", "message": "Database connection successful"}
    except Exception as e:
        return {"status": "disconnected", "error": str(e)}