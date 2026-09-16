"""
Applies schema.sql against Postgres. Safe to run multiple times
(everything in schema.sql uses IF NOT EXISTS).

Usage:
    python init_db.py
"""

from pathlib import Path

from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env")

from clients import get_pg_connection  # noqa: E402


def main():
    schema_sql = Path(__file__).resolve().parent / "schema.sql"
    sql = schema_sql.read_text()

    conn = get_pg_connection()
    cur = conn.cursor()
    cur.execute(sql)
    conn.commit()
    cur.close()
    conn.close()
    print("Schema applied: 'documents' table is ready.")


if __name__ == "__main__":
    main()
