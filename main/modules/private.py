import asyncio
import logging
from datetime import datetime, timedelta
import pytz
from telethon import events, functions
from telethon.tl.functions.messages import UpdatePinnedMessageRequest, DeleteMessagesRequest, GetMessagesRequest
from telethon.tl.functions.users import GetFullUserRequest
from telethon.tl.functions.channels import GetParticipantRequest
from telethon.errors import FloodWaitError, UserPrivacyRestrictedError, ChatAdminRequiredError
from utils import load_json, send_message, get_command_pattern
from models import get_database, load_settings, update_settings

logger = logging.getLogger(__name__)

async def register_private_handlers(client, session_name, owner_id):
    db = await get_database(session_name)
    settings = await load_settings(db)
    if not settings:
        logger.error("Failed to load settings for private handlers")
        await db.close()
        return

    lang = settings.get('lang', 'fa')
    messages = load_json('msg.json')
    commands = load_json('cmd.json')

    def get_message(key, **kwargs):
        return messages[lang]['private'].get(key, '').format(**kwargs)

    # تنظیمات اولیه private
    if 'private_settings' not in settings:
        settings['private_settings'] = {
            'secretary_enabled': False,
            'secretary_message': None,
            'secretary_delay': 0,
            'smart_secretary_enabled': False,
            'smart_secretary_message': None,
            'offline_secretary_enabled': False,
            'offline_secretary_delay': 0,
            'offline_last_seen': datetime.now(pytz.UTC).timestamp(),
            'save_pv_enabled': False,
            'save_pv_chat_id': None,
            'birthday_enabled': False,
            'birthday_messages': [],
            'birthday_users': {},  # {user_id: {date: str, message: str}}
            'block_mode_enabled': False,
            'pin_mode': 'none',  # none, single, mutual
            'silence_pv_enabled': False,
            'silence_specific_enabled': False,
            'save_deleted_enabled': False,
            'save_deleted_chat_id': None,
            'save_edited_enabled': False,
            'save_edited_chat_id': None,
            'save_timed_enabled': False,
            'save_timed_chat_id': None,
            'backup_channel_id': None,
            'bot_token': None,
            'force_join_enabled': False,
            'force_join_chat_id': None,
            'force_join_message': None,
            'force_join_delay': 0,
            'force_join_relax_enabled': False,
            'force_join_relax_delay': 0,
            'force_join_save_enabled': False,
            'force_join_save_chat_id': None,
            'protect_enabled': False,
            'protect_limit': 5,
            'protect_message': None,
            'protect_warning_enabled': False,
            'protect_warning_message': None,
            'protect_relax_enabled': False,
            'protect_relax_delay': 0,
            'filter_list': [],
            'message_counts': {},  # {user_id: count}
            'last_message_time': {},  # {user_id: timestamp}
            'last_owner_message': {}  # {user_id: timestamp}
        }
        await update_settings(db, settings)

    async def get_user_info(user_id):
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

    # وضعیت منشی
    @client.on(events.NewMessage(pattern=get_command_pattern('secretary_status', lang)))
    async def handle_secretary_status(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            status = []
            if settings['private_settings']['secretary_enabled']:
                status.append(get_message('secretary_enabled'))
            if settings['private_settings']['smart_secretary_enabled']:
                status.append(get_message('smart_secretary_enabled'))
            if settings['private_settings']['offline_secretary_enabled']:
                status.append(get_message('offline_secretary_enabled', delay=settings['private_settings']['offline_secretary_delay']))
            if settings['private_settings']['save_pv_enabled']:
                status.append(get_message('save_pv_enabled'))
            if settings['private_settings']['birthday_enabled']:
                status.append(get_message('birthday_enabled'))
            if settings['private_settings']['block_mode_enabled']:
                status.append(get_message('block_mode_enabled'))
            if settings['private_settings']['silence_pv_enabled']:
                status.append(get_message('silence_pv_enabled'))
            if settings['private_settings']['save_deleted_enabled']:
                status.append(get_message('save_deleted_enabled'))
            if settings['private_settings']['save_edited_enabled']:
                status.append(get_message('save_edited_enabled'))
            if settings['private_settings']['save_timed_enabled']:
                status.append(get_message('save_timed_enabled'))
            if settings['private_settings']['force_join_enabled']:
                status.append(get_message('force_join_enabled'))
            if settings['private_settings']['protect_enabled']:
                status.append(get_message('protect_enabled', limit=settings['private_settings']['protect_limit']))
            if not status:
                status.append(get_message('no_features_enabled'))
            await send_message(event, "\n".join(status), parse_mode='html')
        except Exception as e:
            logger.error(f"Error getting secretary status: {e}")
            await send_message(event, get_message('error_occurred'))

    # منشی عادی
    @client.on(events.NewMessage(pattern=get_command_pattern('secretary_on', 'private', lang)))
    async def handle_secretary_on(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            settings['private_settings']['secretary_enabled'] = True
            await update_settings(db, settings)
            await send_message(event, get_message('secretary_enabled'), parse_mode='html')
        except Exception as e:
            logger.error(f"Error enabling secretary: {e}")
            await send_message(event, get_message('error_occurred'))

    @client.on(events.NewMessage(pattern=get_command_pattern('secretary_off', 'private', lang)))
    async def handle_secretary_off(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            settings['private_settings']['secretary_enabled'] = False
            await update_settings(db, settings)
            await send_message(event, get_message('secretary_disabled'), parse_mode='html')
        except Exception as e:
            logger.error(f"Error disabling secretary: {e}")
            await send_message(event, get_message('error_occurred'))

    @client.on(events.NewMessage(pattern=get_command_pattern('set_secretary', 'private', lang)))
    async def handle_set_secretary(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            if event.is_reply:
                reply_msg = await event.get_reply_message()
                settings['private_settings']['secretary_message'] = reply_msg.text
                await update_settings(db, settings)
                await send_message(event, get_message('secretary_message_set'), parse_mode='html')
            else:
                await send_message(event, get_message('reply_to_message'))
        except Exception as e:
            logger.error(f"Error setting secretary message: {e}")
            await send_message(event, get_message('error_occurred'))

    @client.on(events.NewMessage(pattern=get_command_pattern('set_secretary_delay', 'private', lang)))
    async def handle_set_secretary_delay(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            delay = int(event.pattern_match.group(1))
            settings['private_settings']['secretary_delay'] = delay
            await update_settings(db, settings)
            await send_message(event, get_message('secretary_delay_set', delay=delay), parse_mode='html')
        except Exception as e:
            logger.error(f"Error setting secretary delay: {e}")
            await send_message(event, get_message('error_occurred'))

    # منشی هوشمند
    @client.on(events.NewMessage(pattern=get_command_pattern('smart_secretary_on', 'private', lang)))
    async def handle_smart_secretary_on(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            settings['private_settings']['smart_secretary_enabled'] = True
            await update_settings(db, settings)
            await send_message(event, get_message('smart_secretary_enabled'), parse_mode='html')
        except Exception as e:
            logger.error(f"Error enabling smart secretary: {e}")
            await send_message(event, get_message('error_occurred'))

    @client.on(events.NewMessage(pattern=get_command_pattern('smart_secretary_off', 'private', lang)))
    async def handle_smart_secretary_off(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            settings['private_settings']['smart_secretary_enabled'] = False
            await update_settings(db, settings)
            await send_message(event, get_message('smart_secretary_disabled'), parse_mode='html')
        except Exception as e:
            logger.error(f"Error disabling smart secretary: {e}")
            await send_message(event, get_message('error_occurred'))

    @client.on(events.NewMessage(pattern=get_command_pattern('set_smart_secretary', 'private', lang)))
    async def handle_set_smart_secretary(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            if event.is_reply:
                reply_msg = await event.get_reply_message()
                settings['private_settings']['smart_secretary_message'] = reply_msg.text
                await update_settings(db, settings)
                await send_message(event, get_message('smart_secretary_message_set'), parse_mode='html')
            else:
                await send_message(event, get_message('reply_to_message'))
        except Exception as e:
            logger.error(f"Error setting smart secretary message: {e}")
            await send_message(event, get_message('error_occurred'))

    # منشی آفلاین
    @client.on(events.NewMessage(pattern=get_command_pattern('offline_secretary_on', 'private', lang)))
    async def handle_offline_secretary_on(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            settings['private_settings']['offline_secretary_enabled'] = True
            settings['private_settings']['offline_last_seen'] = datetime.now(pytz.UTC).timestamp()
            await update_settings(db, settings)
            await send_message(event, get_message('offline_secretary_enabled'), parse_mode='html')
        except Exception as e:
            logger.error(f"Error enabling offline secretary: {e}")
            await send_message(event, get_message('error_occurred'))

    @client.on(events.NewMessage(pattern=get_command_pattern('offline_secretary_off', 'private', lang)))
    async def handle_offline_secretary_off(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            settings['private_settings']['offline_secretary_enabled'] = False
            await update_settings(db, settings)
            await send_message(event, get_message('offline_secretary_disabled'), parse_mode='html')
        except Exception as e:
            logger.error(f"Error disabling offline secretary: {e}")
            await send_message(event, get_message('error_occurred'))

    @client.on(events.NewMessage(pattern=get_command_pattern('set_offline_secretary', 'private', lang)))
    async def handle_set_offline_secretary(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            delay = int(event.pattern_match.group(1))
            settings['private_settings']['offline_secretary_delay'] = delay
            await update_settings(db, settings)
            await send_message(event, get_message('offline_secretary_delay_set', delay=delay), parse_mode='html')
        except Exception as e:
            logger.error(f"Error setting offline secretary delay: {e}")
            await send_message(event, get_message('error_occurred'))

    # ذخیره پیام‌های پیوی
    @client.on(events.NewMessage(pattern=get_command_pattern('save_pv_on', 'private', lang)))
    async def handle_save_pv_on(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            settings['private_settings']['save_pv_enabled'] = True
            await update_settings(db, settings)
            await send_message(event, get_message('save_pv_enabled'), parse_mode='html')
        except Exception as e:
            logger.error(f"Error enabling save PV: {e}")
            await send_message(event, get_message('error_occurred'))

    @client.on(events.NewMessage(pattern=get_command_pattern('save_pv_off', lang['private'])))
    async def handle_save_pv_off(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            settings['private_settings']['save_pv_enabled'] = False
            await update_settings(db, settings)
            await send_message(event, get_message('save_pv_disabled'), parse_mode='html')
        except Exception as e:
            logger.error(f"Error disabling save PV: {e}")
            await send_message(event, get_message('error_occurred'))

    # تبریک تولد
    @client.on(events.NewMessage(pattern=get_command_pattern('birthday_on', lang['private'])))
    async def handle_birthday_on(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            settings['private_settings']['birthday_enabled'] = True
            await update_settings(db, settings)
            await send_message(event, get_message('birthday_enabled'), parse_mode='html')
        except Exception as e:
            logger.error(f"Error enabling birthday: {e}")
            await send_message(event, get_message('error_occurred'))

    @client.on(events.NewMessage(pattern=get_command_pattern('birthday_off', lang['private'])))
    async def handle_birthday_off(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            settings['private_settings']['birthday_enabled'] = False
            await update_settings(db, settings)
            await send_message(event, get_message('birthday_disabled'), parse_mode='html')
        except Exception as e:
            logger.error(f"Error disabling birthday: {e}")
            await send_message(event, get_message('error_occurred'))

    @client.on(events.NewMessage(pattern=get_command_pattern('add_birthday_message', lang['private'])))
    async def handle_add_birthday_message(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            if event.is_reply:
                reply_msg = await event.get_reply_message()
                settings['private_settings']['birthday_messages'].append(reply_msg.text)
                await update_settings(db, settings)
                await send_message(event, get_message('birthday_message_added'), parse_mode='html')
            else:
                await send_message(event, get_message('reply_to_message'))
        except Exception as e:
            logger.error(f"Error adding birthday message: {e}")
            await send_message(event, get_message('error_occurred'))

    @client.on(events.NewMessage(pattern=get_command_pattern('remove_birthday_message', lang['private'])))
    async def handle_remove_birthday_message(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            if event.is_reply:
                reply_msg = await event.get_reply_message()
                if reply_msg.text in settings['private_settings']['birthday_messages']:
                    settings['private_settings']['birthday_messages'].remove(reply_msg.text)
                    await update_settings(db, settings)
                    await send_message(event, get_message('birthday_message_removed'), parse_mode='html')
                else:
                    await send_message(event, get_message('birthday_message_not_found'), parse_mode='html')
            else:
                await send_message(event, get_message('reply_to_message'))
        except Exception as e:
            logger.error(f"Error removing birthday message: {e}")
            await send_message(event, get_message('error_occurred'))

    @client.on(events.NewMessage(pattern=get_command_pattern('list_birthday_messages', lang['private'])))
    async def handle_list_birthday_messages(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            messages = settings['private_settings']['birthday_messages']
            if messages:
                message_list = "\n".join([f"{i+1}. {msg}" for i, msg in enumerate(messages)])
                await send_message(event, get_message('birthday_messages_list', list=message_list), parse_mode='html')
            else:
                await send_message(event, get_message('no_birthday_messages'), parse_mode='html')
        except Exception as e:
            logger.error(f"Error listing birthday messages: {e}")
            await send_message(event, get_message('error_occurred'))

    @client.on(events.NewMessage(pattern=get_command_pattern('clear_birthday_messages', lang['private'])))
    async def handle_clear_birthday_messages(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            settings['private_settings']['birthday_messages'] = []
            await update_settings(db, settings)
            await send_message(event, get_message('birthday_messages_cleared'), parse_mode='html')
        except Exception as e:
            logger.error(f"Error clearing birthday messages: {e}")
            await send_message(event, get_message('error_occurred'))

    @client.on(events.NewMessage(pattern=get_command_pattern('manage_birthday', lang['private'])))
    async def handle_manage_birthday(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            if event.is_reply:
                reply_msg = await event.get_reply_message()
                user = await client.get_entity(reply_msg.sender_id)
                date = event.pattern_match.group(1)
                if date:
                    settings['private_settings']['birthday_users'][user.id] = {'date': date, 'message': settings['private_settings']['birthday_messages'][0] if settings['private_settings']['birthday_messages'] else 'Happy Birthday!'}
                    await update_settings(db, settings)
                    await send_message(event, get_message('birthday_user_added', user=user.first_name), parse_mode='html')
                else:
                    if user.id in settings['private_settings']['birthday_users']:
                        del settings['private_settings']['birthday_users'][user.id]
                        await update_settings(db, settings)
                        await send_message(event, get_message('birthday_user_removed', user=user.first_name), parse_mode='html')
                    else:
                        await send_message(event, get_message('birthday_user_not_found'), parse_mode='html')
            else:
                await send_message(event, get_message('reply_to_user'))
        except Exception as e:
            logger.error(f"Error managing birthday: {e}")
            await send_message(event, get_message('error_occurred'))

    # حالت بلاک
    @client.on(events.NewMessage(pattern=get_command_pattern('block_mode_on', lang['private'])))
    async def handle_block_mode_on(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            settings['private_settings']['block_mode_enabled'] = True
            await update_settings(db, settings)
            await send_message(event, get_message('block_mode_enabled'), parse_mode='html')
        except Exception as e:
            logger.error(f"Error enabling block mode: {e}")
            await send_message(event, get_message('error_occurred'))

    @client.on(events.NewMessage(pattern=get_command_pattern('block_mode_off', lang['private'])))
    async def handle_block_mode_off(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            settings['private_settings']['block_mode_enabled'] = False
            await update_settings(db, settings)
            await send_message(event, get_message('block_mode_disabled'), parse_mode='html')
        except Exception as e:
            logger.error(f"Error disabling block mode: {e}")
            await send_message(event, get_message('error_occurred'))

    # پین کردن پیام‌ها
    @client.on(events.NewMessage(pattern=get_command_pattern('pin', lang['private'])))
    async def handle_pin(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            if event.is_reply:
                reply_msg = await event.get_reply_message()
                settings['private_settings']['pin_mode'] = 'single'
                await client(UpdatePinnedMessageRequest(peer=event.chat_id, id=reply_msg.id, silent=True, pinned=True))
                await update_settings(db, settings)
                await send_message(event, get_message('message_pinned'), parse_mode='html')
            else:
                await send_message(event, get_message('reply_to_message'))
        except Exception as e:
            logger.error(f"Error pinning message: {e}")
            await send_message(event, get_message('error_occurred'))

    @client.on(events.NewMessage(pattern=get_command_pattern('unpin', lang['private'])))
    async def handle_unpin(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            if event.is_reply:
                reply_msg = await event.get_reply_message()
                await client(UnpinMessageRequest(event.chat_id, reply_msg.id))
                await send_message(event, get_message('message_unpinned'), parse_mode='html')
            else:
                await send_message(event, get_message('reply_to_message'))
        except Exception as e:
            logger.error(f"Error unpinning message: {e}")
            await send_message(event, get_message('error_occurred'))

    @client.on(events.NewMessage(pattern=get_command_pattern('mutual_pin', lang['private'])))
    async def handle_mutual_pin(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            if event.is_reply:
                reply_msg = await event.get_reply_message()
                settings['private_settings']['pin_mode'] = 'mutual'
                await client(UpdatePinnedMessageRequest(peer=event.chat_id, id=reply_msg.id, silent=True, pinned=True))
                await update_settings(db, settings)
                await send_message(event, get_message('message_mutual_pinned'), parse_mode='html')
            else:
                await send_message(event, get_message('reply_to_message'))
        except Exception as e:
            logger.error(f"Error mutual pinning: {e}")
            await send_message(event, get_message('error_occurred'))

    @client.on(events.NewMessage(pattern=get_command_pattern('unpin_all', lang['private'])))
    async def handle_unpin_all(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            settings['private_settings']['pin_mode'] = 'none'
            await client(UpdatePinnedMessageRequest(peer=event.chat_id, id=reply_msg.id, pinned=False))
            await update_settings(db, settings)
            await send_message(event, get_message('all_pins_unpinned'), parse_mode='html')
        except Exception as e:
            logger.error(f"Error unpinning all messages: {e}")
            await send_message(event, get_message('error_occurred'))

    # سکوت پیوی
    @client.on(events.NewMessage(pattern=get_command_pattern('silence_pv_on', lang['private'])))
    async def handle_silence_pv_on(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            settings['private_settings']['silence_pv_enabled'] = True
            await update_settings(db, settings)
            await send_message(event, get_message('silence_pv_enabled'), parse_mode='html')
        except Exception as e:
            logger.error(f"Error enabling silence PV: {e}")
            await send_message(event, get_message('error_occurred'))

    @client.on(events.NewMessage(pattern=get_command_pattern('silence_pv_off', lang['private'])))
    async def handle_silence_pv_off(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            settings['private_settings']['silence_pv_enabled'] = False
            await update_settings(db, settings)
            await send_message(event, get_message('silence_pv_disabled'), parse_mode='html')
        except Exception as e:
            logger.error(f"Error disabling silence PV: {e}")
            await send_message(event, get_message('error_occurred'))

    @client.on(events.NewMessage(pattern=get_command_pattern('silence_specific_on', lang['private'])))
    async def handle_silence_specific_on(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            settings['private_settings']['silence_specific_enabled'] = True
            await update_settings(db, settings)
            await send_message(event, get_message('silence_specific_enabled'), parse_mode='html')
        except Exception as e:
            logger.error(f"Error enabling specific silence: {e}")
            await send_message(event, get_message('error_occurred'))

    @client.on(events.NewMessage(pattern=get_command_pattern('silence_specific_off', lang['private'])))
    async def handle_silence_specific_off(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            settings['private_settings']['silence_specific_enabled'] = False
            await update_settings(db, settings)
            await send_message(event, get_message('silence_specific_disabled'), parse_mode='html')
        except Exception as e:
            logger.error(f"Error disabling specific silence: {e}")
            await send_message(event, get_message('error_occurred'))

    # ذخیره پیام‌های حذف‌شده
    @client.on(events.NewMessage(pattern=get_command_pattern('save_deleted_on', lang['private'])))
    async def handle_save_deleted_on(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            if not settings['private_settings']['backup_channel_id'] or not settings['private_settings']['bot_token']:
                await send_message(event, get_message('backup_not_configured'), parse_mode='html')
                return
            settings['private_settings']['save_deleted_enabled'] = True
            await update_settings(db, settings)
            await send_message(event, get_message('save_deleted_enabled'), parse_mode='html')
        except Exception as e:
            logger.error(f"Error enabling save deleted: {e}")
            await send_message(event, get_message('error_occurred'))

    @client.on(events.NewMessage(pattern=get_command_pattern('save_deleted_off', lang['private'])))
    async def handle_save_deleted_off(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            settings['private_settings']['save_deleted_enabled'] = False
            await update_settings(db, settings)
            await send_message(event, get_message('save_deleted_disabled'), parse_mode='html')
        except Exception as e:
            logger.error(f"Error disabling save deleted: {e}")
            await send_message(event, get_message('error_occurred'))

    @client.on(events.NewMessage(pattern=get_command_pattern('set_save_deleted_realm', lang['private'])))
    async def handle_set_save_deleted_realm(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            settings['private_settings']['save_deleted_chat_id'] = event.chat_id
            await update_settings(db, settings)
            await send_message(event, get_message('save_deleted_realm_set'), parse_mode='html')
        except Exception as e:
            logger.error(f"Error setting save deleted realm: {e}")
            await send_message(event, get_message('error_occurred'))

    @client.on(events.NewMessage(pattern=get_command_pattern('set_backup_channel', lang['private'])))
    async def handle_set_backup_channel(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            settings['private_settings']['backup_channel_id'] = event.chat_id
            await update_settings(db, settings)
            await send_message(event, get_message('backup_channel_set'), parse_mode='html')
        except Exception as e:
            logger.error(f"Error setting backup channel: {e}")
            await send_message(event, get_message('error_occurred'))

    @client.on(events.NewMessage(pattern=get_command_pattern('set_bot_token', lang['private'])))
    async def handle_set_bot_token(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            token = event.pattern_match.group(1)
            settings['private_settings']['bot_token'] = token
            await update_settings(db, settings)
            await send_message(event, get_message('bot_token_set'), parse_mode='html')
        except Exception as e:
            logger.error(f"Error setting bot token: {e}")
            await send_message(event, get_message('error_occurred'))

    @client.on(events.NewMessage(pattern=get_command_pattern('save_deleted_status', lang['private'])))
    async def handle_save_deleted_status(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            status = []
            if settings['private_settings']['backup_channel_id']:
                status.append(get_message('backup_channel_configured', chat_id=settings['private_settings']['backup_channel_id']))
            else:
                status.append(get_message('backup_channel_not_configured'))
            if settings['private_settings']['bot_token']:
                status.append(get_message('bot_token_configured'))
            else:
                status.append(get_message('bot_token_not_configured'))
            if settings['private_settings']['save_deleted_enabled']:
                status.append(get_message('save_deleted_enabled'))
            else:
                status.append(get_message('save_deleted_disabled'))
            await send_message(event, "\n".join(status), parse_mode='html')
        except Exception as e:
            logger.error(f"Error getting save deleted status: {e}")
            await send_message(event, get_message('error_occurred'))

    # ذخیره ویرایش‌ها
    @client.on(events.NewMessage(pattern=get_command_pattern('save_edited_on', lang['private'])))
    async def handle_save_edited_on(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            if not settings['private_settings']['backup_channel_id'] or not settings['private_settings']['bot_token']:
                await send_message(event, get_message('backup_not_configured'), parse_mode='html')
                return
            settings['private_settings']['save_edited_enabled'] = True
            await update_settings(db, settings)
            await send_message(event, get_message('save_edited_enabled'), parse_mode='html')
        except Exception as e:
            logger.error(f"Error enabling save edited: {e}")
            await send_message(event, get_message('error_occurred'))

    @client.on(events.NewMessage(pattern=get_command_pattern('save_edited_off', lang['private'])))
    async def handle_save_edited_off(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            settings['private_settings']['save_edited_enabled'] = False
            await update_settings(db, settings)
            await send_message(event, get_message('save_edited_disabled'), parse_mode='html')
        except Exception as e:
            logger.error(f"Error disabling save edited: {e}")
            await send_message(event, get_message('error_occurred'))

    @client.on(events.NewMessage(pattern=get_command_pattern('set_save_edited_realm', lang['private'])))
    async def handle_set_save_edited_realm(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            settings['private_settings']['save_edited_chat_id'] = event.chat_id
            await update_settings(db, settings)
            await send_message(event, get_message('save_edited_realm_set'), parse_mode='html')
        except Exception as e:
            logger.error(f"Error setting save edited realm: {e}")
            await send_message(event, get_message('error_occurred'))

    # ذخیره پیام‌های زمان‌دار
    @client.on(events.NewMessage(pattern=get_command_pattern('save_timed_on', lang['private'])))
    async def handle_save_timed_on(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            if not settings['private_settings']['backup_channel_id'] or not settings['private_settings']['bot_token']:
                await send_message(event, get_message('backup_not_configured'), parse_mode='html')
                return
            settings['private_settings']['save_timed_enabled'] = True
            await update_settings(db, settings)
            await send_message(event, get_message('save_timed_enabled'), parse_mode='html')
        except Exception as e:
            logger.error(f"Error enabling save timed: {e}")
            await send_message(event, get_message('error_occurred'))

    @client.on(events.NewMessage(pattern=get_command_pattern('save_timed_off', lang['private'])))
    async def handle_save_timed_off(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            settings['private_settings']['save_timed_enabled'] = False
            await update_settings(db, settings)
            await send_message(event, get_message('save_timed_disabled'), parse_mode='html')
        except Exception as e:
            logger.error(f"Error disabling save timed: {e}")
            await send_message(event, get_message('error_occurred'))

    @client.on(events.NewMessage(pattern=get_command_pattern('set_save_timed_realm', lang['private'])))
    async def handle_set_save_timed_realm(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            settings['private_settings']['save_timed_chat_id'] = event.chat_id
            await update_settings(db, settings)
            await send_message(event, get_message('save_timed_realm_set'), parse_mode='html')
        except Exception as e:
            logger.error(f"Error setting save timed realm: {e}")
            await send_message(event, get_message('error_occurred'))

    # پاکسازی پیام‌ها
    @client.on(events.NewMessage(pattern=get_command_pattern('cleanup_gifs', lang['private'])))
    async def handle_cleanup_gifs(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            message_ids = []
            async for message in client.iter_messages(event.chat_id, limit=100):
                if message.gif:
                    message_ids.append(message.id)
            await client.delete_messages(event.chat_id, message_ids)
            await send_message(event, get_message('gifs_cleaned', count=len(message_ids)), parse_mode='html')
        except Exception as e:
            logger.error(f"Error cleaning gifs: {e}")
            await send_message(event, get_message('error_occurred'))

    @client.on(events.NewMessage(pattern=get_command_pattern('cleanup_photos', lang['private'])))
    async def handle_cleanup_photos(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            message_ids = []
            async for message in client.iter_messages(event.chat_id, limit=100):
                if message.photo:
                    message_ids.append(message.id)
            await client.delete_messages(event.chat_id, message_ids)
            await send_message(event, get_message('photos_cleaned', count=len(message_ids)), parse_mode='html')
        except Exception as e:
            logger.error(f"Error cleaning photos: {e}")
            await send_message(event, get_message('error_occurred'))

    @client.on(events.NewMessage(pattern=get_command_pattern('cleanup_videos', lang['private'])))
    async def handle_cleanup_videos(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            message_ids = []
            async for message in client.iter_messages(event.chat_id, limit=100):
                if message.video:
                    message_ids.append(message.id)
            await client.delete_messages(event.chat_id, message_ids)
            await send_message(event, get_message('videos_cleaned', count=len(message_ids)), parse_mode='html')
        except Exception as e:
            logger.error(f"Error cleaning videos: {e}")
            await send_message(event, get_message('error_occurred'))

    @client.on(events.NewMessage(pattern=get_command_pattern('cleanup_video_notes', lang['private'])))
    async def handle_cleanup_video_notes(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            message_ids = []
            async for message in client.iter_messages(event.chat_id, limit=100):
                if message.video_note:
                    message_ids.append(message.id)
            await client.delete_messages(event.chat_id, message_ids)
            await send_message(event, get_message('video_notes_cleaned', count=len(message_ids)), parse_mode='html')
        except Exception as e:
            logger.error(f"Error cleaning video notes: {e}")
            await send_message(event, get_message('error_occurred'))

    @client.on(events.NewMessage(pattern=get_command_pattern('cleanup_files', lang['private'])))
    async def handle_cleanup_files(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            message_ids = []
            async for message in client.iter_messages(event.chat_id, limit=100):
                if message.document:
                    message_ids.append(message.id)
            await client.delete_messages(event.chat_id, message_ids)
            await send_message(event, get_message('files_cleaned', count=len(message_ids)), parse_mode='html')
        except Exception as e:
            logger.error(f"Error cleaning files: {e}")
            await send_message(event, get_message('error_occurred'))

    @client.on(events.NewMessage(pattern=get_command_pattern('cleanup_voices', lang['private'])))
    async def handle_cleanup_voices(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            message_ids = []
            async for message in client.iter_messages(event.chat_id, limit=100):
                if message.voice:
                    message_ids.append(message.id)
            await client.delete_messages(event.chat_id, message_ids)
            await send_message(event, get_message('voices_cleaned', count=len(message_ids)), parse_mode='html')
        except Exception as e:
            logger.error(f"Error cleaning voices: {e}")
            await send_message(event, get_message('error_occurred'))

    @client.on(events.NewMessage(pattern=get_command_pattern('delete_messages', lang['private'])))
    async def handle_delete_messages(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            count = int(event.pattern_match.group(1))
            message_ids = []
            async for message in client.iter_messages(event.chat_id, limit=count):
                message_ids.append(message.id)
            await client.delete_messages(event.chat_id, message_ids)
            await send_message(event, get_message('messages_deleted', count=len(message_ids)), parse_mode='html')
        except Exception as e:
            logger.error(f"Error deleting messages: {e}")
            await send_message(event, get_message('error_occurred'))

    # درباره پیوی
    @client.on(events.NewMessage(pattern=get_command_pattern('pv_info', lang['private'])))
    async def handle_pv_info(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            user = await client.get_entity(event.chat_id)
            info = f"نام: {user.first_name}\nنام کاربری: @{user.username or 'N/A'}\nID: {user.id}"
            await send_message(event, get_message('pv_info', info=info), parse_mode='html')
        except Exception as e:
            logger.error(f"Error getting PV info: {e}")
            await send_message(event, get_message('error_occurred'))

    # پاکسازی پیام‌ها
    @client.on(events.NewMessage(pattern=get_command_pattern('cleanup_messages', lang['private'])))
    async def handle_cleanup_messages(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            message_ids = []
            async for message in client.iter_messages(event.chat_id, limit=100):
                message_ids.append(message.id)
            await client.delete_messages(event.chat_id, message_ids)
            await send_message(event, get_message('messages_cleaned', count=len(message_ids)), parse_mode='html')
        except Exception as e:
            logger.error(f"Error cleaning messages: {e}")
            await send_message(event, get_message('error_occurred'))

    # حذف تاریخچه
    @client.on(events.NewMessage(pattern=get_command_pattern('delete_history', lang['private'])))
    async def handle_delete_history(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            await client(functions.messages.DeleteHistoryRequest(peer=event.chat_id, max_id=0, revoke=True))
            await send_message(event, get_message('history_deleted'), parse_mode='html')
        except Exception as e:
            logger.error(f"Error deleting history: {e}")
            await send_message(event, get_message('error_occurred'))

    # تایپینگ پیوی
    @client.on(events.NewMessage(pattern=get_command_pattern('pv_typing_on', lang['private'])))
    async def handle_pv_typing_on(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            settings['private_settings']['pv_typing_enabled'] = True
            await update_settings(db, settings)
            await send_message(event, get_message('pv_typing_enabled'), parse_mode='html')
        except Exception as e:
            logger.error(f"Error enabling PV typing: {e}")
            await send_message(event, get_message('error_occurred'))

    @client.on(events.NewMessage(pattern=get_command_pattern('pv_typing_off', lang['private'])))
    async def handle_pv_typing_off(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            settings['private_settings']['pv_typing_enabled'] = False
            await update_settings(db, settings)
            await send_message(event, get_message('pv_typing_disabled'), parse_mode='html')
        except Exception as e:
            logger.error(f"Error disabling PV typing: {e}")
            await send_message(event, get_message('error_occurred'))

    # عضویت اجباری
    @client.on(events.NewMessage(pattern=get_command_pattern('force_join_on', lang['private'])))
    async def handle_force_join_on(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            if not settings['private_settings']['force_join_chat_id']:
                await send_message(event, get_message('force_join_chat_not_set'), parse_mode='html')
                return
            try:
                await client(GetParticipantRequest(settings['private_settings']['force_join_chat_id'], '@SelfExpireBot'))
            except ChatAdminRequiredError:
                await send_message(event, get_message('bot_not_admin'), parse_mode='html')
                return
            settings['private_settings']['force_join_enabled'] = True
            await update_settings(db, settings)
            await send_message(event, get_message('force_join_enabled'), parse_mode='html')
        except Exception as e:
            logger.error(f"Error enabling force join: {e}")
            await send_message(event, get_message('error_occurred'))

    @client.on(events.NewMessage(pattern=get_command_pattern('force_join_off', lang['private'])))
    async def handle_force_join_off(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            settings['private_settings']['force_join_enabled'] = False
            await update_settings(db, settings)
            await send_message(event, get_message('force_join_disabled'), parse_mode='html')
        except Exception as e:
            logger.error(f"Error disabling force join: {e}")
            await send_message(event, get_message('error_occurred'))

    @client.on(events.NewMessage(pattern=get_command_pattern('set_force_join_chat', lang['private'])))
    async def handle_set_force_join_chat(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            settings['private_settings']['force_join_chat_id'] = event.chat_id
            await update_settings(db, settings)
            await send_message(event, get_message('force_join_chat_set'), parse_mode='html')
        except Exception as e:
            logger.error(f"Error setting force join chat: {e}")
            await send_message(event, get_message('error_occurred'))

    @client.on(events.NewMessage(pattern=get_command_pattern('set_force_join_message', lang['private'])))
    async def handle_set_force_join_message(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            if event.is_reply:
                reply_msg = await event.get_reply_message()
                settings['private_settings']['force_join_message'] = reply_msg.text
                await update_settings(db, settings)
                await send_message(event, get_message('force_join_message_set'), parse_mode='html')
            else:
                await send_message(event, get_message('reply_to_message'))
        except Exception as e:
            logger.error(f"Error setting force join message: {e}")
            await send_message(event, get_message('error_occurred'))

    @client.on(events.NewMessage(pattern=get_command_pattern('set_force_join_delay', lang['private'])))
    async def handle_set_force_join_delay(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            delay = int(event.pattern_match.group(1))
            settings['private_settings']['force_join_delay'] = delay
            await update_settings(db, settings)
            await send_message(event, get_message('force_join_delay_set', delay=delay), parse_mode='html')
        except Exception as e:
            logger.error(f"Error setting force join delay: {e}")
            await send_message(event, get_message('error_occurred'))

    @client.on(events.NewMessage(pattern=get_command_pattern('force_join_relax_on', lang['private'])))
    async def handle_force_join_relax_on(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            settings['private_settings']['force_join_relax_enabled'] = True
            await update_settings(db, settings)
            await send_message(event, get_message('force_join_relax_enabled'), parse_mode='html')
        except Exception as e:
            logger.error(f"Error enabling force join relax: {e}")
            await send_message(event, get_message('error_occurred'))

    @client.on(events.NewMessage(pattern=get_command_pattern('force_join_relax_off', lang['private'])))
    async def handle_force_join_relax_off(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            settings['private_settings']['force_join_relax_enabled'] = False
            await update_settings(db, settings)
            await send_message(event, get_message('force_join_relax_disabled'), parse_mode='html')
        except Exception as e:
            logger.error(f"Error disabling force join relax: {e}")
            await send_message(event, get_message('error_occurred'))

    @client.on(events.NewMessage(pattern=get_command_pattern('set_force_join_relax_delay', lang['private'])))
    async def handle_set_force_join_relax_delay(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            delay = int(event.pattern_match.group(1))
            settings['private_settings']['force_join_relax_delay'] = delay
            await update_settings(db, settings)
            await send_message(event, get_message('force_join_relax_delay_set', delay=delay), parse_mode='html')
        except Exception as e:
            logger.error(f"Error setting force join relax delay: {e}")
            await send_message(event, get_message('error_occurred'))

    @client.on(events.NewMessage(pattern=get_command_pattern('force_join_save_on', lang['private'])))
    async def handle_force_join_save_on(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            settings['private_settings']['force_join_save_enabled'] = True
            await update_settings(db, settings)
            await send_message(event, get_message('force_join_save_enabled'), parse_mode='html')
        except Exception as e:
            logger.error(f"Error enabling force join save: {e}")
            await send_message(event, get_message('error_occurred'))

    @client.on(events.NewMessage(pattern=get_command_pattern('force_join_save_off', lang['private'])))
    async def handle_force_join_save_off(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            settings['private_settings']['force_join_save_enabled'] = False
            await update_settings(db, settings)
            await send_message(event, get_message('force_join_save_disabled'), parse_mode='html')
        except Exception as e:
            logger.error(f"Error disabling force join save: {e}")
            await send_message(event, get_message('error_occurred'))

    @client.on(events.NewMessage(pattern=get_command_pattern('set_force_join_save_realm', lang['private'])))
    async def handle_set_force_join_save_realm(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            settings['private_settings']['force_join_save_chat_id'] = event.chat_id
            await update_settings(db, settings)
            await send_message(event, get_message('force_join_save_realm_set'), parse_mode='html')
        except Exception as e:
            logger.error(f"Error setting force join save realm: {e}")
            await send_message(event, get_message('error_occurred'))

    # محافظت از اسپم
    @client.on(events.NewMessage(pattern=get_command_pattern('protect_on', lang['private'])))
    async def handle_protect_on(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            settings['private_settings']['protect_enabled'] = True
            await update_settings(db, settings)
            await send_message(event, get_message('protect_enabled'), parse_mode='html')
        except Exception as e:
            logger.error(f"Error enabling protect: {e}")
            await send_message(event, get_message('error_occurred'))

    @client.on(events.NewMessage(pattern=get_command_pattern('protect_off', lang['private'])))
    async def handle_protect_off(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            settings['private_settings']['protect_enabled'] = False
            settings['private_settings']['message_counts'] = {}
            await update_settings(db, settings)
            await send_message(event, get_message('protect_disabled'), parse_mode='html')
        except Exception as e:
            logger.error(f"Error disabling protect: {e}")
            await send_message(event, get_message('error_occurred'))

    @client.on(events.NewMessage(pattern=get_command_pattern('set_protect_limit', lang['private'])))
    async def handle_set_protect_limit(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            limit = int(event.pattern_match.group(1))
            settings['private_settings']['protect_limit'] = limit
            await update_settings(db, settings)
            await send_message(event, get_message('protect_limit_set', limit=limit), parse_mode='html')
        except Exception as e:
            logger.error(f"Error setting protect limit: {e}")
            await send_message(event, get_message('error_occurred'))

    @client.on(events.NewMessage(pattern=get_command_pattern('set_protect_message', lang['private'])))
    async def handle_set_protect_message(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            if event.is_reply:
                reply_msg = await event.get_reply_message()
                settings['private_settings']['protect_message'] = reply_msg.text
                await update_settings(db, settings)
                await send_message(event, get_message('protect_message_set'), parse_mode='html')
            else:
                await send_message(event, get_message('reply_to_message'))
        except Exception as e:
            logger.error(f"Error setting protect message: {e}")
            await send_message(event, get_message('error_occurred'))

    @client.on(events.NewMessage(pattern=get_command_pattern('protect_warning_on', lang['private'])))
    async def handle_protect_warning_on(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            settings['private_settings']['protect_warning_enabled'] = True
            await update_settings(db, settings)
            await send_message(event, get_message('protect_warning_enabled'), parse_mode='html')
        except Exception as e:
            logger.error(f"Error enabling protect warning: {e}")
            await send_message(event, get_message('error_occurred'))

    @client.on(events.NewMessage(pattern=get_command_pattern('protect_warning_off', lang['private'])))
    async def handle_protect_warning_off(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            settings['private_settings']['protect_warning_enabled'] = False
            await update_settings(db, settings)
            await send_message(event, get_message('protect_warning_disabled'), parse_mode='html')
        except Exception as e:
            logger.error(f"Error disabling protect warning: {e}")
            await send_message(event, get_message('error_occurred'))

    @client.on(events.NewMessage(pattern=get_command_pattern('set_protect_warning_message', lang['private'])))
    async def handle_set_protect_warning_message(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            if event.is_reply:
                reply_msg = await event.get_reply_message()
                settings['private_settings']['protect_warning_message'] = reply_msg.text
                await update_settings(db, settings)
                await send_message(event, get_message('protect_warning_message_set'), parse_mode='html')
            else:
                await send_message(event, get_message('reply_to_message'))
        except Exception as e:
            logger.error(f"Error setting protect warning message: {e}")
            await send_message(event, get_message('error_occurred'))

    @client.on(events.NewMessage(pattern=get_command_pattern('protect_relax_on', lang['private'])))
    async def handle_protect_relax_on(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            settings['private_settings']['protect_relax_enabled'] = True
            await update_settings(db, settings)
            await send_message(event, get_message('protect_relax_enabled'), parse_mode='html')
        except Exception as e:
            logger.error(f"Error enabling protect relax: {e}")
            await send_message(event, get_message('error_occurred'))

    @client.on(events.NewMessage(pattern=get_command_pattern('protect_relax_off', lang['private'])))
    async def handle_protect_relax_off(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            settings['private_settings']['protect_relax_enabled'] = False
            await update_settings(db, settings)
            await send_message(event, get_message('protect_relax_disabled'), parse_mode='html')
        except Exception as e:
            logger.error(f"Error disabling protect relax: {e}")
            await send_message(event, get_message('error_occurred'))

    @client.on(events.NewMessage(pattern=get_command_pattern('set_protect_relax_delay', lang['private'])))
    async def handle_set_protect_relax_delay(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            delay = int(event.pattern_match.group(1))
            settings['private_settings']['protect_relax_delay'] = delay
            await update_settings(db, settings)
            await send_message(event, get_message('protect_relax_delay_set', delay=delay), parse_mode='html')
        except Exception as e:
            logger.error(f"Error setting protect relax delay: {e}")
            await send_message(event, get_message('error_occurred'))

    # فیلتر کردن پیوی
    @client.on(events.NewMessage(pattern=get_command_pattern('filter_pv', lang['private'])))
    async def handle_filter_pv(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            words = event.pattern_match.group(1).split('\n')
            for word in words:
                if word and word not in settings['private_settings']['filter_list']:
                    settings['private_settings']['filter_list'].append(word.strip())
            await update_settings(db, settings)
            await send_message(event, get_message('filter_added', count=len(words)), parse_mode='html')
        except Exception as e:
            logger.error(f"Error adding PV filter: {e}")
            await send_message(event, get_message('error_occurred'))

    @client.on(events.NewMessage(pattern=get_command_pattern('remove_filter_pv', lang['private'])))
    async def handle_remove_filter_pv(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            word = event.pattern_match.group(1)
            if word in settings['private_settings']['filter_list']:
                settings['private_settings']['filter_list'].remove(word)
                await update_settings(db, settings)
                await send_message(event, get_message('filter_removed', word=word), parse_mode='html')
            else:
                await send_message(event, get_message('filter_not_found'), parse_mode='html')
        except Exception as e:
            logger.error(f"Error removing PV filter: {e}")
            await send_message(event, get_message('error_occurred'))

    @client.on(events.NewMessage(pattern=get_command_pattern('list_filter_pv', lang['private'])))
    async def handle_list_filter_pv(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            filters = settings['private_settings']['filter_list']
            if filters:
                filter_text = "\n".join([f"{i+1}. {f}" for i, f in enumerate(filters)])
                await send_message(event, get_message('filter_list', filters=filter_text), parse_mode='html')
            else:
                await send_message(event, get_message('no_filters'), parse_mode='html')
        except Exception as e:
            logger.error(f"Error listing PV filters: {e}")
            await send_message(event, get_message('error_occurred'))

    @client.on(events.NewMessage(pattern=get_command_pattern('clear_filter_pv', lang['private'])))
    async def handle_clear_filter_pv(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            settings['private_settings']['filter_list'] = []
            await update_settings(db, settings)
            await send_message(event, get_message('filter_list_cleared'), parse_mode='html')
        except Exception as e:
            logger.error(f"Error clearing PV filter list: {e}")
            await send_message(event, get_message('error_occurred'))

    # نظارت بر پیام‌های ورودی
    @client.on(events.NewMessage(incoming=True, chats=[owner_id]))
    async def handle_owner_message(event):
        try:
            settings['private_settings']['last_owner_message'][event.chat_id] = datetime.now(pytz.UTC).timestamp()
            await update_settings(db, settings)
        except Exception as e:
            logger.error(f"Error handling owner message: {e}")

    @client.on(events.NewMessage(incoming=True))
    async def handle_incoming_message(event):
        try:
            if event.sender_id == owner_id:
                return
            if settings['private_settings']['pv_typing_enabled']:
                await client.send_chat_action(event.chat_id, 'typing')
            user_id = event.sender_id
            current_time = datetime.now(pytz.UTC).timestamp()

            # ذخیره پیام
            if settings['private_settings']['save_pv_enabled'] and settings['private_settings']['save_pv_chat_id']:
                await client.forward_messages(settings['private_settings']['save_pv_chat_id'], event.message)

            # منشی عادی
            if settings['private_settings']['secretary_enabled'] and settings['private_settings']['secretary_message']:
                last_message_time = settings['private_settings']['last_message_time'].get(user_id, 0)
                if current_time - last_message_time >= settings['private_settings']['secretary_delay']:
                    await send_message(event, settings['private_settings']['secretary_message'], parse_mode='html')
                    settings['private_settings']['last_message_time'][user_id] = current_time
                    await update_settings(db, settings)
                    await asyncio.sleep(1)

            # منشی هوشمند
            if settings['private_settings']['smart_secretary_enabled'] and settings['private_settings']['smart_secretary_message']:
                if user_id not in settings['private_settings']['last_message_time']:
                    await send_message(event, settings['private_settings']['smart_secretary_message'], parse_mode='html')
                    settings['private_settings']['last_message_time'][user_id] = current_time
                    await update_settings(db, settings)
                    await asyncio.sleep(1)

            # منشی آفلاین
            if settings['private_settings']['offline_secretary_enabled'] and settings['private_settings']['secretary_message']:
                last_seen = settings['private_settings']['offline_last_seen']
                if current_time - last_seen >= settings['private_settings']['offline_secretary_delay'] * 60:
                    await send_message(event, settings['private_settings']['secretary_message'], parse_mode='html')
                    settings['private_settings']['last_message_time'][user_id] = current_time
                    await update_settings(db, settings)
                    await asyncio.sleep(1)

            # حالت بلاک
            if settings['private_settings']['block_mode_enabled'] and user_id not in settings['private_settings']['last_message_time']:
                await client(functions.contacts.BlockRequest(user_id))
                await send_message(event, get_message('user_blocked'), parse_mode='html')
                await asyncio.sleep(1)

            # سکوت پیوی
            if settings['private_settings']['silence_pv_enabled']:
                await client.delete_messages(event.chat_id, [event.message.id])
                await asyncio.sleep(1)

            # سکوت خاص
            if settings['private_settings']['silence_specific_enabled'] and event.chat_id == event.sender_id:
                await client.delete_messages(event.chat_id, [event.message.id])
                await asyncio.sleep(1)

            # عضویت اجباری
            if settings['private_settings']['force_join_enabled'] and settings['private_settings']['force_join_chat_id']:
                last_message_time = settings['private_settings']['last_message_time'].get(user_id, 0)
                last_owner_message = settings['private_settings']['last_owner_message'].get(user_id, 0)
                if settings['private_settings']['force_join_relax_enabled'] and (current_time - last_owner_message) < (settings['private_settings']['force_join_relax_delay'] * 60):
                    return
                if current_time - last_message_time >= settings['private_settings']['force_join_delay']:
                    try:
                        await client(GetParticipantRequest(settings['private_settings']['force_join_chat_id'], user_id))
                    except ValueError:
                        if settings['private_settings']['force_join_save_enabled'] and settings['private_settings']['force_join_save_chat_id']:
                            await client.forward_messages(settings['private_settings']['force_join_save_chat_id'], event.message)
                        await client.delete_messages(event.chat_id, [event.message.id])
                        await send_message(event, settings['private_settings']['force_join_message'] or get_message('force_join_message'), parse_mode='html')
                        settings['private_settings']['last_message_time'][user_id] = current_time
                        await update_settings(db, settings)
                        await asyncio.sleep(1)

            # محافظت از اسپم
            if settings['private_settings']['protect_enabled']:
                settings['private_settings']['message_counts'][user_id] = settings['private_settings']['message_counts'].get(user_id, 0) + 1
                last_owner_message = settings['private_settings']['last_owner_message'].get(user_id, 0)
                if settings['private_settings']['protect_relax_enabled'] and (current_time - last_owner_message) < (settings['private_settings']['protect_relax_delay'] * 60):
                    settings['private_settings']['message_counts'][user_id] = 0
                if settings['private_settings']['message_counts'][user_id] > settings['private_settings']['protect_limit']:
                    if settings['private_settings']['protect_message']:
                        await send_message(event, settings['private_settings']['protect_message'], parse_mode='html')
                    await client(functions.contacts.BlockRequest(user_id))
                    settings['private_settings']['message_counts'][user_id] = 0
                    await update_settings(db, settings)
                    await asyncio.sleep(1)
                elif settings['private_settings']['protect_warning_enabled'] and settings['private_settings']['protect_warning_message']:
                    remaining = settings['private_settings']['protect_limit'] - settings['private_settings']['message_counts'][user_id]
                    if remaining > 0:
                        await send_message(event, settings['private_settings']['protect_warning_message'].format(WARNS=remaining), parse_mode='html')
                        await asyncio.sleep(1)
                await update_settings(db, settings)

            # فیلتر کردن
            if settings['private_settings']['filter_list'] and event.message.text:
                for word in settings['private_settings']['filter_list']:
                    if word.lower() in event.message.text.lower():
                        await client.delete_messages(event.chat_id, [event.message.id])
                        break

            # ذخیره پیام‌های زمان‌دار
            if settings['private_settings']['save_timed_enabled'] and (event.message.photo or event.message.video) and event.message.ttl_period:
                if settings['private_settings']['save_timed_chat_id'] and settings['private_settings']['backup_channel_id'] and settings['private_settings']['bot_token']:
                    await client.forward_messages(settings['private_settings']['save_timed_chat_id'], event.message)
                    await asyncio.sleep(1)

        except Exception as e:
            logger.error(f"Error handling incoming message: {e}")

    # نظارت بر پیام‌های حذف‌شده
    @client.on(events.MessageDeleted)
    async def handle_deleted_message(event):
        try:
            if settings['private_settings']['save_deleted_enabled'] and settings['private_settings']['save_deleted_chat_id'] and settings['private_settings']['backup_channel_id'] and settings['private_settings']['bot_token']:
                async for message in client.iter_messages(event.chat_id, ids=event.deleted_ids):
                    await client.forward_messages(settings['private_settings']['save_deleted_chat_id'], message)
                    await asyncio.sleep(1)
        except Exception as e:
            logger.error(f"Error handling deleted message: {e}")

    # نظارت بر پیام‌های ویرایش‌شده
    @client.on(events.MessageEdited)
    async def handle_edited_message(event):
        try:
            if settings['private_settings']['save_edited_enabled'] and settings['private_settings']['save_edited_chat_id'] and settings['private_settings']['backup_channel_id'] and settings['private_settings']['bot_token']:
                await client.forward_messages(settings['private_settings']['save_edited_chat_id'], event.message)
                await asyncio.sleep(1)
        except Exception as e:
            logger.error(f"Error handling edited message: {e}")

    # بررسی تبریک تولد
    async def check_birthdays():
        while True:
            try:
                if settings['private_settings']['birthday_enabled']:
                    current_date = datetime.now(pytz.UTC).strftime('%Y/%m/%d')
                    for user_id, data in settings['private_settings']['birthday_users'].items():
                        if data['date'] == current_date:
                            await client.send_message(user_id, data['message'], parse_mode='html')
                            await asyncio.sleep(1)
            except Exception as e:
                logger.error(f"Error checking birthdays: {e}")
            await asyncio.sleep(86400)  # بررسی روزانه

    # شروع بررسی تولد
    client.loop.create_task(check_birthdays())

    await db.close()