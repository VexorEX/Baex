#!/usr/bin/env python3
"""
Permission check script
"""
import os

def check_permissions():
    print("=== Permission Check ===")
    current_dir = os.getcwd()
    print(f"Current directory: {current_dir}")
    
    # Check if we can write to current directory
    try:
        test_file = "permission_test.tmp"
        with open(test_file, "w") as f:
            f.write("test")
        print("✓ Can write to current directory")
        os.remove(test_file)
        print("✓ Can remove files from current directory")
    except Exception as e:
        print(f"✗ Cannot write to current directory: {e}")
    
    # Check if database file exists
    db_file = "selfbot.db"
    if os.path.exists(db_file):
        print(f"✓ Database file exists: {db_file}")
        print(f"  - Readable: {os.access(db_file, os.R_OK)}")
        print(f"  - Writable: {os.access(db_file, os.W_OK)}")
    else:
        print(f"○ Database file does not exist (will be created): {db_file}")
    
    print("========================")

if __name__ == "__main__":
    check_permissions()