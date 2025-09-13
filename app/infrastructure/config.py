from app.config import settings

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


def _to_async_url(url: str) -> str:
    # Convert sync Postgres URL to asyncpg dialect if needed
    if url.startswith("postgresql://") and "+" not in url:
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


def get_engine():
    database_url = getattr(settings, "database_url", None) or getattr(settings, "DATABASE_URI", None)
    if not database_url:
        raise RuntimeError("Database URL is not configured in settings")
    return create_async_engine(_to_async_url(database_url), echo=False)


def get_session():
    engine = get_engine()
    return async_sessionmaker(bind=engine, expire_on_commit=False)
