from ormax import Model
from ormax.fields import CharField, IntegerField, BooleanField, JSONField
from typing import Dict, Any, List, Optional
import json
from datetime import datetime
import asyncio

# Ormax Database setup
class BaseModel(Model):
    class Meta:
        database = "sqlite:///selfbot.db"  # Shared DB path

class Settings(BaseModel):
    class Meta:
        table = "settings"

    id = IntegerField(primary_key=True)
    lang = CharField(max_length=10, default="fa")
    welcome_enabled = BooleanField(default=False)
    welcome_text = CharField(max_length=500, default="")
    welcome_delete_time = IntegerField(default=0)
    clock_enabled = BooleanField(default=False)
    clock_location = CharField(max_length=20, default="name")
    clock_bio_text = CharField(max_length=500, default="")
    clock_fonts = JSONField(default=list)  # List of fonts
    clock_timezone = CharField(max_length=50, default="Asia/Tehran")
    action_enabled = BooleanField(default=False)
    action_types = JSONField(default=dict)  # Dict of action types
    text_format_enabled = BooleanField(default=False)
    text_formats = JSONField(default=dict)  # Dict of formats
    locks = JSONField(default=dict)  # Dict of locks
    antilog_enabled = BooleanField(default=False)
    first_comment_enabled = BooleanField(default=False)
    first_comment_text = CharField(max_length=500, default="")

class MuteList(BaseModel):
    class Meta:
        table = "mute_list"

    id = IntegerField(primary_key=True, auto_increment=True)
    user_id = IntegerField(unique=True)
    mute_until = IntegerField(default=0)
    reason = CharField(max_length=255, default="")

class SpamProtection(BaseModel):
    class Meta:
        table = "spam_protection"

    id = IntegerField(primary_key=True, auto_increment=True)
    user_id = IntegerField(unique=True)
    messages = JSONField(default=list)  # List of message IDs/timestamps
    mute_until = IntegerField(default=0)
    violations = IntegerField(default=0)
    last_violation = CharField(max_length=50, default=str(datetime.now()))  # As string for simplicity

class AutoReplies(BaseModel):
    class Meta:
        table = "auto_replies"

    id = IntegerField(primary_key=True, auto_increment=True)
    trigger = CharField(max_length=255, unique=True)
    response = CharField(max_length=1000)

class Enemies(BaseModel):
    class Meta:
        table = "enemies"

    id = IntegerField(primary_key=True, auto_increment=True)
    user_id = IntegerField(unique=True)
    type = CharField(max_length=10, default="pv")  # pv or group
    group_id = IntegerField(default=0)
    reason = CharField(max_length=255, default="")

# Global DB instance
db = BaseModel.Meta.database

async def init_db(db):
    """
    Initialize the database with Ormax (creates tables automatically).
    """
    await db.connect()
    await db.create_tables([Settings, MuteList, SpamProtection, AutoReplies, Enemies], safe=True)
    print("All tables initialized with Ormax.")

async def load_settings(db=None) -> Dict[str, Any]:
    """
    Load settings from the database.
    """
    try:
        setting = await Settings.get(id=1)
    except:
        # Create default if not exists
        setting = await Settings.create(
            id=1,
            lang="fa",
            welcome_enabled=False,
            welcome_text="",
            welcome_delete_time=0,
            clock_enabled=False,
            clock_location="name",
            clock_bio_text="",
            clock_fonts=[1],
            clock_timezone="Asia/Tehran",
            action_enabled=False,
            action_types={},
            text_format_enabled=False,
            text_formats={},
            locks={},
            antilog_enabled=False,
            first_comment_enabled=False,
            first_comment_text=""
        )

    return {
        'id': setting.id,
        'lang': setting.lang,
        'welcome_enabled': setting.welcome_enabled,
        'welcome_text': setting.welcome_text,
        'welcome_delete_time': setting.welcome_delete_time,
        'clock_enabled': setting.clock_enabled,
        'clock_location': setting.clock_location,
        'clock_bio_text': setting.clock_bio_text,
        'clock_fonts': setting.clock_fonts or [],
        'clock_timezone': setting.clock_timezone,
        'action_enabled': setting.action_enabled,
        'action_types': setting.action_types or {},
        'text_format_enabled': setting.text_format_enabled,
        'text_formats': setting.text_formats or {},
        'locks': setting.locks or {},
        'antilog_enabled': setting.antilog_enabled,
        'first_comment_enabled': setting.first_comment_enabled,
        'first_comment_text': setting.first_comment_text
    }

