from asyncio import current_task

from sqlalchemy.ext.asyncio import create_async_engine, async_scoped_session, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from config import DB_CONNECTION_STRING

engine = create_async_engine(
    DB_CONNECTION_STRING
)


# async_sessionmaker: a factory for new AsyncSession objects.
# expire_on_commit - don't expire objects after transaction commit
async_session_factory = async_sessionmaker(
    engine,
    expire_on_commit=False,
)
AsyncScopedSession = async_scoped_session(
    async_session_factory,
    scopefunc=current_task,
)


class Base(DeclarativeBase):
    pass
