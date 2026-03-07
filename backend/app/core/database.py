import logging

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

logger = logging.getLogger(__name__)

logger.info("Creating database engine for %s", settings.DATABASE_URL.split("@")[-1])  # log host only
engine = create_async_engine(settings.DATABASE_URL, echo=settings.ENVIRONMENT == "development")
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncSession:
    try:
        async with async_session() as session:
            yield session
    except Exception:
        logger.exception("Database session error")
        raise
