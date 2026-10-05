"""SQLAlchemy engine + session plumbing.

We use the classic *synchronous* SQLAlchemy 2.0 style. FastAPI runs plain `def`
endpoints in a thread pool, so blocking DB/LLM calls never freeze the server,
and the code stays far simpler than async."""
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    """All ORM models inherit from this."""


def get_db():
    """FastAPI dependency: one session per request, always closed afterwards."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
