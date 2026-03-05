#!/usr/bin/env python3
"""Test connections to PostgreSQL and Weaviate"""
import sys
import psycopg2
import requests

def test_postgres():
    """Test PostgreSQL connection"""
    try:
        conn = psycopg2.connect(
            host="localhost",
            port=5432,
            database="ethic-companion",
            user="postgres",
            password="postgres"
        )
        cursor = conn.cursor()
        cursor.execute("SELECT version();")
        version = cursor.fetchone()[0]
        cursor.close()
        conn.close()
        print("✅ PostgreSQL connection successful")
        print(f"   Version: {version[:50]}...")
        return True
    except Exception as e:
        print(f"❌ PostgreSQL connection failed: {e}")
        return False

def test_weaviate():
    """Test Weaviate connection"""
    try:
        response = requests.get("http://localhost:8080/v1/meta")
        if response.status_code == 200:
            data = response.json()
            print("✅ Weaviate connection successful")
            print(f"   Version: {data.get('version', 'unknown')}")
            return True
        else:
            print(f"❌ Weaviate connection failed: HTTP {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Weaviate connection failed: {e}")
        return False

if __name__ == "__main__":
    print("Testing database connections...\n")

    postgres_ok = test_postgres()
    weaviate_ok = test_weaviate()

    print(f"\n{'='*50}")
    if postgres_ok and weaviate_ok:
        print("✅ All connections successful!")
        sys.exit(0)
    else:
        print("❌ Some connections failed")
        sys.exit(1)
