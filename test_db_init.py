#!/usr/bin/env python3
"""
Test script for database initialization
"""
import asyncio
import os
import sys

# Add the main directory to the path
sys.path.insert(0, os.path.dirname(__file__))

async def test_db_init():
    print("Testing database initialization...")
    try:
        from main.ormax_models import init_db
        db = await init_db()
        print("Database initialization successful!")
        return True
    except Exception as e:
        print(f"Database initialization failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    result = asyncio.run(test_db_init())
    sys.exit(0 if result else 1)