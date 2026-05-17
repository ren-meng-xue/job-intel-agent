from datetime import datetime, timedelta, timezone

from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.errors import AppError, ErrorCode
from app.core.security import (
    create_access_token,
    decode_access_token,
    generate_refresh_token,
    hash_password,
    hash_token,
    verify_password,
)
from app.models.user import User
from app.repositories.auth_repository import AuthRepository
from app.repositories.user_repository import UserRepository
from app.schemas.auth import LoginResponse


class AuthService:
    """Auth 业务逻辑：注册、登录、刷新、登出"""

    def __init__(self, db: AsyncSession) -> None:
        self.user_repo = UserRepository(db)
        self.auth_repo = AuthRepository(db)

    async def register(self, email: str, username: str, password: str) -> User:
        """注册新用户，email/username 唯一性检查"""
        if await self.user_repo.get_by_email(email):
            raise AppError(ErrorCode.ALREADY_EXISTS, "邮箱已被注册")
        if await self.user_repo.get_by_username(username):
            raise AppError(ErrorCode.ALREADY_EXISTS, "用户名已被占用")
        password_hash = hash_password(password)
        return await self.user_repo.create_user(email, username, password_hash)

    async def login(self, email: str, password: str) -> tuple[LoginResponse, str]:
        """验证密码，返回 (LoginResponse, refresh_token 明文)"""
        user = await self.user_repo.get_by_email(email)

        # 检查账户是否被锁定
        if user and user.locked_until and user.locked_until > datetime.now(timezone.utc).replace(tzinfo=None):
            remaining = int((user.locked_until - datetime.now(timezone.utc).replace(tzinfo=None)).total_seconds() / 60) + 1
            raise AppError(
                ErrorCode.RATE_LIMITED,
                f"账户已被临时锁定，请 {remaining} 分钟后重试",
            )

        if not user or not verify_password(password, user.password_hash):
            if user:
                user.failed_login_count = (user.failed_login_count or 0) + 1
                if user.failed_login_count >= 5:
                    user.locked_until = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(minutes=15)
                await self.user_repo.session.commit()
            raise AppError(ErrorCode.AUTH_CREDENTIALS_WRONG, "邮箱或密码错误")

        # 登录成功，重置失败计数并更新登录时间
        user.failed_login_count = 0
        user.locked_until = None
        user.last_login_at = datetime.now(timezone.utc).replace(tzinfo=None)
        await self.user_repo.session.commit()

        access_token = create_access_token({"sub": user.id})
        refresh_token_plain = generate_refresh_token()
        expires_at = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        await self.auth_repo.create_session(
            user.id, hash_token(refresh_token_plain), expires_at
        )

        response = LoginResponse(
            access_token=access_token,
            user_id=user.id,
            email=user.email,
            username=user.username,
        )
        return response, refresh_token_plain

    async def refresh(self, refresh_token_plain: str) -> str:
        """用 refresh token 换新 access token"""
        token_hash = hash_token(refresh_token_plain)
        auth_session = await self.auth_repo.get_active_session(token_hash)
        if not auth_session:
            raise AppError(ErrorCode.AUTH_REFRESH_INVALID, "refresh token 无效或已过期")
        user = await self.user_repo.get_by_id(auth_session.user_id)
        if not user:
            raise AppError(ErrorCode.AUTH_TOKEN_INVALID, "用户不存在")
        return create_access_token({"sub": user.id})

    async def logout(self, refresh_token_plain: str) -> None:
        """撤销 refresh token 对应的 session"""
        token_hash = hash_token(refresh_token_plain)
        auth_session = await self.auth_repo.get_active_session(token_hash)
        if auth_session:
            await self.auth_repo.revoke_session(auth_session.id)


async def get_user_by_raw_token(token: str, db: AsyncSession) -> User:
    """根据 access token 字符串解析并返回用户，供 SSE / WebSocket 等无 header 场景使用"""
    payload = decode_access_token(token)
    if not payload:
        raise AppError(ErrorCode.AUTH_TOKEN_INVALID, "token 无效或已过期")
    user_repo = UserRepository(db)
    user = await user_repo.get_by_id(payload["sub"])
    if not user:
        raise AppError(ErrorCode.AUTH_TOKEN_INVALID, "用户不存在")
    return user


async def get_current_user(
    authorization: str | None = Header(None),
    db: AsyncSession = Depends(get_db),
) -> User:
    """FastAPI 依赖：从 Authorization: Bearer <token> 中解析并返回当前用户"""
    if not authorization or not authorization.startswith("Bearer "):
        raise AppError(ErrorCode.AUTH_TOKEN_MISSING, "未提供认证 token")
    return await get_user_by_raw_token(authorization[7:], db)
