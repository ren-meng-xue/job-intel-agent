"""seed default admin user

Revision ID: 56a8a00d0ccf
Revises: b3c4d5e6f7a8
Create Date: 2026-06-05 19:28:48.457846
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


import uuid
from datetime import datetime, timezone
from app.core.security import hash_password

revision: str = '56a8a00d0ccf'
down_revision: Union[str, None] = 'b3c4d5e6f7a8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 检查是否已存在该邮箱的用户
    bind = op.get_bind()
    result = bind.execute(sa.text("SELECT id FROM users WHERE email = 'admin@admin.com'")).fetchone()
    if not result:
        password_hash = hash_password("admin123")
        user_id = str(uuid.uuid4())
        created_at = datetime.now(timezone.utc).replace(tzinfo=None)
        bind.execute(
            sa.text(
                "INSERT INTO users (id, email, username, password_hash, status, email_verified, failed_login_count, created_at) "
                "VALUES (:id, :email, :username, :password_hash, :status, :email_verified, :failed_login_count, :created_at)"
            ),
            {
                "id": user_id,
                "email": "admin@admin.com",
                "username": "admin",
                "password_hash": password_hash,
                "status": "active",
                "email_verified": True,
                "failed_login_count": 0,
                "created_at": created_at,
            }
        )


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text("DELETE FROM users WHERE email = 'admin@admin.com'"))
