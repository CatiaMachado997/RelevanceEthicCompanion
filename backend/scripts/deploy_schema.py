#!/usr/bin/env python3
"""
Quick Supabase Schema Deployment

This script helps you deploy the database schema to Supabase.
It provides the SQL that you need to copy-paste into Supabase SQL Editor.

Usage:
    python scripts/deploy_schema.py
"""

import os


def main():
    schema_path = (
        "/Users/catiamachado/RelevanceEthicCompanion/backend/database/schema.sql"
    )

    print("=" * 70)
    print("SUPABASE SCHEMA DEPLOYMENT HELPER")
    print("=" * 70)
    print()
    print("📋 Instructions:")
    print("   1. Go to your Supabase Dashboard → SQL Editor")
    print("   2. Click 'New query'")
    print("   3. Copy the SQL below")
    print("   4. Paste into the SQL editor")
    print("   5. Click 'Run' (or press Cmd/Ctrl + Enter)")
    print()
    print("=" * 70)
    print()

    # Read and display schema
    if os.path.exists(schema_path):
        with open(schema_path, "r") as f:
            schema_sql = f.read()

        print("📄 SCHEMA SQL (copy everything below):")
        print("-" * 70)
        print(schema_sql)
        print("-" * 70)
        print()
        print("✅ Copy the SQL above and run it in Supabase SQL Editor")
        print()
        print("After running, verify in Table Editor that you see:")
        print("  • users")
        print("  • user_values")
        print("  • goals")
        print("  • events")
        print("  • esl_audit_log")
        print("  • semantic_memory")
        print("  • user_sessions")
        print()
    else:
        print(f"❌ Schema file not found at: {schema_path}")
        print("   Make sure you're running this from the backend directory")
        return 1

    print("=" * 70)
    print("Next step: Run 'python scripts/verify_supabase.py' to test connection")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    exit(main())
