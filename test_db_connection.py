import asyncio
import os
import sys

# Add the main directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), 'main'))

from main.ormax_models import init_db

async def test_db_connection():
    print("Testing database connection...")
    try:
        db = await init_db()
        print("Database connected and tables created successfully!")
        return True
    except Exception as e:
        print(f"Error connecting to database: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    result = asyncio.run(test_db_connection())
    if result:
        print("Test passed!")
    else:
        print("Test failed!")