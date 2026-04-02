"""
Tests for authentication endpoints.

Covers both verification methods, validation, audit logging,
progressive guidance, and PII safety.
"""

import os
import tempfile

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from api.models import Base, Citizen, AuthAuditLog, get_db
from api.server import app
from api.seed_data import generate_valid_tc, hash_tc


# --- Test DB setup (temp file SQLite, shared across connections) ---

_test_db_file = os.path.join(tempfile.gettempdir(), "test_citizens.db")
_test_db_url = f"sqlite:///{_test_db_file}"
test_engine = create_engine(_test_db_url, connect_args={"check_same_thread": False})
TestSession = sessionmaker(bind=test_engine)


def override_get_db():
    db = TestSession()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True, scope="module")
def setup_db():
    """Create tables and seed test data once per test module."""
    Base.metadata.drop_all(test_engine)
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
    test_engine.dispose()
    try:
        if os.path.exists(_test_db_file):
            os.remove(_test_db_file)
    except PermissionError:
        pass  # Windows file lock — temp file, cleaned up on reboot


client = TestClient(app)

TC_AHMET = generate_valid_tc("100000001")
TC_FATMA = generate_valid_tc("200000002")


class TestTcKimlikAuth:
    """Test TC Kimlik + DOB verification."""

    def test_valid_credentials(self):
        r = client.post("/auth/verify/tc-kimlik", json={
            "tc_kimlik": TC_AHMET,
            "date_of_birth": "15/03/1990",
            "session_id": "s1",
        })
        assert r.status_code == 200
        data = r.json()
        assert data["is_error"] is False
        assert data["citizen_profile"]["first_name"] == "Ahmet"
        assert data["citizen_profile"]["application_status"] == "in_review"

    def test_invalid_checksum_rejected_before_db(self):
        r = client.post("/auth/verify/tc-kimlik", json={
            "tc_kimlik": "12345678901",
            "date_of_birth": "01/01/1990",
            "session_id": "s2",
        })
        data = r.json()
        assert data["is_error"] is True
        assert "checksum" in data["message"]

    def test_wrong_dob(self):
        r = client.post("/auth/verify/tc-kimlik", json={
            "tc_kimlik": TC_AHMET,
            "date_of_birth": "01/01/2000",
            "session_id": "s3",
        })
        data = r.json()
        assert data["is_error"] is True
        assert "tarihi" in data["message"]

    def test_tc_not_found(self):
        unknown_tc = generate_valid_tc("999000009")
        r = client.post("/auth/verify/tc-kimlik", json={
            "tc_kimlik": unknown_tc,
            "date_of_birth": "01/01/1990",
            "session_id": "s4",
        })
        data = r.json()
        assert data["is_error"] is True
        assert "bulunamadi" in data["message"]

    def test_too_short_tc(self):
        r = client.post("/auth/verify/tc-kimlik", json={
            "tc_kimlik": "12345",
            "date_of_birth": "01/01/1990",
            "session_id": "s5",
        })
        data = r.json()
        assert data["is_error"] is True
        assert "11 digits" in data["message"]

    def test_tc_with_spaces_accepted(self):
        spaced = TC_AHMET[:3] + " " + TC_AHMET[3:7] + " " + TC_AHMET[7:]
        r = client.post("/auth/verify/tc-kimlik", json={
            "tc_kimlik": spaced,
            "date_of_birth": "15/03/1990",
            "session_id": "s6",
        })
        data = r.json()
        assert data["is_error"] is False
        assert data["citizen_profile"]["first_name"] == "Ahmet"


class TestAppRefAuth:
    """Test Application Reference + Last Name verification."""

    def test_valid_credentials(self):
        r = client.post("/auth/verify/app-ref", json={
            "app_ref": "2024-TR-0002",
            "last_name": "Kaya",
            "session_id": "s10",
        })
        data = r.json()
        assert data["is_error"] is False
        assert data["citizen_profile"]["first_name"] == "Fatma"

    def test_case_insensitive_lastname(self):
        r = client.post("/auth/verify/app-ref", json={
            "app_ref": "2024-TR-0002",
            "last_name": "kaya",
            "session_id": "s11",
        })
        assert r.json()["is_error"] is False

    def test_wrong_lastname(self):
        r = client.post("/auth/verify/app-ref", json={
            "app_ref": "2024-TR-0002",
            "last_name": "Demir",
            "session_id": "s12",
        })
        data = r.json()
        assert data["is_error"] is True
        assert "Soyad" in data["message"]

    def test_invalid_app_ref_format(self):
        r = client.post("/auth/verify/app-ref", json={
            "app_ref": "INVALID",
            "last_name": "Kaya",
            "session_id": "s13",
        })
        data = r.json()
        assert data["is_error"] is True
        assert "YYYY-XX-NNNN" in data["message"]

    def test_app_ref_not_found(self):
        r = client.post("/auth/verify/app-ref", json={
            "app_ref": "2024-TR-9999",
            "last_name": "Nobody",
            "session_id": "s14",
        })
        data = r.json()
        assert data["is_error"] is True
        assert "bulunamadi" in data["message"]


