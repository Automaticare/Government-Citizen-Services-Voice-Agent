"""
Authentication endpoint for caller identity verification.

POST /auth/verify — accepts credentials, validates format,
checks against citizen database, and returns auth result
with audit logging. No raw PII in logs or responses.
"""

import hashlib
from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from agent.logging_config import get_logger
from agent.tools.tc_kimlik import validate_tc_kimlik, mask_tc_kimlik
from agent.tools.app_ref import validate_app_ref
from api.models import AuthAuditLog, Citizen, get_db

logger = get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["authentication"])


# --- Request / Response models ---

class AuthRequestTcKimlik(BaseModel):
    """Primary auth method: TC Kimlik + Date of Birth."""
    tc_kimlik: str
    date_of_birth: str  # DD/MM/YYYY
    session_id: str
    attempt_number: int = 1


class AuthRequestAppRef(BaseModel):
    """Secondary auth method: Application Reference + Last Name."""
    app_ref: str
    last_name: str
    session_id: str
    attempt_number: int = 1


class AuthResponse(BaseModel):
    """Standardized auth response."""
    is_error: bool
    message: str
    citizen_profile: dict | None = None
    guidance: str | None = None


# --- Helpers ---

def _hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _citizen_to_safe_profile(citizen: Citizen) -> dict:
    """Convert citizen record to a safe profile (no raw PII).

    Includes citizen_id for subsequent API calls (appointment, document).
    This is safe — citizen_id is an internal DB integer, not PII.
    """
    return {
        "citizen_id": citizen.id,
        "first_name": citizen.first_name,
        "last_name_initial": citizen.last_name[0] + "***",
        "application_ref": citizen.application_ref,
        "application_status": citizen.application_status,
        "language_preference": citizen.language_preference,
    }


def _log_audit(
    db: Session,
    session_id: str,
    method: str,
    attempt_number: int,
    result: str,
    citizen_id_hash: str | None = None,
    failure_reason: str | None = None,
):
    """Write an audit record. No raw PII."""
    audit = AuthAuditLog(
        timestamp=datetime.now(UTC),
        session_id=session_id,
        method=method,
        attempt_number=attempt_number,
        result=result,
        citizen_id_hash=citizen_id_hash,
        failure_reason=failure_reason,
    )
    db.add(audit)
    db.commit()


def _failure_guidance(attempt: int) -> str:
    """Progressive guidance based on attempt number."""
    if attempt == 1:
        return "Girdiginiz bilgiler eslesmedi. Lutfen tekrar deneyin."
    elif attempt == 2:
        return "Bilgiler yine eslesmedi. Son bir deneme hakkiniz var. Dilerseniz basvuru numaraniz ile de dogrulama yapabiliriz."
    else:
        return "Kimliginizi dogrulayamadim. Guvenliginiz icin sizi bir musait operatore bagliyorum."


# --- Endpoints ---

@router.post("/verify/tc-kimlik", response_model=AuthResponse)
def verify_tc_kimlik(
    request: AuthRequestTcKimlik,
    db: Session = Depends(get_db),
):
    """Verify caller identity using TC Kimlik + Date of Birth."""
    logger.info(f"Auth attempt (tc_kimlik) | session={request.session_id} | attempt={request.attempt_number}")

    # Step 1: Validate TC Kimlik format + checksum
    is_valid, error = validate_tc_kimlik(request.tc_kimlik)
    if not is_valid:
        _log_audit(db, request.session_id, "tc_kimlik_dob", request.attempt_number,
                   "failure", failure_reason=f"format_invalid: {error}")
        return AuthResponse(
            is_error=True,
            message=error,
            guidance=_failure_guidance(request.attempt_number),
        )

    # Step 2: Look up citizen by TC Kimlik hash
    tc_hash = _hash(request.tc_kimlik.replace(" ", "").replace("-", ""))
    citizen = db.query(Citizen).filter(Citizen.tc_kimlik_hash == tc_hash).first()

    if not citizen:
        _log_audit(db, request.session_id, "tc_kimlik_dob", request.attempt_number,
                   "failure", failure_reason="tc_kimlik_not_found")
        return AuthResponse(
            is_error=True,
            message="TC Kimlik numarasi sistemde bulunamadi.",
            guidance=_failure_guidance(request.attempt_number),
        )

    # Step 3: Verify date of birth
    dob_cleaned = request.date_of_birth.strip()
    if dob_cleaned != citizen.date_of_birth:
        _log_audit(db, request.session_id, "tc_kimlik_dob", request.attempt_number,
                   "failure", citizen_id_hash=tc_hash, failure_reason="dob_mismatch")
        return AuthResponse(
            is_error=True,
            message="Dogum tarihi eslesmedi.",
            guidance=_failure_guidance(request.attempt_number),
        )

    # Success
    _log_audit(db, request.session_id, "tc_kimlik_dob", request.attempt_number,
               "success", citizen_id_hash=tc_hash)
    logger.info(f"Auth success | session={request.session_id} | citizen_hash={tc_hash[:12]}...")

    return AuthResponse(
        is_error=False,
        message=f"Hosgeldiniz, {citizen.first_name}.",
        citizen_profile=_citizen_to_safe_profile(citizen),
    )


@router.post("/verify/app-ref", response_model=AuthResponse)
def verify_app_ref(
    request: AuthRequestAppRef,
    db: Session = Depends(get_db),
):
    """Verify caller identity using Application Reference + Last Name."""
    logger.info(f"Auth attempt (app_ref) | session={request.session_id} | attempt={request.attempt_number}")

    # Step 1: Validate app ref format
    is_valid, error = validate_app_ref(request.app_ref)
    if not is_valid:
        _log_audit(db, request.session_id, "app_ref_lastname", request.attempt_number,
                   "failure", failure_reason=f"format_invalid: {error}")
        return AuthResponse(
            is_error=True,
            message=error,
            guidance=_failure_guidance(request.attempt_number),
        )

    # Step 2: Look up citizen by application reference
    app_ref_cleaned = request.app_ref.strip().upper()
    citizen = db.query(Citizen).filter(Citizen.application_ref == app_ref_cleaned).first()

    if not citizen:
        _log_audit(db, request.session_id, "app_ref_lastname", request.attempt_number,
                   "failure", failure_reason="app_ref_not_found")
        return AuthResponse(
            is_error=True,
            message="Basvuru numarasi sistemde bulunamadi.",
            guidance=_failure_guidance(request.attempt_number),
        )

    # Step 3: Verify last name (case-insensitive)
    if request.last_name.strip().lower() != citizen.last_name.lower():
        _log_audit(db, request.session_id, "app_ref_lastname", request.attempt_number,
                   "failure", citizen_id_hash=_hash(citizen.application_ref),
                   failure_reason="lastname_mismatch")
        return AuthResponse(
            is_error=True,
            message="Soyad eslesmedi.",
            guidance=_failure_guidance(request.attempt_number),
        )

    # Success
    _log_audit(db, request.session_id, "app_ref_lastname", request.attempt_number,
               "success", citizen_id_hash=_hash(citizen.application_ref))
    logger.info(f"Auth success (app_ref) | session={request.session_id}")

    return AuthResponse(
        is_error=False,
        message=f"Hosgeldiniz, {citizen.first_name}.",
        citizen_profile=_citizen_to_safe_profile(citizen),
    )
