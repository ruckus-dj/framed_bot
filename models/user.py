from __future__ import annotations

from sqlalchemy import Select
from sqlalchemy.orm import Mapped, relationship
from sqlalchemy.orm import mapped_column
from telegram import User as TgUser

from .db import Base, AsyncScopedSession


class User(Base):
    __tablename__ = "user"

    id: Mapped[int] = mapped_column(primary_key=True)
    full_name: Mapped[str]
    username: Mapped[str]

    framed_results: Mapped[list['FramedResult']] = relationship(back_populates='user')

    @staticmethod
    async def update_from_tg_user(tg_user: TgUser):
        async with AsyncScopedSession() as session:
            result = await session.execute(Select(User).filter(User.id == tg_user.id))
            user = result.scalars().first()
            if not user:
                user = User(id=tg_user.id)
            user.full_name = tg_user.full_name
            user.username = tg_user.username
            session.add(user)
            await session.commit()

    @staticmethod
    async def get(user_id: int):
        async with AsyncScopedSession() as session:
            return await session.execute(Select(User).filter(User.id == user_id)).scalars().first()
