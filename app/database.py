from sqlalchemy import create_engine
from sqlalchemy.engine import Engine


def create_database_engine(database_url: str, timeout_seconds: int) -> Engine:
    return create_engine(
        database_url,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=5,
        connect_args={"timeout": timeout_seconds},
    )

