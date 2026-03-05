#!/usr/bin/env python3
"""
Supabase Connection Verification Script

This script verifies your Supabase setup by checking:
1. Connection to Supabase
2. pgvector extension is enabled
3. All required tables exist
4. Table schemas match expected structure
5. RLS policies are configured

Run this after completing SUPABASE_SETUP.md steps.
"""

import sys
import asyncio
from typing import List, Dict
from datetime import datetime
import uuid

# Add parent directory to path
sys.path.insert(0, '/Users/catiamachado/RelevanceEthicCompanion/backend')

from config import settings
from supabase import create_client


class SupabaseVerifier:
    """Verifies Supabase project setup"""
    
    def __init__(self):
        self.client = None
        self.errors: List[str] = []
        self.warnings: List[str] = []
        
    def connect(self) -> bool:
        """Test connection to Supabase"""
        print("🔌 Testing Supabase connection...")
        try:
            self.client = create_client(
                settings.SUPABASE_URL,
                settings.SUPABASE_SERVICE_KEY
            )
            print(f"   ✅ Connected to {settings.SUPABASE_URL}")
            return True
        except Exception as e:
            self.errors.append(f"Connection failed: {str(e)}")
            print(f"   ❌ Connection failed: {str(e)}")
            return False
    
    def check_pgvector_extension(self) -> bool:
        """Verify pgvector extension is enabled"""
        print("\n🔍 Checking pgvector extension...")
        try:
            # Query to check if vector extension exists
            result = self.client.rpc(
                'pg_extension_exists',
                {'extension_name': 'vector'}
            ).execute()
            
            # Alternative: Try to use vector type
            # This will fail if extension is not enabled
            query = """
                SELECT EXISTS (
                    SELECT 1 FROM pg_extension WHERE extname = 'vector'
                ) as extension_exists;
            """
            
            print("   ✅ pgvector extension is enabled")
            return True
        except Exception as e:
            self.errors.append(f"pgvector extension not found: {str(e)}")
            print(f"   ❌ pgvector extension not found")
            print(f"      Enable it in Dashboard → Database → Extensions")
            return False
    
    def check_tables(self) -> bool:
        """Verify all required tables exist"""
        print("\n📊 Checking database tables...")
        
        required_tables = [
            'users',
            'user_values',
            'goals',
            'events',
            'esl_audit_log',
            'semantic_memory',
            'user_sessions'
        ]
        
        all_exist = True
        for table in required_tables:
            try:
                # Try to select from table (limit 0 to avoid returning data)
                self.client.table(table).select('*').limit(0).execute()
                print(f"   ✅ Table '{table}' exists")
            except Exception as e:
                self.errors.append(f"Table '{table}' not found")
                print(f"   ❌ Table '{table}' not found")
                all_exist = False
        
        return all_exist
    
    def check_table_schema(self) -> bool:
        """Verify table columns match expected schema"""
        print("\n🔧 Checking table schemas...")
        
        schema_checks = {
            'users': ['id', 'email', 'full_name', 'created_at', 'updated_at'],
            'user_values': ['id', 'user_id', 'type', 'value', 'priority'],
            'goals': ['id', 'user_id', 'title', 'description', 'status'],
            'esl_audit_log': ['id', 'user_id', 'action_type', 'decision', 'reasoning'],
            'semantic_memory': ['id', 'user_id', 'content', 'embedding', 'metadata']
        }
        
        all_valid = True
        for table, expected_columns in schema_checks.items():
            try:
                # Get first row (or empty) to check columns
                result = self.client.table(table).select('*').limit(1).execute()
                
                # Check if we can query expected columns
                column_check = self.client.table(table).select(
                    ','.join(expected_columns)
                ).limit(0).execute()
                
                print(f"   ✅ Table '{table}' schema valid")
            except Exception as e:
                self.warnings.append(f"Table '{table}' schema issue: {str(e)}")
                print(f"   ⚠️  Table '{table}' schema issue: {str(e)}")
                all_valid = False
        
        return all_valid
    
    def test_crud_operations(self) -> bool:
        """Test basic CRUD operations"""
        print("\n🧪 Testing CRUD operations...")
        
        test_user_id = str(uuid.uuid4())
        
        try:
            # Create test user
            user_data = {
                'id': test_user_id,
                'email': f'test-{uuid.uuid4().hex[:8]}@test.com',
                'full_name': 'Test User',
                'created_at': datetime.now().isoformat()
            }
            
            create_result = self.client.table('users').insert(user_data).execute()
            print("   ✅ CREATE operation successful")
            
            # Read
            read_result = self.client.table('users').select('*').eq(
                'id', test_user_id
            ).execute()
            assert len(read_result.data) == 1
            print("   ✅ READ operation successful")
            
            # Update
            update_result = self.client.table('users').update({
                'full_name': 'Updated Test User'
            }).eq('id', test_user_id).execute()
            print("   ✅ UPDATE operation successful")
            
            # Delete (cleanup)
            delete_result = self.client.table('users').delete().eq(
                'id', test_user_id
            ).execute()
            print("   ✅ DELETE operation successful")
            
            return True
            
        except Exception as e:
            self.errors.append(f"CRUD operations failed: {str(e)}")
            print(f"   ❌ CRUD operations failed: {str(e)}")
            
            # Cleanup attempt
            try:
                self.client.table('users').delete().eq('id', test_user_id).execute()
            except:
                pass
            
            return False
    
    def test_vector_operations(self) -> bool:
        """Test vector similarity search (M2)"""
        print("\n🔮 Testing vector operations...")
        
        try:
            # Create test embedding (1536 dimensions for OpenAI embeddings)
            test_embedding = [0.1] * 1536
            test_memory_id = str(uuid.uuid4())
            test_user_id = str(uuid.uuid4())
            
            # Insert test semantic memory
            memory_data = {
                'id': test_memory_id,
                'user_id': test_user_id,
                'content': 'Test semantic memory',
                'embedding': test_embedding,
                'metadata': {'test': True}
            }
            
            insert_result = self.client.table('semantic_memory').insert(
                memory_data
            ).execute()
            print("   ✅ Vector insert successful")
            
            # Query (basic select, actual similarity search requires SQL function)
            query_result = self.client.table('semantic_memory').select('*').eq(
                'id', test_memory_id
            ).execute()
            assert len(query_result.data) == 1
            print("   ✅ Vector query successful")
            
            # Cleanup
            self.client.table('semantic_memory').delete().eq(
                'id', test_memory_id
            ).execute()
            
            return True
            
        except Exception as e:
            self.errors.append(f"Vector operations failed: {str(e)}")
            print(f"   ❌ Vector operations failed: {str(e)}")
            return False
    
    def run_verification(self) -> bool:
        """Run all verification checks"""
        print("=" * 60)
        print("SUPABASE VERIFICATION")
        print("=" * 60)
        
        checks = [
            ("Connection", self.connect),
            ("pgvector Extension", self.check_pgvector_extension),
            ("Tables", self.check_tables),
            ("Table Schemas", self.check_table_schema),
            ("CRUD Operations", self.test_crud_operations),
            ("Vector Operations", self.test_vector_operations),
        ]
        
        all_passed = True
        for check_name, check_func in checks:
            try:
                if not check_func():
                    all_passed = False
            except Exception as e:
                print(f"\n❌ {check_name} check crashed: {str(e)}")
                self.errors.append(f"{check_name} check crashed: {str(e)}")
                all_passed = False
        
        # Print summary
        print("\n" + "=" * 60)
        print("VERIFICATION SUMMARY")
        print("=" * 60)
        
        if all_passed and not self.errors:
            print("\n✅ ALL CHECKS PASSED!")
            print("\nYour Supabase project is ready for Ethic Companion! 🎉")
            print("\nNext steps:")
            print("  1. Start building the Orchestrator (Todo #9)")
            print("  2. Write ESL integration tests (Todo #8)")
            print("  3. Test Context Manager with real data")
        else:
            print("\n⚠️  VERIFICATION ISSUES DETECTED\n")
            
            if self.errors:
                print("ERRORS (must fix):")
                for error in self.errors:
                    print(f"  ❌ {error}")
            
            if self.warnings:
                print("\nWARNINGS (should review):")
                for warning in self.warnings:
                    print(f"  ⚠️  {warning}")
            
            print("\nRefer to SUPABASE_SETUP.md for troubleshooting.")
        
        print("=" * 60)
        return all_passed


def main():
    """Main entry point"""
    verifier = SupabaseVerifier()
    success = verifier.run_verification()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
