#!/usr/bin/env python3
"""
Simple test script to check database connectivity
"""
import asyncio
import os
import sys

# Add current directory to path
sys.path.insert(0, os.path.dirname(__file__))

# Test database connectivity
async def test_db():
    try:
        print("Testing database connectivity...")
        # Import and test database
        from main.ormax_models import init_db
        db = await init_db()
        print("Database connection successful!")
        return True
    except Exception as e:
        print(f"Database connection failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    result = asyncio.run(test_db())
    sys.exit(0 if result else 1)