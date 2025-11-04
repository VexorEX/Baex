#!/usr/bin/env python3
"""
Detailed debug script for load_json paths
"""
import os
import sys

def debug_load_json_paths():
    print("=== Detailed load_json Path Debug ===")
    
    # Get the path where utils.py is located
    utils_path = "/root/Baex/main/utils.py"
    print(f"utils.py path: {utils_path}")
    
    # Calculate paths the same way load_json does
    utils_dir = os.path.dirname(utils_path)
    print(f"utils directory: {utils_dir}")
    
    main_dir = os.path.abspath(os.path.join(utils_dir, '../'))
    print(f"main directory: {main_dir}")
    
    modules_dir = os.path.join(main_dir, 'modules')
    print(f"modules directory: {modules_dir}")
    
    # Check if these directories exist
    print(f"\nDirectory checks:")
    print(f"main directory exists: {os.path.exists(main_dir)}")
    print(f"modules directory exists: {os.path.exists(modules_dir)}")
    
    # Check specific files
    cmd_json_path = os.path.join(modules_dir, 'cmd.json')
    msg_json_path = os.path.join(modules_dir, 'msg.json')
    
    print(f"\nFile checks:")
    print(f"cmd.json path: {cmd_json_path}")
    print(f"cmd.json exists: {os.path.exists(cmd_json_path)}")
    print(f"msg.json path: {msg_json_path}")
    print(f"msg.json exists: {os.path.exists(msg_json_path)}")
    
    # Also check fallback paths
    cmd_json_fallback = os.path.join(main_dir, 'cmd.json')
    msg_json_fallback = os.path.join(main_dir, 'msg.json')
    
    print(f"\nFallback file checks:")
    print(f"cmd.json fallback path: {cmd_json_fallback}")
    print(f"cmd.json fallback exists: {os.path.exists(cmd_json_fallback)}")
    print(f"msg.json fallback path: {msg_json_fallback}")
    print(f"msg.json fallback exists: {os.path.exists(msg_json_fallback)}")

if __name__ == "__main__":
    debug_load_json_paths()