class TestProgressiveGuidance:
    """Test that failure guidance changes per attempt number."""

    def test_attempt_1_guidance(self):
        r = client.post("/auth/verify/tc-kimlik", json={
            "tc_kimlik": "12345678901",
            "date_of_birth": "01/01/1990",
            "session_id": "g1",
            "attempt_number": 1,
        })
        assert "tekrar" in r.json()["guidance"].lower()

    def test_attempt_2_guidance_offers_alternative(self):
        r = client.post("/auth/verify/tc-kimlik", json={
            "tc_kimlik": "12345678901",
            "date_of_birth": "01/01/1990",
            "session_id": "g2",
            "attempt_number": 2,
        })
        guidance = r.json()["guidance"]
        assert "basvuru" in guidance.lower() or "son" in guidance.lower()

    def test_attempt_3_guidance_human_transfer(self):
        r = client.post("/auth/verify/tc-kimlik", json={
            "tc_kimlik": "12345678901",
            "date_of_birth": "01/01/1990",
            "session_id": "g3",
            "attempt_number": 3,
        })
        assert "operator" in r.json()["guidance"].lower()


class TestPIISafety:
    """Test that no raw PII leaks in responses."""

    def test_profile_has_no_full_lastname(self):
        r = client.post("/auth/verify/tc-kimlik", json={
            "tc_kimlik": TC_AHMET,
            "date_of_birth": "15/03/1990",
            "session_id": "pii1",
        })
        profile = r.json()["citizen_profile"]
        assert profile["last_name_initial"] == "Y***"
        assert "Yilmaz" not in str(profile)

    def test_profile_has_no_tc_kimlik(self):
        r = client.post("/auth/verify/tc-kimlik", json={
            "tc_kimlik": TC_AHMET,
            "date_of_birth": "15/03/1990",
            "session_id": "pii2",
        })
        response_text = str(r.json())
        assert TC_AHMET not in response_text

    def test_profile_has_no_dob(self):
        r = client.post("/auth/verify/tc-kimlik", json={
            "tc_kimlik": TC_AHMET,
            "date_of_birth": "15/03/1990",
            "session_id": "pii3",
        })
        response_text = str(r.json())
        assert "15/03/1990" not in response_text


class TestAuditLog:
    """Test that auth attempts are logged for audit trail."""

    def test_success_logged(self):
        client.post("/auth/verify/tc-kimlik", json={
            "tc_kimlik": TC_AHMET,
            "date_of_birth": "15/03/1990",
            "session_id": "audit1",
        })
        db = TestSession()
        log = db.query(AuthAuditLog).filter(AuthAuditLog.session_id == "audit1").first()
        assert log is not None
        assert log.result == "success"
        assert log.citizen_id_hash is not None
        assert log.failure_reason is None
        db.close()

    def test_failure_logged_with_reason(self):
        client.post("/auth/verify/tc-kimlik", json={
            "tc_kimlik": "12345678901",
            "date_of_birth": "01/01/1990",
            "session_id": "audit2",
        })
        db = TestSession()
        log = db.query(AuthAuditLog).filter(AuthAuditLog.session_id == "audit2").first()
        assert log is not None
        assert log.result == "failure"
        assert "format_invalid" in log.failure_reason
        db.close()

    def test_audit_has_no_raw_pii(self):
        client.post("/auth/verify/tc-kimlik", json={
            "tc_kimlik": TC_AHMET,
            "date_of_birth": "15/03/1990",
            "session_id": "audit3",
        })
        db = TestSession()
        log = db.query(AuthAuditLog).filter(AuthAuditLog.session_id == "audit3").first()
        # citizen_id_hash should be a SHA-256 hash, not raw TC Kimlik
        assert log.citizen_id_hash != TC_AHMET
        assert len(log.citizen_id_hash) == 64  # SHA-256 hex length
        db.close()
