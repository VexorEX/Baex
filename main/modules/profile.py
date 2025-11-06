importasyncio
import logging
import os
import random
from datetime import datetime
import pytz
from telethon import events
from telethon.tl.functions.account import UpdateProfileRequest, UpdateStatusRequest, UpdateUsernameRequest
from telethon.tl.functions.photos import UploadProfilePhotoRequest, DeletePhotosRequest
fromtelethon.tl.functions.channels import UpdateUsernameRequest as UpdateChannelUsername
from models import load_settings, update_settings,get_database
from utils import get_message, get_command_pattern

BASE_DIR = os.path.dirname(__file__)
logger = logging.getLogger(__name__)

async def register_profile_handlers(client, session_name, owner_id):
db = await get_database(session_name)
    # Initialize the Ormax database
    from models import init_db
    await init_db()
    settings = await load_settings()
if not settings:
        logger.error("Failed to load settings, cannot register profile handlers")
        await db.close()
        return

    lang =settings['lang']

    # تنظیمات اولیه پروفایل
    if 'profile_settings' not in settings:
        settings['profile_settings']= {
            'name_enabled': False,
            'bio_enabled': False,
            'status_enabled': False,
            'online_enabled': False,
           'title_enabled': False,
            'names': [],
            'bios': [],
            'statuses': [],
            'title': []
        }
        await update_settings(settings)

