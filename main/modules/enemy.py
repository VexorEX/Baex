import asyncio
import logging
import random
import re
from datetime import datetime
from telethon import events
from telethon.errors import FloodWaitError
from utils import load_json, send_message, get_command_pattern
from models import get_database, load_settings, update_settings

logger = logging.getLogger(__name__)

async def register_enemy_handlers(client, session_name, owner_id):
    db = await get_database(session_name)
    settings = await load_settings(db)
    if not settings:
        logger.error("Failed to load settings for enemy handlers")
        await db.close()
        return

    lang = settings.get('lang', 'fa')
    messages = load_json('msg.json')
    commands = load_json('cmd.json')

    def get_message(key, **kwargs):
        return messages[lang]['enemy'].get(key, '').format(**kwargs)

    # تنظیمات اولیه enemy
    if 'enemy' not in settings:
        settings['enemy'] = {
            'enabled': False,
            'delay_enabled': False,
            'delay_time': 0,  # ثانیه
            'typing_pause': [2, 5],  # محدوده مکث تایپینگ
            'delete_enemy_messages': False,
            'signature': '',
            'friend_signature': '',
            'enemies': {
                'all_chats': {},  # {user_id: {'last_insult': timestamp}}
                'pv': {},  # {user_id: {'chat_id': id, 'last_insult': timestamp}}
                'groups': {},  # {user_id: {'chat_id': id, 'last_insult': timestamp}}
                'this_chat': {}  # {user_id: {'chat_id': id, 'last_insult': timestamp}}
            },
            'friends': {
                'all_chats': {},  # دوست دشمن
                'pv': {},
                'groups': {},
                'this_chat': {}
            },
            'insults': [],  # لیست فحش‌ها
            'friend_insults': []  # لیست فحش‌های دوست دشمن
        }
        await update_settings(db, settings)

    # ایجاد جدول برای دشمنان و فحش‌ها
    await db.execute('''
                     CREATE TABLE IF NOT EXISTS enemies (
                                                            user_id INTEGER,
                                                            mode TEXT,
                                                            chat_id INTEGER,
                                                            last_insult REAL,
                                                            PRIMARY KEY (user_id, mode, chat_id)
                         )
                     ''')
    await db.execute('''
                     CREATE TABLE IF NOT EXISTS insults (
                                                            text TEXT,
                                                            type TEXT,  -- 'enemy' یا 'friend'
                                                            PRIMARY KEY (text, type)
                         )
                     ''')
    await db.commit()

    async def add_enemy(user_id, mode, chat_id=None):
        """اضافه کردن دشمن"""
        try:
            timestamp = datetime.now().timestamp()
            await db.execute('''
                INSERT OR REPLACE INTO enemies (user_id, mode, chat_id, last_insult)
                VALUES (?, ?, ?, ?)
            ''', (user_id, mode, chat_id, timestamp))
            await db.commit()
            settings['enemy']['enemies'][mode][user_id] = {'chat_id': chat_id, 'last_insult': timestamp}
            await update_settings(db, settings)
        except Exception as e:
            logger.error(f"Error adding enemy: {e}")

    async def remove_enemy(user_id, mode, chat_id=None):
        """حذف دشمن"""
        try:
            await db.execute('DELETE FROM enemies WHERE user_id = ? AND mode = ? AND (chat_id = ? OR chat_id IS NULL)', (user_id, mode, chat_id))
            await db.commit()
            if user_id in settings['enemy']['enemies'][mode]:
                del settings['enemy']['enemies'][mode][user_id]
                await update_settings(db, settings)
        except Exception as e:
            logger.error(f"Error removing enemy: {e}")

    async def add_insult(text, insult_type='enemy'):
        """اضافه کردن فحش"""
        try:
            await db.execute('INSERT OR REPLACE INTO insults (text, type) VALUES (?, ?)', (text, insult_type))
            await db.commit()
            if insult_type == 'enemy':
                settings['enemy']['insults'].append(text)
            else:
                settings['enemy']['friend_insults'].append(text)
            await update_settings(db, settings)
        except Exception as e:
            logger.error(f"Error adding insult: {e}")

    async def remove_insult(text, insult_type='enemy'):
        """حذف فحش"""
        try:
            await db.execute('DELETE FROM insults WHERE text = ? AND type = ?', (text, insult_type))
            await db.commit()
            if insult_type == 'enemy':
                settings['enemy']['insults'] = [i for i in settings['enemy']['insults'] if i != text]
            else:
                settings['enemy']['friend_insults'] = [i for i in settings['enemy']['friend_insults'] if i != text]
            await update_settings(db, settings)
        except Exception as e:
            logger.error(f"Error removing insult: {e}")

    async def get_enemies(mode):
        """دریافت لیست دشمنان"""
        try:
            cursor = await db.execute('SELECT user_id, chat_id FROM enemies WHERE mode = ?', (mode,))
            rows = await cursor.fetchall()
            await cursor.close()
            return [(row[0], row[1]) for row in rows]
        except Exception as e:
            logger.error(f"Error getting enemies: {e}")
            return []

    async def get_insults(insult_type='enemy'):
        """دریافت لیست فحش‌ها"""
        try:
            cursor = await db.execute('SELECT text FROM insults WHERE type = ?', (insult_type,))
            rows = await cursor.fetchall()
            await cursor.close()
            return [row[0] for row in rows]
        except Exception as e:
            logger.error(f"Error getting insults: {e}")
            return []

    # فعال کردن فحش
    @client.on(events.NewMessage(pattern=get_command_pattern('insult_on', lang['enemy'])))
    async def handle_insult_on(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            settings['enemy']['enabled'] = True
            await update_settings(db, settings)
            await send_message(event, get_message('insult_enabled'))
        except Exception as e:
            logger.error(f"Error enabling insult: {e}")
            await send_message(event, get_message('error_occurred'))

    # غیرفعال کردن فحش
    @client.on(events.NewMessage(pattern=get_command_pattern('insult_off', lang['enemy'])))
    async def handle_insult_off(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            settings['enemy']['enabled'] = False
            await update_settings(db, settings)
            await send_message(event, get_message('insult_disabled'))
        except Exception as e:
            logger.error(f"Error disabling insult: {e}")
            await send_message(event, get_message('error_occurred'))

    # تنظیم دشمن
    @client.on(events.NewMessage(pattern=get_command_pattern('set_enemy_(all_chats|pv|groups|this_chat)', lang['enemy'])))
    async def handle_set_enemy(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            mode = event.pattern_match.group(1)
            user_id = event.pattern_match.group(2) or (event.message.reply_to_msg_id and (await event.get_reply_message()).sender_id)
            if not user_id:
                await send_message(event, get_message('no_user_specified'))
                return
            chat_id = event.chat_id if mode == 'this_chat' else None
            await add_enemy(user_id, mode, chat_id)
            await send_message(event, get_message(f'enemy_{mode}_set', user_id=user_id))
        except Exception as e:
            logger.error(f"Error setting enemy: {e}")
            await send_message(event, get_message('error_occurred'))

    # حذف دشمن
    @client.on(events.NewMessage(pattern=get_command_pattern('delete_enemy_(all_chats|pv|groups|this_chat)', lang['enemy'])))
    async def handle_delete_enemy(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            mode = event.pattern_match.group(1)
            user_id = event.pattern_match.group(2) or (event.message.reply_to_msg_id and (await event.get_reply_message()).sender_id)
            if not user_id:
                await send_message(event, get_message('no_user_specified'))
                return
            chat_id = event.chat_id if mode == 'this_chat' else None
            await remove_enemy(user_id, mode, chat_id)
            await send_message(event, get_message(f'enemy_{mode}_deleted', user_id=user_id))
        except Exception as e:
            logger.error(f"Error deleting enemy: {e}")
            await send_message(event, get_message('error_occurred'))

    # پاکسازی دشمن
    @client.on(events.NewMessage(pattern=get_command_pattern('clear_enemy_(all_chats|pv|groups|this_chat)', lang['enemy'])))
    async def handle_clear_enemy(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            mode = event.pattern_match.group(1)
            await db.execute('DELETE FROM enemies WHERE mode = ?', (mode,))
            await db.commit()
            settings['enemy']['enemies'][mode] = {}
            await update_settings(db, settings)
            await send_message(event, get_message(f'enemy_{mode}_cleared'))
        except Exception as e:
            logger.error(f"Error clearing enemies: {e}")
            await send_message(event, get_message('error_occurred'))

    # تنظیم دوست دشمن
    @client.on(events.NewMessage(pattern=get_command_pattern('set_friend_(all_chats|pv|groups|this_chat)', lang['enemy'])))
    async def handle_set_friend(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            mode = event.pattern_match.group(1)
            user_id = event.pattern_match.group(2) or (event.message.reply_to_msg_id and (await event.get_reply_message()).sender_id)
            if not user_id:
                await send_message(event, get_message('no_user_specified'))
                return
            chat_id = event.chat_id if mode == 'this_chat' else None
            await add_enemy(user_id, mode, chat_id)
            await send_message(event, get_message(f'friend_{mode}_set', user_id=user_id))
        except Exception as e:
            logger.error(f"Error setting friend: {e}")
            await send_message(event, get_message('error_occurred'))

    # حذف دوست دشمن
    @client.on(events.NewMessage(pattern=get_command_pattern('delete_friend_(all_chats|pv|groups|this_chat)', lang['enemy'])))
    async def handle_delete_friend(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            mode = event.pattern_match.group(1)
            user_id = event.pattern_match.group(2) or (event.message.reply_to_msg_id and (await event.get_reply_message()).sender_id)
            if not user_id:
                await send_message(event, get_message('no_user_specified'))
                return
            chat_id = event.chat_id if mode == 'this_chat' else None
            await remove_enemy(user_id, mode, chat_id)
            await send_message(event, get_message(f'friend_{mode}_deleted', user_id=user_id))
        except Exception as e:
            logger.error(f"Error deleting friend: {e}")
            await send_message(event, get_message('error_occurred'))

    # پاکسازی دوست دشمن
    @client.on(events.NewMessage(pattern=get_command_pattern('clear_friend_(all_chats|pv|groups|this_chat)', lang['enemy'])))
    async def handle_clear_friend(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            mode = event.pattern_match.group(1)
            await db.execute('DELETE FROM enemies WHERE mode = ?', (mode,))
            await db.commit()
            settings['enemy']['friends'][mode] = {}
            await update_settings(db, settings)
            await send_message(event, get_message(f'friend_{mode}_cleared'))
        except Exception as e:
            logger.error(f"Error clearing friends: {e}")
            await send_message(event, get_message('error_occurred'))

    # افزودن فحش
    @client.on(events.NewMessage(pattern=get_command_pattern('add_insult', lang['enemy'])))
    async def handle_add_insult(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            text = event.pattern_match.group(1)
            await add_insult(text, 'enemy')
            await send_message(event, get_message('insult_added', text=text))
        except Exception as e:
            logger.error(f"Error adding insult: {e}")
            await send_message(event, get_message('error_occurred'))

    # حذف فحش
    @client.on(events.NewMessage(pattern=get_command_pattern('delete_insult', lang['enemy'])))
    async def handle_delete_insult(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            text = event.pattern_match.group(1)
            await remove_insult(text, 'enemy')
            await send_message(event, get_message('insult_deleted', text=text))
        except Exception as e:
            logger.error(f"Error deleting insult: {e}")
            await send_message(event, get_message('error_occurred'))

    # نمایش لیست فحش‌ها
    @client.on(events.NewMessage(pattern=get_command_pattern('list_insults', lang['enemy'])))
    async def handle_list_insults(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            insults = await get_insults('enemy')
            if insults:
                insult_list = "\n".join(insults)
                await send_message(event, get_message('insult_list', list=insult_list))
            else:
                await send_message(event, get_message('no_insults'))
        except Exception as e:
            logger.error(f"Error listing insults: {e}")
            await send_message(event, get_message('error_occurred'))

    # پاکسازی فحش‌ها
    @client.on(events.NewMessage(pattern=get_command_pattern('clear_insults', lang['enemy'])))
    async def handle_clear_insults(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            await db.execute('DELETE FROM insults WHERE type = ?', ('enemy',))
            await db.commit()
            settings['enemy']['insults'] = []
            await update_settings(db, settings)
            await send_message(event, get_message('insults_cleared'))
        except Exception as e:
            logger.error(f"Error clearing insults: {e}")
            await send_message(event, get_message('error_occurred'))

    # افزودن فحش دوست دشمن
    @client.on(events.NewMessage(pattern=get_command_pattern('add_friend_insult', lang['enemy'])))
    async def handle_add_friend_insult(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            text = event.pattern_match.group(1)
            await add_insult(text, 'friend')
            await send_message(event, get_message('friend_insult_added', text=text))
        except Exception as e:
            logger.error(f"Error adding friend insult: {e}")
            await send_message(event, get_message('error_occurred'))

    # حذف فحش دوست دشمن
    @client.on(events.NewMessage(pattern=get_command_pattern('delete_friend_insult', lang['enemy'])))
    async def handle_delete_friend_insult(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            text = event.pattern_match.group(1)
            await remove_insult(text, 'friend')
            await send_message(event, get_message('friend_insult_deleted', text=text))
        except Exception as e:
            logger.error(f"Error deleting friend insult: {e}")
            await send_message(event, get_message('error_occurred'))

    # نمایش لیست فحش‌های دوست دشمن
    @client.on(events.NewMessage(pattern=get_command_pattern('list_friend_insults', lang['enemy'])))
    async def handle_list_friend_insults(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            insults = await get_insults('friend')
            if insults:
                insult_list = "\n".join(insults)
                await send_message(event, get_message('friend_insult_list', list=insult_list))
            else:
                await send_message(event, get_message('no_friend_insults'))
        except Exception as e:
            logger.error(f"Error listing friend insults: {e}")
            await send_message(event, get_message('error_occurred'))

    # پاکسازی فحش‌های دوست دشمن
    @client.on(events.NewMessage(pattern=get_command_pattern('clear_friend_insults', lang['enemy'])))
    async def handle_clear_friend_insults(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            await db.execute('DELETE FROM insults WHERE type = ?', ('friend',))
            await db.commit()
            settings['enemy']['friend_insults'] = []
            await update_settings(db, settings)
            await send_message(event, get_message('friend_insults_cleared'))
        except Exception as e:
            logger.error(f"Error clearing friend insults: {e}")
            await send_message(event, get_message('error_occurred'))

    # آپلود فحش از فایل
    @client.on(events.NewMessage(pattern=get_command_pattern('upload_insult', lang['enemy'])))
    async def handle_upload_insult(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            if event.message.document:
                file = await event.message.download_media()
                with open(file, 'r', encoding='utf-8') as f:
                    insults = f.read().splitlines()
                for insult in insults:
                    await add_insult(insult, 'enemy')
                await send_message(event, get_message('insults_uploaded', count=len(insults)))
                os.remove(file)
            else:
                await send_message(event, get_message('no_file'))
        except Exception as e:
            logger.error(f"Error uploading insults: {e}")
            await send_message(event, get_message('error_occurred'))

    # آپلود فحش دوست دشمن از فایل
    @client.on(events.NewMessage(pattern=get_command_pattern('upload_friend_insult', lang['enemy'])))
    async def handle_upload_friend_insult(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            if event.message.document:
                file = await event.message.download_media()
                with open(file, 'r', encoding='utf-8') as f:
                    insults = f.read().splitlines()
                for insult in insults:
                    await add_insult(insult, 'friend')
                await send_message(event, get_message('friend_insults_uploaded', count=len(insults)))
                os.remove(file)
            else:
                await send_message(event, get_message('no_file'))
        except Exception as e:
            logger.error(f"Error uploading friend insults: {e}")
            await send_message(event, get_message('error_occurred'))

    # تنظیم زمان تأخیر
    @client.on(events.NewMessage(pattern=get_command_pattern('set_delay', lang['enemy'])))
    async def handle_set_delay(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            delay = int(event.pattern_match.group(1))
            settings['enemy']['delay_time'] = delay
            settings['enemy']['delay_enabled'] = True
            await update_settings(db, settings)
            await send_message(event, get_message('delay_set', delay=delay))
        except ValueError:
            await send_message(event, get_message('invalid_delay_format'))
        except Exception as e:
            logger.error(f"Error setting delay: {e}")
            await send_message(event, get_message('error_occurred'))

    # فعال کردن زمان تأخیر
    @client.on(events.NewMessage(pattern=get_command_pattern('delay_on', lang['enemy'])))
    async def handle_delay_on(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            settings['enemy']['delay_enabled'] = True
            await update_settings(db, settings)
            await send_message(event, get_message('delay_enabled'))
        except Exception as e:
            logger.error(f"Error enabling delay: {e}")
            await send_message(event, get_message('error_occurred'))

    # غیرفعال کردن زمان تأخیر
    @client.on(events.NewMessage(pattern=get_command_pattern('delay_off', lang['enemy'])))
    async def handle_delay_off(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            settings['enemy']['delay_enabled'] = False
            await update_settings(db, settings)
            await send_message(event, get_message('delay_disabled'))
        except Exception as e:
            logger.error(f"Error disabling delay: {e}")
            await send_message(event, get_message('error_occurred'))

    # تنظیم مکث تایپینگ
    @client.on(events.NewMessage(pattern=get_command_pattern('set_pause', lang['enemy'])))
    async def handle_set_pause(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            match = re.match(r'(\d+)-(\d+)', event.pattern_match.group(1))
            if not match:
                await send_message(event, get_message('invalid_pause_format'))
                return
            min_pause, max_pause = map(int, match.groups())
            settings['enemy']['typing_pause'] = [min_pause, max_pause]
            await update_settings(db, settings)
            await send_message(event, get_message('pause_set', min=min_pause, max=max_pause))
        except Exception as e:
            logger.error(f"Error setting pause: {e}")
            await send_message(event, get_message('error_occurred'))

    # فعال کردن حذف پیام دشمن
    @client.on(events.NewMessage(pattern=get_command_pattern('delete_enemy_message_on', lang['enemy'])))
    async def handle_delete_enemy_message_on(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            settings['enemy']['delete_enemy_messages'] = True
            await update_settings(db, settings)
            await send_message(event, get_message('delete_enemy_message_enabled'))
        except Exception as e:
            logger.error(f"Error enabling delete enemy message: {e}")
            await send_message(event, get_message('error_occurred'))

    # غیرفعال کردن حذف پیام دشمن
    @client.on(events.NewMessage(pattern=get_command_pattern('delete_enemy_message_off', lang['enemy'])))
    async def handle_delete_enemy_message_off(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            settings['enemy']['delete_enemy_messages'] = False
            await update_settings(db, settings)
            await send_message(event, get_message('delete_enemy_message_disabled'))
        except Exception as e:
            logger.error(f"Error disabling delete enemy message: {e}")
            await send_message(event, get_message('error_occurred'))

    # تنظیم امضا
    @client.on(events.NewMessage(pattern=get_command_pattern('set_signature', lang['enemy'])))
    async def handle_set_signature(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            signature = event.pattern_match.group(1)
            settings['enemy']['signature'] = signature
            await update_settings(db, settings)
            await send_message(event, get_message('signature_set', signature=signature))
        except Exception as e:
            logger.error(f"Error setting signature: {e}")
            await send_message(event, get_message('error_occurred'))

    # حذف امضا
    @client.on(events.NewMessage(pattern=get_command_pattern('delete_signature', lang['enemy'])))
    async def handle_delete_signature(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            settings['enemy']['signature'] = ''
            await update_settings(db, settings)
            await send_message(event, get_message('signature_deleted'))
        except Exception as e:
            logger.error(f"Error deleting signature: {e}")
            await send_message(event, get_message('error_occurred'))

    # تنظیم امضای دوست دشمن
    @client.on(events.NewMessage(pattern=get_command_pattern('set_friend_signature', lang['enemy'])))
    async def handle_set_friend_signature(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            signature = event.pattern_match.group(1)
            settings['enemy']['friend_signature'] = signature
            await update_settings(db, settings)
            await send_message(event, get_message('friend_signature_set', signature=signature))
        except Exception as e:
            logger.error(f"Error setting friend signature: {e}")
            await send_message(event, get_message('error_occurred'))

    # حذف امضای دوست دشمن
    @client.on(events.NewMessage(pattern=get_command_pattern('delete_friend_signature', lang['enemy'])))
    async def handle_delete_friend_signature(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            settings['enemy']['friend_signature'] = ''
            await update_settings(db, settings)
            await send_message(event, get_message('friend_signature_deleted'))
        except Exception as e:
            logger.error(f"Error deleting friend signature: {e}")
            await send_message(event, get_message('error_occurred'))

    # نمایش لیست‌ها
    @client.on(events.NewMessage(pattern=get_command_pattern('list_all', lang['enemy'])))
    async def handle_list_all(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            enemy_lists = []
            for mode in ['all_chats', 'pv', 'groups', 'this_chat']:
                enemies = await get_enemies(mode)
                if enemies:
                    enemy_lists.append(f"{mode}:\n" + "\n".join([f"User {user_id} (Chat: {chat_id or 'N/A'})" for user_id, chat_id in enemies]))
                friends = await get_enemies(mode)
                if friends:
                    enemy_lists.append(f"Friend {mode}:\n" + "\n".join([f"User {user_id} (Chat: {chat_id or 'N/A'})" for user_id, chat_id in friends]))
            insults = await get_insults('enemy')
            if insults:
                enemy_lists.append("Insults:\n" + "\n".join(insults))
            friend_insults = await get_insults('friend')
            if friend_insults:
                enemy_lists.append("Friend Insults:\n" + "\n".join(friend_insults))
            if enemy_lists:
                await send_message(event, get_message('lists', list="\n\n".join(enemy_lists)))
            else:
                await send_message(event, get_message('no_lists'))
        except Exception as e:
            logger.error(f"Error listing all: {e}")
            await send_message(event, get_message('error_occurred'))

    # پاکسازی کامل دشمن
    @client.on(events.NewMessage(pattern=get_command_pattern('clear_all_enemies', lang['enemy'])))
    async def handle_clear_all_enemies(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            user_id = event.pattern_match.group(1) or (event.message.reply_to_msg_id and (await event.get_reply_message()).sender_id)
            if not user_id:
                await send_message(event, get_message('no_user_specified'))
                return
            for mode in ['all_chats', 'pv', 'groups', 'this_chat']:
                await remove_enemy(user_id, mode)
            await send_message(event, get_message('all_enemies_cleared', user_id=user_id))
        except Exception as e:
            logger.error(f"Error clearing all enemies: {e}")
            await send_message(event, get_message('error_occurred'))

    # دریافت اطلاعات دشمن
    @client.on(events.NewMessage(pattern=get_command_pattern('get_enemy', lang['enemy'])))
    async def handle_get_enemy(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            user_id = event.pattern_match.group(1) or (event.message.reply_to_msg_id and (await event.get_reply_message()).sender_id)
            if not user_id:
                await send_message(event, get_message('no_user_specified'))
                return
            modes = []
            for mode in ['all_chats', 'pv', 'groups', 'this_chat']:
                if user_id in settings['enemy']['enemies'][mode] or user_id in settings['enemy']['friends'][mode]:
                    modes.append(mode)
            if modes:
                await send_message(event, get_message('enemy_info', user_id=user_id, modes=", ".join(modes)))
            else:
                await send_message(event, get_message('enemy_not_found', user_id=user_id))
        except Exception as e:
            logger.error(f"Error getting enemy info: {e}")
            await send_message(event, get_message('error_occurred'))

    # مدیریت پیام‌های ورودی برای ارسال فحش
    @client.on(events.NewMessage)
    async def handle_incoming_message(event):
        try:
            if not settings['enemy']['enabled']:
                return
            sender_id = event.sender_id
            chat_id = event.chat_id
            current_time = datetime.now().timestamp()

            # بررسی دشمن
            for mode, enemies in settings['enemy']['enemies'].items():
                if sender_id in enemies:
                    if mode == 'all_chats' or \
                            (mode == 'pv' and event.is_private) or \
                            (mode == 'groups' and event.is_group) or \
                            (mode == 'this_chat' and enemies[sender_id]['chat_id'] == chat_id):
                        if settings['enemy']['delay_enabled'] and (current_time - enemies[sender_id]['last_insult']) < settings['enemy']['delay_time']:
                            continue
                        if settings['enemy']['delete_enemy_messages']:
                            await event.delete()
                        if settings['enemy']['insults']:
                            insult = random.choice(settings['enemy']['insults'])
                            pause = random.uniform(*settings['enemy']['typing_pause'])
                            await client.send_message(chat_id, action='typing')
                            await asyncio.sleep(pause)
                            await send_message(event, f"{insult}\n{settings['enemy']['signature']}")
                            enemies[sender_id]['last_insult'] = current_time
                            await update_settings(db, settings)

            # بررسی دوست دشمن
            for mode, friends in settings['enemy']['friends'].items():
                if sender_id in friends:
                    if mode == 'all_chats' or \
                            (mode == 'pv' and event.is_private) or \
                            (mode == 'groups' and event.is_group) or \
                            (mode == 'this_chat' and friends[sender_id]['chat_id'] == chat_id):
                        if settings['enemy']['delay_enabled'] and (current_time - friends[sender_id]['last_insult']) < settings['enemy']['delay_time']:
                            continue
                        if settings['enemy']['delete_enemy_messages']:
                            await event.delete()
                        if settings['enemy']['friend_insults']:
                            insult = random.choice(settings['enemy']['friend_insults'])
                            pause = random.uniform(*settings['enemy']['typing_pause'])
                            await client.send_message(chat_id, action='typing')
                            await asyncio.sleep(pause)
                            await send_message(event, f"{insult}\n{settings['enemy']['friend_signature']}")
                            friends[sender_id]['last_insult'] = current_time
                            await update_settings(db, settings)
        except FloodWaitError as e:
            logger.error(f"Flood wait error: {e.seconds} seconds")
            await asyncio.sleep(e.seconds)
        except Exception as e:
            logger.error(f"Error handling incoming message: {e}")

    await db.close()