#!/usr/bin/env python3
"""
Test script for vars module
"""
import asyncio
import os
import sys

# Add the main directory to the path
sys.path.insert(0, os.path.dirname(__file__))

def test_get_command_pattern():
    print("Testing get_command_pattern function...")
    try:
        from main.utils import get_command_pattern
        # Test with English language
        pattern = get_command_pattern('list_timezones', 'en')
        print(f"English pattern for 'list_timezones': {pattern}")
        
        # Test with Farsi language
        pattern = get_command_pattern('list_timezones', 'fa')
        print(f"Farsi pattern for 'list_timezones': {pattern}")
        
        print("get_command_pattern test passed!")
        return True
    except Exception as e:
        print(f"get_command_pattern test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    result = test_get_command_pattern()
    sys.exit(0 if result else 1)