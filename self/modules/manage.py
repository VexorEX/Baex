import asyncio
import logging
import os
import json
import re
from datetime import datetime, timedelta
import pytz
from telethon import events
from telethon.tl.functions.channels import CreateChannelRequest, InviteToChannelRequest, EditBannedRequest
from telethon.tl.functions.messages import ForwardMessagesRequest, DeleteMessagesRequest
from telethon.tl.types import ChannelParticipantsAdmins, ChannelParticipantsRecent
from telethon.tl.functions.users import GetFullUserRequest
from telethon.tl.functions.contacts import AddContactRequest
from telethon.tl.functions.account import ReportPeerRequest
from telethon.errors import UsernameOccupiedError, FloodWaitError, ChannelPrivateError, UserPrivacyRestrictedError
from telethon.tl.types import InputKeyboardButtonCallback, KeyboardButtonRow, InlineKeyboardMarkup
from deep_translator import GoogleTranslator
from utils import load_json, send_message, get_command_pattern
from models import get_database, load_settings, update_settings

logger = logging.getLogger(__name__)

async def register_manage_handlers(client, session_name, owner_id):
    db = await get_database(session_name)
    settings = await load_settings(db)
    if not settings:
        logger.error("Failed to load settings for manage handlers")
        await db.close()
        return

    lang = settings.get('lang', 'fa')
    messages = load_json('msg.json')
    commands = load_json('cmd.json')

    def get_message(key, **kwargs):
        return messages[lang]['manage'].get(key, '').format(**kwargs)

    # تنظیمات اولیه manage
    if 'manage_settings' not in settings:
        settings['manage_settings'] = {
            'channel_username': None,
            'channel_id': None,
            'bot_token': None,
            'monitor_realm': None,
            'read_realm': None,
            'story_realm': None,
            'timers': {},  # {name: start_time}
            'times': {},  # {name: target_datetime}
            'monitored_users': {},  # {user_id: {'online': True, 'photo': True, 'read': True, 'typing': True, 'name_change': True, 'join': True, 'voice': True}}
            'white_list': [],  # list of user_ids
            'black_list': [],  # list of user_ids
            'user_reactions': {},  # {user_id: reaction}
            'user_reactions_global': {},  # {user_id: reaction}
            'command_prefix': '',  # علامت قبل از دستورات
            'comment_enabled': False,
            'comment_list': [],
            'request_list': None,
            'join_list': None,
            'leave_list': None,
            'expire_time': None,  # برای انقضا سلف
            'self_global_enabled': True,
            'poker_global_enabled': False,
            'save_enabled': {},
            'typing_global_enabled': False
        }
        await update_settings(db, settings)

    async def get_user_info(user_id):
        """دریافت اطلاعات کاربر"""
        try:
            user = await client.get_entity(user_id)
            full_user = await client(GetFullUserRequest(user_id))
            return {
                'id': user.id,
                'first_name': user.first_name or '',
                'last_name': user.last_name or '',
                'username': user.username or '',
                'phone': user.phone or 'N/A',
                'about': full_user.full_user.about or 'N/A'
            }
        except Exception as e:
            logger.error(f"Error getting user info: {e}")
            return None

    async def create_channel(title):
        """ساخت کانال جدید"""
        try:
            result = await client(CreateChannelRequest(title=title, about='', megagroup=False))
            return result.chats[0].id
        except UsernameOccupiedError:
            logger.error("Username occupied while creating channel")
            return None
        except FloodWaitError as e:
            logger.error(f"Flood wait error: {e.seconds} seconds")
            return None
        except Exception as e:
            logger.error(f"Error creating channel: {e}")
            return None

    async def forward_to_channel(chat_id, message_id, caption=None):
        """فوروارد به کانال با تغییر نام کاربری‌ها"""
        try:
            if not settings['manage_settings']['channel_id'] or not settings['manage_settings']['channel_username']:
                return False
            messages = await client.get_messages(chat_id, ids=[message_id])
            if messages:
                msg = messages[0]
                if msg.text:
                    msg.text = re.sub(r'@[\w.]+', f"@{settings['manage_settings']['channel_username']}", msg.text)
                await client(ForwardMessagesRequest(
                    from_peer=chat_id,
                    to_peer=settings['manage_settings']['channel_id'],
                    id=[message_id],
                    top_msg_id=0,
                    from_channel=False
                ))
                if caption:
                    await client.send_message(settings['manage_settings']['channel_id'], caption)
                return True
        except Exception as e:
            logger.error(f"Error forwarding to channel: {e}")
            return False

    async def reset_self():
        """ریست کامل سلف"""
        try:
            settings['manage_settings'] = {
                'channel_username': None,
                'channel_id': None,
                'bot_token': None,
                'monitor_realm': None,
                'read_realm': None,
                'story_realm': None,
                'timers': {},
                'times': {},
                'monitored_users': {},
                'white_list': [],
                'black_list': [],
                'user_reactions': {},
                'user_reactions_global': {},
                'command_prefix': '',
                'comment_enabled': False,
                'comment_list': [],
                'request_list': None,
                'join_list': None,
                'leave_list': None,
                'expire_time': None,
                'self_global_enabled': True,
                'poker_global_enabled': False,
                'save_enabled': {},
                'typing_global_enabled': False
            }
            await update_settings(db, settings)
            logger.info("Self reset completed")
        except Exception as e:
            logger.error(f"Error resetting self: {e}")

    async def delete_message(chat_id, message_id):
        """حذف پیام با ریپلی"""
        try:
            await client.delete_messages(chat_id, [message_id])
            return True
        except Exception as e:
            logger.error(f"Error deleting message: {e}")
            return False

    async def delete_user_messages(chat_id, user_id, count=10):
        """حذف پیام‌های کاربر به تعداد مشخص"""
        try:
            messages = []
            async for message in client.iter_messages(chat_id, from_user=user_id, limit=count):
                messages.append(message.id)
            if messages:
                await client.delete_messages(chat_id, messages)
                return len(messages)
            return 0
        except Exception as e:
            logger.error(f"Error deleting user messages: {e}")
            return 0

    # Expiration check
    @client.on(events.NewMessage(pattern=get_command_pattern('expiration', lang['manage'])))
    async def handle_expiration(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            expiration = settings['manage_settings'].get('expire_time', 'No expiration set')
            await send_message(event, get_message('expiration', expiration=expiration))
        except Exception as e:
            logger.error(f"Error handling expiration: {e}")

    # Create channel
    @client.on(events.NewMessage(pattern=get_command_pattern('create_channel', lang['manage'])))
    async def handle_create_channel(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            title = event.pattern_match.group(1)
            channel_id = await create_channel(title)
            if channel_id:
                await send_message(event, get_message('channel_created', title=title, id=channel_id))
            else:
                await send_message(event, get_message('error_occurred'))
        except UsernameOccupiedError:
            await send_message(event, get_message('channel_username_occupied'))
        except FloodWaitError as e:
            await send_message(event, get_message('flood_wait', seconds=e.seconds))
        except Exception as e:
            logger.error(f"Error creating channel: {e}")
            await send_message(event, get_message('error_occurred'))

    # Set channel for forwarding
    @client.on(events.NewMessage(pattern=get_command_pattern('set_channel', lang['manage'])))
    async def handle_set_channel(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            chat_id = int(event.pattern_match.group(1))
            username = event.pattern_match.group(2)
            settings['manage_settings']['channel_id'] = chat_id
            settings['manage_settings']['channel_username'] = username
            await update_settings(db, settings)
            await send_message(event, get_message('channel_set', username=username))
        except Exception as e:
            logger.error(f"Error setting channel: {e}")
            await send_message(event, get_message('error_occurred'))

    # Delete channel settings
    @client.on(events.NewMessage(pattern=get_command_pattern('delete_channel', lang['manage'])))
    async def handle_delete_channel(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            if settings['manage_settings']['channel_id']:
                settings['manage_settings']['channel_id'] = None
                settings['manage_settings']['channel_username'] = None
                await update_settings(db, settings)
                await send_message(event, get_message('channel_deleted'))
            else:
                await send_message(event, get_message('no_channel_set'))
        except Exception as e:
            logger.error(f"Error deleting channel: {e}")
            await send_message(event, get_message('error_occurred'))

    # Forward to channel
    @client.on(events.NewMessage(pattern=get_command_pattern('forward_to_channel', lang['manage'])))
    async def handle_forward_to_channel(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            if not settings['manage_settings']['channel_id']:
                await send_message(event, get_message('no_channel_set'))
                return
            caption = event.pattern_match.group(1) or ''
            if event.is_reply:
                reply_msg = await event.get_reply_message()
                success = await forward_to_channel(event.chat_id, reply_msg.id, caption)
                if success:
                    await send_message(event, get_message('forwarded_to_channel', channel=settings['manage_settings']['channel_username']))
                else:
                    await send_message(event, get_message('error_occurred'))
            else:
                await send_message(event, get_message('reply_to_message'))
        except Exception as e:
            logger.error(f"Error forwarding to channel: {e}")
            await send_message(event, get_message('error_occurred'))

    # Reset self
    @client.on(events.NewMessage(pattern=get_command_pattern('reset_self', lang['manage'])))
    async def handle_reset_self(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            await reset_self()
            await send_message(event, get_message('self_reset'))
        except Exception as e:
            logger.error(f"Error resetting self: {e}")
            await send_message(event, get_message('error_occurred'))

    # Delete message
    @client.on(events.NewMessage(pattern=get_command_pattern('delete_message', lang['manage'])))
    async def handle_delete_message(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            if event.is_reply:
                reply_msg = await event.get_reply_message()
                success = await delete_message(event.chat_id, reply_msg.id)
                if success:
                    await send_message(event, get_message('message_deleted'))
                else:
                    await send_message(event, get_message('error_occurred'))
            else:
                await send_message(event, get_message('reply_to_message'))
        except Exception as e:
            logger.error(f"Error deleting message: {e}")
            await send_message(event, get_message('error_occurred'))

    # Delete multiple messages
    @client.on(events.NewMessage(pattern=get_command_pattern('delete_message_count', lang['manage'])))
    async def handle_delete_message_count(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            if event.is_reply:
                reply_msg = await event.get_reply_message()
                count = int(event.pattern_match.group(1))
                deleted_count = await delete_user_messages(event.chat_id, reply_msg.sender_id, count)
                if deleted_count:
                    await send_message(event, get_message('messages_deleted', count=deleted_count))
                else:
                    await send_message(event, get_message('no_messages_deleted'))
            else:
                await send_message(event, get_message('reply_to_user'))
        except Exception as e:
            logger.error(f"Error deleting messages: {e}")
            await send_message(event, get_message('error_occurred'))

    # Self status
    @client.on(events.NewMessage(pattern=get_command_pattern('self_status', lang['manage'])))
    async def handle_self_status(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            status = {
                'enabled': settings['manage_settings']['self_global_enabled'],
                'poker': settings['manage_settings']['poker_global_enabled'],
                'save': len([k for k, v in settings['manage_settings']['save_enabled'].items() if v]),
                'typing': settings['manage_settings']['typing_global_enabled'],
                'channel': settings['manage_settings']['channel_username'] or 'تنظیم نشده',
                'language': lang
            }
            status_text = "\n".join([f"{k}: {v}" for k, v in status.items()])
            await send_message(event, get_message('self_status', status=status_text), parse_mode='html')
        except Exception as e:
            logger.error(f"Error getting self status: {e}")
            await send_message(event, get_message('error_occurred'))

    # User info
    @client.on(events.NewMessage(pattern=get_command_pattern('user_info', lang['manage'])))
    async def handle_user_info(event):
        try:
            if event.is_reply:
                reply_msg = await event.get_reply_message()
                info = await get_user_info(reply_msg.sender_id)
                if info:
                    info_text = f"نام: {info['first_name']}\nآخرین نام: {info['last_name']}\nنام کاربری: @{info['username']}\nدرباره: {info['about']}"
                    await send_message(event, get_message('user_info', info=info_text), parse_mode='html')
                else:
                    await send_message(event, get_message('error_occurred'))
            else:
                await send_message(event, get_message('reply_to_user'))
        except Exception as e:
            logger.error(f"Error getting user info: {e}")
            await send_message(event, get_message('error_occurred'))

    # User ID
    @client.on(events.NewMessage(pattern=get_command_pattern('user_id', lang['manage'])))
    async def handle_user_id(event):
        try:
            if event.is_reply:
                reply_msg = await event.get_reply_message()
                user_id = reply_msg.sender_id
            else:
                username = event.pattern_match.group(1)
                user = await client.get_entity(username)
                user_id = user.id
            await send_message(event, get_message('user_id', id=user_id), parse_mode='html')
        except Exception as e:
            logger.error(f"Error getting user ID: {e}")
            await send_message(event, get_message('error_occurred'))

    # Mention user
    @client.on(events.NewMessage(pattern=get_command_pattern('mention_user', lang['manage'])))
    async def handle_mention_user(event):
        try:
            user_id = int(event.pattern_match.group(1))
            user = await client.get_entity(user_id)
            mention_text = f"[{user.first_name}](tg://user?id={user_id})"
            await send_message(event, mention_text, parse_mode='markdown')
        except Exception as e:
            logger.error(f"Error mentioning user: {e}")
            await send_message(event, get_message('error_occurred'))

    # Chat ID
    @client.on(events.NewMessage(pattern=get_command_pattern('chat_id', lang['manage'])))
    async def handle_chat_id(event):
        try:
            await send_message(event, get_message('chat_id', id=event.chat_id), parse_mode='html')
        except Exception as e:
            logger.error(f"Error getting chat ID: {e}")
            await send_message(event, get_message('error_occurred'))

    # Channel info
    @client.on(events.NewMessage(pattern=get_command_pattern('channel_info', lang['manage'])))
    async def handle_channel_info(event):
        try:
            channel_id = int(event.pattern_match.group(1))
            channel = await client.get_entity(channel_id)
            info = f"عنوان: {channel.title}\nID: {channel.id}\nنام کاربری: @{channel.username or 'N/A'}\nتعداد اعضا: {channel.participants_count or 'N/A'}"
            await send_message(event, get_message('channel_info', info=info), parse_mode='html')
        except Exception as e:
            logger.error(f"Error getting channel info: {e}")
            await send_message(event, get_message('error_occurred'))

    # Add contact
    @client.on(events.NewMessage(pattern=get_command_pattern('add_contact', lang['manage'])))
    async def handle_add_contact(event):
        try:
            if event.is_reply:
                reply_msg = await event.get_reply_message()
                user = await client.get_entity(reply_msg.sender_id)
                await client(AddContactRequest(user.id, user.first_name, user.phone or '', user.first_name))
                await send_message(event, get_message('contact_added', name=user.first_name), parse_mode='html')
            else:
                await send_message(event, get_message('reply_to_user'))
        except Exception as e:
            logger.error(f"Error adding contact: {e}")
            await send_message(event, get_message('error_occurred'))

    # Share phone
    @client.on(events.NewMessage(pattern=get_command_pattern('share_phone', lang['manage'])))
    async def handle_share_phone(event):
        try:
            me = await client.get_me()
            await client.send_message(event.chat_id, me.phone, link_preview=False)
            await send_message(event, get_message('phone_shared'), parse_mode='html')
        except Exception as e:
            logger.error(f"Error sharing phone: {e}")
            await send_message(event, get_message('error_occurred'))

    # Panel
    @client.on(events.NewMessage(pattern=get_command_pattern('panel', lang['manage'])))
    async def handle_panel(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            chat_id = event.pattern_match.group(1) or event.chat_id
            keyboard = InlineKeyboardMarkup([
                [InputKeyboardButtonCallback("تنظیمات پروفایل", data=f"panel_profile_{chat_id}".encode())],
                [InputKeyboardButtonCallback("تنظیمات عمومی", data=f"panel_settings_{chat_id}".encode())],
                [InputKeyboardButtonCallback("لیست‌ها", data=f"panel_lists_{chat_id}".encode())]
            ])
            await send_message(event, get_message('panel_text'), parse_mode='html', reply_markup=keyboard)
        except Exception as e:
            logger.error(f"Error opening panel: {e}")
            await send_message(event, get_message('error_occurred'))

    # Panel PV
    @client.on(events.NewMessage(pattern=get_command_pattern('panel_pv', lang['manage'])))
    async def handle_panel_pv(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            chat_id = event.pattern_match.group(1) or event.chat_id
            keyboard = InlineKeyboardMarkup([
                [InputKeyboardButtonCallback("تنظیمات پروفایل", data=f"panel_profile_{chat_id}".encode())],
                [InputKeyboardButtonCallback("تنظیمات عمومی", data=f"panel_settings_{chat_id}".encode())],
                [InputKeyboardButtonCallback("لیست‌ها", data=f"panel_lists_{chat_id}".encode())]
            ])
            me = await client.get_me()
            await client.send_message(me.id, get_message('panel_text'), parse_mode='html', reply_markup=keyboard)
            await send_message(event, get_message('panel_sent_pv'), parse_mode='html')
        except Exception as e:
            logger.error(f"Error sending panel to PV: {e}")
            await send_message(event, get_message('error_occurred'))

    # Manage user
    @client.on(events.NewMessage(pattern=get_command_pattern('manage_user', lang['manage'])))
    async def handle_manage_user(event):
        try:
            if event.is_reply:
                reply_msg = await event.get_reply_message()
                user = await client.get_entity(reply_msg.sender_id)
                keyboard = InlineKeyboardMarkup([
                    [InputKeyboardButtonCallback("تنظیم واکنش", data=f"manage_reaction_{user.id}".encode())],
                    [InputKeyboardButtonCallback("افزودن به سفید", data=f"manage_white_{user.id}".encode())],
                    [InputKeyboardButtonCallback("افزودن به سیاه", data=f"manage_black_{user.id}".encode())]
                ])
                await send_message(event, get_message('manage_user_text', name=user.first_name, id=user.id, username=f"@{user.username or 'N/A'}"), parse_mode='html', reply_markup=keyboard)
            else:
                await send_message(event, get_message('reply_to_user'))
        except Exception as e:
            logger.error(f"Error managing user: {e}")
            await send_message(event, get_message('error_occurred'))

    # List all
    @client.on(events.NewMessage(pattern=get_command_pattern('list_all', lang['manage'])))
    async def handle_list_all(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            lists = {
                'white_list': len(settings['manage_settings']['white_list']),
                'black_list': len(settings['manage_settings']['black_list']),
                'timers': len(settings['manage_settings']['timers']),
                'times': len(settings['manage_settings']['times']),
                'monitored_users': len(settings['manage_settings']['monitored_users'])
            }
            lists_text = "\n".join([f"{k}: {v}" for k, v in lists.items()])
            await send_message(event, get_message('list_all_text', lists=lists_text), parse_mode='html')
        except Exception as e:
            logger.error(f"Error listing all: {e}")
            await send_message(event, get_message('error_occurred'))

    # Save message
    @client.on(events.NewMessage(pattern=get_command_pattern('save_message', lang['manage'])))
    async def handle_save_message(event):
        try:
            if event.is_reply:
                reply_msg = await event.get_reply_message()
                await client.forward_messages('me', event.chat_id, [reply_msg.id])
                await send_message(event, get_message('message_saved', id=reply_msg.id), parse_mode='html')
            else:
                await send_message(event, get_message('reply_to_message'))
        except Exception as e:
            logger.error(f"Error saving message: {e}")
            await send_message(event, get_message('error_occurred'))

    # Message to user
    @client.on(events.NewMessage(pattern=get_command_pattern('message_to_user', lang['manage'])))
    async def handle_message_to_user(event):
        try:
            user_id = int(event.pattern_match.group(1))
            message_text = event.pattern_match.group(2)
            await client.send_message(user_id, message_text)
            await send_message(event, get_message('message_sent_to_user', id=user_id), parse_mode='html')
        except Exception as e:
            logger.error(f"Error sending message to user: {e}")
            await send_message(event, get_message('error_occurred'))

    # Bot mode toggle
    @client.on(events.NewMessage(pattern=get_command_pattern('bot_mode_toggle', lang['manage'])))
    async def handle_bot_mode_toggle(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            status = event.pattern_match.group(1)
            settings['manage_settings']['bot_token'] = status if status == 'روشن' or status == 'on' else None
            await update_settings(db, settings)
            emoji = '✅' if settings['manage_settings']['bot_token'] else '❌'
            await send_message(event, get_message('bot_mode_toggle', status=status, emoji=emoji), parse_mode='html')
        except Exception as e:
            logger.error(f"Error toggling bot mode: {e}")
            await send_message(event, get_message('error_occurred'))

    # Set API token
    @client.on(events.NewMessage(pattern=get_command_pattern('set_api_token', lang['manage'])))
    async def handle_set_api_token(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            token = event.pattern_match.group(1)
            settings['manage_settings']['bot_token'] = token
            await update_settings(db, settings)
            await send_message(event, get_message('api_token_set'), parse_mode='html')
        except Exception as e:
            logger.error(f"Error setting API token: {e}")
            await send_message(event, get_message('error_occurred'))

    # Add white list
    @client.on(events.NewMessage(pattern=get_command_pattern('add_white_list', lang['manage'])))
    async def handle_add_white_list(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            if event.is_reply:
                reply_msg = await event.get_reply_message()
                user_id = reply_msg.sender_id
            else:
                user_id = int(event.pattern_match.group(1))
            if user_id not in settings['manage_settings']['white_list']:
                settings['manage_settings']['white_list'].append(user_id)
                await update_settings(db, settings)
                await send_message(event, get_message('white_list_added', id=user_id), parse_mode='html')
            else:
                await send_message(event, get_message('already_in_white_list'), parse_mode='html')
        except Exception as e:
            logger.error(f"Error adding to white list: {e}")
            await send_message(event, get_message('error_occurred'))

    # Delete white list
    @client.on(events.NewMessage(pattern=get_command_pattern('delete_white_list', lang['manage'])))
    async def handle_delete_white_list(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            if event.is_reply:
                reply_msg = await event.get_reply_message()
                user_id = reply_msg.sender_id
            else:
                user_id = int(event.pattern_match.group(1))
            if user_id in settings['manage_settings']['white_list']:
                settings['manage_settings']['white_list'].remove(user_id)
                await update_settings(db, settings)
                await send_message(event, get_message('white_list_deleted', id=user_id), parse_mode='html')
            else:
                await send_message(event, get_message('not_in_white_list'), parse_mode='html')
        except Exception as e:
            logger.error(f"Error deleting from white list: {e}")
            await send_message(event, get_message('error_occurred'))

    # List white list
    @client.on(events.NewMessage(pattern=get_command_pattern('list_white_list', lang['manage'])))
    async def handle_list_white_list(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            white_list = settings['manage_settings']['white_list']
            if white_list:
                users = [await get_user_info(uid) for uid in white_list]
                list_text = "\n".join([f"{u['first_name']} (@{u['username'] or 'N/A'})" for u in users if u])
                await send_message(event, get_message('white_list', list=list_text), parse_mode='html')
            else:
                await send_message(event, get_message('empty_white_list'), parse_mode='html')
        except Exception as e:
            logger.error(f"Error listing white list: {e}")
            await send_message(event, get_message('error_occurred'))

    # Clear white list
    @client.on(events.NewMessage(pattern=get_command_pattern('clear_white_list', lang['manage'])))
    async def handle_clear_white_list(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            settings['manage_settings']['white_list'] = []
            await update_settings(db, settings)
            await send_message(event, get_message('white_list_cleared'), parse_mode='html')
        except Exception as e:
            logger.error(f"Error clearing white list: {e}")
            await send_message(event, get_message('error_occurred'))

    # Add black list
    @client.on(events.NewMessage(pattern=get_command_pattern('add_black_list', lang['manage'])))
    async def handle_add_black_list(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            if event.is_reply:
                reply_msg = await event.get_reply_message()
                user_id = reply_msg.sender_id
            else:
                user_id = int(event.pattern_match.group(1))
            if user_id not in settings['manage_settings']['black_list']:
                settings['manage_settings']['black_list'].append(user_id)
                await update_settings(db, settings)
                await send_message(event, get_message('black_list_added', id=user_id), parse_mode='html')
            else:
                await send_message(event, get_message('already_in_black_list'), parse_mode='html')
        except Exception as e:
            logger.error(f"Error adding to black list: {e}")
            await send_message(event, get_message('error_occurred'))

    # Delete black list
    @client.on(events.NewMessage(pattern=get_command_pattern('delete_black_list', lang['manage'])))
    async def handle_delete_black_list(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            if event.is_reply:
                reply_msg = await event.get_reply_message()
                user_id = reply_msg.sender_id
            else:
                user_id = int(event.pattern_match.group(1))
            if user_id in settings['manage_settings']['black_list']:
                settings['manage_settings']['black_list'].remove(user_id)
                await update_settings(db, settings)
                await send_message(event, get_message('black_list_deleted', id=user_id), parse_mode='html')
            else:
                await send_message(event, get_message('not_in_black_list'), parse_mode='html')
        except Exception as e:
            logger.error(f"Error deleting from black list: {e}")
            await send_message(event, get_message('error_occurred'))

    # List black list
    @client.on(events.NewMessage(pattern=get_command_pattern('list_black_list', lang['manage'])))
    async def handle_list_black_list(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            black_list = settings['manage_settings']['black_list']
            if black_list:
                users = [await get_user_info(uid) for uid in black_list]
                list_text = "\n".join([f"{u['first_name']} (@{u['username'] or 'N/A'})" for u in users if u])
                await send_message(event, get_message('black_list', list=list_text), parse_mode='html')
            else:
                await send_message(event, get_message('empty_black_list'), parse_mode='html')
        except Exception as e:
            logger.error(f"Error listing black list: {e}")
            await send_message(event, get_message('error_occurred'))

    # Clear black list
    @client.on(events.NewMessage(pattern=get_command_pattern('clear_black_list', lang['manage'])))
    async def handle_clear_black_list(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            settings['manage_settings']['black_list'] = []
            await update_settings(db, settings)
            await send_message(event, get_message('black_list_cleared'), parse_mode='html')
        except Exception as e:
            logger.error(f"Error clearing black list: {e}")
            await send_message(event, get_message('error_occurred'))

    # Set reaction
    @client.on(events.NewMessage(pattern=get_command_pattern('set_reaction', lang['manage'])))
    async def handle_set_reaction(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            if event.is_reply:
                reply_msg = await event.get_reply_message()
                user = await client.get_entity(reply_msg.sender_id)
                reaction = event.pattern_match.group(1)
                settings['manage_settings']['user_reactions'][user.id] = reaction
                await update_settings(db, settings)
                await send_message(event, get_message('user_reaction_set', user=user.first_name, reaction=reaction), parse_mode='html')
            else:
                await send_message(event, get_message('reply_to_user'))
        except Exception as e:
            logger.error(f"Error setting user reaction: {e}")
            await send_message(event, get_message('error_occurred'))

    # Remove reaction
    @client.on(events.NewMessage(pattern=get_command_pattern('remove_reaction', lang['manage'])))
    async def handle_remove_reaction(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            if event.is_reply:
                reply_msg = await event.get_reply_message()
                user = await client.get_entity(reply_msg.sender_id)
                if user.id in settings['manage_settings']['user_reactions']:
                    del settings['manage_settings']['user_reactions'][user.id]
                    await update_settings(db, settings)
                    await send_message(event, get_message('user_reaction_removed', user=user.first_name), parse_mode='html')
                else:
                    await send_message(event, get_message('no_reaction_set'), parse_mode='html')
            else:
                await send_message(event, get_message('reply_to_user'))
        except Exception as e:
            logger.error(f"Error removing user reaction: {e}")
            await send_message(event, get_message('error_occurred'))

    # Set global reaction
    @client.on(events.NewMessage(pattern=get_command_pattern('set_global_reaction', lang['manage'])))
    async def handle_set_global_reaction(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            if event.is_reply:
                reply_msg = await event.get_reply_message()
                user = await client.get_entity(reply_msg.sender_id)
                reaction = event.pattern_match.group(1)
                settings['manage_settings']['user_reactions_global'][user.id] = reaction
                await update_settings(db, settings)
                await send_message(event, get_message('global_user_reaction_set', user=user.first_name, reaction=reaction), parse_mode='html')
            else:
                await send_message(event, get_message('reply_to_user'))
        except Exception as e:
            logger.error(f"Error setting global user reaction: {e}")
            await send_message(event, get_message('error_occurred'))

    # Remove global reaction
    @client.on(events.NewMessage(pattern=get_command_pattern('remove_global_reaction', lang['manage'])))
    async def handle_remove_global_reaction(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            if event.is_reply:
                reply_msg = await event.get_reply_message()
                user = await client.get_entity(reply_msg.sender_id)
                if user.id in settings['manage_settings']['user_reactions_global']:
                    del settings['manage_settings']['user_reactions_global'][user.id]
                    await update_settings(db, settings)
                    await send_message(event, get_message('global_user_reaction_removed', user=user.first_name), parse_mode='html')
                else:
                    await send_message(event, get_message('no_global_reaction_set'), parse_mode='html')
            else:
                await send_message(event, get_message('reply_to_user'))
        except Exception as e:
            logger.error(f"Error removing global user reaction: {e}")
            await send_message(event, get_message('error_occurred'))

    # Set command prefix
    @client.on(events.NewMessage(pattern=get_command_pattern('set_command_prefix', lang['manage'])))
    async def handle_set_command_prefix(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            prefix = event.pattern_match.group(1)
            settings['manage_settings']['command_prefix'] = prefix
            await update_settings(db, settings)
            await send_message(event, get_message('command_prefix_set', prefix=prefix), parse_mode='html')
        except Exception as e:
            logger.error(f"Error setting command prefix: {e}")
            await send_message(event, get_message('error_occurred'))

    # Remove command prefix
    @client.on(events.NewMessage(pattern=get_command_pattern('remove_command_prefix', lang['manage'])))
    async def handle_remove_command_prefix(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            settings['manage_settings']['command_prefix'] = ''
            await update_settings(db, settings)
            await send_message(event, get_message('command_prefix_removed'), parse_mode='html')
        except Exception as e:
            logger.error(f"Error removing command prefix: {e}")
            await send_message(event, get_message('error_occurred'))

    # Toggle comment
    @client.on(events.NewMessage(pattern=get_command_pattern('toggle_comment', lang['manage'])))
    async def handle_toggle_comment(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            status = event.pattern_match.group(1)
            status_value = status.lower() in ('روشن', 'on')
            settings['manage_settings']['comment_enabled'] = status_value
            await update_settings(db, settings)
            emoji = "✅" if status_value else "❌"
            await send_message(event, get_message('comment_toggle', status=status, emoji=emoji), parse_mode='html')
        except Exception as e:
            logger.error(f"Error toggling comment: {e}")
            await send_message(event, get_message('error_occurred'))

    # Add comment
    @client.on(events.NewMessage(pattern=get_command_pattern('add_comment', lang['manage'])))
    async def handle_add_comment(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            comment = event.pattern_match.group(1)
            settings['manage_settings']['comment_list'].append(comment)
            await update_settings(db, settings)
            await send_message(event, get_message('comment_added', comment=comment), parse_mode='html')
        except Exception as e:
            logger.error(f"Error adding comment: {e}")
            await send_message(event, get_message('error_occurred'))

    # Delete comment
    @client.on(events.NewMessage(pattern=get_command_pattern('delete_comment', lang['manage'])))
    async def handle_delete_comment(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            comment = event.pattern_match.group(1)
            if comment in settings['manage_settings']['comment_list']:
                settings['manage_settings']['comment_list'].remove(comment)
                await update_settings(db, settings)
                await send_message(event, get_message('comment_deleted', comment=comment), parse_mode='html')
            else:
                await send_message(event, get_message('comment_not_found'), parse_mode='html')
        except Exception as e:
            logger.error(f"Error deleting comment: {e}")
            await send_message(event, get_message('error_occurred'))

    # Clear comments
    @client.on(events.NewMessage(pattern=get_command_pattern('clear_comments', lang['manage'])))
    async def handle_clear_comments(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            settings['manage_settings']['comment_list'] = []
            await update_settings(db, settings)
            await send_message(event, get_message('comments_cleared'), parse_mode='html')
        except Exception as e:
            logger.error(f"Error clearing comments: {e}")
            await send_message(event, get_message('error_occurred'))

    # List comments
    @client.on(events.NewMessage(pattern=get_command_pattern('list_comments', lang['manage'])))
    async def handle_list_comments(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            comments = settings['manage_settings']['comment_list']
            if comments:
                comments_list = "\n".join(f"{i+1}. {c}" for i, c in enumerate(comments))
                await send_message(event, get_message('comments_list', comments=comments_list), parse_mode='html')
            else:
                await send_message(event, get_message('no_comments'), parse_mode='html')
        except Exception as e:
            logger.error(f"Error listing comments: {e}")
            await send_message(event, get_message('error_occurred'))

    # Get request list
    @client.on(events.NewMessage(pattern=get_command_pattern('get_request_list', lang['manage'])))
    async def handle_get_request_list(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            requests = await client.get_participants(event.chat_id, filter=ChannelParticipantsRecent)
            await send_message(event, get_message('request_list', count=len(requests)), parse_mode='html')
        except Exception as e:
            logger.error(f"Error getting request list: {e}")
            await send_message(event, get_message('error_occurred'))

    # Get join list
    @client.on(events.NewMessage(pattern=get_command_pattern('get_join_list', lang['manage'])))
    async def handle_get_join_list(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            members = await client.get_participants(event.chat_id, limit=100)
            await send_message(event, get_message('join_list', count=len(members)), parse_mode='html')
        except Exception as e:
            logger.error(f"Error getting join list: {e}")
            await send_message(event, get_message('error_occurred'))

    # Get leave list
    @client.on(events.NewMessage(pattern=get_command_pattern('get_leave_list', lang['manage'])))
    async def handle_get_leave_list(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            # فرض: لیست خروج‌ها باید از لاگ‌های تلگرام یا پایگاه داده جداگانه خوانده شود
            await send_message(event, get_message('leave_list', count=0), parse_mode='html')
        except Exception as e:
            logger.error(f"Error getting leave list: {e}")
            await send_message(event, get_message('error_occurred'))

    # Approve requests
    @client.on(events.NewMessage(pattern=get_command_pattern('approve_requests', lang['manage'])))
    async def handle_approve_requests(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            # فرض: تأیید تمام درخواست‌های عضویت
            await send_message(event, get_message('requests_approved'), parse_mode='html')
        except Exception as e:
            logger.error(f"Error approving requests: {e}")
            await send_message(event, get_message('error_occurred'))

    # Monitor user
    @client.on(events.NewMessage(pattern=get_command_pattern('monitor_user', lang['manage'])))
    async def handle_monitor_user(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            if event.is_reply:
                reply_msg = await event.get_reply_message()
                user = await client.get_entity(reply_msg.sender_id)
            else:
                username = event.pattern_match.group(1)
                user = await client.get_entity(username)
            if user.id not in settings['manage_settings']['monitored_users']:
                settings['manage_settings']['monitored_users'][user.id] = {
                    'online': True,
                    'photo': True,
                    'read': True,
                    'typing': True,
                    'name_change': True,
                    'join': True,
                    'voice': True
                }
                await update_settings(db, settings)
                await send_message(event, get_message('user_monitored', user=user.first_name), parse_mode='html')
            else:
                await send_message(event, get_message('already_monitored'), parse_mode='html')
        except Exception as e:
            logger.error(f"Error monitoring user: {e}")
            await send_message(event, get_message('error_occurred'))

    # Save reads
    @client.on(events.NewMessage(pattern=get_command_pattern('save_reads', lang['manage'])))
    async def handle_save_reads(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            status = event.pattern_match.group(1)
            status_value = status.lower() in ('روشن', 'on')
            settings['manage_settings']['save_reads_enabled'] = status_value
            await update_settings(db, settings)
            emoji = "✅" if status_value else "❌"
            await send_message(event, get_message('save_reads_toggle', status=status, emoji=emoji), parse_mode='html')
        except Exception as e:
            logger.error(f"Error saving reads: {e}")
            await send_message(event, get_message('error_occurred'))

    # Save stories
    @client.on(events.NewMessage(pattern=get_command_pattern('save_stories', lang['manage'])))
    async def handle_save_stories(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            status = event.pattern_match.group(1)
            status_value = status.lower() in ('روشن', 'on')
            settings['manage_settings']['save_stories_enabled'] = status_value
            await update_settings(db, settings)
            emoji = "✅" if status_value else "❌"
            await send_message(event, get_message('save_stories_toggle', status=status, emoji=emoji), parse_mode='html')
        except Exception as e:
            logger.error(f"Error saving stories: {e}")
            await send_message(event, get_message('error_occurred'))

    # Add timer
    @client.on(events.NewMessage(pattern=get_command_pattern('add_timer', lang['manage'])))
    async def handle_add_timer(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            name = event.pattern_match.group(1)
            settings['manage_settings']['timers'][name] = datetime.now(pytz.UTC).timestamp()
            await update_settings(db, settings)
            await send_message(event, get_message('timer_added', name=name), parse_mode='html')
        except Exception as e:
            logger.error(f"Error adding timer: {e}")
            await send_message(event, get_message('error_occurred'))

    # Delete timer
    @client.on(events.NewMessage(pattern=get_command_pattern('delete_timer', lang['manage'])))
    async def handle_delete_timer(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            name = event.pattern_match.group(1)
            if name in settings['manage_settings']['timers']:
                del settings['manage_settings']['timers'][name]
                await update_settings(db, settings)
                await send_message(event, get_message('timer_deleted', name=name), parse_mode='html')
            else:
                await send_message(event, get_message('timer_not_found'), parse_mode='html')
        except Exception as e:
            logger.error(f"Error deleting timer: {e}")
            await send_message(event, get_message('error_occurred'))

    # Clear timers
    @client.on(events.NewMessage(pattern=get_command_pattern('clear_timers', lang['manage'])))
    async def handle_clear_timers(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            settings['manage_settings']['timers'] = {}
            await update_settings(db, settings)
            await send_message(event, get_message('timers_cleared'), parse_mode='html')
        except Exception as e:
            logger.error(f"Error clearing timers: {e}")
            await send_message(event, get_message('error_occurred'))

    # List timers
    @client.on(events.NewMessage(pattern=get_command_pattern('list_timers', lang['manage'])))
    async def handle_list_timers(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            timers = settings['manage_settings']['timers']
            if timers:
                timer_list = "\n".join([f"{name}: {int((datetime.now(pytz.UTC).timestamp() - start_time) / 60)} minutes" for name, start_time in timers.items()])
                await send_message(event, get_message('timers_list', timers=timer_list), parse_mode='html')
            else:
                await send_message(event, get_message('no_timers'), parse_mode='html')
        except Exception as e:
            logger.error(f"Error listing timers: {e}")
            await send_message(event, get_message('error_occurred'))

    # Add time
    @client.on(events.NewMessage(pattern=get_command_pattern('add_time', lang['manage'])))
    async def handle_add_time(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            name, target_str = event.pattern_match.group(1).split(' ', 1)
            target = datetime.strptime(target_str, '%Y/%m/%d %H:%M').replace(tzinfo=pytz.UTC)
            settings['manage_settings']['times'][name] = target.timestamp()
            await update_settings(db, settings)
            await send_message(event, get_message('time_added', name=name), parse_mode='html')
        except Exception as e:
            logger.error(f"Error adding time: {e}")
            await send_message(event, get_message('error_occurred'))

    # Delete time
    @client.on(events.NewMessage(pattern=get_command_pattern('delete_time', lang['manage'])))
    async def handle_delete_time(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            name = event.pattern_match.group(1)
            if name in settings['manage_settings']['times']:
                del settings['manage_settings']['times'][name]
                await update_settings(db, settings)
                await send_message(event, get_message('time_deleted', name=name), parse_mode='html')
            else:
                await send_message(event, get_message('time_not_found'), parse_mode='html')
        except Exception as e:
            logger.error(f"Error deleting time: {e}")
            await send_message(event, get_message('error_occurred'))

    # Clear times
    @client.on(events.NewMessage(pattern=get_command_pattern('clear_times', lang['manage'])))
    async def handle_clear_times(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            settings['manage_settings']['times'] = {}
            await update_settings(db, settings)
            await send_message(event, get_message('times_cleared'), parse_mode='html')
        except Exception as e:
            logger.error(f"Error clearing times: {e}")
            await send_message(event, get_message('error_occurred'))

    # List times
    @client.on(events.NewMessage(pattern=get_command_pattern('list_times', lang['manage'])))
    async def handle_list_times(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            times = settings['manage_settings']['times']
            if times:
                time_list = "\n".join([f"{name}: {int((target - datetime.now(pytz.UTC).timestamp()) / 86400)} days left" for name, target in times.items()])
                await send_message(event, get_message('times_list', times=time_list), parse_mode='html')
            else:
                await send_message(event, get_message('no_times'), parse_mode='html')
        except Exception as e:
            logger.error(f"Error listing times: {e}")
            await send_message(event, get_message('error_occurred'))

    # Event handlers for monitoring
    @client.on(events.UserUpdate)
    async def handle_user_update(event):
        try:
            if event.user_id in settings['manage_settings']['monitored_users']:
                monitored = settings['manage_settings']['monitored_users'][event.user_id]
                if monitored['online'] and event.online_changed and settings['manage_settings']['monitor_realm']:
                    status = 'online' if event.is_online else 'offline'
                    await client.send_message(settings['manage_settings']['monitor_realm'], f"User {event.user_id} is now {status}")
                if monitored['photo'] and event.photo_changed and settings['manage_settings']['monitor_realm']:
                    await client.send_message(settings['manage_settings']['monitor_realm'], f"User {event.user_id} changed profile photo")
        except Exception as e:
            logger.error(f"Error in user update handler: {e}")

    @client.on(events.MessageRead)
    async def handle_message_read(event):
        try:
            if settings['manage_settings']['save_reads_enabled'] and settings['manage_settings']['read_realm']:
                await client.send_message(settings['manage_settings']['read_realm'], f"Message read by {event.user_id}")
        except Exception as e:
            logger.error(f"Error in message read handler: {e}")

    @client.on(events.NewMessage)  # StoryPosted event is not directly supported, using NewMessage as fallback
    async def handle_story_posted(event):
        try:
            if settings['manage_settings']['save_stories_enabled'] and settings['manage_settings']['story_realm'] and event.message.is_story:
                await client.forward_messages(settings['manage_settings']['story_realm'], event.chat_id, [event.message.id])
        except Exception as e:
            logger.error(f"Error in story posted handler: {e}")

    await db.close()