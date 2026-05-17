from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.errors import AppError, ErrorCode
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    LoginResponse,
    RegisterRequest,
    UserInfoResponse,
)
from app.services.auth_service import AuthService, get_current_user

router = APIRouter()


@router.post("/register", response_model=UserInfoResponse, status_code=201)
async def register(payload: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """注册新用户"""
    service = AuthService(db)
    user = await service.register(payload.email, payload.username, payload.password)
    return UserInfoResponse(
        id=user.id,
        email=user.email,
        username=user.username,
        status=user.status,
        email_verified=user.email_verified,
    )


@router.post("/login", response_model=LoginResponse)
async def login(
    payload: LoginRequest, response: Response, db: AsyncSession = Depends(get_db)
):
    """登录，access token 在响应体，refresh token 写入 HttpOnly Cookie"""
    service = AuthService(db)
    login_response, refresh_token = await service.login(payload.email, payload.password)
    response.set_cookie(
        key=settings.REFRESH_TOKEN_COOKIE_NAME,
        value=refresh_token,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite="none",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600,
    )
    return login_response


@router.post("/refresh-token")
async def refresh_token(request: Request, db: AsyncSession = Depends(get_db)):
    """用 Cookie 中的 refresh token 换取新 access token"""
    token = request.cookies.get(settings.REFRESH_TOKEN_COOKIE_NAME)
    if not token:
        raise AppError(ErrorCode.AUTH_TOKEN_MISSING, "未找到 refresh token")
    service = AuthService(db)
    access_token = await service.refresh(token)
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/logout")
async def logout(
    request: Request, response: Response, db: AsyncSession = Depends(get_db)
):
    """登出：撤销 session + 清除 Cookie"""
    token = request.cookies.get(settings.REFRESH_TOKEN_COOKIE_NAME)
    if token:
        service = AuthService(db)
        await service.logout(token)
    response.delete_cookie(settings.REFRESH_TOKEN_COOKIE_NAME)
    return {"message": "已登出"}


@router.get("/me", response_model=UserInfoResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """返回当前登录用户信息"""
    return UserInfoResponse(
        id=current_user.id,
        email=current_user.email,
        username=current_user.username,
        status=current_user.status,
        email_verified=current_user.email_verified,
    )
