"""
Database models for the citizen services platform.

Uses SQLAlchemy ORM for database abstraction. Default: SQLite for demo.
Production: switch to PostgreSQL by changing DATABASE_URL in .env.

    SQLite:      sqlite:///data/citizens.db
    PostgreSQL:  postgresql://user:pass@host/dbname
"""

import os
from datetime import datetime, timezone

from dotenv import load_dotenv
from sqlalchemy import (
    Column,
    DateTime,
    Integer,
    String,
    create_engine,
)
from sqlalchemy.orm import declarative_base, sessionmaker

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///data/citizens.db")

engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


class Citizen(Base):
    """Mock citizen record for identity verification."""

    __tablename__ = "citizens"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tc_kimlik_hash = Column(String, nullable=False, unique=True, index=True)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    date_of_birth = Column(String, nullable=False)  # DD/MM/YYYY
    application_ref = Column(String, unique=True, index=True)
    application_status = Column(String, nullable=False, default="pending")
    language_preference = Column(String, nullable=False, default="tr")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class AuthAuditLog(Base):
    """Audit trail for authentication attempts. No raw PII stored."""

    __tablename__ = "auth_audit_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    session_id = Column(String, nullable=False, index=True)
    method = Column(String, nullable=False)  # "tc_kimlik_dob" or "app_ref_lastname"
    attempt_number = Column(Integer, nullable=False)
    result = Column(String, nullable=False)  # "success" or "failure"
    citizen_id_hash = Column(String, nullable=True)  # SHA-256 hash, null on failure
    failure_reason = Column(String, nullable=True)


def init_db():
    """Create all tables if they don't exist."""
    Base.metadata.create_all(engine)


def get_db():
    """Get a database session. Use as context manager or FastAPI dependency."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