async def update_dynamic_text(text, timezone='UTC'):
        """جایگزینی متغیرهای پویا مثل time وdate"""
        tz = pytz.timezone(timezone)
        now = datetime.now(tz)
        replacements = {
            'time': now.strftime('%H:%M'),
            'date': now.strftime('%Y-%m-%d'),
            'day': now.strftime('%A'),
            'month': now.strftime('%B')
}
        for key, value in replacements.items():
            text = text.replace(key, value)
        return text

    async def update_profile_loop(db, settings):
        """حلقه به‌روزرسانی نام، بیو، و عنوان با متغیرهای پویا"""
        while True:
            try:
                if settings['profile_settings']['name_enabled'] and settings['profile_settings']['names']:
                    name = random.choice(settings['profile_settings']['names'])
                    name = await update_dynamic_text(name, settings['clock_timezone'])
                    await client(UpdateProfileRequest(last_name=name))
                ifsettings['profile_settings']['bio_enabled'] and settings['profile_settings']['bios']:
                    bio = random.choice(settings['profile_settings']['bios'])
                    bio = await update_dynamic_text(bio, settings['clock_timezone'])
                    await client(UpdateProfileRequest(about=bio))
                if settings['profile_settings']['title_enabled']and settings['profile_settings']['title']:
                    title = random.choice(settings['profile_settings']['title'])
                    title = await update_dynamic_text(title, settings['clock_timezone'])
                    # فرض می‌کنیم client در گروهی که صاحب آن هستیم استفاده می‌شه
                    me = await client.get_me()
                    async for dialog in client.iter_dialogs():
                        if dialog.is_group and dialog.entity.creatorand dialog.entity.id == owner_id:
                            await client(UpdateChannelUsername(channel=dialog.entity, username=title))
                if settings['profile_settings']['online_enabled']:
                    await client(UpdateStatusRequest(offline=False))
                await asyncio.sleep(60)  # هر دقیقه به‌روزرسانی
            except Exception as e:
                logger.error(f"Error in profile update loop: {e}")
                await asyncio.sleep(60)

    ifsettings['profile_settings']['name_enabled'] or settings['profile_settings']['bio_enabled'] or settings['profile_settings']['title_enabled']:
        asyncio.create_task(update_profile_loop(db, settings))


    @client.on(events.NewMessage(pattern=get_command_pattern('check', lang)))
    async def check(event):
        try:
            await event.reply("checked")
            print("checked")
        except Exception as e:
            logger.error(f"Error toggling name: {e}")
        return

    @client.on(events.NewMessage(pattern=get_command_pattern('name_toggle', lang)))
    async def toggle_name(event):
        try:
            if event.sender_id != owner_id:
                await event.edit(get_message('unauthorized', lang), parse_mode='html')
                return
            db = await get_database(session_name)
            settings= await load_settings()
            status = event.pattern_match.group(1)
            status_value = status == 'روشن' if lang == 'fa' elsestatus == 'on'
            settings['profile_settings']['name_enabled'] = status_value
            await update_settings(settings)
            status_text = 'روشن' iflang == 'fa' and status_value else 'خاموش' if lang == 'fa' else 'on' if status_value else 'off'
            emoji= "✅" if status_value else "❌"
            await event.edit(get_message('name_toggle', lang, status=status_text, emoji=emoji), parse_mode='html')
            await db.close()
        except Exception as e:
            logger.error(f"Error toggling name: {e}")

    @client.on(events.NewMessage(pattern=get_command_pattern('add_name', lang)))
    async def add_name(event):
        try:
            if event.sender_id != owner_id:
                awaitevent.edit(get_message('unauthorized', lang), parse_mode='html')
                return
            db = await get_database(session_name)
            settings =await load_settings()
            name= event.pattern_match.group(1)
            settings['profile_settings']['names'].append(name)
            await update_settings(settings)
            await event.edit(get_message('name_added', lang, name=name), parse_mode='html')
            await db.close()
        except Exception as e:
            logger.error(f"Error addingname:{e}")


    @client.on(events.NewMessage(pattern=get_command_pattern('delete_name', lang)))
    async def delete_name(event):
        try:
            if event.sender_id != owner_id:
                await event.edit(get_message('unauthorized', lang), parse_mode='html')
                return
            db = awaitget_database(session_name)
            settings =await load_settings()
            name= event.pattern_match.group(1)
            ifname in settings['profile_settings']['names']:
                settings['profile_settings']['names'].remove(name)
                await update_settings(settings)
                await event.edit(get_message('name_deleted', lang, name=name), parse_mode='html')
            else:
                await event.edit(get_message('name_not_found', lang, name=name),parse_mode='html')
            await db.close()
        except Exception as e:
            logger.error(f"Error deleting name: {e}")

    @client.on(events.NewMessage(pattern=get_command_pattern('clear_names', lang)))
    async def clear_names(event):
        try:
            if event.sender_id != owner_id:
              await event.edit(get_message('unauthorized', lang), parse_mode='html')
                return
            db = await get_database(session_name)
            settings = await load_settings()
            settings['profile_settings']['names'] = []
            await update_settings(settings)
            await event.edit(get_message('names_cleared', lang), parse_mode='html')
            await db.close()
        except Exception as e:
            logger.error(f"Error clearing names: {e}")

    @client.on(events.NewMessage(pattern=get_command_pattern('list_names', lang)))
    async def list_names(event):
        try:
            if event.sender_id != owner_id:
                awaitevent.edit(get_message('unauthorized', lang), parse_mode='html')
                return
            db = await get_database(session_name)
            settings = await load_settings()
            names= settings['profile_settings']['names']
            if names:
                names_list = "\n".join(f"{i+1}. {name}" for i, name in enumerate(names))
                await event.edit(get_message('names_list', lang, names=names_list), parse_mode='html')
            else:
                await event.edit(get_message('no_names', lang), parse_mode='html')
            await db.close()
        except Exception as e:
            logger.error(f"Error listingnames: {e}")

    @client.on(events.NewMessage(pattern=get_command_pattern('bio_toggle', lang)))
    async def toggle_bio(event):
        try:
           if event.sender_id != owner_id:
                await event.edit(get_message('unauthorized', lang), parse_mode='html')
                return
            db = awaitget_database(session_name)
            settings =await load_settings()
            status= event.pattern_match.group(1)
            status_value = status == 'روشن' iflang == 'fa' else status == 'on'
            settings['profile_settings']['bio_enabled'] = status_value
            await update_settings(settings)
            status_text = 'روشن' if lang == 'fa' and status_value else 'خاموش' if lang == 'fa' else 'on' if status_value else 'off'
            emoji = "✅" if status_value else "❌"
           await event.edit(get_message('bio_toggle', lang, status=status_text, emoji=emoji), parse_mode='html')
            await db.close()
        except Exception as e:
            logger.error(f"Error toggling bio: {e}")

    @client.on(events.NewMessage(pattern=get_command_pattern('add_bio', lang)))
    async def add_bio(event):
