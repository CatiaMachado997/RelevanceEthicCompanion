#!/usr/bin/env python3
"""Initialize Weaviate schemas"""
import sys
sys.path.insert(0, '/Users/catiamachado/RelevanceEthicCompanion/backend')

from utils.weaviate_client import get_weaviate_client

try:
    print("Connecting to Weaviate...")
    client = get_weaviate_client()
    print("✅ Weaviate schemas initialized successfully!")
except Exception as e:
    print(f"❌ Error: {e}")
    sys.exit(1)
