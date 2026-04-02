import os
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings


settings = get_settings()

database_url = settings.DATABASE_URL

if database_url.startswith("sqlite:///"):
    db_path = database_url.replace("sqlite:///", "")
    if not os.path.isabs(db_path):
        db_dir = os.path.dirname(db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)

connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
engine = create_engine(database_url, future=True, connect_args=connect_args)
session_factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def get_session() -> Session:
    return session_factory()
