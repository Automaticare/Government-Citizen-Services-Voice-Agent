"""
Seed the citizen database with 20+ realistic sample records.

Usage:
    python -m api.seed_data          # Seed the database
    python -m api.seed_data --reset  # Drop and recreate tables, then seed

TC Kimlik numbers use valid checksums. All PII is fictional.
"""

import argparse
import hashlib

from api.models import Base, Citizen, Appointment, DocumentRequest, SessionLocal, engine, init_db


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
SEED_CITIZENS = [
    # (first_9_digits, first_name, last_name, father_name, dob, app_ref, status, lang)
    ("100000001", "Ahmet", "Yilmaz", "Mehmet", "15/03/1990", "2024-TR-0001", "in_review", "tr"),
    ("200000002", "Fatma", "Kaya", "Ali", "22/07/1985", "2024-TR-0002", "approved", "tr"),
    ("300000003", "Mehmet", "Demir", "Hasan", "01/01/1978", "2024-TR-0003", "pending", "tr"),
    ("400000004", "Ayse", "Celik", "Mustafa", "30/11/1995", "2024-TR-0004", "rejected", "tr"),
    ("500000005", "Mustafa", "Sahin", "Ibrahim", "14/06/1982", "2024-TR-0005", "in_review", "tr"),
    ("600000006", "Emine", "Yildiz", "Osman", "08/09/1973", "2024-TR-0006", "approved", "tr"),
    ("700000007", "Huseyin", "Ozturk", "Yusuf", "25/12/1988", "2024-TR-0007", "additional_docs_needed", "tr"),
    ("800000008", "Zeynep", "Aydin", "Kemal", "03/04/1992", "2024-TR-0008", "pending", "tr"),
    ("900000009", "Ali", "Arslan", "Huseyin", "19/10/1980", "2024-TR-0009", "in_review", "tr"),
    ("110000001", "Hatice", "Dogan", "Ahmet", "27/02/1969", "2024-TR-0010", "approved", "tr"),
    ("120000001", "Ibrahim", "Kilic", "Omer", "11/08/1975", "2024-TR-0011", "pending", "tr"),
    ("130000001", "Meryem", "Koc", "Hasan", "05/05/1998", "2024-TR-0012", "in_review", "tr"),
    ("140000001", "Hasan", "Ozdemir", "Ali", "16/01/1987", "2024-TR-0013", "approved", "tr"),
    ("150000001", "Elif", "Polat", "Mehmet", "29/09/1993", "2024-TR-0014", "rejected", "tr"),
    ("160000001", "Omer", "Erdogan", "Mustafa", "07/12/1970", "2024-TR-0015", "additional_docs_needed", "tr"),
    ("170000001", "Sule", "Tas", "Ibrahim", "20/06/1984", "2024-TR-0016", "pending", "tr"),
    ("180000001", "Osman", "Cinar", "Yusuf", "12/03/1991", "2024-TR-0017", "in_review", "tr"),
    ("190000001", "Merve", "Acar", "Kemal", "23/11/1996", "2024-TR-0018", "approved", "tr"),
    ("210000002", "Yusuf", "Kurt", "Osman", "04/07/1977", "2024-TR-0019", "pending", "tr"),
    ("220000002", "Busra", "Oz", "Ahmet", "18/04/1989", "2024-TR-0020", "in_review", "tr"),
    # English-preference citizens
    ("230000002", "John", "Smith", "Robert", "10/02/1985", "2024-EN-0001", "approved", "en"),
    ("240000002", "Sarah", "Johnson", "Michael", "28/08/1992", "2024-EN-0002", "in_review", "en"),
    ("250000002", "David", "Williams", "James", "15/05/1978", "2024-EN-0003", "pending", "en"),
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

        for row in SEED_CITIZENS:
            first_9, first_name, last_name, father_name, dob, app_ref, status, lang = row
            tc_kimlik = generate_valid_tc(first_9)

            citizen = Citizen(
                tc_kimlik_hash=hash_tc(tc_kimlik),
                first_name=first_name,
                last_name=last_name,
                father_name=father_name,
                date_of_birth=dob,
                application_ref=app_ref,
                application_status=status,
                language_preference=lang,
            )
            db.add(citizen)

        db.commit()
        print(f"Seeded {len(SEED_CITIZENS)} citizen records.")

        # Seed sample appointments
        appointments = [
            Appointment(citizen_id=1, service_type="passport", appointment_date="2026-04-07",
                       appointment_time="10:00", office="Kadikoy Nufus Mudurlugu"),
            Appointment(citizen_id=2, service_type="id_card", appointment_date="2026-04-08",
                       appointment_time="14:00", office="Uskudar Nufus Mudurlugu"),
            Appointment(citizen_id=3, service_type="driver_license", appointment_date="2026-04-09",
                       appointment_time="09:00", office="Besiktas Nufus Mudurlugu"),
            Appointment(citizen_id=1, service_type="id_card", appointment_date="2026-03-15",
                       appointment_time="11:00", office="Kadikoy Nufus Mudurlugu", status="completed"),
            Appointment(citizen_id=5, service_type="passport", appointment_date="2026-04-10",
                       appointment_time="15:00", office="Bakirkoy Nufus Mudurlugu"),
        ]
        db.add_all(appointments)

        # Seed sample document requests
        doc_requests = [
            DocumentRequest(citizen_id=1, document_type="birth_certificate",
                          request_ref="DOC-2026-0001", status="ready", estimated_days=3),
            DocumentRequest(citizen_id=2, document_type="residence_cert",
                          request_ref="DOC-2026-0002", status="processing", estimated_days=5),
            DocumentRequest(citizen_id=6, document_type="marriage_cert",
                          request_ref="DOC-2026-0003", status="delivered", estimated_days=3),
        ]
        db.add_all(doc_requests)

        db.commit()
        print(f"Seeded {len(appointments)} appointments, {len(doc_requests)} document requests.")

        # Print sample for verification (no raw TC Kimlik)
        print("\nSample records:")
        for c in db.query(Citizen).limit(3):
            print(f"  {c.first_name} {c.last_name} | {c.application_ref} | {c.application_status}")

    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed citizen database")
    parser.add_argument("--reset", action="store_true", help="Drop and recreate tables")
    args = parser.parse_args()
    seed(reset=args.reset)
