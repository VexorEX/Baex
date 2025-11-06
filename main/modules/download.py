import asyncio
import logging
import os
import re
import requests
import yt_dlp
from git import Repo
from zipfile import ZipFile
from telethon import events, types
from telethon.errors import FloodWaitError
from utils import load_json, send_message, get_command_pattern, upload_to_backup_channel
from models import get_database, load_settings, update_settings

logger = logging.getLogger(__name__)

async def register_download_handlers(client, session_name, owner_id):
    db = await get_database(session_name)
    settings = await load_settings(db)
    if not settings:
        logger.error("Failed to load settings for download handlers")
        await db.close()
        return

    lang = settings.get('lang', 'fa')
    messages = load_json('msg.json')
    commands = load_json('cmd.json')

    def get_message(key, **kwargs):
        return messages[lang]['download'].get(key, '').format(**kwargs)

    # ایجاد جدول برای تاریخچه دانلود (در صورت پشتیبانی DB)
    has_db_exec = hasattr(db, 'execute')
    if has_db_exec:
        await db.execute('''
                         CREATE TABLE IF NOT EXISTS download_history (
                                                                     id INTEGER PRIMARY KEY AUTOINCREMENT,
                                                                     user_id INTEGER,
                                                                     query TEXT,
                                                                     type TEXT,
                                                                     timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                         )
                         ''')
        if hasattr(db, 'commit'):
            await db.commit()

    async def save_download_history(user_id, query, download_type):
        try:
            if has_db_exec:
                await db.execute('INSERT INTO download_history (user_id, query, type) VALUES (?, ?, ?)',
                                 (user_id, query, download_type))
                if hasattr(db, 'commit'):
                    await db.commit()
        except Exception as e:
            logger.error(f"Error saving download history: {e}")

    # دانلود آهنگ
    @client.on(events.NewMessage(pattern=get_command_pattern('download_song', 'download', lang)))
    async def handle_download_song(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            query = event.pattern_match.group(1)
            if not query:
                await send_message(event, get_message('no_query'))
                return
            async for msg in client.iter_messages(None, search=query, filter=types.InputMessagesFilterMusic, limit=1):
                if msg.audio:
                    file_path = await msg.download_media()
                    await client.send_file(event.chat_id, file_path, attributes=msg.audio.attributes)
                    await send_message(event, get_message('song_downloaded', query=query))
                    os.remove(file_path)
                    await save_download_history(event.sender_id, query, 'song')
                    return
            await send_message(event, get_message('no_song_found', query=query))
        except FloodWaitError as e:
            await send_message(event, get_message('flood_wait', seconds=e.seconds))
        except Exception as e:
            logger.error(f"Error downloading song: {e}")
            await send_message(event, get_message('error_occurred'))

    # دانلود ویدئو از یوتیوب
    @client.on(events.NewMessage(pattern=get_command_pattern('download_video', 'download', lang)))
    async def handle_download_video(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            url = event.pattern_match.group(1) or (event.message.is_reply and (await event.get_reply_message()).text)
            if not url or not re.match(r'^https?://(www\.)?(youtube\.com|youtu\.be)/', url):
                await send_message(event, get_message('invalid_url'))
                return
            ydl_opts = {
                'format': 'bestvideo[height<=1080]+bestaudio/best[height<=1080]',
                'outtmpl': 'output.%(ext)s',
                'merge_output_format': 'mp4',
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                file_path = 'output.mp4'
                if os.path.exists(file_path):
                    if os.path.getsize(file_path) > 200 * 1024 * 1024:  # 200 مگابایت
                        await send_message(event, get_message('file_too_large'))
                        os.remove(file_path)
                        return
                    await client.send_file(event.chat_id, file_path, caption=info.get('title', ''))
                    await send_message(event, get_message('video_downloaded', title=info.get('title', '')))
                    os.remove(file_path)
                    await save_download_history(event.sender_id, url, 'video')
                else:
                    await send_message(event, get_message('download_failed'))
        except FloodWaitError as e:
            await send_message(event, get_message('flood_wait', seconds=e.seconds))
        except Exception as e:
            logger.error(f"Error downloading video: {e}")
            await send_message(event, get_message('error_occurred'))

    # دریافت لیست ویدئوهای یوتیوب
    @client.on(events.NewMessage(pattern=get_command_pattern('download_list', 'download', lang)))
    async def handle_download_list(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            query = event.pattern_match.group(1)
            if not query:
                await send_message(event, get_message('no_query'))
                return
            ydl_opts = {'quiet': True, 'extract_flat': True}
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                results = ydl.extract_info(f"ytsearch10:{query}", download=False)
                videos = results.get('entries', [])
                if not videos:
                    await send_message(event, get_message('no_videos_found', query=query))
                    return
                response = f"📋 {get_message('video_list', count=len(videos), query=query)}\n"
                for i, video in enumerate(videos, 1):
                    response += f"{i}. {video['title']} - {video['url']}\n"
                await send_message(event, response)
                await save_download_history(event.sender_id, query, 'video_list')
        except Exception as e:
            logger.error(f"Error getting video list: {e}")
            await send_message(event, get_message('error_occurred'))

    # دانلود همه استوری‌ها
    @client.on(events.NewMessage(pattern=get_command_pattern('download_all_stories', 'download', lang)))
    async def handle_download_all_stories(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            stories = await client.get_stories(None)
            if not stories:
                await send_message(event, get_message('no_stories_found'))
                return
            count = 0
            for story in stories:
                file_path = await client.download_media(story)
                await client.send_file(event.chat_id, file_path)
                os.remove(file_path)
                count += 1
            await send_message(event, get_message('all_stories_downloaded', count=count))
            await save_download_history(event.sender_id, 'all_stories', 'stories')
        except FloodWaitError as e:
            await send_message(event, get_message('flood_wait', seconds=e.seconds))
        except Exception as e:
            logger.error(f"Error downloading all stories: {e}")
            await send_message(event, get_message('error_occurred'))

    # دانلود استوری‌های یک کاربر
    @client.on(events.NewMessage(pattern=get_command_pattern('download_stories', 'download', lang)))
    async def handle_download_stories(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            username = event.pattern_match.group(1)
            if not username:
                await send_message(event, get_message('no_username'))
                return
            entity = await client.get_entity(username)
            stories = await client.get_stories(entity.id)
            if not stories:
                await send_message(event, get_message('no_stories_found_for_user', username=username))
                return
            count = 0
            for story in stories:
                file_path = await client.download_media(story)
                await client.send_file(event.chat_id, file_path)
                os.remove(file_path)
                count += 1
            await send_message(event, get_message('stories_downloaded', username=username, count=count))
            await save_download_history(event.sender_id, username, 'user_stories')
        except FloodWaitError as e:
            await send_message(event, get_message('flood_wait', seconds=e.seconds))
        except Exception as e:
            logger.error(f"Error downloading user stories: {e}")
            await send_message(event, get_message('error_occurred'))

    # انتشار استوری
    @client.on(events.NewMessage(pattern=get_command_pattern('new_story', 'download', lang)))
    async def handle_new_story(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            if not event.message.is_reply:
                await send_message(event, get_message('reply_required'))
                return
            reply_msg = await event.get_reply_message()
            if not reply_msg.media:
                await send_message(event, get_message('no_media'))
                return
            try:
                file_path = await reply_msg.download_media()
                await client.send_file('me', file_path, story=True)
                await send_message(event, get_message('story_posted'))
                os.remove(file_path)
                await save_download_history(event.sender_id, 'new_story', 'story')
            except PremiumRequiredError:
                await send_message(event, get_message('premium_required'))
            except Exception as e:
                logger.error(f"Error posting story: {e}")
                await send_message(event, get_message('error_occurred'))
        except Exception as e:
            logger.error(f"Error in new story: {e}")
            await send_message(event, get_message('error_occurred'))

    # دانلود فایل از لینک مستقیم
    @client.on(events.NewMessage(pattern=get_command_pattern('download_file', 'download', lang)))
    async def handle_download_file(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            url = event.pattern_match.group(1) or (event.message.is_reply and (await event.get_reply_message()).text)
            if not url or not re.match(r'^https?://', url):
                await send_message(event, get_message('invalid_url'))
                return
            response = requests.get(url, stream=True)
            if response.status_code != 200:
                await send_message(event, get_message('download_failed'))
                return
            file_size = int(response.headers.get('content-length', 0))
            if file_size > 200 * 1024 * 1024:  # 200 مگابایت
                await send_message(event, get_message('file_too_large'))
                return
            file_name = url.split('/')[-1] or 'downloaded_file'
            with open(file_name, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            await client.send_file(event.chat_id, file_name)
            await send_message(event, get_message('file_downloaded', file_name=file_name))
            os.remove(file_name)
            await save_download_history(event.sender_id, url, 'file')
        except Exception as e:
            logger.error(f"Error downloading file: {e}")
            await send_message(event, get_message('error_occurred'))

    # دانلود مخزن GitHub
    @client.on(events.NewMessage(pattern=get_command_pattern('download_git', 'download', lang)))
    async def handle_download_git(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            url = event.pattern_match.group(1) or (event.message.is_reply and (await event.get_reply_message()).text)
            if not url or not re.match(r'^https?://github\.com/[^/]+/[^/]+/?$', url):
                await send_message(event, get_message('invalid_git_url'))
                return
            repo_name = url.rstrip('/').split('/')[-1]
            temp_dir = f"temp_{repo_name}"
            Repo.clone_from(url, temp_dir)
            zip_name = f"{repo_name}.zip"
            with ZipFile(zip_name, 'w') as zipf:
                for root, _, files in os.walk(temp_dir):
                    for file in files:
                        zipf.write(os.path.join(root, file), os.path.relpath(os.path.join(root, file), temp_dir))
            if os.path.getsize(zip_name) > 200 * 1024 * 1024:  # 200 مگابایت
                await send_message(event, get_message('file_too_large'))
                os.remove(zip_name)
                shutil.rmtree(temp_dir)
                return
            await client.send_file(event.chat_id, zip_name)
            await send_message(event, get_message('git_downloaded', repo_name=repo_name))
            os.remove(zip_name)
            shutil.rmtree(temp_dir)
            await save_download_history(event.sender_id, url, 'git')
        except Exception as e:
            logger.error(f"Error downloading git repo: {e}")
            await send_message(event, get_message('error_occurred'))

    await db.close()