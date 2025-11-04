#!/usr/bin/env python3
"""
Setup script to copy required JSON files to the correct locations
"""
import os
import shutil

def setup_json_files():
    # Source directory where cmd.json and msg.json are located
    source_dir = "/home/vexorex/develops/robots/telegram/tgraf/selfs/grok/main/modules"
    
    # Target directories
    target_main_dir = "/home/vexorex/develops/robots/telegram/tgraf/selfs/grok/Baex/main"
    target_modules_dir = "/home/vexorex/develops/robots/telegram/tgraf/selfs/grok/Baex/main/modules"
    
    files_to_copy = ["cmd.json", "msg.json"]
    
    print("Setting up JSON files...")
    
    for filename in files_to_copy:
        source_path = os.path.join(source_dir, filename)
        
        # Copy to main directory
        target_path_main = os.path.join(target_main_dir, filename)
        if os.path.exists(source_path):
            try:
                shutil.copy2(source_path, target_path_main)
                print(f"Copied {filename} to {target_path_main}")
            except Exception as e:
                print(f"Failed to copy {filename} to {target_path_main}: {e}")
        else:
            print(f"Source file not found: {source_path}")
            
        # Copy to modules directory
        target_path_modules = os.path.join(target_modules_dir, filename)
        if os.path.exists(source_path):
            try:
                shutil.copy2(source_path, target_path_modules)
                print(f"Copied {filename} to {target_path_modules}")
            except Exception as e:
                print(f"Failed to copy {filename} to {target_path_modules}: {e}")
        else:
            print(f"Source file not found: {source_path}")

if __name__ == "__main__":
    setup_json_files()