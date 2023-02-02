from __future__ import annotations

from typing import Optional

from sqlalchemy import ForeignKey, Select
from sqlalchemy.orm import Mapped, relationship
from sqlalchemy.orm import mapped_column

from .db import Base, AsyncScopedSession


class EpisodeResult(Base):
    __tablename__ = "episode_result"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('user.id'), index=True)
    framed_round: Mapped[int] = mapped_column(index=True)
    won: Mapped[bool]
    win_frame: Mapped[Optional[int]]

    user: Mapped['User'] = relationship(back_populates='episode_results')

    @staticmethod
    async def save_result(user_id: int, framed_round: int, won: bool, win_frame: Optional[int]) -> bool:
        async with AsyncScopedSession() as session:
            result = await session.execute(Select(EpisodeResult).filter(EpisodeResult.user_id == user_id,
                                                                        EpisodeResult.framed_round == framed_round))
            framed_result = result.first()
            if framed_result:
                return False
            framed_result = EpisodeResult(user_id=user_id, framed_round=framed_round, won=won, win_frame=win_frame)
            session.add(framed_result)
            await session.commit()
            return True
