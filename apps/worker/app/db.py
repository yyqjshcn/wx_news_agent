from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings


settings = get_settings()

database_url = settings.DATABASE_URL
engine = create_engine(database_url, future=True)
session_factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def get_session() -> Session:
    return session_factory()
