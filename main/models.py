from ormax_models import init_db, load_settings, update_settings, load_spam_protection, update_spam_protection

async def get_database(session_name):
    # For compatibility with existing code, but not used with Ormax
    pass

async def init_db(db):
    # Initialize Ormax database
    await init_db()
    pass

async def load_settings(db):
    return await load_settings()

async def update_settings(db, settings):
    await update_settings(settings)

async def load_spam_protection(db, user_id):
    return await load_spam_protection(user_id)

async def update_spam_protection(db, spam_data):
    await update_spam_protection(spam_data)