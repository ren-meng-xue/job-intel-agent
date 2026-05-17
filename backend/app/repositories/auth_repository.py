from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.auth_session import AuthSession


class AuthRepository:
    """AuthSession 表数据访问层"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_session(
        self, user_id: str, refresh_token_hash: str, expires_at: datetime
    ) -> AuthSession:
        auth_session = AuthSession(
            user_id=user_id,
            refresh_token_hash=refresh_token_hash,
            expires_at=expires_at,
        )
        self.session.add(auth_session)
        await self.session.commit()
        await self.session.refresh(auth_session)
        return auth_session

    async def get_active_session(self, refresh_token_hash: str) -> AuthSession | None:
        """查找未撤销且未过期的 session"""
        result = await self.session.execute(
            select(AuthSession).where(
                AuthSession.refresh_token_hash == refresh_token_hash,
                AuthSession.revoked_at.is_(None),
                AuthSession.expires_at > datetime.now(timezone.utc).replace(
                    tzinfo=None
                ),
            )
        )
        return result.scalar_one_or_none()

    async def revoke_session(self, session_id: str) -> None:
        """撤销 session，写入 revoked_at 时间戳"""
        result = await self.session.execute(
            select(AuthSession).where(AuthSession.id == session_id)
        )
        auth_session = result.scalar_one_or_none()
        if auth_session:
            auth_session.revoked_at = datetime.now(timezone.utc).replace(tzinfo=None)
            await self.session.commit()
