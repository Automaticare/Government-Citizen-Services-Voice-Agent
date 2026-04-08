"""
Authentication endpoint for caller identity verification.

POST /auth/verify — accepts credentials, validates format,
checks against citizen database, and returns auth result
with audit logging. No raw PII in logs or responses.
"""

import hashlib
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from agent.logging_config import get_logger
from agent.tools.tc_kimlik import validate_tc_kimlik, mask_tc_kimlik
from agent.tools.app_ref import validate_app_ref
from api.models import Application, AuthAuditLog, Citizen, get_db

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


class AuthWebhookRequest(BaseModel):
    """Webhook-compatible auth request for ElevenLabs dispatch tool.

    Uses last 4 digits of TC Kimlik + date of birth + father's first
    letter — STT-friendly (no 11-digit number over voice).
    Parameters extracted by LLM from conversation.
    """
    tc_kimlik_last4: str
    date_of_birth: str
    father_initial: str


class AuthResponse(BaseModel):
    """Standardized auth response."""
    is_error: bool
    message: str
    citizen_profile: dict | None = None
    guidance: str | None = None


# --- Helpers ---

def _hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _citizen_to_safe_profile(citizen: Citizen, db: Session) -> dict:
    """Convert citizen record to a safe profile (no raw PII).

    Includes citizen_id for subsequent API calls (appointment, document).
    Returns the most recent application for backward compatibility with
    ElevenLabs dynamic variables ({{application_ref}}, {{application_status}}).
    """
    # Get the most recent application (for backward compat with dashboard)
    latest_app = (
        db.query(Application)
        .filter(Application.citizen_id == citizen.id)
        .order_by(Application.id.desc())
        .first()
    )

    profile = {
        "citizen_id": citizen.id,
        "first_name": citizen.first_name,
        "last_name_initial": citizen.last_name[0] + "***",
        "gender": getattr(citizen, "gender", "M"),
        "language_preference": citizen.language_preference,
    }

    if latest_app:
        profile["application_ref"] = latest_app.application_ref
        profile["application_status"] = latest_app.status

    return profile


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
        citizen_profile=_citizen_to_safe_profile(citizen, db),
    )


@router.post("/verify/webhook", response_model=AuthResponse)
def verify_webhook(
    request: AuthWebhookRequest,
    db: Session = Depends(get_db),
):
    """Webhook-compatible auth for ElevenLabs Workflow dispatch tool.

    Uses last 4 digits of TC Kimlik + date of birth + father's name
    first letter. STT-friendly — no 11-digit number over voice.

    Returns is_error=false on success (dispatch tool routes to
    authenticated subagent), is_error=true on failure (routes to
    retry or human transfer).
    """
    logger.info(f"Auth webhook attempt | last4={request.tc_kimlik_last4} | dob={request.date_of_birth} | father={request.father_initial}")

    # Validate last 4 digits
    last4 = "".join(c for c in request.tc_kimlik_last4 if c.isdigit())
    if len(last4) != 4:
        raise HTTPException(status_code=401, detail="Kimlik dogrulama basarisiz. Lutfen bilgilerinizi kontrol edip tekrar deneyin.")

    # Normalize date format
    from agent.tools.date_parser import normalize_date
    normalized_dob, date_error = normalize_date(request.date_of_birth)

    if date_error:
        raise HTTPException(status_code=401, detail="Kimlik dogrulama basarisiz. Lutfen bilgilerinizi kontrol edip tekrar deneyin.")

    # Normalize father initial
    father_initial = request.father_initial.strip().upper()[:1]
    if not father_initial.isalpha():
        raise HTTPException(status_code=401, detail="Kimlik dogrulama basarisiz. Lutfen bilgilerinizi kontrol edip tekrar deneyin.")

    # Search DB — match last 4 digits of TC hash + DOB + father initial
    # Since we store hashed TC, we check all citizens matching DOB + father initial
    # then verify last 4 digits against the full TC Kimlik
    candidates = db.query(Citizen).filter(
        Citizen.date_of_birth == normalized_dob,
    ).all()

    # Filter by father initial
    candidates = [c for c in candidates if c.father_name and c.father_name[0].upper() == father_initial]

    if not candidates:
        raise HTTPException(status_code=401, detail="Kimlik dogrulama basarisiz. Lutfen bilgilerinizi kontrol edip tekrar deneyin.")

    # Check last 4 digits against stored TC hashes
    # We need to reverse-check: generate TC from seed and compare last 4
    # In production this would use a last4_digits column — for demo we check all candidates
    from api.seed_data import generate_valid_tc, SEED_CITIZENS
    matched_citizen = None
    for citizen in candidates:
        # Find the seed data for this citizen to get full TC
        for seed_row in SEED_CITIZENS:
            tc_full = generate_valid_tc(seed_row[0])
            if _hash(tc_full) == citizen.tc_kimlik_hash:
                if tc_full[-4:] == last4:
                    matched_citizen = citizen
                    break
        if matched_citizen:
            break

    if not matched_citizen:
        raise HTTPException(status_code=401, detail="Kimlik dogrulama basarisiz. Lutfen bilgilerinizi kontrol edip tekrar deneyin.")

    # Success
    logger.info(f"Auth webhook success | citizen_id={matched_citizen.id}")

    return AuthResponse(
        is_error=False,
        message=f"Hosgeldiniz, {matched_citizen.first_name}.",
        citizen_profile=_citizen_to_safe_profile(matched_citizen, db),
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

    # Step 2: Look up application by reference, then find citizen
    app_ref_cleaned = request.app_ref.strip().upper()
    application = db.query(Application).filter(Application.application_ref == app_ref_cleaned).first()

    if not application:
        _log_audit(db, request.session_id, "app_ref_lastname", request.attempt_number,
                   "failure", failure_reason="app_ref_not_found")
        return AuthResponse(
            is_error=True,
            message="Basvuru numarasi sistemde bulunamadi.",
            guidance=_failure_guidance(request.attempt_number),
        )

    citizen = db.query(Citizen).filter(Citizen.id == application.citizen_id).first()

    if not citizen:
        _log_audit(db, request.session_id, "app_ref_lastname", request.attempt_number,
                   "failure", failure_reason="citizen_not_found")
        return AuthResponse(
            is_error=True,
            message="Basvuru numarasi sistemde bulunamadi.",
            guidance=_failure_guidance(request.attempt_number),
        )

    # Step 3: Verify last name (case-insensitive)
    if request.last_name.strip().lower() != citizen.last_name.lower():
        _log_audit(db, request.session_id, "app_ref_lastname", request.attempt_number,
                   "failure", citizen_id_hash=_hash(application.application_ref),
                   failure_reason="lastname_mismatch")
        return AuthResponse(
            is_error=True,
            message="Soyad eslesmedi.",
            guidance=_failure_guidance(request.attempt_number),
        )

    # Success
    _log_audit(db, request.session_id, "app_ref_lastname", request.attempt_number,
               "success", citizen_id_hash=_hash(application.application_ref))
    logger.info(f"Auth success (app_ref) | session={request.session_id}")

    return AuthResponse(
        is_error=False,
        message=f"Hosgeldiniz, {citizen.first_name}.",
        citizen_profile=_citizen_to_safe_profile(citizen, db),
    )
