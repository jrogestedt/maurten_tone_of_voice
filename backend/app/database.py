from collections.abc import Generator

from sqlmodel import Session, SQLModel, create_engine

from .config import get_settings


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


def init_db() -> None:
    # Import models so SQLModel sees the tables before create_all.
    from . import models  # noqa: F401

    SQLModel.metadata.create_all(engine)


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