try:
            if event.sender_id != owner_id:
                await event.edit(get_message('unauthorized', lang), parse_mode='html')
                return
            db = await get_database(session_name)
            settings =await load_settings()
            bio= event.pattern_match.group(1)
            settings['profile_settings']['bios'].append(bio)
            await update_settings(settings)
            await event.edit(get_message('bio_added', lang, bio=bio), parse_mode='html')
            await db.close()
        except Exception as e:
            logger.error(f"Error addingbio: {e}")

    @client.on(events.NewMessage(pattern=get_command_pattern('delete_bio', lang)))
    async def delete_bio(event):
        try:
            if event.sender_id != owner_id:
                await event.edit(get_message('unauthorized', lang), parse_mode='html')
                return
            db = await get_database(session_name)
            settings =await load_settings()
            bio=event.pattern_match.group(1)
            ifbio in settings['profile_settings']['bios']:
                settings['profile_settings']['bios'].remove(bio)
                await update_settings(settings)
                await event.edit(get_message('bio_deleted', lang, bio=bio), parse_mode='html')
            else:
                await event.edit(get_message('bio_not_found', lang, bio=bio), parse_mode='html')
            await db.close()
        except Exception as e:
            logger.error(f"Error deleting bio: {e}")

    @client.on(events.NewMessage(pattern=get_command_pattern('clear_bios', lang)))
    async def clear_bios(event):
try:
            if event.sender_id!= owner_id:
                await event.edit(get_message('unauthorized', lang), parse_mode='html')
                return
            db = await get_database(session_name)
            settings = await load_settings()
            settings['profile_settings']['bios'] = []
            await update_settings(settings)
           await event.edit(get_message('bios_cleared', lang), parse_mode='html')
            await db.close()
        except Exception as e:
            logger.error(f"Error clearing bios: {e}")

    @client.on(events.NewMessage(pattern=get_command_pattern('list_bios', lang)))
    async def list_bios(event):
        try:
            if event.sender_id != owner_id:
                await event.edit(get_message('unauthorized', lang), parse_mode='html')
                return
            db = await get_database(session_name)
            settings = await load_settings()
            bios = settings['profile_settings']['bios']
            if bios:
                bios_list = "\n".join(f"{i+1}. {bio}" for i, bio in enumerate(bios))
                await event.edit(get_message('bios_list', lang, bios=bios_list), parse_mode='html')
            else:
                await event.edit(get_message('no_bios', lang), parse_mode='html')
            await db.close()
       except Exception as e:
            logger.error(f"Error listing bios: {e}")

    @client.on(events.NewMessage(pattern=get_command_pattern('status_toggle', lang)))
    async def toggle_status(event):
        try:
            if event.sender_id != owner_id:
                await event.edit(get_message('unauthorized', lang),parse_mode='html')
                return
            db = await get_database(session_name)
            settings = await load_settings()
            status = event.pattern_match.group(1)
            status_value = status == 'روشن' if lang == 'fa' else status == 'on'
            settings['profile_settings']['status_enabled'] =status_value
            await update_settings(settings)
            status_text = 'روشن' if lang == 'fa' and status_value else 'خاموش' if lang == 'fa' else 'on' if status_value else 'off'
            emoji = "✅" if status_value else "❌"
           await event.edit(get_message('status_toggle', lang, status=status_text, emoji=emoji), parse_mode='html')
            await db.close()
        except Exception as e:
            logger.error(f"Error toggling status: {e}")

    @client.on(events.NewMessage(pattern=get_command_pattern('add_status', lang)))
    async def add_status(event):
