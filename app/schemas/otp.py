from pydantic import BaseModel, EmailStr

class ForgotPasswordIn(BaseModel):
    email: EmailStr

class VerifyOtpIn(BaseModel):
    email: EmailStr
    otp: str

class ResetPasswordIn(BaseModel):
    reset_token: str
    new_password: str