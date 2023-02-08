from __future__ import annotations

from sqlalchemy import Select
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.types import BigInteger
from telegram import Chat as TgChat

from .db import Base, AsyncScopedSession


class Group(Base):
    __tablename__ = "group"

    id: Mapped[int] = mapped_column('id', BigInteger, primary_key=True)
    title: Mapped[str]

    @staticmethod
    async def update_from_tg_chat(tg_chat: TgChat):
        async with AsyncScopedSession() as session:
            result = await session.execute(Select(Group).filter(Group.id == tg_chat.id))
            group = result.scalars().first()
            if not group:
                group = Group(id=tg_chat.id)
            group.title = tg_chat.title
            session.add(group)
            await session.commit()

    @staticmethod
    async def get(group_id: int) -> Group:
        async with AsyncScopedSession() as session:
            result = await session.execute(Select(Group).filter(Group.id == group_id))
            return result.scalars().first()

    @staticmethod
    async def get_all() -> list[Group]:
        async with AsyncScopedSession() as session:
            result = await session.execute(Select(Group))
            return result.scalars().all()