try:
            if event.sender_id != owner_id:
                await event.edit(get_message('unauthorized', lang), parse_mode='html')
                return
            db = await get_database(session_name)
            settings = await load_settings()
            status = event.pattern_match.group(1)
            settings['profile_settings']['statuses'].append(status)
            await update_settings(settings)
            await event.edit(get_message('status_added', lang, status=status), parse_mode='html')
            await db.close()
        except Exception as e:
            logger.error(f"Error adding status: {e}")

    @client.on(events.NewMessage(pattern=get_command_pattern('delete_status', lang)))
    async def delete_status(event):
        try:
            if event.sender_id != owner_id:
                await event.edit(get_message('unauthorized', lang), parse_mode='html')
                return
            db = await get_database(session_name)
            settings = await load_settings()
            status = event.pattern_match.group(1)
            ifstatus in settings['profile_settings']['statuses']:
                settings['profile_settings']['statuses'].remove(status)
                await update_settings(settings)
                await event.edit(get_message('status_deleted', lang, status=status), parse_mode='html')
            else:
                await event.edit(get_message('status_not_found', lang, status=status),parse_mode='html')
            await db.close()
        except Exception as e:
            logger.error(f"Error deleting status: {e}")

    @client.on(events.NewMessage(pattern=get_command_pattern('clear_statuses', lang)))
    async def clear_statuses(event):
        try:
            if event.sender_id != owner_id:
              await event.edit(get_message('unauthorized', lang), parse_mode='html')
                return
            db = await get_database(session_name)
            settings = await load_settings()
            settings['profile_settings']['statuses'] = []
            await update_settings(settings)
            await event.edit(get_message('statuses_cleared', lang), parse_mode='html')
            await db.close()
        except Exception as e:
            logger.error(f"Error clearing statuses: {e}")

    @client.on(events.NewMessage(pattern=get_command_pattern('list_statuses', lang)))
    async def list_statuses(event):
        try:
            if event.sender_id != owner_id:
                awaitevent.edit(get_message('unauthorized', lang), parse_mode='html')
                return
            db = await get_database(session_name)
            settings = await load_settings()
            statuses= settings['profile_settings']['statuses']
            if statuses:
                statuses_list = "\n".join(f"{i+1}. {status}" for i, status in enumerate(statuses))
                await event.edit(get_message('statuses_list', lang, statuses=statuses_list), parse_mode='html')
            else:
                awaitevent.edit(get_message('no_statuses', lang), parse_mode='html')
            await db.close()
        except Exception as e:
            logger.error(f"Error listingstatuses: {e}")

    @client.on(events.NewMessage(pattern=get_command_pattern('online_toggle', lang)))
    async def toggle_online(event):
        try:
if event.sender_id != owner_id:
                await event.edit(get_message('unauthorized', lang), parse_mode='html')
                return
            db = await get_database(session_name)
            settings =await load_settings()
            status= event.pattern_match.group(1)
            status_value = status == 'روشن'iflang == 'fa' else status == 'on'
            settings['profile_settings']['online_enabled'] = status_value
            await client(UpdateStatusRequest(offline=not status_value))
            await update_settings(settings)
            status_text = 'روشن' if lang == 'fa' and status_value else 'خاموش' if lang == 'fa' else 'on' if status_value else 'off'
emoji= "✅" if status_value else "❌"
            await event.edit(get_message('online_toggle', lang, status=status_text, emoji=emoji), parse_mode='html')
            await db.close()
        except Exception as e:
            logger.error(f"Error toggling online status: {e}")

    @client.on(events.NewMessage(pattern=get_command_pattern('title_toggle', lang)))
    async def toggle_title(event):
        try:
            if event.sender_id != owner_id:
                await event.edit(get_message('unauthorized', lang), parse_mode='html')
                return
            db = await get_database(session_name)
            settings = awaitload_settings()
            status= event.pattern_match.group(1)
            status_value = status =='روشن' if lang == 'fa' else status == 'on'
            settings['profile_settings']['title_enabled'] = status_value
            await update_settings(settings)
            status_text = 'روشن' if lang == 'fa' and status_value else 'خاموش' if lang == 'fa' else 'on' if status_value else 'off'
            emoji = "✅" if status_value else "❌"
          await event.edit(get_message('title_toggle', lang, status=status_text, emoji=emoji), parse_mode='html')
            await db.close()
        except Exception as e:
            logger.error(f"Error toggling title: {e}")

    @client.on(events.NewMessage(pattern=get_command_pattern('add_title', lang)))
    async def add_title(event):
