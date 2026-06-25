import logging
from collections.abc import Generator

from sqlalchemy import inspect, text
from sqlmodel import Session, SQLModel, create_engine

from .config import get_settings

logger = logging.getLogger(__name__)


def _normalize_db_url(url: str) -> str:
    """Railway/Heroku hand out `postgres://...`. SQLAlchemy + psycopg v3 needs
    the `postgresql+psycopg://` scheme."""
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+psycopg://", 1)
    elif url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


settings = get_settings()
DB_URL = _normalize_db_url(settings.database_url)

connect_args = {"check_same_thread": False} if DB_URL.startswith("sqlite") else {}
engine = create_engine(DB_URL, echo=False, connect_args=connect_args)


# Columns added after the initial release. `create_all` only creates missing
# *tables*, never new columns on an existing one, and there's no Alembic here —
# so we add them by hand. Plain `ADD COLUMN` works on both SQLite and Postgres.
_DOCUMENT_ADDED_COLUMNS = {
    "source_type": "VARCHAR DEFAULT 'text'",
    "original_filename": "VARCHAR",
    "s3_key": "VARCHAR",
    "mime_type": "VARCHAR",
}


def _migrate(engine_) -> None:
    """Idempotently add columns introduced after the first deploy."""
    inspector = inspect(engine_)
    if "document" not in inspector.get_table_names():
        return  # create_all will build it fresh with all columns
    existing = {col["name"] for col in inspector.get_columns("document")}
    missing = {k: v for k, v in _DOCUMENT_ADDED_COLUMNS.items() if k not in existing}
    if not missing:
        return
    with engine_.begin() as conn:
        for name, ddl in missing.items():
            logger.info("Migrating: adding document.%s", name)
            conn.execute(text(f"ALTER TABLE document ADD COLUMN {name} {ddl}"))


def init_db() -> None:
    # Import models so SQLModel sees the tables before create_all.
    from . import models  # noqa: F401

    SQLModel.metadata.create_all(engine)
    _migrate(engine)


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
