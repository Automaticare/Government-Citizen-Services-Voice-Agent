"""
Seed the citizen database with 20+ realistic sample records.

Usage:
    python -m api.seed_data          # Seed the database
    python -m api.seed_data --reset  # Drop and recreate tables, then seed

TC Kimlik numbers use valid checksums. All PII is fictional.
"""

import argparse
import hashlib

from api.models import Base, Citizen, Application, Appointment, DocumentRequest, SessionLocal, engine, init_db


def hash_tc(tc_kimlik: str) -> str:
    """SHA-256 hash a TC Kimlik for storage."""
    return hashlib.sha256(tc_kimlik.encode()).hexdigest()


def generate_valid_tc(first_9: str) -> str:
    """Generate a valid 11-digit TC Kimlik from the first 9 digits."""
    digits = [int(d) for d in first_9]
    odd_sum = sum(digits[i] for i in range(0, 9, 2))
    even_sum = sum(digits[i] for i in range(1, 8, 2))
    d10 = (odd_sum * 7 - even_sum) % 10
    d11 = (sum(digits) + d10) % 10
    return first_9 + str(d10) + str(d11)


# Fictional citizens with valid TC Kimlik checksums
# (first_9_digits, first_name, last_name, father_name, dob, lang)
SEED_CITIZENS = [
    ("100000001", "Ahmet", "Yilmaz", "Mehmet", "15/03/1990", "tr"),
    ("200000002", "Fatma", "Kaya", "Ali", "22/07/1985", "tr"),
    ("300000003", "Mehmet", "Demir", "Hasan", "01/01/1978", "tr"),
    ("400000004", "Ayse", "Celik", "Mustafa", "30/11/1995", "tr"),
    ("500000005", "Mustafa", "Sahin", "Ibrahim", "14/06/1982", "tr"),
    ("600000006", "Emine", "Yildiz", "Osman", "08/09/1973", "tr"),
    ("700000007", "Huseyin", "Ozturk", "Yusuf", "25/12/1988", "tr"),
    ("800000008", "Zeynep", "Aydin", "Kemal", "03/04/1992", "tr"),
    ("900000009", "Ali", "Arslan", "Huseyin", "19/10/1980", "tr"),
    ("110000001", "Hatice", "Dogan", "Ahmet", "27/02/1969", "tr"),
    ("120000001", "Ibrahim", "Kilic", "Omer", "11/08/1975", "tr"),
    ("130000001", "Meryem", "Koc", "Hasan", "05/05/1998", "tr"),
    ("140000001", "Hasan", "Ozdemir", "Ali", "16/01/1987", "tr"),
    ("150000001", "Elif", "Polat", "Mehmet", "29/09/1993", "tr"),
    ("160000001", "Omer", "Erdogan", "Mustafa", "07/12/1970", "tr"),
    ("170000001", "Sule", "Tas", "Ibrahim", "20/06/1984", "tr"),
    ("180000001", "Osman", "Cinar", "Yusuf", "12/03/1991", "tr"),
    ("190000001", "Merve", "Acar", "Kemal", "23/11/1996", "tr"),
    ("210000002", "Yusuf", "Kurt", "Osman", "04/07/1977", "tr"),
    ("220000002", "Busra", "Oz", "Ahmet", "18/04/1989", "tr"),
    # English-preference citizens
    ("230000002", "John", "Smith", "Robert", "10/02/1985", "en"),
    ("240000002", "Sarah", "Johnson", "Michael", "28/08/1992", "en"),
    ("250000002", "David", "Williams", "James", "15/05/1978", "en"),
]

# Applications: (citizen_index, ref, service_type, status)
# citizen_index is 0-based index into SEED_CITIZENS
SEED_APPLICATIONS = [
    # Ahmet — 2 applications (passport in_review, id_card approved)
    (0, "2024-TR-0001", "passport", "in_review"),
    (0, "2024-TR-0024", "id_card", "approved"),
    # Fatma — 1 application
    (1, "2024-TR-0002", "id_card", "approved"),
    # Mehmet — 2 applications (driver_license pending, passport rejected)
    (2, "2024-TR-0003", "driver_license", "pending"),
    (2, "2024-TR-0025", "passport", "rejected"),
    # Ayse — 1 application
    (3, "2024-TR-0004", "civil_registry", "rejected"),
    # Mustafa — 1 application
    (4, "2024-TR-0005", "passport", "in_review"),
    # Emine — 2 applications (id_card approved, civil_registry pending)
    (5, "2024-TR-0006", "id_card", "approved"),
    (5, "2024-TR-0026", "civil_registry", "pending"),
    # Huseyin — 1 application
    (6, "2024-TR-0007", "passport", "additional_docs_needed"),
    # Zeynep — 1 application
    (7, "2024-TR-0008", "driver_license", "pending"),
    # Ali — 1 application
    (8, "2024-TR-0009", "id_card", "in_review"),
    # Hatice — 1 application
    (9, "2024-TR-0010", "passport", "approved"),
    # Ibrahim — 1 application
    (10, "2024-TR-0011", "civil_registry", "pending"),
    # Meryem — 1 application
    (11, "2024-TR-0012", "driver_license", "in_review"),
    # Hasan — 1 application
    (12, "2024-TR-0013", "id_card", "approved"),
    # Elif — 1 application
    (13, "2024-TR-0014", "passport", "rejected"),
    # Omer — 1 application
    (14, "2024-TR-0015", "driver_license", "additional_docs_needed"),
    # Sule — 1 application
    (15, "2024-TR-0016", "civil_registry", "pending"),
    # Osman — 1 application
    (16, "2024-TR-0017", "passport", "in_review"),
    # Merve — 1 application
    (17, "2024-TR-0018", "id_card", "approved"),
    # Yusuf — 1 application
    (18, "2024-TR-0019", "driver_license", "pending"),
    # Busra — 1 application
    (19, "2024-TR-0020", "passport", "in_review"),
    # English citizens
    (20, "2024-EN-0001", "passport", "approved"),
    (21, "2024-EN-0002", "id_card", "in_review"),
    (22, "2024-EN-0003", "driver_license", "pending"),
]


