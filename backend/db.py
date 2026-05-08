import os
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker


def _default_sqlite_url() -> str:
    # Works locally and inside Docker/ECS without extra setup.
    # If you mount a volume, point DATABASE_URL to a persistent location.
    return "sqlite:///./data/tagchecker.db"


DATABASE_URL = os.getenv("DATABASE_URL", "").strip() or _default_sqlite_url()

# SQLite needs check_same_thread for FastAPI multi-threaded workers.
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, echo=False, future=True, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


@contextmanager
def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

