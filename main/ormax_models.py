import asyncio
from ormax import Database, Model
from ormax.fields import AutoField, CharField, BooleanField, IntegerField, TextField, JSONField, DateTimeField
import json
from typing import Dict, Any, Optional
import aiosqlite
import os

# Initialize database
import os
# Use a path in the /tmp directory which should be writable
DB_PATH = "/tmp/selfbot.db"
db = Database(f"sqlite:///{DB_PATH}")

class Settings(Model):
    id = AutoField()
    lang = CharField(max_length=10, default='fa')
    welcome_enabled = BooleanField(default=False)
    welcome_text = TextField(default='')
    welcome_delete_time = IntegerField(default=0)
    clock_enabled = BooleanField(default=False)
    clock_location = CharField(max_length=50, default='name')
    clock_bio_text = TextField(default='')
    clock_fonts = JSONField(default=[1])
    clock_timezone = CharField(max_length=50, default='Asia/Tehran')
    action_enabled = BooleanField(default=False)
    action_types = JSONField(default={})
    text_format_enabled = BooleanField(default=False)
    text_formats = JSONField(default={})
    locks = JSONField(default={})
    antilog_enabled = BooleanField(default=False)
    first_comment_enabled = BooleanField(default=False)
    first_comment_text = TextField(default='')

    class Meta:
        table_name = 'settings'

class MuteList(Model):
    id = AutoField()
    user_id = IntegerField()
    mute_until = IntegerField(default=0)

    class Meta:
        table_name = 'mute_list'

class SpamProtection(Model):
    id = AutoField()
    user_id = IntegerField()
    messages = JSONField(default=[])
    mute_until = IntegerField(default=0)
    violations = IntegerField(default=0)

    class Meta:
        table_name = 'spam_protection'

async def init_db():
    """Initialize the database and create tables"""
    try:
        # Ensure the directory exists
        db_dir = os.path.dirname(DB_PATH)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
        
        await db.connect()
        db.register_model(Settings)
        db.register_model(MuteList)
        db.register_model(SpamProtection)
        await db.create_tables()
    except Exception as e:
        print(f"Error initializing database: {e}")
        raise
    
    # Create default settings if not exists
    try:
        settings = await Settings.objects().get(id=1)
    except:
        settings = await Settings.create(
            id=1,
            lang='fa',
            welcome_enabled=False,
            welcome_text='',
            welcome_delete_time=0,
            clock_enabled=False,
            clock_location='name',
            clock_bio_text='',
            clock_fonts=[1],
            clock_timezone='Asia/Tehran',
            action_enabled=False,
            action_types={},
            text_format_enabled=False,
            text_formats={},
            locks={},
            antilog_enabled=False,
            first_comment_enabled=False,
            first_comment_text=''
        )
    
    return db

async def load_settings() -> Dict[str, Any]:
    """Load settings from database"""
    try:
        settings = await Settings.objects().get(id=1)
        return {
            'id': settings.id,
            'lang': settings.lang,
            'welcome_enabled': settings.welcome_enabled,
            'welcome_text': settings.welcome_text,
            'welcome_delete_time': settings.welcome_delete_time,
            'clock_enabled': settings.clock_enabled,
            'clock_location': settings.clock_location,
            'clock_bio_text': settings.clock_bio_text,
            'clock_fonts': settings.clock_fonts,
            'clock_timezone': settings.clock_timezone,
            'action_enabled': settings.action_enabled,
            'action_types': settings.action_types,
            'text_format_enabled': settings.text_format_enabled,
            'text_formats': settings.text_formats,
            'locks': settings.locks,
            'antilog_enabled': settings.antilog_enabled,
            'first_comment_enabled': settings.first_comment_enabled,
            'first_comment_text': settings.first_comment_text
        }
    except Exception as e:
        print(f"Error loading settings: {e}")
        # Return default settings
        return {
            'id': 1,
            'lang': 'fa',
            'welcome_enabled': False,
            'welcome_text': '',
            'welcome_delete_time': 0,
            'clock_enabled': False,
            'clock_location': 'name',
            'clock_bio_text': '',
            'clock_fonts': [1],
            'clock_timezone': 'Asia/Tehran',
            'action_enabled': False,
            'action_types': {},
            'text_format_enabled': False,
            'text_formats': {},
            'locks': {},
            'antilog_enabled': False,
            'first_comment_enabled': False,
            'first_comment_text': ''
        }

async def update_settings(settings_data: Dict[str, Any]):
    """Update settings in database"""
    try:
        settings = await Settings.objects().get(id=1)
        # Update all fields
        settings.lang = settings_data['lang']
        settings.welcome_enabled = settings_data['welcome_enabled']
        settings.welcome_text = settings_data['welcome_text']
        settings.welcome_delete_time = settings_data['welcome_delete_time']
        settings.clock_enabled = settings_data['clock_enabled']
        settings.clock_location = settings_data['clock_location']
        settings.clock_bio_text = settings_data['clock_bio_text']
        settings.clock_fonts = settings_data['clock_fonts']
        settings.clock_timezone = settings_data['clock_timezone']
        settings.action_enabled = settings_data['action_enabled']
        settings.action_types = settings_data['action_types']
        settings.text_format_enabled = settings_data['text_format_enabled']
        settings.text_formats = settings_data['text_formats']
        settings.locks = settings_data['locks']
        settings.antilog_enabled = settings_data['antilog_enabled']
        settings.first_comment_enabled = settings_data['first_comment_enabled']
        settings.first_comment_text = settings_data['first_comment_text']
        
        await settings.save()
        return True
    except Exception as e:
        print(f"Error updating settings: {e}")
        return False

async def load_spam_protection(user_id: int) -> Dict[str, Any]:
    """Load spam protection data for a user"""
    try:
        spam_data = await SpamProtection.objects().get(user_id=user_id)
        return {
            'id': spam_data.id,
            'user_id': spam_data.user_id,
            'messages': spam_data.messages,
            'mute_until': spam_data.mute_until,
            'violations': spam_data.violations
        }
    except:
        # Create new spam protection entry
        spam_data = await SpamProtection.create(
            user_id=user_id,
            messages=[],
            mute_until=0,
            violations=0
        )
        return {
            'id': spam_data.id,
            'user_id': spam_data.user_id,
            'messages': spam_data.messages,
            'mute_until': spam_data.mute_until,
            'violations': spam_data.violations
        }

async def update_spam_protection(spam_data: Dict[str, Any]):
    """Update spam protection data"""
    try:
        # Try to get existing record
        spam_record = await SpamProtection.objects().get(user_id=spam_data['user_id'])
        spam_record.messages = spam_data['messages']
        spam_record.mute_until = spam_data['mute_until']
        spam_record.violations = spam_data['violations']
        await spam_record.save()
    except:
        # Create new record
        await SpamProtection.create(
            user_id=spam_data['user_id'],
            messages=spam_data['messages'],
            mute_until=spam_data['mute_until'],
            violations=spam_data['violations']
        )