from collections.abc import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings

# Engine setup
# SQLite requires check_same_thread=False
connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    connect_args=connect_args,
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


class Base(DeclarativeBase):
    """SQLAlchemy 2.x Declarative Base Class."""
    pass


def get_db() -> Generator[Session, None, None]:
    """FastAPI request-scoped database dependency yielding a managed session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
