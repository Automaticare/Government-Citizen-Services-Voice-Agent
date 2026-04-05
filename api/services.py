"""
Government services API endpoints.

Provides application status lookup, appointment booking,
document requests, and service catalog.
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from agent.logging_config import get_logger
from api.models import Application, Appointment, Citizen, DocumentRequest, get_db

logger = get_logger(__name__)

router = APIRouter(tags=["services"])


# --- Response models ---

class ApplicationStatusResponse(BaseModel):
    application_ref: str
    service_type: str
    status: str
    first_name: str
    last_name_initial: str
    estimated_completion: str | None = None
    notes: str | None = None


class AppointmentRequest(BaseModel):
    citizen_id: int
    service_type: str
    preferred_date: str  # YYYY-MM-DD


class AppointmentResponse(BaseModel):
    id: int
    service_type: str
    appointment_date: str
    appointment_time: str
    office: str
    status: str


class DocumentRequestCreate(BaseModel):
    citizen_id: int
    document_type: str


class DocumentRequestResponse(BaseModel):
    request_ref: str
    document_type: str
    status: str
    estimated_days: int


class ServiceInfo(BaseModel):
    id: str
    name_tr: str
    name_en: str
    description_tr: str
    description_en: str
    requires_auth: bool


# --- Available services catalog ---

SERVICES_CATALOG = [
    ServiceInfo(
        id="passport", name_tr="Pasaport Islemleri", name_en="Passport Services",
        description_tr="Yeni pasaport, yenileme, kayip pasaport islemleri",
        description_en="New passport, renewal, lost passport services",
        requires_auth=True,
    ),
    ServiceInfo(
        id="id_card", name_tr="Kimlik Karti Islemleri", name_en="ID Card Services",
        description_tr="Yeni kimlik karti, yenileme, kayip kimlik islemleri",
        description_en="New ID card, renewal, lost ID card services",
        requires_auth=True,
    ),
    ServiceInfo(
        id="driver_license", name_tr="Ehliyet Islemleri", name_en="Driver's License Services",
        description_tr="Yeni ehliyet, yenileme, sinif yukseltme islemleri",
        description_en="New license, renewal, class upgrade services",
        requires_auth=True,
    ),
    ServiceInfo(
        id="civil_registry", name_tr="Nufus Hizmetleri", name_en="Civil Registry Services",
        description_tr="Dogum belgesi, ikametgah, evlilik islemleri",
        description_en="Birth certificate, residence, marriage services",
        requires_auth=True,
    ),
    ServiceInfo(
        id="general_inquiry", name_tr="Genel Bilgi", name_en="General Information",
        description_tr="Calisma saatleri, ucretler, gerekli belgeler hakkinda bilgi",
        description_en="Working hours, fees, required documents information",
        requires_auth=False,
    ),
]

# Mock available slots for appointment booking
AVAILABLE_SLOTS = {
    "Kadikoy Nufus Mudurlugu": [
        ("2026-04-07", "10:00"), ("2026-04-07", "14:00"),
        ("2026-04-08", "09:00"), ("2026-04-08", "11:00"),
    ],
    "Uskudar Nufus Mudurlugu": [
        ("2026-04-08", "10:00"), ("2026-04-09", "14:00"),
    ],
    "Besiktas Nufus Mudurlugu": [
        ("2026-04-09", "09:00"), ("2026-04-10", "11:00"),
    ],
    "Bakirkoy Nufus Mudurlugu": [
        ("2026-04-10", "10:00"), ("2026-04-10", "15:00"),
    ],
}

ESTIMATED_COMPLETION = {
    "pending": "15-20 is gunu",
    "in_review": "5-10 is gunu",
    "approved": "Tamamlandi",
    "rejected": "Reddedildi",
    "additional_docs_needed": "Ek belge bekleniyor",
}


# --- Endpoints ---

@router.get("/applications/{ref_number}", response_model=ApplicationStatusResponse)
def get_application_status(ref_number: str, db: Session = Depends(get_db)):
    """Look up application status by reference number."""
    application = db.query(Application).filter(
        Application.application_ref == ref_number.strip().upper()
    ).first()

    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    citizen = db.query(Citizen).filter(Citizen.id == application.citizen_id).first()

    logger.info(f"Application lookup | ref={ref_number}")

    return ApplicationStatusResponse(
        application_ref=application.application_ref,
        service_type=application.service_type,
        status=application.status,
        first_name=citizen.first_name if citizen else "Unknown",
        last_name_initial=(citizen.last_name[0] + "***") if citizen else "?***",
        estimated_completion=ESTIMATED_COMPLETION.get(application.status),
        notes=f"Basvuru {application.status} asamasindadir." if application.status != "approved" else None,
    )


@router.get("/applications", response_model=list[ApplicationStatusResponse])
def list_citizen_applications(citizen_id: int, db: Session = Depends(get_db)):
    """List all applications for a citizen."""
    citizen = db.query(Citizen).filter(Citizen.id == citizen_id).first()
    if not citizen:
        raise HTTPException(status_code=404, detail="Citizen not found")

    applications = db.query(Application).filter(
        Application.citizen_id == citizen_id
    ).order_by(Application.id.desc()).all()

    logger.info(f"Applications list | citizen_id={citizen_id} | count={len(applications)}")

    return [
        ApplicationStatusResponse(
            application_ref=app.application_ref,
            service_type=app.service_type,
            status=app.status,
            first_name=citizen.first_name,
            last_name_initial=citizen.last_name[0] + "***",
            estimated_completion=ESTIMATED_COMPLETION.get(app.status),
            notes=f"Basvuru {app.status} asamasindadir." if app.status != "approved" else None,
        )
        for app in applications
    ]


@router.post("/appointments", response_model=AppointmentResponse)
def book_appointment(request: AppointmentRequest, db: Session = Depends(get_db)):
    """Book a new appointment with edge case handling."""
    citizen = db.query(Citizen).filter(Citizen.id == request.citizen_id).first()
    if not citizen:
        raise HTTPException(status_code=404, detail="Citizen not found")

    # Edge case: past date
    if request.preferred_date:
        from datetime import date as date_type
        try:
            preferred = date_type.fromisoformat(request.preferred_date)
            if preferred < date_type.today():
                raise HTTPException(
                    status_code=400,
                    detail="Cannot book an appointment in the past. Please choose a future date."
                )
        except ValueError:
            pass  # Invalid date format — let it fall through to slot matching

    # Edge case: duplicate appointment (same citizen, same service, same date)
    if request.preferred_date:
        existing = db.query(Appointment).filter(
            Appointment.citizen_id == request.citizen_id,
            Appointment.service_type == request.service_type,
            Appointment.appointment_date == request.preferred_date,
            Appointment.status == "confirmed",
        ).first()
        if existing:
            raise HTTPException(
                status_code=409,
                detail=f"You already have a {request.service_type} appointment on {request.preferred_date} at {existing.appointment_time}."
            )

    # Find first available slot
    office = None
    date = None
    time = None
    for office_name, slots in AVAILABLE_SLOTS.items():
        for slot_date, slot_time in slots:
            if request.preferred_date and slot_date != request.preferred_date:
                continue
            office = office_name
            date = slot_date
            time = slot_time
            break
        if office:
            break

    if not office:
        raise HTTPException(status_code=409, detail="No available appointment slots for the requested date. Please try a different date.")

    appointment = Appointment(
        citizen_id=request.citizen_id,
        service_type=request.service_type,
        appointment_date=date,
        appointment_time=time,
        office=office,
        status="confirmed",
    )
    db.add(appointment)
    db.commit()
    db.refresh(appointment)

    logger.info(f"Appointment booked | citizen={request.citizen_id} | {date} {time} @ {office}")

    return AppointmentResponse(
        id=appointment.id,
        service_type=appointment.service_type,
        appointment_date=appointment.appointment_date,
        appointment_time=appointment.appointment_time,
        office=appointment.office,
        status=appointment.status,
    )


@router.get("/appointments/{citizen_id}", response_model=list[AppointmentResponse])
def get_appointments(citizen_id: int, db: Session = Depends(get_db)):
    """Get all appointments for a citizen."""
    appointments = db.query(Appointment).filter(Appointment.citizen_id == citizen_id).all()

    return [
        AppointmentResponse(
            id=a.id, service_type=a.service_type,
            appointment_date=a.appointment_date, appointment_time=a.appointment_time,
            office=a.office, status=a.status,
        )
        for a in appointments
    ]


@router.post("/documents/request", response_model=DocumentRequestResponse)
def request_document(request: DocumentRequestCreate, db: Session = Depends(get_db)):
    """Request preparation of an official document."""
    citizen = db.query(Citizen).filter(Citizen.id == request.citizen_id).first()
    if not citizen:
        raise HTTPException(status_code=404, detail="Citizen not found")

    estimated = {"birth_certificate": 3, "residence_cert": 5, "marriage_cert": 5,
                 "criminal_record": 7, "general": 5}

    doc_ref = f"DOC-2026-{uuid.uuid4().hex[:4].upper()}"

    doc_request = DocumentRequest(
        citizen_id=request.citizen_id,
        document_type=request.document_type,
        request_ref=doc_ref,
        status="processing",
        estimated_days=estimated.get(request.document_type, 5),
    )
    db.add(doc_request)
    db.commit()
    db.refresh(doc_request)

    logger.info(f"Document requested | citizen={request.citizen_id} | type={request.document_type} | ref={doc_ref}")

    return DocumentRequestResponse(
        request_ref=doc_request.request_ref,
        document_type=doc_request.document_type,
        status=doc_request.status,
        estimated_days=doc_request.estimated_days,
    )


@router.get("/services", response_model=list[ServiceInfo])
def list_services():
    """Return catalog of available government services."""
    return SERVICES_CATALOG
