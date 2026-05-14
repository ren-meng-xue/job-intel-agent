from pydantic import BaseModel, EmailStr


class RegisterRequest(BaseModel):
    """注册请求体"""

    email: EmailStr
    username: str
    password: str


class LoginRequest(BaseModel):
    """登录请求体"""

    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    """登录成功响应，access token + 用户基本信息"""

    access_token: str
    token_type: str = "bearer"
    user_id: str
    email: str
    username: str


class UserInfoResponse(BaseModel):
    """当前用户信息响应"""

    id: str
    email: str
    username: str
    status: str
    email_verified: bool
