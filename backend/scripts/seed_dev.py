#!/usr/bin/env python3
"""Seed a local dev user (idempotent).

Usage:
    python scripts/seed_dev.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.db import get_db_connection  # noqa: E402

DEV_EMAIL = "dev@ethic-companion.local"


def seed() -> None:
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, email FROM public.users WHERE email = %s",
                (DEV_EMAIL,),
            )
            existing = cur.fetchone()
            if existing:
                print(f"✅ Dev user already exists: {existing['email']}")
                return

            cur.execute(
                """
                INSERT INTO public.users (email, full_name)
                VALUES (%s, %s)
                RETURNING id, email
                """,
                (DEV_EMAIL, "Dev User"),
            )
            created = cur.fetchone()
        conn.commit()
        print(f"✅ Created dev user: {created['email']}")


if __name__ == "__main__":
    seed()
