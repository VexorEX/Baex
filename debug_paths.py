#!/usr/bin/env python3
"""
Debug script to check file paths and directory structure
"""
import os

def check_paths():
    print("=== Path Debug Information ===")
    
    # Current working directory
    print(f"Current working directory: {os.getcwd()}")
    
    # Script directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    print(f"Script directory: {script_dir}")
    
    # Main directory
    main_dir = os.path.join(script_dir, 'main')
    print(f"Main directory: {main_dir}")
    print(f"Main directory exists: {os.path.exists(main_dir)}")
    
    # Modules directory
    modules_dir = os.path.join(main_dir, 'modules')
    print(f"Modules directory: {modules_dir}")
    print(f"Modules directory exists: {os.path.exists(modules_dir)}")
    
    # Check for JSON files in modules directory
    if os.path.exists(modules_dir):
        json_files = [f for f in os.listdir(modules_dir) if f.endswith('.json')]
        print(f"JSON files in modules directory: {json_files}")
        
        for json_file in json_files:
            file_path = os.path.join(modules_dir, json_file)
            print(f"  {json_file}: {os.path.exists(file_path)}")
    
    # Check for JSON files in main directory
    if os.path.exists(main_dir):
        json_files = [f for f in os.listdir(main_dir) if f.endswith('.json')]
        print(f"JSON files in main directory: {json_files}")
        
        for json_file in json_files:
            file_path = os.path.join(main_dir, json_file)
            print(f"  {json_file}: {os.path.exists(file_path)}")

if __name__ == "__main__":
    check_paths()