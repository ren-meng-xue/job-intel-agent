from datetime import datetime, timedelta, timezone

from app.repositories.auth_repository import AuthRepository
from app.repositories.user_repository import UserRepository


async def test_create_and_get_active_session(db):
    user_repo = UserRepository(db)
    auth_repo = AuthRepository(db)

    user = await user_repo.create_user("dave@example.com", "dave", "hashed_pw")
    expires = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=7)
    session = await auth_repo.create_session(user.id, "token_hash_abc", expires)

    assert session.id is not None

    found = await auth_repo.get_active_session("token_hash_abc")
    assert found is not None
    assert found.user_id == user.id


async def test_get_session_not_found_with_wrong_hash(db):
    auth_repo = AuthRepository(db)
    found = await auth_repo.get_active_session("nonexistent_hash")
    assert found is None


async def test_revoke_session(db):
    user_repo = UserRepository(db)
    auth_repo = AuthRepository(db)

    user = await user_repo.create_user("eve@example.com", "eve", "hashed_pw")
    expires = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=7)
    await auth_repo.create_session(user.id, "revocable_hash", expires)

    session = await auth_repo.get_active_session("revocable_hash")
    await auth_repo.revoke_session(session.id)

    # 撤销后应查不到
    revoked = await auth_repo.get_active_session("revocable_hash")
    assert revoked is None
