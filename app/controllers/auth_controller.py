from datetime import datetime, timedelta
import random
from typing import Tuple
from fastapi import File, Form, UploadFile
from jose import ExpiredSignatureError, JWTError, jwt
from sqlalchemy.orm import Session
from sqlalchemy import or_
from app.core.config import settings
from app.core.email import sent_email_brevo
from app.core.security import create_access_token, create_refresh_token, verify_password, get_password_hash
from app.models import OTP, User
from app.schemas.user import UserCreate, UserLogin, User as UserResponse
import cloudinary.uploader

class AuthController:
    def __init__(self, db: Session) -> None:
        self.db = db

    def signup(self, user: UserCreate) -> Tuple[User, str]:
        """
        Create a new user account.
        Args:
            user: UserCreate schema instance
        Returns:
            Tuple[User, str]: The created user and access token
        Raises:
            ValueError: If the email or username is already in use
        """
        email = user.email.lower().strip()
        username = user.username.lower().strip()
        if self.db.query(User).filter(User.email == user.email).first():
            raise ValueError("Email already in use")

        if self.db.query(User).filter(User.username == user.username).first():
            raise ValueError("Username already in use")

        hashed_password = get_password_hash(user.password)
        new_user = User(
            email = email,
            username = username,
            password = hashed_password,
        )

        self.db.add(new_user) # stage the ORM user's object in the session
        self.db.commit() # commit the transaction to the database
        self.db.refresh(new_user) # refresh the ORM user's object in the session

        access_token = create_access_token({"sub": str(new_user.id)})
        refresh_token = create_refresh_token({"sub": str(new_user.id)})

        return new_user, access_token, refresh_token

    def signin(self, user: UserLogin) -> Tuple[User, str]:
        """
        Sign in a user.
        Args:
            user: UserLogin schema instance
        Returns:
            Tuple[User, str, str]: The signed user and access token and refresh token
        Raises:
            ValueError: If the email is incorrect or password is incorrect or account is inactive
        """
        email = user.email.lower().strip()
        password = user.password

        login_user = self.db.query(User).filter(User.email == email).first()
        if login_user is None:
            raise ValueError("Incorrect email or password")

        if not login_user.is_active:
            raise ValueError("Account is inactive")

        if not verify_password(password, login_user.password):
            raise ValueError("Incorrect email or password")

        access_token = create_access_token({"sub": str(login_user.id)})
        refresh_token = create_refresh_token({"sub": str(login_user.id)})

        return login_user, access_token, refresh_token
        
    def get_current_user(self, token: str):
        """
        Get the current user from the access token.
        Args:
            token: str
        Returns:
            UserResponse: The current user
        Raises:
            ValueError: If the token is expired or invalid or token type is not access
        """
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        except ExpiredSignatureError:
            raise ValueError("Token has expired")
        except JWTError:
            raise ValueError("Invalid token")

        if payload.get("type") != "access":
            raise ValueError("Invalid token type")

        sub = payload["sub"]
        user = self.db.query(User).filter(User.id == sub).first()
    
        if not user:
            raise ValueError("User not found")
        if not user.is_active:
            raise ValueError("User is in active")

        return user

    async def update_profile(self, email: str = Form(...), username: str = Form(...), full_name: str = Form(...), profile: UploadFile = File(None), token: str = ""):
        """
        Update the current user's profile information, including email, username, full name, and profile image.

        Args:
            email (str): New email address for the user.
            username (str): New username for the user.
            full_name (str): New full name for the user.
            profile (UploadFile, optional): Profile image file (JPEG, PNG, GIF, or WebP, up to 5MB).
            token (str): JWT access token identifying the user.

        Returns:
            user (User): The updated user object.

        Raises:
            ValueError: If the token is expired, invalid, or not an access token.
            ValueError: If the user is not found.
            ValueError: If the profile image type or size is invalid, or if image upload fails.
            ValueError: If saving the updated information to the database fails.
            ValueError: For unexpected errors encountered during the update process.
        """
        try:
            try:
                payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
            except ExpiredSignatureError:
                raise ValueError("Token has expired")
            except JWTError:
                raise ValueError("Invalid token")

            if payload.get("type") != "access":
                raise ValueError("Invalid token type")

            user_id = payload.get("sub")
            user = self.db.query(User).filter(User.id == user_id).first()
            if not user:
                raise ValueError("User not found")

            email_norm = email.lower().strip()
            username_norm = username.lower().strip()

            exists = (
                self.db.query(User.id)
                .filter(User.id != user_id)
                .filter(or_(User.username == username_norm, User.email == email_norm))
                .first()
            )
            if exists:
                raise ValueError("Email or username already exist")

            user.email = email
            user.username = username
            user.full_name = full_name
            user.updated_at = datetime.now()

            if profile is not None:
                try:
                    if profile.content_type not in ["image/jpeg", "image/png", "image/gif", "image/webp"]:
                        raise ValueError("Invalid file type. Only JPEG, PNG, GIF, and WebP images are allowed.")
                    
                    content = await profile.read()
                    if len(content) > 5 * 1024 * 1024:  # 5MB in bytes
                        raise ValueError("File size too large. Maximum size is 5MB.")
                    
                    upload_result = cloudinary.uploader.upload(
                        content,
                        folder="profiles",
                        resource_type="image",
                        overwrite=True
                    )
                    
                    if not upload_result or "secure_url" not in upload_result:
                        raise ValueError("Failed to upload image to cloud storage")
                    
                    user.profile = upload_result["secure_url"]
                    
                except Exception as e:
                    self.db.rollback()
                    raise ValueError(f"Profile image upload failed: {str(e)}")

            try:
                self.db.commit()
                self.db.refresh(user)
            except Exception as e:
                self.db.rollback()
                raise ValueError(f"Failed to update user profile in database: {str(e)}")

            return user

        except ValueError as e:
            raise e
        except Exception as e:
            raise ValueError(f"Unexpected error occurred while updating profile: {str(e)}")

    def request_password_reset(self, email: str):
        email = email.lower().strip()
        user = self.db.query(User).filter(User.email == email).first()
        if not user:
            raise ValueError("Email not found")

        self.db.query(OTP).filter(OTP.email == email).delete()

        code = f"{random.randint(0, 999999):06d}"
        print(code)
        otp_hashed = get_password_hash(code)
        expires_at = datetime.utcnow() + timedelta(minutes=settings.OTP_EXPIRE_MINUTES)

        otp = OTP(email=email, otp_hash=otp_hashed, expires_at=expires_at, is_verified=False)
        self.db.add(otp)
        self.db.commit()        

        subject = "Your password reset code"
        html = f"""
            <p>Hello,</p>
            <p>Your password reset code is:</p>
            <h2 style="letter-spacing:4px">{code}</h2>
            <p>This code will expire in {settings.OTP_EXPIRE_MINUTES} minutes.</p>
            <p>If you didn't request this, you can ignore this email.</p>
        """
        sent_email_brevo(email, subject, html)

    def verify_otp_issue_reset_password(self, email: str, otp_code: str):
        email = email.lower().strip()
        user = self.db.query(User).filter(User.email == email).first()
        if not user:
            raise ValueError("Invalid OTP or expired")

        otp_row = (self.db.query(OTP).filter(OTP.email == email).order_by(OTP.created_at.desc()).first())
        if not otp_row:
            raise ValueError("Invalid OTP or expired")
        
        if datetime.utcnow() > otp_row.expires_at:
            self.db.delete(otp_row)
            self.db.commit()
            raise ValueError("OTP expired")

        if not verify_password(otp_code, otp_row.otp_hash):
            raise ValueError("Invalid OTP")

        otp_row.is_verified = True
        self.db.commit()

        exp = datetime.utcnow() + timedelta(minutes=settings.RESET_PASSWORD_TOKEN_EXPIRE_MINUTES)
        payload = {
            "sub": str(user.id),
            "email": email,
            "type": "password_reset",
            "exp": exp,
        }
        reset_token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
        return reset_token

    def reset_password_with_token(self, reset_token: str, new_password):
        try:
            payload = jwt.decode(reset_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        except ExpiredSignatureError:
            raise ValueError("Reset token expired")
        except JWTError:
            raise ValueError("Invalid reset token")

        if payload.get("type") != "password_reset":
            raise ValueError("Invalid reset token")

        user_id = payload.get("sub")
        email = payload.get("email")
        user = self.db.query(User).filter(User.id == user_id, User.email == email).first()
        if not user:
            raise ValueError("Invalid reset token")

        self.db.query(OTP).filter(OTP.email == email).delete()

        user.password = get_password_hash(new_password)
        user.updated_at = datetime.now()
        self.db.commit()