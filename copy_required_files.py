#!/usr/bin/env python3
"""
Script to copy required JSON files to the main directory
"""
import os
import shutil

def copy_files():
    print("Copying required JSON files...")
    
    # Source directory
    source_dir = "/root/Baex/main/modules"
    
    # Target directory
    target_dir = "/root/Baex/main"
    
    # Files to copy
    files = ["cmd.json", "msg.json"]
    
    for filename in files:
        source_path = os.path.join(source_dir, filename)
        target_path = os.path.join(target_dir, filename)
        
        if os.path.exists(source_path):
            try:
                shutil.copy2(source_path, target_path)
                print(f"Successfully copied {filename}")
            except Exception as e:
                print(f"Error copying {filename}: {e}")
        else:
            print(f"Source file not found: {source_path}")

if __name__ == "__main__":
    copy_files()