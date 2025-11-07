import asyncio
import logging

from ormax_models import init_db as ormax_init_db
from ormax_models import load_settings as ormax_load_settings
from ormax_models import load_spam_protection as ormax_load_spam_protection
from ormax_models import update_settings as ormax_update_settings
from ormax_models import update_spam_protection as ormax_update_spam_protection

logger = logging.getLogger(__name__)


class MockDB:
    """Mock database class for compatibility with existing code"""

    def __init__(self):
        self._closed = False

    async def close(self):
        self._closed = True

    def __getitem__(self, key):
        # Make it behave like a dictionary for settings access
        return None

    def __setitem__(self, key, value):
        pass

    def __contains__(self, key):
        return False

    def get(self, key, default=None):
        return default

    def keys(self):
        return []

    def values(self):
        return []

    def items(self):
        return []


async def get_database(session_name):
    """Get database connection - returns MockDB for compatibility"""
    return MockDB()


async def init_db(db=None):
    """Initialize Ormax database"""
    try:
        await ormax_init_db()
        logger.info("Ormax database initialized successfully")
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        raise


async def load_settings(db=None):
    """Load settings with proper error handling"""
    try:
        settings = await ormax_load_settings()
        # Ensure essential keys exist
        if not settings:
            settings = {}

        # Set default values for critical settings
        default_settings = {
            "lang": "fa",
            "self_enabled": {},
            "self_global_enabled": False,
            "profile_settings": {
                "name_enabled": False,
                "bio_enabled": False,
                "status_enabled": False,
                "online_enabled": False,
                "title_enabled": False,
                "names": [],
                "bios": [],
                "statuses": [],
                "title": [],
            },
            "save_profile_enabled": {},
            "reaction_enabled": {},
            "typing_enabled": {},
            "action_enabled": {},
            "tick_enabled": {},
            "tag_enabled": {},
            "translate_mode_enabled": {},
            "translate_enabled": {},
            "hashtag_enabled": {},
            "signature_enabled": {},
            "auto_approve_enabled": {},
            "emoji_enabled": {},
            "bold_enabled": {},
            "underline_enabled": {},
            "code_enabled": {},
            "font_en_enabled": {},
            "font_fa_enabled": {},
            "strikethrough_enabled": {},
            "italic_enabled": {},
            "spoiler_enabled": {},
            "poker_enabled": {},
            "save_enabled": {},
            "save_pv_enabled": {},
        }

        # Merge defaults with existing settings
        for key, value in default_settings.items():
            if key not in settings:
                settings[key] = value

        logger.info(f"Settings loaded successfully with {len(settings)} keys")
        return settings

    except Exception as e:
        logger.error(f"Error loading settings: {e}")
        # Return default settings on error
        return {
            "lang": "fa",
            "self_global_enabled": False,
            "profile_settings": {
                "name_enabled": False,
                "bio_enabled": False,
                "status_enabled": False,
                "online_enabled": False,
                "title_enabled": False,
                "names": [],
                "bios": [],
                "statuses": [],
                "title": [],
            },
        }


async def update_settings(settings, db=None):
    """Update settings with proper error handling"""
    try:
        if not settings or not isinstance(settings, dict):
            logger.warning("update_settings called with invalid settings")
            return False

        result = await ormax_update_settings(settings)
        logger.info(f"Settings updated successfully with {len(settings)} keys")
        return result

    except Exception as e:
        logger.error(f"Error updating settings: {e}")
        return False


async def load_spam_protection(db=None, user_id=None):
    """Load spam protection settings"""
    try:
        return await ormax_load_spam_protection(user_id)
    except Exception as e:
        logger.error(f"Error loading spam protection: {e}")
        return {}


async def update_spam_protection(spam_data, db=None):
    """Update spam protection settings"""
    try:
        await ormax_update_spam_protection(spam_data)
        return True
    except Exception as e:
        logger.error(f"Error updating spam protection: {e}")
        return False


# Additional utility functions for settings management
async def get_user_setting(settings, user_id, setting_key, default=False):
    """Safely get a user-specific setting"""
    try:
        user_settings = settings.get(setting_key, {})
        if isinstance(user_settings, dict):
            return user_settings.get(user_id, default)
        return default
    except Exception as e:
        logger.error(
            f"Error getting user setting {setting_key} for user {user_id}: {e}"
        )
        return default


async def set_user_setting(settings, user_id, setting_key, value):
    """Safely set a user-specific setting"""
    try:
        if setting_key not in settings:
            settings[setting_key] = {}
        if not isinstance(settings[setting_key], dict):
            settings[setting_key] = {}
        settings[setting_key][user_id] = value
        return True
    except Exception as e:
        logger.error(
            f"Error setting user setting {setting_key} for user {user_id}: {e}"
        )
        return False


async def get_global_setting(settings, setting_key, default=False):
    """Safely get a global setting"""
    try:
        return settings.get(setting_key, default)
    except Exception as e:
        logger.error(f"Error getting global setting {setting_key}: {e}")
        return default


async def set_global_setting(settings, setting_key, value):
    """Safely set a global setting"""
    try:
        settings[setting_key] = value
        return True
    except Exception as e:
        logger.error(f"Error setting global setting {setting_key}: {e}")
        return False
