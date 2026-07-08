from __future__ import annotations

from sqlalchemy import Select
from sqlalchemy.orm import Mapped, mapped_column, relationship
from telegram import User as TgUser

from .db import AsyncScopedSession, Base, ResultForStats


class User(Base):
    __tablename__ = 'user'

    id: Mapped[int] = mapped_column(primary_key=True)
    full_name: Mapped[str] = mapped_column()
    username: Mapped[str] = mapped_column()

    framed_results: Mapped[list[ResultForStats]] = relationship('FramedResult', back_populates='user', lazy='joined')
    episode_results: Mapped[list[ResultForStats]] = relationship('EpisodeResult', back_populates='user', lazy='joined')

    @staticmethod
    async def update_from_tg_user(tg_user: TgUser) -> None:
        async with AsyncScopedSession() as session:
            result = await session.execute(Select(User).filter(User.id == tg_user.id))
            user = result.scalars().first()
            if not user:
                user = User(id=tg_user.id)
            user.full_name = tg_user.full_name
            user.username = tg_user.username or ''
            session.add(user)
            await session.commit()

    @staticmethod
    async def get(user_id: int) -> User | None:
        async with AsyncScopedSession() as session:
            result = await session.execute(Select(User).filter(User.id == user_id))
            return result.scalars().first()
