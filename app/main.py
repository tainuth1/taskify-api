from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from app.api.route import api_router
from app.core.config import settings
from app.database import engine, Base
from sqlalchemy import text
from fastapi.middleware.cors import CORSMiddleware
import cloudinary

# Import models to register them with SQLAlchemy
from app.models.user import User
from app.models.otp import OTP

# This will migrate model into database
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title = settings.PROJECT_NAME,
    description = settings.DESCRIBTION,
    version = settings.VERSION
)

cloudinary.config(
    cloud_name=settings.CLOUDINARY_CLOUD_NAME,
    api_key=settings.CLOUDINARY_API_KEY,
    api_secret=settings.CLOUDINARY_API_SECRET,
    secure=True
)

app.include_router(api_router, prefix=settings.API_V1_STR)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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