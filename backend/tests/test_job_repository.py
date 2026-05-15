import pytest

from app.models.user import User
from app.repositories.job_repository import JobRepository


@pytest.fixture
async def user(db):
    """创建测试用户，Job 需要 user_id FK"""
    u = User(id="u-1", email="t@example.com", username="testuser", password_hash="h")
    db.add(u)
    await db.commit()
    return u


async def test_create_job_returns_job_with_parsing_status(db, user):
    repo = JobRepository(db)
    job = await repo.create_job(url="https://example.com/job", user_id=user.id)
    assert job.id is not None
    assert job.url == "https://example.com/job"
    assert job.status == "parsing"
    assert job.user_id == user.id


async def test_create_job_with_resume_id(db, user):
    repo = JobRepository(db)
    job = await repo.create_job(
        url="https://example.com/job", user_id=user.id, resume_id="r-1"
    )
    assert job.resume_id == "r-1"


async def test_get_by_id_returns_job(db, user):
    repo = JobRepository(db)
    job = await repo.create_job(url="https://example.com/job", user_id=user.id)
    fetched = await repo.get_by_id(job.id)
    assert fetched.id == job.id


async def test_get_by_id_returns_none_for_missing(db):
    repo = JobRepository(db)
    result = await repo.get_by_id("nonexistent-id")
    assert result is None


async def test_update_after_parse_updates_all_fields(db, user):
    repo = JobRepository(db)
    job = await repo.create_job(url="https://example.com/job", user_id=user.id)
    await repo.update_after_parse(
        job.id,
        raw_content="## JD\n...",
        title="Software Engineer",
        company="Acme",
        requirements=["Python", "FastAPI"],
        jd_summary="A great role.",
        salary_range="25k-40k",
        location="上海",
        work_type="hybrid",
    )
    updated = await repo.get_by_id(job.id)
    assert updated.status == "awaiting_confirm"
    assert updated.title == "Software Engineer"
    assert updated.company == "Acme"
    assert updated.requirements == ["Python", "FastAPI"]
    assert updated.jd_summary == "A great role."
    assert updated.raw_content == "## JD\n..."
    assert updated.salary_range == "25k-40k"
    assert updated.location == "上海"
    assert updated.work_type == "hybrid"


async def test_update_after_parse_nullable_fields_can_be_none(db, user):
    """salary_range / location / work_type 不在 JD 里时可以为 None"""
    repo = JobRepository(db)
    job = await repo.create_job(url="https://example.com/job", user_id=user.id)
    await repo.update_after_parse(
        job.id,
        raw_content="## JD\n...",
        title="Engineer",
        company="Co",
        requirements=["Python"],
        jd_summary="A role.",
    )
    updated = await repo.get_by_id(job.id)
    assert updated.salary_range is None
    assert updated.location is None
    assert updated.work_type is None


async def test_update_status(db, user):
    repo = JobRepository(db)
    job = await repo.create_job(url="https://example.com/job", user_id=user.id)
    await repo.update_status(job.id, "failed")
    updated = await repo.get_by_id(job.id)
    assert updated.status == "failed"