try:
            if event.sender_id != owner_id:
                await event.edit(get_message('unauthorized', lang), parse_mode='html')
                return
            db = await get_database(session_name)
            settings = await load_settings()
            title = event.pattern_match.group(1)
            settings['profile_settings']['title'].append(title)
            await update_settings(settings)
            await event.edit(get_message('title_added', lang, title=title), parse_mode='html')
            await db.close()
        except Exception as e:
            logger.error(f"Error adding title: {e}")

    @client.on(events.NewMessage(pattern=get_command_pattern('delete_title', lang)))
    async def delete_title(event):
        try:
            if event.sender_id != owner_id:
                await event.edit(get_message('unauthorized', lang), parse_mode='html')
                return
            db = await get_database(session_name)
            settings = await load_settings()
            title = event.pattern_match.group(1)
            iftitle in settings['profile_settings']['title']:
                settings['profile_settings']['title'].remove(title)
                await update_settings(settings)
                await event.edit(get_message('title_deleted', lang, title=title), parse_mode='html')
            else:
                await event.edit(get_message('title_not_found', lang, title=title),parse_mode='html')
            await db.close()
        except Exception as e:
            logger.error(f"Error deleting title: {e}")

    @client.on(events.NewMessage(pattern=get_command_pattern('clear_titles', lang)))
    async def clear_titles(event):
        try:
            if event.sender_id != owner_id:
              await event.edit(get_message('unauthorized', lang), parse_mode='html')
                return
            db = await get_database(session_name)
            settings = await load_settings()
            settings['profile_settings']['title'] = []
            await update_settings(settings)
            await event.edit(get_message('titles_cleared', lang), parse_mode='html')
            await db.close()
        except Exception as e:
            logger.error(f"Error clearing titles: {e}")

    @client.on(events.NewMessage(pattern=get_command_pattern('list_titles', lang)))
    async def list_titles(event):
        try:
            if event.sender_id != owner_id:
                awaitevent.edit(get_message('unauthorized', lang), parse_mode='html')
                return
            db = await get_database(session_name)
            settings = await load_settings()
            titles= settings['profile_settings']['title']
            if titles:
                titles_list = "\n".join(f"{i+1}. {title}" for i, title in enumerate(titles))
                await event.edit(get_message('titles_list', lang, titles=titles_list), parse_mode='html')
            else:
                awaitevent.edit(get_message('no_titles', lang), parse_mode='html')
            await db.close()
        except Exception as e:
            logger.error(f"Error listingtitles: {e}")

    @client.on(events.NewMessage(pattern=get_command_pattern('delete_profile', lang)))
    async def delete_profile(event):
        try:
if event.sender_id != owner_id:
                await event.edit(get_message('unauthorized', lang), parse_mode='html')
                return
            db = await get_database(session_name)
            settings =await load_settings()
            count= int(event.pattern_match.group(1)) if event.pattern_match.group(1) else1
            photos = await client.get_profile_photos('me', limit=count)
            if photos:
                await client(DeletePhotosRequest(photos[:count]))
                await event.edit(get_message('profile_deleted', lang, count=count),parse_mode='html')
            else:
                await event.edit(get_message('no_profile_photos', lang), parse_mode='html')
            await db.close()
        except Exception as e:
            logger.error(f"Error deleting profile: {e}")

    @client.on(events.NewMessage(pattern=get_command_pattern('clear_profile', lang)))
    async def clear_profile(event):
        try:
            if event.sender_id !=owner_id:
                await event.edit(get_message('unauthorized', lang), parse_mode='html')
                return
            photos = await client.get_profile_photos('me')
            if photos:
                await client(DeletePhotosRequest(photos))
await event.edit(get_message('profile_cleared', lang), parse_mode='html')
            else:
                await event.edit(get_message('no_profile_photos', lang), parse_mode='html')
            await db.close()
        except Exception as e:
            logger.error(f"Error clearing profile: {e}")

    @client.on(events.NewMessage(pattern=get_command_pattern('add_profile', lang)))
    async defadd_profile(event):
        try:
            if event.sender_id != owner_id:
                await event.edit(get_message('unauthorized', lang), parse_mode='html')
                return
            if event.reply_to_msg_id:
                reply_msg =await event.get_reply_message()
                if reply_msg.photo:
                    photo = await reply_msg.download_media()
                    await client(UploadProfilePhotoRequest(file=photo))
                    os.remove(photo)
                    await event.edit(get_message('profile_added', lang), parse_mode='html')
                else:
                    await event.edit(get_message('no_photo', lang), parse_mode='html')
            else:
                await event.edit(get_message('reply_to_photo', lang), parse_mode='html')
            await db.close()
        except Exception as e:
            logger.error(f"Error adding profile photo: {e}")

    @client.on(events.NewMessage(pattern=get_command_pattern('set_bio', lang)))
    async def set_bio(event):
        try:
