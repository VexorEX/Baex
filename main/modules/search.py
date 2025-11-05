import asyncio
import logging
from telethon import events, types
from telethon.errors import FloodWaitError
from utils import load_json, send_message, get_command_pattern
from models import get_database, load_settings, update_settings

logger = logging.getLogger(__name__)

async def register_search_handlers(client, session_name, owner_id):
    db = await get_database(session_name)
    settings = await load_settings(db)
    if not settings:
        logger.error("Failed to load settings for search handlers")
        await db.close()
        return

    lang = settings.get('lang', 'fa')
    messages = load_json('msg.json')
    commands = load_json('cmd.json')

    def get_message(key, **kwargs):
        return messages[lang]['search'].get(key, '').format(**kwargs)

    # ایجاد جدول برای تاریخچه جست‌وجو
    await db.execute('''
                     CREATE TABLE IF NOT EXISTS search_history (
                                                                   id INTEGER PRIMARY KEY AUTOINCREMENT,
                                                                   user_id INTEGER,
                                                                   query TEXT,
                                                                   type TEXT,
                                                                   timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                     )
                     ''')
    await db.commit()

    async def save_search_history(user_id, query, search_type):
        try:
            await db.execute('INSERT INTO search_history (user_id, query, type) VALUES (?, ?, ?)',
                             (user_id, query, search_type))
            await db.commit()
        except Exception as e:
            logger.error(f"Error saving search history: {e}")

    # جست‌وجوی همگانی (آهنگ، فیلم، ویدئو نوت، فایل، عکس، مخاطب)
    async def search_general(event, query, media_type):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            chats = await client.get_dialogs()
            results = []
            for chat in chats:
                async for msg in client.iter_messages(chat.id, search=query, filter=media_type):
                    if len(results) >= 10:  # محدودیت 10 نتیجه
                        break
                    link = f"https://t.me/{chat.username}/{msg.id}" if chat.username else f"Message ID: {msg.id} in {chat.title}"
                    results.append(link)
                if len(results) >= 10:
                    break
            if results:
                await send_message(event, get_message('results_found', count=len(results), query=query, type=media_type.__name__) + '\n' + '\n'.join(results))
            else:
                await send_message(event, get_message('no_results', query=query, type=media_type.__name__))
            await save_search_history(event.sender_id, query, media_type.__name__)
        except FloodWaitError as e:
            await send_message(event, get_message('flood_wait', seconds=e.seconds))
        except Exception as e:
            logger.error(f"Error in general search: {e}")
            await send_message(event, get_message('error_occurred'))

    # جست‌وجوی همگانی آهنگ
    @client.on(events.NewMessage(pattern=get_command_pattern('search_song', 'search', lang)))
    async def handle_search_song(event):
        query = event.pattern_match.group(1) or ''
        await search_general(event, query, types.InputMessagesFilterMusic)

    # جست‌وجوی همگانی فیلم
    @client.on(events.NewMessage(pattern=get_command_pattern('search_video', 'search', lang)))
    async def handle_search_video(event):
        query = event.pattern_match.group(1) or ''
        await search_general(event, query, types.InputMessagesFilterVideo)

    # جست‌وجوی همگانی ویدئو نوت
    @client.on(events.NewMessage(pattern=get_command_pattern('search_video_note', 'search', lang)))
    async def handle_search_video_note(event):
        query = event.pattern_match.group(1) or ''
        await search_general(event, query, types.InputMessagesFilterRoundVideo)

    # جست‌وجوی همگانی فایل
    @client.on(events.NewMessage(pattern=get_command_pattern('search_file', 'search', lang)))
    async def handle_search_file(event):
        query = event.pattern_match.group(1) or ''
        await search_general(event, query, types.InputMessagesFilterDocument)

    # جست‌وجوی همگانی عکس
    @client.on(events.NewMessage(pattern=get_command_pattern('search_photo', 'search', lang)))
    async def handle_search_photo(event):
        query = event.pattern_match.group(1) or ''
        await search_general(event, query, types.InputMessagesFilterPhotos)

    # جست‌وجوی همگانی مخاطب
    @client.on(events.NewMessage(pattern=get_command_pattern('search_contact', 'search', lang)))
    async def handle_search_contact(event):
        query = event.pattern_match.group(1) or ''
        await search_general(event, query, types.InputMessagesFilterContacts)

    # جست‌وجوی تخصصی با ربات‌های خارجی
    async def search_with_bot(event, query, bot_username, search_type):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            if not query:
                await send_message(event, get_message('no_query'))
                return
            async with client.conversation(bot_username) as conv:
                await conv.send_message(query)
                response = await conv.get_response()
                if response.text:
                    await send_message(event, get_message('bot_result', bot=bot_username, result=response.text))
                else:
                    await send_message(event, get_message('no_bot_result', bot=bot_username))
                await save_search_history(event.sender_id, query, search_type)
        except Exception as e:
            logger.error(f"Error searching with bot {bot_username}: {e}")
            await send_message(event, get_message('bot_error', bot=bot_username))

    # جست‌وجوی موسیقی با @melobot
    @client.on(events.NewMessage(pattern=get_command_pattern('search_music', 'search', lang)))
    async def handle_search_music(event):
        query = event.pattern_match.group(1)
        if not query:
            await send_message(event, get_message('no_query'))
            return
        await search_with_bot(event, query, '@melobot', 'music')

    # جست‌وجوی فیلم با @imdb
    @client.on(events.NewMessage(pattern=get_command_pattern('search_movie', 'search', lang)))
    async def handle_search_movie(event):
        query = event.pattern_match.group(1)
        if not query:
            await send_message(event, get_message('no_query'))
            return
        await search_with_bot(event, query, '@imdb', 'movie')

    # جست‌وجوی تصویر با @bing
    @client.on(events.NewMessage(pattern=get_command_pattern('search_image', 'search', lang)))
    async def handle_search_image(event):
        query = event.pattern_match.group(1)
        if not query:
            await send_message(event, get_message('no_query'))
            return
        await search_with_bot(event, query, '@bing', 'image')

    # جست‌وجوی میم با @Persian_Meme_Bot
    @client.on(events.NewMessage(pattern=get_command_pattern('persian_meme', 'search', lang)))
    async def handle_persian_meme(event):
        query = event.pattern_match.group(1)
        if not query:
            await send_message(event, get_message('no_query'))
            return
        try:
            async with client.conversation('@Persian_Meme_Bot') as conv:
                await conv.send_message('/start')
                await conv.get_response()
                await conv.send_message(query)
                response = await conv.get_response()
                if response.text or response.media:
                    await send_message(event, get_message('bot_result', bot='@Persian_Meme_Bot', result=response.text or 'رسانه ارسال شد'))
                    if response.media:
                        await client.send_file(event.chat_id, response.media)
                else:
                    await send_message(event, get_message('no_bot_result', bot='@Persian_Meme_Bot'))
                await save_search_history(event.sender_id, query, 'meme')
        except Exception as e:
            logger.error(f"Error searching with @Persian_Meme_Bot: {e}")
            await send_message(event, get_message('bot_error', bot='@Persian_Meme_Bot'))

    # جست‌وجوی ویکی‌پدیا
    @client.on(events.NewMessage(pattern=get_command_pattern('wiki', 'search', lang)))
    async def handle_wiki(event):
        query = event.pattern_match.group(1)
        if not query:
            await send_message(event, get_message('no_query'))
            return
        await search_with_bot(event, query, '@Wiki', 'wiki')

    # جست‌وجوی گوگل
    @client.on(events.NewMessage(pattern=get_command_pattern('google', 'search', lang)))
    async def handle_google(event):
        query = event.pattern_match.group(1)
        if not query:
            await send_message(event, get_message('no_query'))
            return
        await search_with_bot(event, query, '@BotFather', 'google')  # فرضاً @BotFather یا ربات مشابه

    # جست‌وجوی متن و شمارش تکرار
    @client.on(events.NewMessage(pattern=get_command_pattern('search_text', 'search', lang)))
    async def handle_search_text(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            query = event.pattern_match.group(1)
            if not query:
                await send_message(event, get_message('no_query'))
                return
            if event.message.is_reply:
                reply_msg = await event.get_reply_message()
                user_id = reply_msg.sender_id
                count = 0
                chats = await client.get_dialogs()
                for chat in chats:
                    async for msg in client.iter_messages(chat.id, from_user=user_id, search=query):
                        count += 1
                        if count >= 100:  # محدودیت 100 نتیجه
                            break
                    if count >= 100:
                        break
                await send_message(event, get_message('text_count_user', query=query, count=count, user_id=user_id))
                await save_search_history(event.sender_id, query, 'text_user')
            else:
                count = 0
                chats = await client.get_dialogs()
                for chat in chats:
                    async for msg in client.iter_messages(chat.id, search=query):
                        count += 1
                        if count >= 100:  # محدودیت 100 نتیجه
                            break
                    if count >= 100:
                        break
                await send_message(event, get_message('text_count', query=query, count=count))
                await save_search_history(event.sender_id, query, 'text')
        except FloodWaitError as e:
            await send_message(event, get_message('flood_wait', seconds=e.seconds))
        except Exception as e:
            logger.error(f"Error in text search: {e}")
            await send_message(event, get_message('error_occurred'))

    # جست‌وجوی همگانی متن
    @client.on(events.NewMessage(pattern=get_command_pattern('search_general', 'search', lang)))
    async def handle_search_general(event):
        query = event.pattern_match.group(1)
        if not query:
            await send_message(event, get_message('no_query'))
            return
        try:
            chats = await client.get_dialogs()
            results = []
            for chat in chats:
                async for msg in client.iter_messages(chat.id, search=query):
                    if len(results) >= 10:  # محدودیت 10 نتیجه
                        break
                    link = f"https://t.me/{chat.username}/{msg.id}" if chat.username else f"Message ID: {msg.id} in {chat.title}"
                    results.append(link)
                if len(results) >= 10:
                    break
            if results:
                await send_message(event, get_message('results_found', count=len(results), query=query, type='متن') + '\n' + '\n'.join(results))
            else:
                await send_message(event, get_message('no_results', query=query, type='متن'))
            await save_search_history(event.sender_id, query, 'general')
        except FloodWaitError as e:
            await send_message(event, get_message('flood_wait', seconds=e.seconds))
        except Exception as e:
            logger.error(f"Error in general search: {e}")
            await send_message(event, get_message('error_occurred'))

    await db.close()