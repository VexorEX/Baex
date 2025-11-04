import asyncio
import sys
import os

# Add the main directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), 'main'))

from ormax_models import init_db, load_settings, update_settings, load_spam_protection, update_spam_protection

async def test_ormax():
    print("Testing Ormax ORM implementation...")
    
    # Initialize the database
    print("Initializing database...")
    db = await init_db()
    print("Database initialized successfully!")
    
    # Test loading settings
    print("Loading settings...")
    settings = await load_settings()
    print(f"Settings loaded: {settings}")
    
    # Test updating settings
    print("Updating settings...")
    settings['lang'] = 'en'
    settings['welcome_enabled'] = True
    settings['welcome_text'] = 'Welcome to our service!'
    await update_settings(settings)
    print("Settings updated!")
    
    # Load settings again to verify update
    print("Loading settings again to verify update...")
    updated_settings = await load_settings()
    print(f"Updated settings: {updated_settings}")
    
    # Test spam protection
    print("Testing spam protection...")
    user_id = 12345
    spam_data = await load_spam_protection(user_id)
    print(f"Spam protection data for user {user_id}: {spam_data}")
    
    # Update spam protection
    spam_data['messages'] = ['msg1', 'msg2', 'msg3']
    spam_data['violations'] = 2
    await update_spam_protection(spam_data)
    print("Spam protection updated!")
    
    # Load spam protection again to verify update
    updated_spam_data = await load_spam_protection(user_id)
    print(f"Updated spam protection data: {updated_spam_data}")
    
    print("All tests completed successfully!")

if __name__ == "__main__":
    asyncio.run(test_ormax())