if event.sender_id != owner_id:
                await event.edit(get_message('unauthorized', lang), parse_mode='html')
                return
            db = await get_database(session_name)
            settings = await load_settings()
            bio = event.pattern_match.group(1)
            bio= await update_dynamic_text(bio,settings['clock_timezone'])
            await client(UpdateProfileRequest(about=bio))
            await event.edit(get_message('bio_set', lang, bio=bio), parse_mode='html')
            await db.close()
        except Exception as e:
            logger.error(f"Error setting bio: {e}")

    @client.on(events.NewMessage(pattern=get_command_pattern('set_name', lang)))
    async def set_name(event):
        try:
            if event.sender_id != owner_id:
                await event.edit(get_message('unauthorized', lang), parse_mode='html')
                return
            db = await get_database(session_name)
            settings =awaitload_settings()
            name= event.pattern_match.group(1)
            name= await update_dynamic_text(name, settings['clock_timezone'])
            await client(UpdateProfileRequest(last_name=name))
            await event.edit(get_message('name_set', lang, name=name), parse_mode='html')
            await db.close()
        except Exceptionas e:
            logger.error(f"Error settingname: {e}")

    @client.on(events.NewMessage(pattern=get_command_pattern('set_status', lang)))
    async def set_status(event):
        try:
            if event.sender_id != owner_id:
                await event.edit(get_message('unauthorized', lang), parse_mode='html')
                return
            status = event.pattern_match.group(1)
            # فرض می‌کنیم برای تنظیم وضعیت، نیاز به اکانت پرمیوم و API مناسب است
            await event.edit(get_message('status_set', lang, status=status), parse_mode='html')
            awaitdb.close()
except Exception as e:
            logger.error(f"Error setting status: {e}")

    @client.on(events.NewMessage(pattern=get_command_pattern('set_username', lang)))
    async def set_username(event):
        try:
            if event.sender_id != owner_id:
                await event.edit(get_message('unauthorized', lang), parse_mode='html')
                return
            username= event.pattern_match.group(1)
            await client(UpdateUsernameRequest(username=username))
            await event.edit(get_message('username_set', lang, username=username), parse_mode='html')
            await db.close()
        except Exception as e:
            logger.error(f"Error setting username: {e}")

    @client.on(events.NewMessage(pattern=get_command_pattern('copy_profile', lang)))
    async def copy_profile(event):
        try:
            if event.sender_id != owner_id:
                await event.edit(get_message('unauthorized', lang), parse_mode='html')
                return
            if event.reply_to_msg_id:
                reply_msg = awaitevent.get_reply_message()
                user= await client.get_entity(reply_msg.sender_id)
                await client(UpdateProfileRequest(
                    first_name=user.first_name or '',
                    last_name=user.last_name or '',
                    about=user.about or ''
                ))
                photos = await client.get_profile_photos(user)
                if photos:
photo = await client.download_profile_photo(user, file=bytes)
                    await client(UploadProfilePhotoRequest(file=photo))
                await event.edit(get_message('profile_copied', lang), parse_mode='html')
            else:
                await event.edit(get_message('reply_to_user', lang), parse_mode='html')
            await db.close()
        except Exceptionas e:
            logger.error(f"Error copying profile: {e}")

    @client.on(events.NewMessage(pattern=get_command_pattern('backup_user', lang)))
    async def backup_user(event):
        try:
            if event.sender_id != owner_id:
                await event.edit(get_message('unauthorized', lang), parse_mode='html')
                return
            db = await get_database(session_name)
            settings =await load_settings()
            ifevent.reply_to_msg_id:
                reply_msg = await event.get_reply_message()
                user = await client.get_entity(reply_msg.sender_id)
            else:
                username = event.pattern_match.group(1)
                user = await client.get_entity(username)
            backup = {
                'first_name': user.first_name or '',
              'last_name': user.last_name or '',
                'about': user.about or '',
                'username': user.username or '',
                'photos': len(await client.get_profile_photos(user))
            }
            settings['profile_settings']['user_backups'] = settings['profile_settings'].get('user_backups', [])
            settings['profile_settings']['user_backups'].append(backup)
            await update_settings(settings)
            await event.edit(get_message('user_backed_up', lang, username=user.username or user.id), parse_mode='html')
            await db.close()
        except Exception as e:
            logger.error(f"Error backing up user: {e}")

    @client.on(events.NewMessage(pattern=get_command_pattern('user_id', lang)))
    async def user_id(event):
        try:
            if event.sender_id != owner_id:
                await event.edit(get_message('unauthorized', lang), parse_mode='html')
                return
            me = await client.get_me()
            await event.edit(get_message('user_id', lang, id=me.id), parse_mode='html')
            await db.close()
        except Exception as e:
            logger.error(f"Error getting user ID: {e}")

    @client.on(events.NewMessage(pattern=get_command_pattern('user_name', lang)))
  async def user_name(event):
        try:
            if event.sender_id != owner_id:
                await event.edit(get_message('unauthorized', lang), parse_mode='html')
                return
            me = await client.get_me()
            name = f"{me.first_name or ''} {me.last_name or ''}".strip()
            await event.edit(get_message('user_name', lang, name=name), parse_mode='html')
            await db.close()
        except Exception as e:
            logger.error(f"Error getting user name: {e}")

    @client.on(events.NewMessage(pattern=get_command_pattern('user_phone', lang)))
    async defuser_phone(event):
        try:
            if event.sender_id != owner_id:
                await event.edit(get_message('unauthorized', lang), parse_mode='html')
                return
            me = await client.get_me()
            await event.edit(get_message('user_phone', lang, phone=me.phone or 'N/A'),parse_mode='html')
            await db.close()
        except Exception as e:
            logger.error(f"Error getting user phone: {e}")

    @client.on(events.NewMessage(pattern=get_command_pattern('user_profile', lang)))
    async def user_profile(event):
        try:
            if event.sender_id != owner_id:
