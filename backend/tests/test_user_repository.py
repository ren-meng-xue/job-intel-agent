import pytest

from app.repositories.user_repository import UserRepository


async def test_create_and_get_user_by_email(db):
    repo = UserRepository(db)
    user = await repo.create_user("alice@example.com", "alice", "hashed_pw")
    assert user.id is not None

    found = await repo.get_by_email("alice@example.com")
    assert found is not None
    assert found.username == "alice"


async def test_get_by_email_not_found(db):
    repo = UserRepository(db)
    found = await repo.get_by_email("nonexistent@example.com")
    assert found is None


async def test_get_by_id(db):
    repo = UserRepository(db)
    user = await repo.create_user("bob@example.com", "bob", "hashed_pw")
    found = await repo.get_by_id(user.id)
    assert found is not None
    assert found.email == "bob@example.com"


async def test_get_by_username(db):
    repo = UserRepository(db)
    await repo.create_user("charlie@example.com", "charlie", "hashed_pw")
    found = await repo.get_by_username("charlie")
    assert found is not None
    assert found.email == "charlie@example.com"
