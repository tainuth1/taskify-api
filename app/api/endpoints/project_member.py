from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db


router = APIRouter()

@router.post("/project-member", status_code=201, description="Create a new project member")
def create_project_member(payload, db: Session = Depends(get_db)):
    pass