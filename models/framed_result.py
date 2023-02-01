from __future__ import annotations

from typing import Optional

from sqlalchemy import ForeignKey, Select
from sqlalchemy.orm import Mapped, relationship
from sqlalchemy.orm import mapped_column

from .db import Base, AsyncScopedSession


class FramedResult(Base):
    __tablename__ = "framed_result"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('user.id'), index=True)
    framed_round: Mapped[int] = mapped_column(index=True)
    won: Mapped[bool]
    win_frame: Mapped[Optional[int]]

    user: Mapped['User'] = relationship(back_populates='framed_results')

    @staticmethod
    async def save_result(user_id: int, framed_round: int, won: bool, win_frame: Optional[int]) -> bool:
        async with AsyncScopedSession() as session:
            result = await session.execute(Select(FramedResult).filter(FramedResult.user_id == user_id,
                                                                       FramedResult.framed_round == framed_round))
            framed_result = result.first()
            if framed_result:
                return False
            framed_result = FramedResult(user_id=user_id, framed_round=framed_round, won=won, win_frame=win_frame)
            session.add(framed_result)
            await session.commit()
            return True
