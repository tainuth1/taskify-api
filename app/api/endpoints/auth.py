from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import clear_token_cookies, create_access_token, create_refresh_token, set_token_cookies
from app.database import get_db
from app.schemas.otp import ForgotPasswordIn, ResetPasswordIn, VerifyOtpIn
from app.schemas.user import UserCreate, UserLogin, User
from app.controllers.auth_controller import AuthController
from app.core.limiter import limiter

router = APIRouter() 

@router.post("/refresh", status_code=200, description="Refresh Access Token")
# @limiter.limit("30/minute")
def refresh_token(request: Request):
    try:
        refresh_token = request.cookies.get(settings.REFRESH_TOKEN_COOKIE_NAME)
        if not refresh_token:
            raise HTTPException(status_code=401, detail="Missing refresh token")

        payload = jwt.decode(refresh_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=400, detail="Invalid token type")
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=400, detail="Invalid token")
        
        # create new access token
        new_access_token = create_access_token({"sub": user_id, "type": "access"})
        # rotate the refresh token
        new_refresh_token = create_refresh_token({"sub": user_id, "type": "refresh"})

        response = JSONResponse(
            content = {
                "success": True,
                "message": "Refresh token successfully",
                "data": {"token_type": "bearer"}
            }
        )

        set_token_cookies(response, new_access_token, new_refresh_token)
        return response
    except JWTError as e:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

@router.post("/signin", status_code=200, description="Signed User In")
# @limiter.limit("5/minute")
def signin(request: Request, user: UserLogin, db: Session = Depends(get_db)):
    controller = AuthController(db)
    try:
        login_user, access_token, refresh_token = controller.signin(user)
        user_out = User.model_validate(login_user)
        
        response = JSONResponse(
            content = {
                "success": True,
                "message": "Signin successfully.",
                "data": user_out.model_dump(mode="json"),
                "token_type": "bearer"
            }
        )

        set_token_cookies(response, access_token, refresh_token)
        return response
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))

@router.post("/signup", status_code=201, description="Create User Account")
# @limiter.limit("5/hour")
async def signup(request: Request, user: UserCreate, db: Session = Depends(get_db)):
    controller = AuthController(db)
    
    try:
        created_user, access_token, refresh_token = controller.signup(user)
        # converts the SQLAlchemy User ORM instance into pydantic User schema instance.
        user_out = User.model_validate(created_user)
        
        response = JSONResponse(
            content = {
                "success": True,
                "message": "Registered successfully",
                "data": user_out.model_dump(mode="json"),
                "token_type": "bearer"
            }
        )

        set_token_cookies(response, access_token, refresh_token)
        return response
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/me", status_code=200, description="Get User Data")
# @limiter.limit("60/minute")
def me(request: Request, db: Session = Depends(get_db)):
    controller = AuthController(db)
    token: str | None = None

    # Try cookie first (preferred method)
    token = request.cookies.get(settings.ACCESS_TOKEN_COOKIE_NAME)
    
    if not token:
        raise HTTPException(status_code=401, detail="Missing access token")
    try:
        user_data = controller.get_current_user(token)
        user_out = User.model_validate(user_data)
        return {
            "success": True,
            "message": "Get profile is successfully",
            "data": user_out.model_dump(mode="json")
        }
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))

@router.patch("/update", status_code=200, description="Update Profile")
# @limiter.limit("10/hour")
async def update_profile(
    request: Request, 
    email: str = Form(...), 
    username: str = Form(...),
    full_name: str = Form(...),
    profile: UploadFile = File(None),
    db: Session = Depends(get_db)
):
    controller = AuthController(db)
    token: str | None = None
    token = request.cookies.get(settings.ACCESS_TOKEN_COOKIE_NAME)

    if not token:
        raise HTTPException(status_code=401, detail="Missing access token")

    try:
        updated_profile = await controller.update_profile(email, username, full_name, profile, token)
        profile_data_out = User.model_validate(updated_profile)
        return {
            "success": True,
            "message": "Update profile successfully",
            "data": profile_data_out.model_dump(mode="json")
        }
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))

@router.post("/signout", status_code=200)
# @limiter.limit("30/minute")
def signout(request: Request):
    response = JSONResponse(
        content={"success": True, "message": "Signed out"}
    )
    clear_token_cookies(response)
    return response

@router.post("/forgot-password", status_code=200, description="Request OTP for change password")
# @limiter.limit("3/hour")
def forgot_password(request: Request, payload: ForgotPasswordIn, db: Session = Depends(get_db)):
    controller = AuthController(db)
    try:
        controller.request_password_reset(payload.email)
        return {
            "success":  True,
            "message": "OTP code has been sent to your email address.",
            "data": None
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.post("/verify-otp", status_code=200, description="Verify OTP")
# @limiter.limit("5/minute")
def verify_otp(request: Request, payload: VerifyOtpIn, db: Session = Depends(get_db)):
    controller = AuthController(db)
    try:
        reset_token = controller.verify_otp_issue_reset_password(payload.email, payload.otp)
        return {
            "success": True,
            "message": "OTP verified. Use reset_token to set a new password.",
            "data": {"reset_token": reset_token}
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/reset-password", status_code=200, description="Reset Password")
# @limiter.limit("5/hour")
def reset_password(request: Request, payload: ResetPasswordIn, db: Session = Depends(get_db)):
    controller = AuthController(db)
    try:
        controller.reset_password_with_token(payload.reset_token, payload.new_password)
        return {
            "success": True,
            "message": "Password has been reset successfully",
            "data": None
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))