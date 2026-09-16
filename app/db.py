from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def run_migrations() -> None:
    if not settings.database_url.startswith("sqlite"):
        return

    with engine.begin() as conn:
        rows = conn.execute(text("PRAGMA table_info(sections)")).fetchall()
        if not rows:
            return
        columns = {row[1] for row in rows}
        if "attempt_count" not in columns:
            conn.execute(
                text("ALTER TABLE sections ADD COLUMN attempt_count INTEGER NOT NULL DEFAULT 0")
            )
        if "next_retry_at" not in columns:
            conn.execute(text("ALTER TABLE sections ADD COLUMN next_retry_at DATETIME"))


def init_db() -> None:
    from app import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    run_migrations()
