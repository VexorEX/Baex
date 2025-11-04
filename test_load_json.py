#!/usr/bin/env python3
"""
Debug script to check load_json function
"""
import os
import sys

# Add main directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'main'))

def test_load_json():
    print("=== Testing load_json function ===")
    
    try:
        from main.utils import load_json
        
        print("Testing cmd.json:")
        cmd_data = load_json('cmd.json')
        print(f"cmd.json loaded successfully, keys: {len(cmd_data) if cmd_data else 0}")
        if cmd_data:
            print(f"Languages in cmd.json: {list(cmd_data.keys())}")
        
        print("\nTesting msg.json:")
        msg_data = load_json('msg.json')
        print(f"msg.json loaded successfully, keys: {len(msg_data) if msg_data else 0}")
        if msg_data:
            print(f"Languages in msg.json: {list(msg_data.keys())}")
            
    except Exception as e:
        print(f"Error testing load_json: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_load_json()