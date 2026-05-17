import pytest

from app.core.errors import AppError, ErrorCode
from app.services.auth_service import AuthService


async def test_register_creates_user(db):
    service = AuthService(db)
    user = await service.register("frank@example.com", "frank", "password123")
    assert user.email == "frank@example.com"
    assert user.password_hash != "password123"  # 已哈希，非明文


async def test_register_duplicate_email_raises(db):
    service = AuthService(db)
    await service.register("grace@example.com", "grace", "password123")
    with pytest.raises(AppError) as exc:
        await service.register("grace@example.com", "grace2", "password456")
    assert exc.value.code == ErrorCode.ALREADY_EXISTS
    assert exc.value.status_code == 409


async def test_register_duplicate_username_raises(db):
    service = AuthService(db)
    await service.register("henry@example.com", "henry", "password123")
    with pytest.raises(AppError) as exc:
        await service.register("henry2@example.com", "henry", "password456")
    assert exc.value.code == ErrorCode.ALREADY_EXISTS
    assert exc.value.status_code == 409


async def test_login_success_returns_tokens(db):
    service = AuthService(db)
    await service.register("ivan@example.com", "ivan", "mypassword")
    response, refresh_token = await service.login("ivan@example.com", "mypassword")
    assert response.access_token
    assert response.email == "ivan@example.com"
    assert refresh_token  # 明文 refresh token


async def test_login_wrong_password_raises(db):
    service = AuthService(db)
    await service.register("julia@example.com", "julia", "correct")
    with pytest.raises(AppError) as exc:
        await service.login("julia@example.com", "wrong")
    assert exc.value.code == ErrorCode.AUTH_CREDENTIALS_WRONG
    assert exc.value.status_code == 401


async def test_refresh_returns_new_access_token(db):
    service = AuthService(db)
    await service.register("kevin@example.com", "kevin", "password")
    _, refresh_token = await service.login("kevin@example.com", "password")
    new_access_token = await service.refresh(refresh_token)
    assert new_access_token


async def test_logout_invalidates_refresh_token(db):
    service = AuthService(db)
    await service.register("laura@example.com", "laura", "password")
    _, refresh_token = await service.login("laura@example.com", "password")
    await service.logout(refresh_token)
    # 登出后 refresh 应抛 401
    with pytest.raises(AppError) as exc:
        await service.refresh(refresh_token)
    assert exc.value.code == ErrorCode.AUTH_REFRESH_INVALID
    assert exc.value.status_code == 401
