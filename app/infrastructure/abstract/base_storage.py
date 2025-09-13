from abc import ABC
from app.infrastructure.config import get_session
from sqlalchemy.ext.asyncio import AsyncSession

from contextlib import asynccontextmanager


class BaseStorage(ABC):
    def __init__(self):
        self.__Session = get_session()

    @asynccontextmanager
    async def session_scope(self, read_only=False):
        session: AsyncSession = self.__Session()
        try:
            if read_only:
                session = self.__Session(
                    bind=session.bind.execution_options(isolation_level="AUTOCOMMIT")  # type: ignore
                )
            yield session
            if not read_only:
                await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
