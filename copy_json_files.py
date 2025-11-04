#!/usr/bin/env python3
"""
Script to copy JSON files to the correct locations
"""
import os
import shutil

def copy_json_files():
    print("Copying JSON files to correct locations...")
    
    # Source directory
    source_dir = "/root/Baex/main/modules"
    
    # Target directory (main directory)
    target_dir = "/root/Baex/main"
    
    files_to_copy = ["cmd.json", "msg.json"]
    
    for filename in files_to_copy:
        source_path = os.path.join(source_dir, filename)
        target_path = os.path.join(target_dir, filename)
        
        if os.path.exists(source_path):
            try:
                shutil.copy2(source_path, target_path)
                print(f"Successfully copied {filename} to {target_path}")
            except Exception as e:
                print(f"Failed to copy {filename}: {e}")
        else:
            print(f"Source file not found: {source_path}")

if __name__ == "__main__":
    copy_json_files()