"""Database engine and session management for TimescaleDB."""
import contextlib
from typing import Generator, Optional

import sqlalchemy as sa

from src.config.settings import Settings
from src.logging_config import get_logger

logger = get_logger("db")

_engine: Optional[sa.Engine] = None


def get_engine(db_url: Optional[str] = None) -> sa.Engine:
    """Get or create the SQLAlchemy engine singleton.

    Args:
        db_url: Database URL. If None, loads from Settings.

    Returns:
        SQLAlchemy Engine instance.
    """
    global _engine
    if _engine is not None:
        return _engine

    if db_url is None:
        settings = Settings()
        db_url = settings.database_url

    _engine = sa.create_engine(
        db_url,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
        pool_recycle=3600,
    )
    # Log connection info with masked password
    masked_url = db_url.split("@")[-1] if "@" in db_url else db_url
    logger.info("Database engine created: %s", masked_url)
    return _engine


@contextlib.contextmanager
def get_connection() -> Generator[sa.Connection, None, None]:
    """Context manager for database connections.

    Commits on success, rolls back on exception.

    Usage:
        with get_connection() as conn:
            conn.execute(text("SELECT 1"))
    """
    engine = get_engine()
    with engine.connect() as conn:
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise


def reset_engine() -> None:
    """Dispose the engine and reset the singleton.

    Useful for testing and reconnection scenarios.
    """
    global _engine
    if _engine is not None:
        _engine.dispose()
        _engine = None
        logger.info("Database engine disposed and reset")


def check_health() -> bool:
    """Check database connectivity.

    Returns:
        True if database is reachable, False otherwise.
    """
    try:
        with get_connection() as conn:
            conn.execute(sa.text("SELECT 1"))
        logger.info("Database health check: OK")
        return True
    except Exception as e:
        logger.error("Database health check failed: %s", e)
        return False
