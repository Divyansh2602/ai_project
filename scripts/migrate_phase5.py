"""Phase 5 DB migration — add signature/blockchain columns to audit_logs.

Idempotent (ADD COLUMN IF NOT EXISTS); safe to re-run. Uses DATABASE_URL from
backend/.env (Supabase session pooler).

Run from repo root:
  .\\backend\\venv\\Scripts\\python.exe scripts\\migrate_phase5.py
"""
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND))

from dotenv import load_dotenv

load_dotenv(BACKEND / ".env")

from sqlalchemy import text
from models.database import engine

STATEMENTS = [
    "ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS record_signature TEXT",
    "ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS signature_algorithm VARCHAR(32)",
    "ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS signature_key_fingerprint VARCHAR(128)",
    "ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS signed_payload JSONB",
    "ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS blockchain_network VARCHAR(32)",
    "ALTER TABLE audit_logs ADD COLUMN IF NOT EXISTS blockchain_status VARCHAR(32)",
]


def main():
    with engine.begin() as conn:
        for stmt in STATEMENTS:
            print(f"  {stmt}")
            conn.execute(text(stmt))
    print("[OK] audit_logs migrated for Phase 5.")


if __name__ == "__main__":
    main()