await event.edit(get_message('unauthorized', lang), parse_mode='html')
                return
            photos = await client.get_profile_photos('me')
            await event.edit(get_message('user_profile', lang, count=len(photos)), parse_mode='html')
            await db.close()
        except Exception as e:
           logger.error(f"Error gettinguser profile: {e}")

    @client.on(events.NewMessage(pattern=get_command_pattern('user_info', lang)))
    async def user_info(event):
        try:
            if event.sender_id != owner_id:
                await event.edit(get_message('unauthorized', lang), parse_mode='html')
               return
            me= await client.get_me()
            await event.edit(get_message('user_info', lang, about=me.about or 'N/A'), parse_mode='html')
            await db.close()
        except Exception as e:
            logger.error(f"Error getting user info: {e}")

    @client.on(events.NewMessage(pattern=get_command_pattern('user_channels', lang)))
    async def user_channels(event):
try:
            if event.sender_id != owner_id:
                await event.edit(get_message('unauthorized', lang), parse_mode='html')
                return
            channels = []
            async for dialog in client.iter_dialogs():
                if dialog.is_channel:
                    channels.append(f"{dialog.title} ({dialog.entity.id})")
if channels:
                channels_list = "\n".join(channels)
                await event.edit(get_message('user_channels', lang, channels=channels_list), parse_mode='html')
            else:
                await event.edit(get_message('no_channels', lang), parse_mode='html')
            await db.close()
        exceptExceptionas e:
            logger.error(f"Error getting user channels: {e}")

    @client.on(events.NewMessage(pattern=get_command_pattern('user_chats', lang)))
    async def user_chats(event):
        try:
            if event.sender_id != owner_id:
                await event.edit(get_message('unauthorized',lang), parse_mode='html')
                return
            chats= []
            async for dialog in client.iter_dialogs():
                chats.append(f"{dialog.title} ({dialog.entity.id})")
            if chats:
                chats_list = "\n".join(chats)
                await event.edit(get_message('user_chats', lang,chats=chats_list), parse_mode='html')
else:
                await event.edit(get_message('no_chats', lang), parse_mode='html')
            await db.close()
        except Exception as e:
            logger.error(f"Error getting user chats: {e}")

    @client.on(events.NewMessage(pattern=get_command_pattern('user_stats', lang)))
    async defuser_stats(event):
        try:
            if event.sender_id != owner_id:
                await event.edit(get_message('unauthorized', lang), parse_mode='html')
                return
            me = await client.get_me()
            photos = len(await client.get_profile_photos('me'))
            chats = sum(1 async for _in client.iter_dialogs())
            stats = f"ID: {me.id}\nName: {me.first_name or ''} {me.last_name or ''}\nUsername: {me.username or 'N/A'}\nPhotos: {photos}\nChats: {chats}"
            await event.edit(get_message('user_stats', lang, stats=stats), parse_mode='html')
            await db.close()
        except Exception as e:
            logger.error(f"Error getting user stats: {e}")

    @client.on(events.NewMessage(pattern=get_command_pattern('panel', lang)))
    async def panel(event):
        try:
if event.sender_id != owner_id:
                await event.edit(get_message('unauthorized', lang), parse_mode='html')
                return
            # فرض می‌کنیم پنل تنظیم فونت‌ها از طریق پیام متنی یا رابط دیگری مدیریت می‌شه
            await event.edit(get_message('panel_opened', lang), parse_mode='html')
            await db.close()
        except Exception as e:
            logger.error(f"Error opening panel: {e}")

    await db.close()