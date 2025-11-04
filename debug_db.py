#!/usr/bin/env python3
"""
Debug script to check database connectivity and permissions
"""
import asyncio
import os

# Print current working directory
print(f"Current working directory: {os.getcwd()}")

# Check permissions
current_dir = os.getcwd()
print(f"Directory exists: {os.path.exists(current_dir)}")
print(f"Directory is readable: {os.access(current_dir, os.R_OK)}")
print(f"Directory is writable: {os.access(current_dir, os.W_OK)}")
print(f"Directory is executable: {os.access(current_dir, os.X_OK)}")

# Try to create a test file
try:
    test_file = "test_write.txt"
    with open(test_file, "w") as f:
        f.write("test")
    print(f"Successfully created test file: {test_file}")
    os.remove(test_file)
    print(f"Successfully removed test file: {test_file}")
except Exception as e:
    print(f"Failed to create test file: {e}")

# Try database connection
try:
    print("Attempting to import ormax_models...")
    from main.ormax_models import init_db, DB_PATH
    print(f"Database path: {DB_PATH}")
    print(f"Database path exists: {os.path.exists(DB_PATH)}")
    print(f"Database directory: {os.path.dirname(DB_PATH)}")
    
    if os.path.dirname(DB_PATH):
        db_dir = os.path.dirname(DB_PATH)
        print(f"Database directory exists: {os.path.exists(db_dir)}")
        print(f"Database directory readable: {os.access(db_dir, os.R_OK)}")
        print(f"Database directory writable: {os.access(db_dir, os.W_OK)}")
        print(f"Database directory executable: {os.access(db_dir, os.X_OK)}")
    
    print("Attempting database connection...")
    #asyncio.run(init_db())
    print("Database connection successful!")
except Exception as e:
    print(f"Database connection failed: {e}")
    import traceback
    traceback.print_exc()