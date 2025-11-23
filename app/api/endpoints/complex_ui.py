from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.controllers.complex_ui_controller import ComplexUIController
from app.core.config import settings
from app.database import get_db
from app.schemas.dashboard import DashboardResponse

router = APIRouter() 

@router.get("/dashboard", status_code=200, description="Get dashboard data")
def get_dashboard_data(request: Request, db: Session = Depends(get_db)):
    controller = ComplexUIController(db)
    token: str | None = None

    token = request.cookies.get(settings.ACCESS_TOKEN_COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=401, detail="Missing access token")

    try:
        dashboard_data = controller.get_dashboard_data(token)
        return {
            "success": True,
            "message": "Get dashboard data successfully",
            "data": dashboard_data.model_dump(mode="json")
        }
    except ValueError as e:
        error_message = str(e)
        if "not found" in error_message.lower():
            raise HTTPException(status_code=404, detail=error_message)
        elif "access denied" in error_message.lower():
            raise HTTPException(status_code=403, detail=error_message)
        else:
            raise HTTPException(status_code=401, detail=error_message)