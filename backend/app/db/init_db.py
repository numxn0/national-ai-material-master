from alembic import command
from alembic.config import Config

from .models import *  # noqa: F403 - registers models on Base metadata for local create_all
from .session import Base, engine


def run_migrations(alembic_ini_path: str = "alembic.ini") -> None:
    """Apply Alembic migrations for local development or deployment scripts."""
    cfg = Config(alembic_ini_path)
    command.upgrade(cfg, "head")


def create_all_local_dev() -> None:
    """Create tables from metadata only when explicitly called for local development."""
    Base.metadata.create_all(bind=engine)
