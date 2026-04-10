import json
import sys
import time
from pathlib import Path
from datetime import datetime
from sqlalchemy.exc import IntegrityError

sys.path.insert(0, "/app")

from app.database import SessionLocal
from app.models.lead import Lead


def wait_for_database(max_retries=30, sleep_seconds=2):
    for i in range(max_retries):
        try:
            db = SessionLocal()
            db.query(Lead).limit(1).all()
            db.close()
            print("Database + tables ready")
            return True
        except Exception as e:
            print(f"Waiting for database/tables... ({i+1}/{max_retries}) -> {e}")
            time.sleep(sleep_seconds)

    print("Database not available after retries")
    return False


def normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def chunked(iterable, size=500):
    buf = []
    for item in iterable:
        buf.append(item)
        if len(buf) >= size:
            yield buf
            buf = []
    if buf:
        yield buf


def import_json_leads(json_file_path: str, commit_every: int = 200):
    db = SessionLocal()
    imported = skipped = errors = 0

    try:
        print(f"\nLoading: {Path(json_file_path).name}")

        with open(json_file_path, "r", encoding="utf-8") as f:
            leads_data = json.load(f)

        print(f"Found {len(leads_data):,} leads in file")

        # Build a list of candidate emails (normalized + valid)
        candidates = []
        for ld in leads_data:
            em = normalize_email(ld.get("email", ""))
            if em and "@" in em:
                candidates.append(em)

        # Prefetch existing emails in chunks to avoid N queries
        existing_emails = set()
        for email_chunk in chunked(candidates, size=800):
            rows = (
                db.query(Lead.email)
                .filter(Lead.email.in_(email_chunk))
                .all()
            )
            existing_emails.update(r[0].lower() for r in rows if r and r[0])

        pending_inserts = 0

        for idx, lead_data in enumerate(leads_data, start=1):
            try:
                email = normalize_email(lead_data.get("email", ""))
                if not email or "@" not in email:
                    skipped += 1
                    continue

                if email in existing_emails:
                    skipped += 1
                    continue

                company_name = (lead_data.get("company_name") or "").strip()
                executive_name = (lead_data.get("executive_name") or "").strip()

                name_parts = executive_name.split() if executive_name else []
                first_name = name_parts[0] if len(name_parts) > 0 else None
                last_name = " ".join(name_parts[1:]) if len(name_parts) > 1 else None

                state = (lead_data.get("state") or "").strip()
                location = state or "USA"

                lead = Lead(
                    email=email,
                    first_name=first_name,
                    last_name=last_name,
                    company=company_name or None,
                    industry="Wood",
                    location=location,
                    phone=(lead_data.get("phone") or "").strip() or None,
                    website=(lead_data.get("website") or "").strip() or None,
                    source=(lead_data.get("source") or "Google Maps Scraper").strip(),
                    status="new",
                    sequence_step=0,
                    agent_enabled=True,
                    agent_paused=False,
                    priority_score=5.0,
                    next_agent_check_at=datetime.utcnow(),
                )

                db.add(lead)
                imported += 1
                pending_inserts += 1
                existing_emails.add(email)  # prevent duplicates within same file

                if pending_inserts >= commit_every:
                    db.commit()
                    pending_inserts = 0
                    print(f"  Progress: {idx:,}/{len(leads_data):,}")

            except IntegrityError:
                # In case DB UNIQUE constraint catches a race/duplicate
                db.rollback()
                skipped += 1
                continue
            except Exception as e:
                db.rollback()
                errors += 1
                print(f"  Error importing row #{idx} ({lead_data.get('email')}): {e}")
                continue

        if pending_inserts:
            db.commit()

        print(f"File complete: {imported:,} imported, {skipped:,} skipped, {errors} errors")
        return imported, skipped, errors

    except FileNotFoundError:
        print(f"File not found: {json_file_path}")
        return 0, 0, 0
    except Exception as e:
        db.rollback()
        print(f"Error reading/importing file: {e}")
        return 0, 0, 1
    finally:
        db.close()


def import_all_scraped_leads():
    data_dir = Path("/app/data")
    if not data_dir.exists():
        print("/app/data folder not found")
        return

    json_files = list(data_dir.glob("carpentry_leads_*.json")) + list(data_dir.glob("session_*.json"))
    if not json_files:
        print("No JSON files found in /app/data folder")
        return

    print("=" * 70)
    print("AUTO-IMPORT SCRAPED LEADS")
    print("=" * 70)
    print(f"Found {len(json_files)} JSON files to process")

    total_imported = total_skipped = total_errors = 0
    start_time = time.time()

    for json_file in sorted(json_files):
        imported, skipped, errors = import_json_leads(str(json_file))
        total_imported += imported
        total_skipped += skipped
        total_errors += errors

    elapsed = time.time() - start_time

    print("\n" + "=" * 70)
    print("FINAL SUMMARY")
    print("=" * 70)
    print(f"Total imported: {total_imported:,}")
    print(f"Total skipped: {total_skipped:,}")
    print(f"Total errors: {total_errors}")
    print(f"Files processed: {len(json_files)}")
    print(f"Time taken: {elapsed/60:.1f} minutes")
    if elapsed > 0:
        print(f"Speed: {total_imported/(elapsed/60):.0f} leads/minute")
    print("=" * 70)


def main():
    print("Auto-Import Service Starting...\n")
    if not wait_for_database():
        sys.exit(1)

    import_all_scraped_leads()
    print("\nAuto-import service completed successfully")


if __name__ == "__main__":
    main()
