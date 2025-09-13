from app.config import settings

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


def get_engine():
    return create_async_engine(settings.DATABASE_URI, echo=False)


def get_session():
    engine = get_engine()
    return async_sessionmaker(bind=engine, expire_on_commit=False)
