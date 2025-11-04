from ormax_models import init_db as ormax_init_db, load_settings as ormax_load_settings, update_settings as ormax_update_settings, load_spam_protection as ormax_load_spam_protection, update_spam_protection as ormax_update_spam_protection

async def get_database(session_name):
    # For compatibility with existing code, but not used with Ormax
    pass

async def init_db(db):
    # Initialize Ormax database
    await ormax_init_db()
    pass

async def load_settings(db=None):
    return await ormax_load_settings()

async def update_settings(db=None, settings=None):
    await ormax_update_settings(settings)

async def load_spam_protection(db=None, user_id=None):
    return await ormax_load_spam_protection(user_id)

async def update_spam_protection(db=None, spam_data=None):
    await ormax_update_spam_protection(spam_data)