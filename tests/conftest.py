"""
Shared test fixtures — single test DB for all API tests.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.models import Base, get_db
from api.server import app
from api.seed_data import generate_valid_tc, hash_tc
from api.models import Citizen

# Single in-memory DB shared across all test modules
test_engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSession = sessionmaker(bind=test_engine)


def override_get_db():
    db = TestSession()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True, scope="session")
def setup_test_db():
    """Create tables and seed once for the entire test session."""
    Base.metadata.create_all(test_engine)

    db = TestSession()
    tc_ahmet = generate_valid_tc("100000001")
    tc_fatma = generate_valid_tc("200000002")

    db.add_all([
        Citizen(
            tc_kimlik_hash=hash_tc(tc_ahmet),
            first_name="Ahmet", last_name="Yilmaz",
            date_of_birth="15/03/1990",
            application_ref="2024-TR-0001", application_status="in_review",
            language_preference="tr",
        ),
        Citizen(
            tc_kimlik_hash=hash_tc(tc_fatma),
            first_name="Fatma", last_name="Kaya",
            date_of_birth="22/07/1985",
            application_ref="2024-TR-0002", application_status="approved",
            language_preference="tr",
        ),
    ])
    db.commit()
    db.close()

    yield

    Base.metadata.drop_all(test_engine)
