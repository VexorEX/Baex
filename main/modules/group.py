import asyncio,logging,pytz
from datetime import datetime
from telethon import events
from telethon.tl.functions.channels import CreateChannelRequest, InviteToChannelRequest, EditBannedRequest, EditPhotoRequest, EditTitleRequest, LeaveChannelRequest, GetParticipantRequest, EditAdminRequest
from telethon.tl.functions.messages import UpdatePinnedMessageRequest, DeleteMessagesRequest, GetMessagesRequest
from telethon.tl.types import ChannelParticipantsAdmins, ChannelParticipantsRecent, ChannelParticipantsBots, ChannelParticipantCreator, InputPeerChannel
from telethon.tl.functions.users import GetFullUserRequest
from telethon.errors import UsernameOccupiedError, FloodWaitError, ChannelPrivateError, UserPrivacyRestrictedError
from deep_translator import GoogleTranslator
from utils import load_json, send_message, get_command_pattern
from models import get_database, load_settings, update_settings

logger = logging.getLogger(__name__)

async def register_group_handlers(client, session_name, owner_id):
    db = await get_database(session_name)
    settings = await load_settings(db)
    if not settings:
        logger.error("Failed to load settings for group handlers")
        await db.close()
        return

    lang = settings.get('lang', 'fa')
    messages = load_json('msg.json')
    commands = load_json('cmd.json')

    def get_message(key, **kwargs):
        return messages[lang]['group'].get(key, '').format(**kwargs)

    # تنظیمات اولیه group
    if 'group_settings' not in settings:
        settings['group_settings'] = {
            'lock_photo': False,
            'lock_title': False,
            'locked_title': None,
            'auto_leave': False,
            'silence_mode': False,
            'silence_all': False,
            'silence_duration': 0,
            'filter_list': [],
            'allow_list': [],
            'welcome_enabled': False,
            'welcome_message': None,
            'ban_all_enabled': False,
            'ban_all_list': [],
            'mute_list': [],
            'slow_mode_duration': 0,
            'join_mode': False,
            'join_mode_type': 'ban',  # یا 'mute'
            'typing_group': False,
            'join_time': {},  # {user_id: join_time}
            'owner_info': None,
            'nickname_list': {}  # {user_id: nickname}
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

    # قفل عکس گروه
    @client.on(events.NewMessage(pattern=get_command_pattern('lock_chat_photo_on', lang['group'])))
    async def handle_lock_chat_photo_on(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            if not event.is_group or not event.chat.megagroup:
                await send_message(event, get_message('not_supergroup'))
                return
            settings['group_settings']['lock_photo'] = True
            await update_settings(db, settings)
            await send_message(event, get_message('lock_photo_enabled'), parse_mode='html')
        except Exception as e:
            logger.error(f"Error locking chat photo: {e}")
            await send_message(event, get_message('error_occurred'))

    @client.on(events.NewMessage(pattern=get_command_pattern('lock_chat_photo_off', lang['group'])))
    async def handle_lock_chat_photo_off(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            settings['group_settings']['lock_photo'] = False
            await update_settings(db, settings)
            await send_message(event, get_message('lock_photo_disabled'), parse_mode='html')
        except Exception as e:
            logger.error(f"Error unlocking chat photo: {e}")
            await send_message(event, get_message('error_occurred'))

    # نظارت بر تغییر عکس گروه
    @client.on(events.ChatAction)
    async def handle_photo_change(event):
        try:
            if settings['group_settings']['lock_photo'] and event.photo_changed and event.user_id != owner_id:
                # فرض: بازگرداندن عکس قبلی امکان‌پذیر نیست، بنابراین اطلاع‌رسانی می‌کنیم
                await send_message(event, get_message('photo_change_restricted'), parse_mode='html')
        except Exception as e:
            logger.error(f"Error handling photo change: {e}")

    # قفل عنوان گروه
    @client.on(events.NewMessage(pattern=get_command_pattern('lock_title_on', lang['group'])))
    async def handle_lock_title_on(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            if not event.is_group or not event.chat.megagroup:
                await send_message(event, get_message('not_supergroup'))
                return
            settings['group_settings']['lock_title'] = True
            settings['group_settings']['locked_title'] = (await client.get_entity(event.chat_id)).title
            await update_settings(db, settings)
            await send_message(event, get_message('lock_title_enabled'), parse_mode='html')
        except Exception as e:
            logger.error(f"Error locking title: {e}")
            await send_message(event, get_message('error_occurred'))

    @client.on(events.NewMessage(pattern=get_command_pattern('lock_title_off', lang['group'])))
    async def handle_lock_title_off(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            settings['group_settings']['lock_title'] = False
            settings['group_settings']['locked_title'] = None
            await update_settings(db, settings)
            await send_message(event, get_message('lock_title_disabled'), parse_mode='html')
        except Exception as e:
            logger.error(f"Error unlocking title: {e}")
            await send_message(event, get_message('error_occurred'))

    # نظارت بر تغییر عنوان گروه
    @client.on(events.ChatAction)
    async def handle_title_change(event):
        try:
            if settings['group_settings']['lock_title'] and event.title_changed and event.user_id != owner_id:
                await client(EditTitleRequest(event.chat_id, settings['group_settings']['locked_title']))
                await send_message(event, get_message('title_reverted'), parse_mode='html')
        except Exception as e:
            logger.error(f"Error handling title change: {e}")

    # خروج خودکار
    @client.on(events.NewMessage(pattern=get_command_pattern('auto_leave_on', lang['group'])))
    async def handle_auto_leave_on(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            settings['group_settings']['auto_leave'] = True
            await update_settings(db, settings)
            await send_message(event, get_message('auto_leave_enabled'), parse_mode='html')
        except Exception as e:
            logger.error(f"Error enabling auto leave: {e}")
            await send_message(event, get_message('error_occurred'))

    @client.on(events.NewMessage(pattern=get_command_pattern('auto_leave_off', lang['group'])))
    async def handle_auto_leave_off(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            settings['group_settings']['auto_leave'] = False
            await update_settings(db, settings)
            await send_message(event, get_message('auto_leave_disabled'), parse_mode='html')
        except Exception as e:
            logger.error(f"Error disabling auto leave: {e}")
            await send_message(event, get_message('error_occurred'))

    # نظارت بر عضویت جدید
    @client.on(events.ChatAction)
    async def handle_new_member(event):
        try:
            if settings['group_settings']['auto_leave'] and event.user_id == owner_id:
                await client(LeaveChannelRequest(event.chat_id))
                await send_message(event, get_message('auto_left_group'), parse_mode='html')
            elif settings['group_settings']['welcome_enabled'] and event.user_added:
                user = await client.get_entity(event.user_id)
                await send_message(event, settings['group_settings']['welcome_message'].format(user=user.first_name), parse_mode='html')
            elif settings['group_settings']['join_mode'] and event.user_added:
                if settings['group_settings']['join_mode_type'] == 'ban':
                    await client(EditBannedRequest(event.chat_id, event.user_id, banned_rights=ChannelParticipantBanned(until_date=None)))
                    await send_message(event, get_message('new_member_banned', user_id=event.user_id), parse_mode='html')
                elif settings['group_settings']['join_mode_type'] == 'mute':
                    await client(EditBannedRequest(event.chat_id, event.user_id, banned_rights=ChannelParticipantBanned(until_date=None, send_messages=False)))
                    await send_message(event, get_message('new_member_muted', user_id=event.user_id), parse_mode='html')
            if event.user_added:
                settings['group_settings']['join_time'][event.user_id] = datetime.now(pytz.UTC).timestamp()
                await update_settings(db, settings)
        except Exception as e:
            logger.error(f"Error handling new member: {e}")

    # سکوت گروه
    @client.on(events.NewMessage(pattern=get_command_pattern('silence_on', lang['group'])))
    async def handle_silence_on(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            settings['group_settings']['silence_mode'] = True
            await update_settings(db, settings)
            await send_message(event, get_message('silence_enabled'), parse_mode='html')
        except Exception as e:
            logger.error(f"Error enabling silence: {e}")
            await send_message(event, get_message('error_occurred'))

    @client.on(events.NewMessage(pattern=get_command_pattern('silence_off', lang['group'])))
    async def handle_silence_off(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            settings['group_settings']['silence_mode'] = False
            await update_settings(db, settings)
            await send_message(event, get_message('silence_disabled'), parse_mode='html')
        except Exception as e:
            logger.error(f"Error disabling silence: {e}")
            await send_message(event, get_message('error_occurred'))

    # نظارت بر پیام‌ها در حالت سکوت
    @client.on(events.NewMessage)
    async def handle_silence_messages(event):
        try:
            if settings['group_settings']['silence_mode'] and event.sender_id != owner_id and event.is_group:
                await client.delete_messages(event.chat_id, [event.message.id])
            elif settings['group_settings']['silence_all'] and event.is_group:
                if (datetime.now(pytz.UTC).timestamp() > settings['group_settings']['silence_duration']):
                    settings['group_settings']['silence_all'] = False
                    await update_settings(db, settings)
                else:
                    await client.delete_messages(event.chat_id, [event.message.id])
            elif settings['group_settings']['filter_list'] and event.message.text:
                for word in settings['group_settings']['filter_list']:
                    if word.lower() in event.message.text.lower():
                        await client.delete_messages(event.chat_id, [event.message.id])
                        break
            elif settings['group_settings']['allow_list'] and event.message.text:
                allowed = False
                for word in settings['group_settings']['allow_list']:
                    if word.lower() in event.message.text.lower():
                        allowed = True
                        break
                if not allowed:
                    await client.delete_messages(event.chat_id, [event.message.id])
            elif settings['group_settings']['ban_all_enabled'] and event.sender_id in settings['group_settings']['ban_all_list']:
                try:
                    await client(EditBannedRequest(event.chat_id, event.sender_id, banned_rights=ChannelParticipantBanned(until_date=None)))
                except:
                    await client.delete_messages(event.chat_id, [event.message.id])
        except Exception as e:
            logger.error(f"Error handling silence messages: {e}")

    # سکوت همگانی
    @client.on(events.NewMessage(pattern=get_command_pattern('silence_all', lang['group'])))
    async def handle_silence_all(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            duration = int(event.pattern_match.group(1)) if event.pattern_match.group(1) else 0
            settings['group_settings']['silence_all'] = True
            settings['group_settings']['silence_duration'] = datetime.now(pytz.UTC).timestamp() + duration
            await update_settings(db, settings)
            await send_message(event, get_message('silence_all_enabled', duration=duration), parse_mode='html')
        except Exception as e:
            logger.error(f"Error enabling silence all: {e}")
            await send_message(event, get_message('error_occurred'))

    @client.on(events.NewMessage(pattern=get_command_pattern('cancel_silence_all', lang['group'])))
    async def handle_cancel_silence_all(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            settings['group_settings']['silence_all'] = False
            settings['group_settings']['silence_duration'] = 0
            await update_settings(db, settings)
            await send_message(event, get_message('silence_all_disabled'), parse_mode='html')
        except Exception as e:
            logger.error(f"Error disabling silence all: {e}")
            await send_message(event, get_message('error_occurred'))

    # تگ اعضا
    @client.on(events.NewMessage(pattern=get_command_pattern('tag', lang['group'])))
    async def handle_tag_members(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            text = event.pattern_match.group(1) or ''
            members = []
            async for user in client.iter_participants(event.chat_id, limit=200):
                if user.username:
                    members.append(f"@{user.username}")
                else:
                    members.append(f"[{user.first_name}](tg://user?id={user.id})")
            chunk_size = 20
            for i in range(0, len(members), chunk_size):
                chunk = members[i:i + chunk_size]
                chunk_text = text + " " + " ".join(chunk)
                await send_message(event, chunk_text, parse_mode='markdown')
                await asyncio.sleep(1)  # جلوگیری از Flood
            await send_message(event, get_message('members_tagged', count=len(members)), parse_mode='html')
        except Exception as e:
            logger.error(f"Error tagging members: {e}")
            await send_message(event, get_message('error_occurred'))

    @client.on(events.NewMessage(pattern=get_command_pattern('cancel_tag', lang['group'])))
    async def handle_cancel_tag(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            await send_message(event, get_message('tag_cancelled'), parse_mode='html')
        except Exception as e:
            logger.error(f"Error cancelling tag: {e}")
            await send_message(event, get_message('error_occurred'))

    # تگ مدیران
    @client.on(events.NewMessage(pattern=get_command_pattern('tag_admins', lang['group'])))
    async def handle_tag_admins(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            admins = []
            async for user in client.iter_participants(event.chat_id, filter=ChannelParticipantsAdmins):
                if user.username:
                    admins.append(f"@{user.username}")
                else:
                    admins.append(f"[{user.first_name}](tg://user?id={user.id})")
            chunk_size = 20
            for i in range(0, len(admins), chunk_size):
                chunk = admins[i:i + chunk_size]
                await send_message(event, " ".join(chunk), parse_mode='markdown')
                await asyncio.sleep(1)
            await send_message(event, get_message('admins_tagged', count=len(admins)), parse_mode='html')
        except Exception as e:
            logger.error(f"Error tagging admins: {e}")
            await send_message(event, get_message('error_occurred'))

    # تگ ربات‌ها
    @client.on(events.NewMessage(pattern=get_command_pattern('tag_bots', lang['group'])))
    async def handle_tag_bots(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            bots = []
            async for user in client.iter_participants(event.chat_id, filter=ChannelParticipantsBots):
                if user.username:
                    bots.append(f"@{user.username}")
                else:
                    bots.append(f"[{user.first_name}](tg://user?id={user.id})")
            chunk_size = 20
            for i in range(0, len(bots), chunk_size):
                chunk = bots[i:i + chunk_size]
                await send_message(event, " ".join(chunk), parse_mode='markdown')
                await asyncio.sleep(1)
            await send_message(event, get_message('bots_tagged', count=len(bots)), parse_mode='html')
        except Exception as e:
            logger.error(f"Error tagging bots: {e}")
            await send_message(event, get_message('error_occurred'))

    # دعوت به گروه
    @client.on(events.NewMessage(pattern=get_command_pattern('invite', lang['group'])))
    async def handle_invite(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            if event.is_reply:
                reply_msg = await event.get_reply_message()
                user = await client.get_entity(reply_msg.sender_id)
                await client(InviteToChannelRequest(event.chat_id, [user.id]))
                await send_message(event, get_message('user_invited', user=user.first_name), parse_mode='html')
            else:
                usernames = event.pattern_match.group(1).split(',')
                for username in usernames:
                    user = await client.get_entity(username.strip())
                    await client(InviteToChannelRequest(event.chat_id, [user.id]))
                    await send_message(event, get_message('user_invited', user=user.first_name), parse_mode='html')
                    await asyncio.sleep(1)
        except UserPrivacyRestrictedError:
            await send_message(event, get_message('user_privacy_restricted'), parse_mode='html')
        except Exception as e:
            logger.error(f"Error inviting user: {e}")
            await send_message(event, get_message('error_occurred'))

    # افزودن ربات‌ها
    @client.on(events.NewMessage(pattern=get_command_pattern('add_bots', lang['group'])))
    async def handle_add_bots(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            bot_list = ['@BotFather', '@userinfobot', '@MissRose_bot']  # لیست ربات‌های پیش‌فرض
            added_count = 0
            for bot_username in bot_list:
                try:
                    bot = await client.get_entity(bot_username)
                    await client(InviteToChannelRequest(event.chat_id, [bot.id]))
                    added_count += 1
                    await asyncio.sleep(1)
                except:
                    continue
            await send_message(event, get_message('bots_added', count=added_count), parse_mode='html')
        except Exception as e:
            logger.error(f"Error adding bots: {e}")
            await send_message(event, get_message('error_occurred'))

    # سنجاق پیام
    @client.on(events.NewMessage(pattern=get_command_pattern('pin', lang['group'])))
    async def handle_pin_message(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            if event.is_reply:
                reply_msg = await event.get_reply_message()
                from telethon.tl.functions.messages import UpdatePinnedMessageRequest, DeleteMessagesRequest, GetMessagesRequest
                await send_message(event, get_message('message_pinned'), parse_mode='html')
            else:
                await send_message(event, get_message('reply_to_message'))
        except Exception as e:
            logger.error(f"Error pinning message: {e}")
            await send_message(event, get_message('error_occurred'))

    @client.on(events.NewMessage(pattern=get_command_pattern('unpin', lang['group'])))
    async def handle_unpin_message(event):
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

    @client.on(events.NewMessage(pattern=get_command_pattern('repin', lang['group'])))
    async def handle_repin_message(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            if event.is_reply:
                reply_msg = await event.get_reply_message()
                from telethon.tl.functions.messages import UpdatePinnedMessageRequest, DeleteMessagesRequest, GetMessagesRequest
                await send_message(event, get_message('message_repinned'), parse_mode='html')
            else:
                await send_message(event, get_message('reply_to_message'))
        except Exception as e:
            logger.error(f"Error repinning message: {e}")
            await send_message(event, get_message('error_occurred'))

    @client.on(events.NewMessage(pattern=get_command_pattern('unpin_all', lang['group'])))
    async def handle_unpin_all(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            await client(UnpinMessageRequest(event.chat_id, None))
            await send_message(event, get_message('all_pins_unpinned'), parse_mode='html')
        except Exception as e:
            logger.error(f"Error unpinning all messages: {e}")
            await send_message(event, get_message('error_occurred'))

    # درباره گروه
    @client.on(events.NewMessage(pattern=get_command_pattern('group_info', lang['group'])))
    async def handle_group_info(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            entity = await client.get_entity(event.chat_id)
            info = f"عنوان: {entity.title}\nID: {entity.id}\nنام کاربری: @{entity.username or 'N/A'}\nتعداد اعضا: {entity.participants_count or 'N/A'}"
            await send_message(event, get_message('group_info', info=info), parse_mode='html')
        except Exception as e:
            logger.error(f"Error getting group info: {e}")
            await send_message(event, get_message('error_occurred'))

    # شناسه گروه
    @client.on(events.NewMessage(pattern=get_command_pattern('group_id', lang['group'])))
    async def handle_group_id(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            await send_message(event, get_message('group_id', id=event.chat_id), parse_mode='html')
        except Exception as e:
            logger.error(f"Error getting group ID: {e}")
            await send_message(event, get_message('error_occurred'))

    # خروج از گروه
    @client.on(events.NewMessage(pattern=get_command_pattern('leave', lang['group'])))
    async def handle_leave_group(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            chat_id = int(event.pattern_match.group(1)) if event.pattern_match.group(1) else event.chat_id
            await client(LeaveChannelRequest(chat_id))
            await send_message(event, get_message('left_group'), parse_mode='html')
        except Exception as e:
            logger.error(f"Error leaving group: {e}")
            await send_message(event, get_message('error_occurred'))

    # لینک گروه
    @client.on(events.NewMessage(pattern=get_command_pattern('group_link', lang['group'])))
    async def handle_group_link(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            entity = await client.get_entity(event.chat_id)
            link = f"https://t.me/{entity.username}" if entity.username else "گروه خصوصی است"
            await send_message(event, get_message('group_link', link=link), parse_mode='html')
        except Exception as e:
            logger.error(f"Error getting group link: {e}")
            await send_message(event, get_message('error_occurred'))

    # تنظیم لقب
    @client.on(events.NewMessage(pattern=get_command_pattern('set_nickname', lang['group'])))
    async def handle_set_nickname(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            if event.is_reply:
                reply_msg = await event.get_reply_message()
                user = await client.get_entity(reply_msg.sender_id)
                nickname = event.pattern_match.group(1)
                settings['group_settings']['nickname_list'][user.id] = nickname
                await update_settings(db, settings)
                await client(EditAdminRequest(event.chat_id, user.id, title=nickname))
                await send_message(event, get_message('nickname_set', user=user.first_name, nickname=nickname), parse_mode='html')
            else:
                await send_message(event, get_message('reply_to_user'))
        except Exception as e:
            logger.error(f"Error setting nickname: {e}")
            await send_message(event, get_message('error_occurred'))

    # لفت از همه گروه‌ها
    @client.on(events.NewMessage(pattern=get_command_pattern('leave_all_groups', lang['group'])))
    async def handle_leave_all_groups(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            left_count = 0
            async for dialog in client.iter_dialogs():
                if dialog.is_group or (dialog.is_channel and dialog.entity.megagroup):
                    await client(LeaveChannelRequest(dialog.entity.id))
                    left_count += 1
                    await asyncio.sleep(1)  # جلوگیری از Flood
            await send_message(event, get_message('left_all_groups', count=left_count), parse_mode='html')
        except Exception as e:
            logger.error(f"Error leaving all groups: {e}")
            await send_message(event, get_message('error_occurred'))

    # دریافت زمان عضویت
    @client.on(events.NewMessage(pattern=get_command_pattern('get_join_time', lang['group'])))
    async def handle_get_join_time(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            if event.is_reply:
                reply_msg = await event.get_reply_message()
                user = await client.get_entity(reply_msg.sender_id)
                join_time = settings['group_settings']['join_time'].get(user.id, 'N/A')
                if join_time != 'N/A':
                    join_time = datetime.fromtimestamp(join_time, tz=pytz.UTC).strftime('%Y/%m/%d %H:%M:%S')
                await send_message(event, get_message('join_time', user=user.first_name, time=join_time), parse_mode='html')
            else:
                await send_message(event, get_message('reply_to_user'))
        except Exception as e:
            logger.error(f"Error getting join time: {e}")
            await send_message(event, get_message('error_occurred'))

    # دریافت مالک گروه
    @client.on(events.NewMessage(pattern=get_command_pattern('get_owner', lang['group'])))
    async def handle_get_owner(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            chat_id = int(event.pattern_match.group(1)) if event.pattern_match.group(1) else event.chat_id
            async for participant in client.iter_participants(chat_id, filter=ChannelParticipantCreator):
                user = await client.get_entity(participant.user_id)
                owner_info = f"نام: {user.first_name}\nنام کاربری: @{user.username or 'N/A'}\nID: {user.id}"
                await send_message(event, get_message('owner_info', info=owner_info), parse_mode='html')
                break
        except Exception as e:
            logger.error(f"Error getting owner: {e}")
            await send_message(event, get_message('error_occurred'))

    # تایپینگ گروه
    @client.on(events.NewMessage(pattern=get_command_pattern('group_typing_on', lang['group'])))
    async def handle_group_typing_on(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            settings['group_settings']['typing_group'] = True
            await update_settings(db, settings)
            await send_message(event, get_message('group_typing_enabled'), parse_mode='html')
        except Exception as e:
            logger.error(f"Error enabling group typing: {e}")
            await send_message(event, get_message('error_occurred'))

    @client.on(events.NewMessage(pattern=get_command_pattern('group_typing_off', lang['group'])))
    async def handle_group_typing_off(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            settings['group_settings']['typing_group'] = False
            await update_settings(db, settings)
            await send_message(event, get_message('group_typing_disabled'), parse_mode='html')
        except Exception as e:
            logger.error(f"Error disabling group typing: {e}")
            await send_message(event, get_message('error_occurred'))

    # ساخت گروه
    @client.on(events.NewMessage(pattern=get_command_pattern('create_group', lang['group'])))
    async def handle_create_group(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            title = event.pattern_match.group(1)
            if not title:
                await send_message(event, get_message('missing_group_title'), parse_mode='html')
                return
            group_id = await client(CreateChannelRequest(title=title, about='', megagroup=True)).chats[0].id
            await send_message(event, get_message('group_created', title=title, id=group_id), parse_mode='html')
        except UsernameOccupiedError:
            await send_message(event, get_message('group_title_taken'), parse_mode='html')
        except Exception as e:
            logger.error(f"Error creating group: {e}")
            await send_message(event, get_message('error_occurred'))

    # پاکسازی پیام‌ها
    @client.on(events.NewMessage(pattern=get_command_pattern('cleanup_messages', lang['group'])))
    async def handle_cleanup_messages(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            count = int(event.pattern_match.group(1)) if event.pattern_match.group(1) else 100
            message_ids = []
            async for message in client.iter_messages(event.chat_id, limit=count):
                message_ids.append(message.id)
            await client.delete_messages(event.chat_id, message_ids)
            await send_message(event, get_message('messages_cleaned', count=len(message_ids)), parse_mode='html')
        except Exception as e:
            logger.error(f"Error cleaning messages: {e}")
            await send_message(event, get_message('error_occurred'))

    @client.on(events.NewMessage(pattern=get_command_pattern('cleanup_gifs', lang['group'])))
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

    @client.on(events.NewMessage(pattern=get_command_pattern('cleanup_photos', lang['group'])))
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

    @client.on(events.NewMessage(pattern=get_command_pattern('cleanup_videos', lang['group'])))
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

    @client.on(events.NewMessage(pattern=get_command_pattern('cleanup_audios', lang['group'])))
    async def handle_cleanup_audios(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            message_ids = []
            async for message in client.iter_messages(event.chat_id, limit=100):
                if message.audio:
                    message_ids.append(message.id)
            await client.delete_messages(event.chat_id, message_ids)
            await send_message(event, get_message('audios_cleaned', count=len(message_ids)), parse_mode='html')
        except Exception as e:
            logger.error(f"Error cleaning audios: {e}")
            await send_message(event, get_message('error_occurred'))

    @client.on(events.NewMessage(pattern=get_command_pattern('cleanup_voices', lang['group'])))
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

    @client.on(events.NewMessage(pattern=get_command_pattern('cleanup_user', lang['group'])))
    async def handle_cleanup_user(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            if event.is_reply:
                reply_msg = await event.get_reply_message()
                user = await client.get_entity(reply_msg.sender_id)
                message_ids = []
                async for message in client.iter_messages(event.chat_id, from_user=user.id, limit=100):
                    message_ids.append(message.id)
                await client.delete_messages(event.chat_id, message_ids)
                await send_message(event, get_message('user_messages_cleaned', user=user.first_name, count=len(message_ids)), parse_mode='html')
            else:
                await send_message(event, get_message('reply_to_user'))
        except Exception as e:
            logger.error(f"Error cleaning user messages: {e}")
            await send_message(event, get_message('error_occurred'))

    @client.on(events.NewMessage(pattern=get_command_pattern('cleanup_block_list', lang['group'])))
    async def handle_cleanup_block_list(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            settings['group_settings']['ban_all_list'] = []
            await update_settings(db, settings)
            await send_message(event, get_message('block_list_cleaned'), parse_mode='html')
        except Exception as e:
            logger.error(f"Error cleaning block list: {e}")
            await send_message(event, get_message('error_occurred'))

    @client.on(events.NewMessage(pattern=get_command_pattern('cleanup_deleted_accounts', lang['group'])))
    async def handle_cleanup_deleted_accounts(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            deleted_count = 0
            async for user in client.iter_participants(event.chat_id):
                if user.deleted:
                    await client(EditBannedRequest(event.chat_id, user.id, banned_rights=ChannelParticipantBanned(until_date=None)))
                    deleted_count += 1
                    await asyncio.sleep(1)
            await send_message(event, get_message('deleted_accounts_cleaned', count=deleted_count), parse_mode='html')
        except Exception as e:
            logger.error(f"Error cleaning deleted accounts: {e}")
            await send_message(event, get_message('error_occurred'))

    @client.on(events.NewMessage(pattern=get_command_pattern('cleanup_bots', lang['group'])))
    async def handle_cleanup_bots(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            bot_count = 0
            async for user in client.iter_participants(event.chat_id, filter=ChannelParticipantsBots):
                await client(EditBannedRequest(event.chat_id, user.id, banned_rights=ChannelParticipantBanned(until_date=None)))
                bot_count += 1
                await asyncio.sleep(1)
            await send_message(event, get_message('bots_cleaned', count=bot_count), parse_mode='html')
        except Exception as e:
            logger.error(f"Error cleaning bots: {e}")
            await send_message(event, get_message('error_occurred'))

    @client.on(events.NewMessage(pattern=get_command_pattern('cleanup_members', lang['group'])))
    async def handle_cleanup_members(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            member_count = 0
            async for user in client.iter_participants(event.chat_id, filter=ChannelParticipantsRecent):
                if user.id != owner_id:
                    await client(EditBannedRequest(event.chat_id, user.id, banned_rights=ChannelParticipantBanned(until_date=None)))
                    member_count += 1
                    await asyncio.sleep(1)
            await send_message(event, get_message('members_cleaned', count=member_count), parse_mode='html')
        except Exception as e:
            logger.error(f"Error cleaning members: {e}")
            await send_message(event, get_message('error_occurred'))

    @client.on(events.NewMessage(pattern=get_command_pattern('cleanup_all', lang['group'])))
    async def handle_cleanup_all(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            keyword = event.pattern_match.group(1)
            message_ids = []
            async for message in client.iter_messages(event.chat_id, limit=100):
                if message.text and keyword.lower() in message.text.lower():
                    message_ids.append(message.id)
            await client.delete_messages(event.chat_id, message_ids)
            await send_message(event, get_message('messages_cleaned_by_keyword', keyword=keyword, count=len(message_ids)), parse_mode='html')
        except Exception as e:
            logger.error(f"Error cleaning messages by keyword: {e}")
            await send_message(event, get_message('error_occurred'))

    @client.on(events.NewMessage(pattern=get_command_pattern('cleanup_between', lang['group'])))
    async def handle_cleanup_between(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            start_url, end_url = event.pattern_match.group(1).split()
            start_id = int(start_url.split('/')[-1])
            end_id = int(end_url.split('/')[-1])
            message_ids = list(range(min(start_id, end_id), max(start_id, end_id) + 1))
            await client.delete_messages(event.chat_id, message_ids)
            await send_message(event, get_message('messages_cleaned_between', count=len(message_ids)), parse_mode='html')
        except Exception as e:
            logger.error(f"Error cleaning messages between: {e}")
            await send_message(event, get_message('error_occurred'))

    # حالت عضویت
    @client.on(events.NewMessage(pattern=get_command_pattern('join_mode_on', lang['group'])))
    async def handle_join_mode_on(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            settings['group_settings']['join_mode'] = True
            await update_settings(db, settings)
            await send_message(event, get_message('join_mode_enabled'), parse_mode='html')
        except Exception as e:
            logger.error(f"Error enabling join mode: {e}")
            await send_message(event, get_message('error_occurred'))

    @client.on(events.NewMessage(pattern=get_command_pattern('join_mode_off', lang['group'])))
    async def handle_join_mode_off(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            settings['group_settings']['join_mode'] = False
            await update_settings(db, settings)
            await send_message(event, get_message('join_mode_disabled'), parse_mode='html')
        except Exception as e:
            logger.error(f"Error disabling join mode: {e}")
            await send_message(event, get_message('error_occurred'))

    @client.on(events.NewMessage(pattern=get_command_pattern('join_mode_ban', lang['group'])))
    async def handle_join_mode_ban(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            settings['group_settings']['join_mode_type'] = 'ban'
            await update_settings(db, settings)
            await send_message(event, get_message('join_mode_ban_set'), parse_mode='html')
        except Exception as e:
            logger.error(f"Error setting join mode to ban: {e}")
            await send_message(event, get_message('error_occurred'))

    @client.on(events.NewMessage(pattern=get_command_pattern('join_mode_mute', lang['group'])))
    async def handle_join_mode_mute(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            settings['group_settings']['join_mode_type'] = 'mute'
            await update_settings(db, settings)
            await send_message(event, get_message('join_mode_mute_set'), parse_mode='html')
        except Exception as e:
            logger.error(f"Error setting join mode to mute: {e}")
            await send_message(event, get_message('error_occurred'))

    # فیلتر کردن
    @client.on(events.NewMessage(pattern=get_command_pattern('filter_add', lang['group'])))
    async def handle_filter_add(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            words = event.pattern_match.group(1).split('\n')
            for word in words:
                if word and word not in settings['group_settings']['filter_list']:
                    settings['group_settings']['filter_list'].append(word.strip())
            await update_settings(db, settings)
            await send_message(event, get_message('filter_added', count=len(words)), parse_mode='html')
        except Exception as e:
            logger.error(f"Error adding filter: {e}")
            await send_message(event, get_message('error_occurred'))

    @client.on(events.NewMessage(pattern=get_command_pattern('filter_remove', lang['group'])))
    async def handle_filter_remove(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            word = event.pattern_match.group(1)
            if word in settings['group_settings']['filter_list']:
                settings['group_settings']['filter_list'].remove(word)
                await update_settings(db, settings)
                await send_message(event, get_message('filter_removed', word=word), parse_mode='html')
            else:
                await send_message(event, get_message('filter_not_found'), parse_mode='html')
        except Exception as e:
            logger.error(f"Error removing filter: {e}")
            await send_message(event, get_message('error_occurred'))

    @client.on(events.NewMessage(pattern=get_command_pattern('filter_list', lang['group'])))
    async def handle_filter_list(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            filters = settings['group_settings']['filter_list']
            if filters:
                filter_text = "\n".join([f"{i+1}. {f}" for i, f in enumerate(filters)])
                await send_message(event, get_message('filter_list', filters=filter_text), parse_mode='html')
            else:
                await send_message(event, get_message('no_filters'), parse_mode='html')
        except Exception as e:
            logger.error(f"Error listing filters: {e}")
            await send_message(event, get_message('error_occurred'))

    @client.on(events.NewMessage(pattern=get_command_pattern('filter_clear', lang['group'])))
    async def handle_filter_clear(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            settings['group_settings']['filter_list'] = []
            await update_settings(db, settings)
            await send_message(event, get_message('filter_list_cleared'), parse_mode='html')
        except Exception as e:
            logger.error(f"Error clearing filter list: {e}")
            await send_message(event, get_message('error_occurred'))

    # کلمات مجاز
    @client.on(events.NewMessage(pattern=get_command_pattern('sallow', lang['group'])))
    async def handle_sallow(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            words = event.pattern_match.group(1).split('\n')
            for word in words:
                if word and word not in settings['group_settings']['allow_list']:
                    settings['group_settings']['allow_list'].append(word.strip())
            await update_settings(db, settings)
            await send_message(event, get_message('allow_added', count=len(words)), parse_mode='html')
        except Exception as e:
            logger.error(f"Error adding allow list: {e}")
            await send_message(event, get_message('error_occurred'))

    @client.on(events.NewMessage(pattern=get_command_pattern('sdelallow', lang['group'])))
    async def handle_sdelallow(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            word = event.pattern_match.group(1)
            if word in settings['group_settings']['allow_list']:
                settings['group_settings']['allow_list'].remove(word)
                await update_settings(db, settings)
                await send_message(event, get_message('allow_removed', word=word), parse_mode='html')
            else:
                await send_message(event, get_message('allow_not_found'), parse_mode='html')
        except Exception as e:
            logger.error(f"Error removing allow list: {e}")
            await send_message(event, get_message('error_occurred'))

    @client.on(events.NewMessage(pattern=get_command_pattern('sallowlist', lang['group'])))
    async def handle_sallowlist(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            allows = settings['group_settings']['allow_list']
            if allows:
                allow_text = "\n".join([f"{i+1}. {a}" for i, a in enumerate(allows)])
                await send_message(event, get_message('allow_list', allows=allow_text), parse_mode='html')
            else:
                await send_message(event, get_message('no_allows'), parse_mode='html')
        except Exception as e:
            logger.error(f"Error listing allow list: {e}")
            await send_message(event, get_message('error_occurred'))

    @client.on(events.NewMessage(pattern=get_command_pattern('clean_sallowlist', lang['group'])))
    async def handle_clean_sallowlist(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            settings['group_settings']['allow_list'] = []
            await update_settings(db, settings)
            await send_message(event, get_message('allow_list_cleared'), parse_mode='html')
        except Exception as e:
            logger.error(f"Error clearing allow list: {e}")
            await send_message(event, get_message('error_occurred'))

    # حالت آرام
    @client.on(events.NewMessage(pattern=get_command_pattern('set_slow_mode', lang['group'])))
    async def handle_set_slow_mode(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            duration = int(event.pattern_match.group(1)) if event.pattern_match.group(1) else 0
            settings['group_settings']['slow_mode_duration'] = duration
            await update_settings(db, settings)
            await send_message(event, get_message('slow_mode_set', duration=duration), parse_mode='html')
        except Exception as e:
            logger.error(f"Error setting slow mode: {e}")
            await send_message(event, get_message('error_occurred'))

    @client.on(events.NewMessage(pattern=get_command_pattern('remove_slow_mode', lang['group'])))
    async def handle_remove_slow_mode(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            settings['group_settings']['slow_mode_duration'] = 0
            await update_settings(db, settings)
            await send_message(event, get_message('slow_mode_removed'), parse_mode='html')
        except Exception as e:
            logger.error(f"Error removing slow mode: {e}")
            await send_message(event, get_message('error_occurred'))

    # اخراج کاربر
    @client.on(events.NewMessage(pattern=get_command_pattern('kick', lang['group'])))
    async def handle_kick(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            if event.is_reply:
                reply_msg = await event.get_reply_message()
                user = await client.get_entity(reply_msg.sender_id)
                await client(EditBannedRequest(event.chat_id, user.id, banned_rights=ChannelParticipantBanned(until_date=None)))
                await send_message(event, get_message('user_kicked', user=user.first_name), parse_mode='html')
            else:
                users = event.pattern_match.group(1).split(',')
                for user_id in users:
                    user = await client.get_entity(user_id.strip())
                    await client(EditBannedRequest(event.chat_id, user.id, banned_rights=ChannelParticipantBanned(until_date=None)))
                    await send_message(event, get_message('user_kicked', user=user.first_name), parse_mode='html')
                    await asyncio.sleep(1)
        except Exception as e:
            logger.error(f"Error kicking user: {e}")
            await send_message(event, get_message('error_occurred'))

    # لغو مسدودیت
    @client.on(events.NewMessage(pattern=get_command_pattern('unban', lang['group'])))
    async def handle_unban(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            if event.is_reply:
                reply_msg = await event.get_reply_message()
                user = await client.get_entity(reply_msg.sender_id)
                await client(EditBannedRequest(event.chat_id, user.id, banned_rights=None))
                await send_message(event, get_message('user_unbanned', user=user.first_name), parse_mode='html')
            else:
                user_id = event.pattern_match.group(1)
                user = await client.get_entity(user_id.strip())
                await client(EditBannedRequest(event.chat_id, user.id, banned_rights=None))
                await send_message(event, get_message('user_unbanned', user=user.first_name), parse_mode='html')
        except Exception as e:
            logger.error(f"Error unbanning user: {e}")
            await send_message(event, get_message('error_occurred'))

    # سکوت کاربر
    @client.on(events.NewMessage(pattern=get_command_pattern('mute', lang['group'])))
    async def handle_mute(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            if event.is_reply:
                reply_msg = await event.get_reply_message()
                user = await client.get_entity(reply_msg.sender_id)
                settings['group_settings']['mute_list'].append(user.id)
                await client(EditBannedRequest(event.chat_id, user.id, banned_rights=ChannelParticipantBanned(until_date=None, send_messages=False)))
                await send_message(event, get_message('user_muted', user=user.first_name), parse_mode='html')
            else:
                await send_message(event, get_message('reply_to_user'))
        except Exception as e:
            logger.error(f"Error muting user: {e}")
            await send_message(event, get_message('error_occurred'))

    @client.on(events.NewMessage(pattern=get_command_pattern('unmute', lang['group'])))
    async def handle_unmute(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            if event.is_reply:
                reply_msg = await event.get_reply_message()
                user = await client.get_entity(reply_msg.sender_id)
                if user.id in settings['group_settings']['mute_list']:
                    settings['group_settings']['mute_list'].remove(user.id)
                    await client(EditBannedRequest(event.chat_id, user.id, banned_rights=None))
                    await send_message(event, get_message('user_unmuted', user=user.first_name), parse_mode='html')
                else:
                    await send_message(event, get_message('user_not_muted'), parse_mode='html')
            else:
                await send_message(event, get_message('reply_to_user'))
        except Exception as e:
            logger.error(f"Error unmuting user: {e}")
            await send_message(event, get_message('error_occurred'))

    @client.on(events.NewMessage(pattern=get_command_pattern('mute_list', lang['group'])))
    async def handle_mute_list(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            mute_list = settings['group_settings']['mute_list']
            if mute_list:
                users = [await get_user_info(uid) for uid in mute_list]
                mute_text = "\n".join([f"{u['first_name']} (@{u['username'] or 'N/A'})" for u in users if u])
                await send_message(event, get_message('mute_list', list=mute_text), parse_mode='html')
            else:
                await send_message(event, get_message('no_muted_users'), parse_mode='html')
        except Exception as e:
            logger.error(f"Error listing muted users: {e}")
            await send_message(event, get_message('error_occurred'))

    @client.on(events.NewMessage(pattern=get_command_pattern('clear_mute_list', lang['group'])))
    async def handle_clear_mute_list(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            settings['group_settings']['mute_list'] = []
            await update_settings(db, settings)
            await send_message(event, get_message('mute_list_cleared'), parse_mode='html')
        except Exception as e:
            logger.error(f"Error clearing mute list: {e}")
            await send_message(event, get_message('error_occurred'))

    # خوش‌آمدگویی
    @client.on(events.NewMessage(pattern=get_command_pattern('welcome_on', lang['group'])))
    async def handle_welcome_on(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            settings['group_settings']['welcome_enabled'] = True
            await update_settings(db, settings)
            await send_message(event, get_message('welcome_enabled'), parse_mode='html')
        except Exception as e:
            logger.error(f"Error enabling welcome: {e}")
            await send_message(event, get_message('error_occurred'))

    @client.on(events.NewMessage(pattern=get_command_pattern('welcome_off', lang['group'])))
    async def handle_welcome_off(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            settings['group_settings']['welcome_enabled'] = False
            await update_settings(db, settings)
            await send_message(event, get_message('welcome_disabled'), parse_mode='html')
        except Exception as e:
            logger.error(f"Error disabling welcome: {e}")
            await send_message(event, get_message('error_occurred'))

    @client.on(events.NewMessage(pattern=get_command_pattern('set_welcome', lang['group'])))
    async def handle_set_welcome(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            if event.is_reply:
                reply_msg = await event.get_reply_message()
                settings['group_settings']['welcome_message'] = reply_msg.text
                await update_settings(db, settings)
                await send_message(event, get_message('welcome_message_set'), parse_mode='html')
            else:
                await send_message(event, get_message('reply_to_message'))
        except Exception as e:
            logger.error(f"Error setting welcome message: {e}")
            await send_message(event, get_message('error_occurred'))

    # بن کردن در همه گروه‌ها
    @client.on(events.NewMessage(pattern=get_command_pattern('ban_all', lang['group'])))
    async def handle_ban_all(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            if event.is_reply:
                reply_msg = await event.get_reply_message()
                user = await client.get_entity(reply_msg.sender_id)
                settings['group_settings']['ban_all_enabled'] = True
                settings['group_settings']['ban_all_list'].append(user.id)
                await update_settings(db, settings)
                async for dialog in client.iter_dialogs():
                    if dialog.is_group or (dialog.is_channel and dialog.entity.megagroup):
                        try:
                            await client(EditBannedRequest(dialog.entity.id, user.id, banned_rights=ChannelParticipantBanned(until_date=None)))
                        except:
                            await client.delete_messages(dialog.entity.id, [m.id async for m in client.iter_messages(dialog.entity.id, from_user=user.id, limit=10)])
                        await asyncio.sleep(1)
                await send_message(event, get_message('user_banned_all', user=user.first_name), parse_mode='html')
            else:
                await send_message(event, get_message('reply_to_user'))
        except Exception as e:
            logger.error(f"Error banning user in all groups: {e}")
            await send_message(event, get_message('error_occurred'))

    @client.on(events.NewMessage(pattern=get_command_pattern('unban_all', lang['group'])))
    async def handle_unban_all(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            if event.is_reply:
                reply_msg = await event.get_reply_message()
                user = await client.get_entity(reply_msg.sender_id)
                if user.id in settings['group_settings']['ban_all_list']:
                    settings['group_settings']['ban_all_list'].remove(user.id)
                    if not settings['group_settings']['ban_all_list']:
                        settings['group_settings']['ban_all_enabled'] = False
                    await update_settings(db, settings)
                    async for dialog in client.iter_dialogs():
                        if dialog.is_group or (dialog.is_channel and dialog.entity.megagroup):
                            await client(EditBannedRequest(dialog.entity.id, user.id, banned_rights=None))
                            await asyncio.sleep(1)
                    await send_message(event, get_message('user_unbanned_all', user=user.first_name), parse_mode='html')
                else:
                    await send_message(event, get_message('user_not_banned_all'), parse_mode='html')
            else:
                await send_message(event, get_message('reply_to_user'))
        except Exception as e:
            logger.error(f"Error unbanning user in all groups: {e}")
            await send_message(event, get_message('error_occurred'))

    @client.on(events.NewMessage(pattern=get_command_pattern('ban_all_list', lang['group'])))
    async def handle_ban_all_list(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            ban_list = settings['group_settings']['ban_all_list']
            if ban_list:
                users = [await get_user_info(uid) for uid in ban_list]
                ban_text = "\n".join([f"{u['first_name']} (@{u['username'] or 'N/A'})" for u in users if u])
                await send_message(event, get_message('ban_all_list', list=ban_text), parse_mode='html')
            else:
                await send_message(event, get_message('no_banned_users'), parse_mode='html')
        except Exception as e:
            logger.error(f"Error listing banned users: {e}")
            await send_message(event, get_message('error_occurred'))

    @client.on(events.NewMessage(pattern=get_command_pattern('clear_ban_all_list', lang['group'])))
    async def handle_clear_ban_all_list(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            settings['group_settings']['ban_all_list'] = []
            settings['group_settings']['ban_all_enabled'] = False
            await update_settings(db, settings)
            await send_message(event, get_message('ban_all_list_cleared'), parse_mode='html')
        except Exception as e:
            logger.error(f"Error clearing ban all list: {e}")
            await send_message(event, get_message('error_occurred'))

    # دعوت به ویس چت
    @client.on(events.NewMessage(pattern=get_command_pattern('invite_voice_chat', lang['group'])))
    async def handle_invite_voice_chat(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            usernames = event.pattern_match.group(1).split(',')
            invited_count = 0
            for username in usernames:
                try:
                    user = await client.get_entity(username.strip())
                    await client.send_message(user.id, get_message('voice_chat_invite', group=(await client.get_entity(event.chat_id)).title), parse_mode='html')
                    invited_count += 1
                    await asyncio.sleep(1)
                except:
                    continue
            await send_message(event, get_message('voice_chat_invited', count=invited_count), parse_mode='html')
        except Exception as e:
            logger.error(f"Error inviting to voice chat: {e}")
            await send_message(event, get_message('error_occurred'))

    @client.on(events.NewMessage(pattern=get_command_pattern('invite_all_voice_chat', lang['group'])))
    async def handle_invite_all_voice_chat(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            invited_count = 0
            async for user in client.iter_participants(event.chat_id, limit=200):
                try:
                    await client.send_message(user.id, get_message('voice_chat_invite', group=(await client.get_entity(event.chat_id)).title), parse_mode='html')
                    invited_count += 1
                    await asyncio.sleep(1)
                except:
                    continue
            await send_message(event, get_message('voice_chat_all_invited', count=invited_count), parse_mode='html')
        except Exception as e:
            logger.error(f"Error inviting all to voice chat: {e}")
            await send_message(event, get_message('error_occurred'))

    await db.close()