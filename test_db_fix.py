import asyncio
import os
import sys

# Add the main directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), 'main'))

from ormax_models import init_db, load_settings, update_settings

async def test_db_fix():
    print("Testing database fix...")
    
    try:
        # Initialize the database
        print("Initializing database...")
        db = await init_db()
        print("Database initialized successfully!")
        
        # Test loading settings
        print("Loading settings...")
        settings = await load_settings()
        print(f"Settings loaded: {settings}")
        
        print("All tests passed!")
        
    except Exception as e:
        print(f"Error during test: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_db_fix())