def seed(reset: bool = False):
    """Populate the database with sample citizen records."""
    if reset:
        Base.metadata.drop_all(engine)
        print("Dropped all tables.")

    init_db()
    print("Tables created.")

    db = SessionLocal()
    try:
        existing = db.query(Citizen).count()
        if existing > 0 and not reset:
            print(f"Database already has {existing} records. Use --reset to recreate.")
            return

        # Seed citizens
        citizens = []
        for row in SEED_CITIZENS:
            first_9, first_name, last_name, father_name, dob, lang = row
            tc_kimlik = generate_valid_tc(first_9)

            citizen = Citizen(
                tc_kimlik_hash=hash_tc(tc_kimlik),
                first_name=first_name,
                last_name=last_name,
                father_name=father_name,
                date_of_birth=dob,
                language_preference=lang,
            )
            db.add(citizen)
            citizens.append(citizen)

        db.flush()  # Assign IDs before creating applications
        print(f"Seeded {len(SEED_CITIZENS)} citizen records.")

        # Seed applications (1:N with citizens)
        for citizen_idx, ref, service_type, status in SEED_APPLICATIONS:
            app = Application(
                citizen_id=citizens[citizen_idx].id,
                application_ref=ref,
                service_type=service_type,
                status=status,
            )
            db.add(app)

        print(f"Seeded {len(SEED_APPLICATIONS)} applications ({len([a for a in SEED_APPLICATIONS if a[0] in (0, 2, 5)])} citizens with multiple).")

        # Seed sample appointments
        appointments = [
            Appointment(citizen_id=citizens[0].id, service_type="passport", appointment_date="2026-04-07",
                       appointment_time="10:00", office="Kadikoy Nufus Mudurlugu"),
            Appointment(citizen_id=citizens[1].id, service_type="id_card", appointment_date="2026-04-08",
                       appointment_time="14:00", office="Uskudar Nufus Mudurlugu"),
            Appointment(citizen_id=citizens[2].id, service_type="driver_license", appointment_date="2026-04-09",
                       appointment_time="09:00", office="Besiktas Nufus Mudurlugu"),
            Appointment(citizen_id=citizens[0].id, service_type="id_card", appointment_date="2026-03-15",
                       appointment_time="11:00", office="Kadikoy Nufus Mudurlugu", status="completed"),
            Appointment(citizen_id=citizens[4].id, service_type="passport", appointment_date="2026-04-10",
                       appointment_time="15:00", office="Bakirkoy Nufus Mudurlugu"),
        ]
        db.add_all(appointments)

        # Seed sample document requests
        doc_requests = [
            DocumentRequest(citizen_id=citizens[0].id, document_type="birth_certificate",
                          request_ref="DOC-2026-0001", status="ready", estimated_days=3),
            DocumentRequest(citizen_id=citizens[1].id, document_type="residence_cert",
                          request_ref="DOC-2026-0002", status="processing", estimated_days=5),
            DocumentRequest(citizen_id=citizens[5].id, document_type="marriage_cert",
                          request_ref="DOC-2026-0003", status="delivered", estimated_days=3),
        ]
        db.add_all(doc_requests)

        db.commit()
        print(f"Seeded {len(appointments)} appointments, {len(doc_requests)} document requests.")

        # Print sample for verification (no raw TC Kimlik)
        print("\nSample records:")
        for c in db.query(Citizen).limit(3):
            apps = db.query(Application).filter(Application.citizen_id == c.id).all()
            app_strs = [f"{a.application_ref}({a.service_type}:{a.status})" for a in apps]
            print(f"  {c.first_name} {c.last_name} | apps: {', '.join(app_strs)}")

    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed citizen database")
    parser.add_argument("--reset", action="store_true", help="Drop and recreate tables")
    args = parser.parse_args()
    seed(reset=args.reset)
