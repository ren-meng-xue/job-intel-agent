"""make jobs url nullable for text/image input

Revision ID: b3c4d5e6f7a8
Revises: 3941612ef62f
Create Date: 2026-05-15 12:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = 'b3c4d5e6f7a8'
down_revision: Union[str, None] = '46d9a19803b5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column('jobs', 'url', existing_type=sa.Text(), nullable=True)


def downgrade() -> None:
    op.alter_column('jobs', 'url', existing_type=sa.Text(), nullable=False)
