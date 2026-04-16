#!/usr/bin/env python3
"""
Initialize Local PostgreSQL Database

This script creates all necessary tables for local development.
Run this after starting PostgreSQL via docker-compose.

Usage:
    python scripts/init_local_db.py
"""

import os
import sys
import psycopg

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import settings


def main():
    print("=" * 70)
    print("🗄️  INITIALIZING LOCAL DATABASE")
    print("=" * 70)
    print()

    schema_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "database",
        "schema_local.sql",
    )

    if not os.path.exists(schema_path):
        print(f"❌ Schema file not found at: {schema_path}")
        return 1

    # Read schema SQL
    with open(schema_path, "r") as f:
        schema_sql = f.read()

    print(f"📄 Schema file: {schema_path}")
    print(f"🔗 Database URL: {settings.DATABASE_URL}")
    print()

    try:
        print("🔄 Connecting to database...")
        conn = psycopg.connect(settings.DATABASE_URL)

        print("✅ Connected!")
        print()
        print("🔄 Executing schema...")

        with conn.cursor() as cur:
            cur.execute(schema_sql)

        conn.commit()
        print()
        print("✅ Schema executed successfully!")
        print()

        # Verify tables were created
        with conn.cursor() as cur:
            cur.execute("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                ORDER BY table_name
            """)
            tables = cur.fetchall()

        print("📊 Created tables:")
        for table in tables:
            print(f"   • {table[0]}")

        conn.close()

        print()
        print("=" * 70)
        print("✅ DATABASE READY!")
        print("=" * 70)
        print()
        print("🎉 You can now:")
        print("   1. Start the backend: python main.py")
        print("   2. Login with: test@example.com")
        print("   3. Test at: http://localhost:8000/docs")
        print()

        return 0

    except psycopg.OperationalError as e:
        print()
        print("❌ DATABASE CONNECTION FAILED")
        print()
        print("Error:", str(e))
        print()
        print("💡 Make sure PostgreSQL is running:")
        print("   cd backend")
        print("   docker-compose up -d")
        print()
        return 1

    except Exception as e:
        print()
        print("❌ ERROR:", str(e))
        print()
        return 1


if __name__ == "__main__":
    exit(main())
