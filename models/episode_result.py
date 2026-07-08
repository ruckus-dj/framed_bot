from __future__ import annotations

from sqlalchemy import ForeignKey, Select
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import AsyncScopedSession, Base


class EpisodeResult(Base):
    __tablename__ = 'episode_result'

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('user.id'), index=True)
    framed_round: Mapped[int] = mapped_column(index=True)
    won: Mapped[bool] = mapped_column()
    win_frame: Mapped[int | None] = mapped_column()

    user: Mapped[Base] = relationship('User', back_populates='episode_results')

    @staticmethod
    async def save_result(user_id: int, framed_round: int, won: bool, win_frame: int | None) -> bool:
        async with AsyncScopedSession() as session:
            result = await session.execute(
                Select(EpisodeResult).filter(
                    EpisodeResult.user_id == user_id, EpisodeResult.framed_round == framed_round
                )
            )
            framed_result = result.first()
            if framed_result:
                return False
            framed_result = EpisodeResult(user_id=user_id, framed_round=framed_round, won=won, win_frame=win_frame)
            session.add(framed_result)
            await session.commit()
            return True
