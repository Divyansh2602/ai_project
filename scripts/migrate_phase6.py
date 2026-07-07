"""Phase 6 DB migration — add extras column to agent_results.

Idempotent (ADD COLUMN IF NOT EXISTS); safe to re-run. Uses DATABASE_URL from
backend/.env (Supabase session pooler).

Run from repo root:
  .\\backend\\venv\\Scripts\\python.exe scripts\\migrate_phase6.py
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
    "ALTER TABLE agent_results ADD COLUMN IF NOT EXISTS extras JSONB",
]


def main():
    with engine.begin() as conn:
        for stmt in STATEMENTS:
            print(f"  {stmt}")
            conn.execute(text(stmt))
    print("[OK] agent_results migrated for Phase 6.")


if __name__ == "__main__":
    main()
