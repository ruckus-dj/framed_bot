from __future__ import annotations

from sqlalchemy import Select
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import BigInteger
from telegram import Chat as TgChat

from .db import AsyncScopedSession, Base


class Group(Base):
    __tablename__ = 'group'

    id: Mapped[int] = mapped_column('id', BigInteger, primary_key=True)
    title: Mapped[str] = mapped_column()

    @staticmethod
    async def update_from_tg_chat(tg_chat: TgChat) -> None:
        async with AsyncScopedSession() as session:
            result = await session.execute(Select(Group).filter(Group.id == tg_chat.id))
            group = result.scalars().first()
            if not group:
                group = Group(id=tg_chat.id)
            group.title = tg_chat.title or ''
            session.add(group)
            await session.commit()

    @staticmethod
    async def get(group_id: int) -> Group | None:
        async with AsyncScopedSession() as session:
            result = await session.execute(Select(Group).filter(Group.id == group_id))
            return result.scalars().first()

    @staticmethod
    async def get_all() -> list[Group]:
        async with AsyncScopedSession() as session:
            result = await session.execute(Select(Group))
            return list(result.scalars().all())