async def update_settings(settings: Dict[str, Any], db=None):
    """
    Update settings in the database.
    """
    try:
        setting = await Settings.get(id=1)
        for key, value in settings.items():
            if hasattr(setting, key):
                setattr(setting, key, value)
        await setting.save()
        return True
    except Exception as e:
        # If not exists, create
        try:
            await Settings.create(id=1, **settings)
            return True
        except Exception as e2:
            print(f"Error updating settings: {e2}")
            return False

async def load_spam_protection(user_id: int) -> Dict[str, Any]:
    """
    Load spam protection data for a user.
    """
    try:
        spam = await SpamProtection.get(user_id=user_id)
    except:
        spam = await SpamProtection.create(
            user_id=user_id,
            messages=[],
            mute_until=0,
            violations=0
        )

    return {
        'id': spam.id,
        'user_id': spam.user_id,
        'messages': spam.messages or [],
        'mute_until': spam.mute_until,
        'violations': spam.violations,
        'last_violation': spam.last_violation
    }

async def update_spam_protection(spam_data: Dict[str, Any]):
    """
    Update spam protection data for a user.
    """
    try:
        spam = await SpamProtection.get(user_id=spam_data['user_id'])
        for key, value in spam_data.items():
            if hasattr(spam, key):
                setattr(spam, key, value)
        await spam.save()
    except:
        await SpamProtection.create(**spam_data)

async def add_mute(user_id: int, mute_until: int = 0, reason: str = ""):
    """
    Add or update a mute for a user.
    """
    try:
        mute = await MuteList.get(user_id=user_id)
        mute.mute_until = mute_until
        mute.reason = reason
        await mute.save()
    except:
        await MuteList.create(user_id=user_id, mute_until=mute_until, reason=reason)

async def remove_mute(user_id: int):
    """
    Remove a mute for a user.
    """
    try:
        mute = await MuteList.get(user_id=user_id)
        await mute.delete()
    except:
        pass

async def is_muted(user_id: int) -> bool:
    """
    Check if a user is muted (active).
    """
    try:
        mute = await MuteList.get(user_id=user_id)
        if mute.mute_until > int(asyncio.get_event_loop().time() * 1000):
            return True
        else:
            await mute.delete()  # Expired, remove
            return False
    except:
        return False

async def load_auto_replies() -> Dict[str, str]:
    """
    Load all auto replies.
    """
    replies = await AutoReplies.all()
    return {reply.trigger: reply.response for reply in replies}

async def add_auto_reply(trigger: str, response: str):
    """
    Add or update an auto reply.
    """
    try:
        reply = await AutoReplies.get(trigger=trigger)
        reply.response = response
        await reply.save()
    except:
        await AutoReplies.create(trigger=trigger, response=response)

async def remove_auto_reply(trigger: str):
    """
    Remove an auto reply.
    """
    try:
        reply = await AutoReplies.get(trigger=trigger)
        await reply.delete()
    except:
        pass

async def load_enemies(type_filter: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Load enemies list (pv or group).
    """
    query = Enemies.all()
    if type_filter:
        query = query.filter(type=type_filter)
    enemies = await query
    return [{'id': e.id, 'user_id': e.user_id, 'type': e.type, 'group_id': e.group_id, 'reason': e.reason} for e in enemies]

async def add_enemy(user_id: int, enemy_type: str = 'pv', group_id: int = 0, reason: str = ""):
    """
    Add or update an enemy.
    """
    try:
        enemy = await Enemies.get(user_id=user_id)
        enemy.type = enemy_type
        enemy.group_id = group_id
        enemy.reason = reason
        await enemy.save()
    except:
        await Enemies.create(user_id=user_id, type=enemy_type, group_id=group_id, reason=reason)

async def remove_enemy(user_id: int):
    """
    Remove an enemy.
    """
    try:
        enemy = await Enemies.get(user_id=user_id)
        await enemy.delete()
    except:
        pass

async def close_db(db):
    """
    Close the database connection.
    """
    await db.disconnect()