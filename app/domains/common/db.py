"""CasaQuant Unified — Database layer.

Supports both PostgreSQL (production) and SQLite WAL (development/offline).
"""

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings

# Determine driver based on URL
if settings.is_sqlite:
    ASYNC_DATABASE_URL = settings.database_url.replace(
        "sqlite:///", "sqlite+aiosqlite:///"
    )
    SYNC_DATABASE_URL = settings.database_url
    CONNECT_ARGS = {"check_same_thread": False}
else:
    ASYNC_DATABASE_URL = str(settings.database_url).replace(
        "postgresql://", "postgresql+asyncpg://"
    )
    SYNC_DATABASE_URL = str(settings.database_url)
    CONNECT_ARGS = {}

# Async engine (FastAPI)
async_engine = create_async_engine(
    ASYNC_DATABASE_URL,
    echo=settings.casaquant_env == "development",
    future=True,
    connect_args=CONNECT_ARGS,
)

# Sync engine (Celery workers, Alembic)
sync_engine = create_engine(
    SYNC_DATABASE_URL,
    echo=settings.casaquant_env == "development",
    future=True,
    connect_args=CONNECT_ARGS,
)

AsyncSessionLocal = sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# SQLModel metadata imported for Alembic
from sqlmodel import SQLModel  # noqa: E402

metadata = SQLModel.metadata


async def init_db():
    """Create all tables (development only). In production use Alembic."""
    if settings.casaquant_env == "development":
        async with async_engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)


def get_sync_session():
    """Yield a synchronous session for Celery workers."""
    from sqlalchemy.orm import Session

    with Session(sync_engine) as session:
        yield session
