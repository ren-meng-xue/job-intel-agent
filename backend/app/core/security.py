import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
from jose import JWTError, jwt

from app.core.config import settings


def hash_password(plain: str) -> str:
    """对明文密码做 bcrypt 哈希"""
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    """验证明文密码与哈希是否匹配"""
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """生成 HS256 JWT access token"""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_access_token(token: str) -> dict | None:
    """解码 JWT；过期或签名错误返回 None"""
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        return None


def generate_refresh_token() -> str:
    """生成 64 字节 URL-safe 随机串作为 refresh token 明文"""
    return secrets.token_urlsafe(64)


def hash_token(token: str) -> str:
    """SHA256 哈希 token 后存 DB，避免明文泄露"""
    return hashlib.sha256(token.encode()).hexdigest()
