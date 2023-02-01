from .db import Base, engine
from .framed_result import FramedResult
from .user import User


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
