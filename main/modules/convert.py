import asyncio
import logging
import os
import re
from datetime import datetime
from telethon import events
from telethon.errors import FloodWaitError
from PIL import Image
from pydub import AudioSegment
from moviepy.video.io.VideoFileClip import VideoFileClip
import qrcode
from zipfile import ZipFile
from dateutil.parser import parse
from utils import load_json, send_message, get_command_pattern, upload_to_backup_channel
from models import get_database, load_settings, update_settings

logger = logging.getLogger(__name__)

async def register_convert_handlers(client, session_name, owner_id):
    db = await get_database(session_name)
    settings = await load_settings(db)
    if not settings:
        logger.error("Failed to load settings for convert handlers")
        await db.close()
        return

    lang = settings.get('lang', 'fa')
    messages = load_json('msg.json')
    commands = load_json('cmd.json')

    def get_message(key, **kwargs):
        data = messages.get(lang) or messages.get('fa') or messages.get('en') or {}
        section = data.get('convert', {})
        text = section.get(key) or key
        try:
            return text.format(**kwargs)
        except Exception:
            return text

    # تنظیمات اولیه convert
    if 'convert' not in settings:
        settings['convert'] = {
            'cover': None,  # مسیر کاور پیش‌فرض
            'backup_channel': None  # ID کانال پشتیبان
        }
        await update_settings(db, settings)

    # ایجاد جدول برای تنظیمات تبدیل (در صورت پشتیبانی DB)
    has_db_exec = hasattr(db, 'execute')
    if has_db_exec:
        await db.execute('''
                         CREATE TABLE IF NOT EXISTS convert_settings (
                                                                     key TEXT PRIMARY KEY,
                                                                     value TEXT
                         )
                         ''')
        if hasattr(db, 'commit'):
            await db.commit()

    async def save_cover(cover_path):
        """ذخیره کاور پیش‌فرض"""
        try:
            if has_db_exec:
                await db.execute('INSERT OR REPLACE INTO convert_settings (key, value) VALUES (?, ?)', ('cover', cover_path))
                if hasattr(db, 'commit'):
                    await db.commit()
            settings['convert']['cover'] = cover_path
            await update_settings(db, settings)
        except Exception as e:
            logger.error(f"Error saving cover: {e}")

    async def get_cover():
        """دریافت کاور پیش‌فرض"""
        try:
            if has_db_exec:
                cursor = await db.execute('SELECT value FROM convert_settings WHERE key = ?', ('cover',))
                result = await cursor.fetchone()
                await cursor.close()
                return result[0] if result else None
            return settings['convert'].get('cover')
        except Exception as e:
            logger.error(f"Error getting cover: {e}")
            return None

    # بررسی وجود کانال پشتیبان
    async def check_backup_channel(event):
        if not settings['convert']['backup_channel']:
            await send_message(event, get_message('no_backup_channel'))
            return False
        return True

    # تنظیم کاور
    @client.on(events.NewMessage(pattern=get_command_pattern('set_cover', 'convert', lang)))
    async def handle_set_cover(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            if not event.message.photo:
                await send_message(event, get_message('no_photo'))
                return
            if not await check_backup_channel(event):
                return
            file_path = await event.message.download_media()
            cover_path = await upload_to_backup_channel(client, settings['convert']['backup_channel'], file_path)
            await save_cover(cover_path)
            await send_message(event, get_message('cover_set'))
            os.remove(file_path)
        except Exception as e:
            logger.error(f"Error setting cover: {e}")
            await send_message(event, get_message('error_occurred'))

    # افزودن کاور به آهنگ
    @client.on(events.NewMessage(pattern=get_command_pattern('add_cover', 'convert', lang)))
    async def handle_add_cover(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            if not event.message.is_reply:
                await send_message(event, get_message('reply_required'))
                return
            if not await check_backup_channel(event):
                return
            reply_msg = await event.get_reply_message()
            if not reply_msg.audio:
                await send_message(event, get_message('no_audio'))
                return
            cover_path = await get_cover()
            if not cover_path:
                await send_message(event, get_message('no_cover_set'))
                return
            audio_path = await reply_msg.download_media()
            audio = AudioSegment.from_file(audio_path)
            cover = Image.open(cover_path)
            cover.save('cover.jpg')
            audio.export('output.mp3', format='mp3', cover='cover.jpg')
            await client.send_file(event.chat_id, 'output.mp3', attributes=reply_msg.audio.attributes)
            await send_message(event, get_message('cover_added'))
            os.remove(audio_path)
            os.remove('cover.jpg')
            os.remove('output.mp3')
        except Exception as e:
            logger.error(f"Error adding cover: {e}")
            await send_message(event, get_message('error_occurred'))

    # دریافت کاور
    @client.on(events.NewMessage(pattern=get_command_pattern('get_cover', 'convert', lang)))
    async def handle_get_cover(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            if not event.message.is_reply:
                await send_message(event, get_message('reply_required'))
                return
            reply_msg = await event.get_reply_message()
            if not reply_msg.audio and not reply_msg.video:
                await send_message(event, get_message('no_media'))
                return
            media_path = await reply_msg.download_media()
            if reply_msg.audio:
                audio = AudioSegment.from_file(media_path)
                cover = audio.get_cover()
                if cover:
                    await client.send_file(event.chat_id, cover)
                    await send_message(event, get_message('cover_extracted'))
                else:
                    await send_message(event, get_message('no_cover_found'))
            else:
                video = VideoFileClip(media_path)
                frame = video.get_frame(0)
                Image.fromarray(frame).save('cover.jpg')
                await client.send_file(event.chat_id, 'cover.jpg')
                await send_message(event, get_message('cover_extracted'))
                os.remove('cover.jpg')
            os.remove(media_path)
        except Exception as e:
            logger.error(f"Error getting cover: {e}")
            await send_message(event, get_message('error_occurred'))

    # حذف پس‌زمینه
    @client.on(events.NewMessage(pattern=get_command_pattern('remove_background', 'convert', lang)))
    async def handle_remove_background(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            if not event.message.is_reply:
                await send_message(event, get_message('reply_required'))
                return
            reply_msg = await event.get_reply_message()
            if not reply_msg.photo:
                await send_message(event, get_message('no_photo'))
                return
            image_path = await reply_msg.download_media()
            image = Image.open(image_path)
            # فرض می‌کنیم از یک API یا ماژول مثل rembg استفاده می‌شود
            from rembg import remove
            output = remove(image)
            output.save('output.png')
            await client.send_file(event.chat_id, 'output.png')
            await send_message(event, get_message('background_removed'))
            os.remove(image_path)
            os.remove('output.png')
        except Exception as e:
            logger.error(f"Error removing background: {e}")
            await send_message(event, get_message('error_occurred'))

    # تغییر نام فایل/آهنگ
    @client.on(events.NewMessage(pattern=get_command_pattern('edit_name', 'convert', lang)))
    async def handle_edit_name(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            if not event.message.is_reply:
                await send_message(event, get_message('reply_required'))
                return
            name = event.pattern_match.group(1)
            reply_msg = await event.get_reply_message()
            if not reply_msg.media:
                await send_message(event, get_message('no_media'))
                return
            file_path = await reply_msg.download_media()
            if reply_msg.audio and ':' in name:
                artist, title = name.split(':', 1)
                audio = AudioSegment.from_file(file_path)
                audio.export('output.mp3', format='mp3', tags={'artist': artist.strip(), 'title': title.strip()})
                await client.send_file(event.chat_id, 'output.mp3', attributes=reply_msg.audio.attributes)
                await send_message(event, get_message('name_edited', name=name))
                os.remove('output.mp3')
            else:
                ext = os.path.splitext(name)[1] or os.path.splitext(file_path)[1]
                new_path = f"output{ext}"
                os.rename(file_path, new_path)
                await client.send_file(event.chat_id, new_path)
                await send_message(event, get_message('name_edited', name=name))
                os.remove(new_path)
            os.remove(file_path)
        except Exception as e:
            logger.error(f"Error editing name: {e}")
            await send_message(event, get_message('error_occurred'))

    # تغییر زمان
    @client.on(events.NewMessage(pattern=get_command_pattern('edit_duration', 'convert', lang)))
    async def handle_edit_duration(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            if not event.message.is_reply:
                await send_message(event, get_message('reply_required'))
                return
            duration = int(event.pattern_match.group(1))
            reply_msg = await event.get_reply_message()
            if not reply_msg.audio and not reply_msg.video and not reply_msg.voice:
                await send_message(event, get_message('no_media'))
                return
            file_path = await reply_msg.download_media()
            if reply_msg.audio or reply_msg.voice:
                audio = AudioSegment.from_file(file_path)[:duration * 1000]
                audio.export('output.mp3', format='mp3')
                await client.send_file(event.chat_id, 'output.mp3', attributes=reply_msg.media.attributes)
            else:
                video = VideoFileClip(file_path).subclip(0, duration)
                video.write('output.mp4')
                await client.send_file(event.chat_id, 'output.mp4')
            await send_message(event, get_message('duration_edited', duration=duration))
            os.remove(file_path)
            os.remove('output.mp3' if reply_msg.audio or reply_msg.voice else 'output.mp4')
        except Exception as e:
            logger.error(f"Error editing duration: {e}")
            await send_message(event, get_message('error_occurred'))

    # تبدیل استیکر به عکس
    @client.on(events.NewMessage(pattern=get_command_pattern('to_photo', 'convert', lang)))
    async def handle_to_photo(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            if not event.message.is_reply:
                await send_message(event, get_message('reply_required'))
                return
            reply_msg = await event.get_reply_message()
            if not reply_msg.sticker:
                await send_message(event, get_message('no_sticker'))
                return
            file_path = await reply_msg.download_media()
            image = Image.open(file_path)
            image.save('output.png')
            await client.send_file(event.chat_id, 'output.png')
            await send_message(event, get_message('converted_to_photo'))
            os.remove(file_path)
            os.remove('output.png')
        except Exception as e:
            logger.error(f"Error converting to photo: {e}")
            await send_message(event, get_message('error_occurred'))

    # تبدیل ویدئو/استیکر به گیف
    @client.on(events.NewMessage(pattern=get_command_pattern('to_gif', 'convert', lang)))
    async def handle_to_gif(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            if not event.message.is_reply:
                await send_message(event, get_message('reply_required'))
                return
            reply_msg = await event.get_reply_message()
            if not reply_msg.video and not reply_msg.sticker:
                await send_message(event, get_message('no_video_or_sticker'))
                return
            file_path = await reply_msg.download_media()
            video = VideoFileClip(file_path)
            video.write('output.gif')
            await client.send_file(event.chat_id, 'output.gif')
            await send_message(event, get_message('converted_to_gif'))
            os.remove(file_path)
            os.remove('output.gif')
        except Exception as e:
            logger.error(f"Error converting to gif: {e}")
            await send_message(event, get_message('error_occurred'))

    # تبدیل عکس به استیکر
    @client.on(events.NewMessage(pattern=get_command_pattern('to_sticker', 'convert', lang)))
    async def handle_to_sticker(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            if not event.message.is_reply:
                await send_message(event, get_message('reply_required'))
                return
            reply_msg = await event.get_reply_message()
            if not reply_msg.photo:
                await send_message(event, get_message('no_photo'))
                return
            file_path = await reply_msg.download_media()
            image = Image.open(file_path).convert('RGBA')
            image.save('output.png')
            await client.send_file(event.chat_id, 'output.png', attributes=[DocumentAttributeSticker('', None)])
            await send_message(event, get_message('converted_to_sticker'))
            os.remove(file_path)
            os.remove('output.png')
        except Exception as e:
            logger.error(f"Error converting to sticker: {e}")
            await send_message(event, get_message('error_occurred'))

    # تبدیل به فایل
    @client.on(events.NewMessage(pattern=get_command_pattern('to_file', 'convert', lang)))
    async def handle_to_file(event):
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
            file_path = await reply_msg.download_media()
            await client.send_file(event.chat_id, file_path, force_document=True)
            await send_message(event, get_message('converted_to_file'))
            os.remove(file_path)
        except Exception as e:
            logger.error(f"Error converting to file: {e}")
            await send_message(event, get_message('error_occurred'))

    # تبدیل به ویس
    @client.on(events.NewMessage(pattern=get_command_pattern('to_voice', 'convert', lang)))
    async def handle_to_voice(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            if not event.message.is_reply:
                await send_message(event, get_message('reply_required'))
                return
            reply_msg = await event.get_reply_message()
            if not reply_msg.audio and not reply_msg.video:
                await send_message(event, get_message('no_audio_or_video'))
                return
            file_path = await reply_msg.download_media()
            if reply_msg.audio:
                audio = AudioSegment.from_file(file_path)
                audio.export('output.ogg', format='ogg', codec='libopus')
            else:
                video = VideoFileClip(file_path)
                video.audio.write('output.ogg', codec='libopus')
                video.close()
            await client.send_file(event.chat_id, 'output.ogg', voice_note=True)
            await send_message(event, get_message('converted_to_voice'))
            os.remove(file_path)
            os.remove('output.ogg')
        except Exception as e:
            logger.error(f"Error converting to voice: {e}")
            await send_message(event, get_message('error_occurred'))

    # تبدیل به آهنگ
    @client.on(events.NewMessage(pattern=get_command_pattern('to_audio', 'convert', lang)))
    async def handle_to_audio(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            if not event.message.is_reply:
                await send_message(event, get_message('reply_required'))
                return
            reply_msg = await event.get_reply_message()
            if not reply_msg.voice and not reply_msg.video:
                await send_message(event, get_message('no_voice_or_video'))
                return
            file_path = await reply_msg.download_media()
            if reply_msg.voice:
                audio = AudioSegment.from_file(file_path)
                audio.export('output.mp3', format='mp3')
            else:
                video = VideoFileClip(file_path)
                video.audio.write('output.mp3')
                video.close()
            await client.send_file(event.chat_id, 'output.mp3')
            await send_message(event, get_message('converted_to_audio'))
            os.remove(file_path)
            os.remove('output.mp3')
        except Exception as e:
            logger.error(f"Error converting to audio: {e}")
            await send_message(event, get_message('error_occurred'))

    # تبدیل تاریخ
    @client.on(events.NewMessage(pattern=get_command_pattern('convert_date', 'convert', lang)))
    async def handle_convert_date(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            date_str = event.pattern_match.group(1)
            try:
                date = parse(date_str)
                jalali_date = date.strftime('%Y/%m/%d')  # فرضاً تبدیل به شمسی
                gregorian_date = date.strftime('%Y-%m-%d')
                await send_message(event, get_message('date_converted', jalali=jalali_date, gregorian=gregorian_date))
            except ValueError:
                await send_message(event, get_message('invalid_date_format'))
        except Exception as e:
            logger.error(f"Error converting date: {e}")
            await send_message(event, get_message('error_occurred'))

    # استخراج فایل زیپ
    @client.on(events.NewMessage(pattern=get_command_pattern('extract_file', 'convert', lang)))
    async def handle_extract_file(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            if not event.message.is_reply:
                await send_message(event, get_message('reply_required'))
                return
            reply_msg = await event.get_reply_message()
            if not reply_msg.document or reply_msg.document.mime_type != 'application/zip':
                await send_message(event, get_message('no_zip_file'))
                return
            file_name = event.pattern_match.group(1)
            file_path = await reply_msg.download_media()
            if os.path.getsize(file_path) > 300 * 1024 * 1024:  # 300 مگابایت
                await send_message(event, get_message('file_too_large'))
                return
            with ZipFile(file_path, 'r') as zip_ref:
                zip_ref.extractall('extracted')
                files = zip_ref.namelist()
                if file_name:
                    if file_name in files:
                        await client.send_file(event.chat_id, f'extracted/{file_name}')
                        await send_message(event, get_message('file_extracted', file_name=file_name))
                    else:
                        await send_message(event, get_message('file_not_found', file_name=file_name))
                else:
                    for file in files:
                        await client.send_file(event.chat_id, f'extracted/{file}')
                    await send_message(event, get_message('all_files_extracted', count=len(files)))
            os.remove(file_path)
            for file in files:
                os.remove(f'extracted/{file}')
            os.rmdir('extracted')
        except Exception as e:
            logger.error(f"Error extracting file: {e}")
            await send_message(event, get_message('error_occurred'))

    # تبدیل به QR کد
    @client.on(events.NewMessage(pattern=get_command_pattern('to_qr', 'convert', lang)))
    async def handle_to_qr(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            text = event.pattern_match.group(1) or (event.message.is_reply and (await event.get_reply_message()).text)
            if not text:
                await send_message(event, get_message('no_text'))
                return
            qr = qrcode.QRCode()
            qr.add_data(text)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            img.save('output.png')
            await client.send_file(event.chat_id, 'output.png')
            await send_message(event, get_message('converted_to_qr'))
            os.remove('output.png')
        except Exception as e:
            logger.error(f"Error converting to QR: {e}")
            await send_message(event, get_message('error_occurred'))

    # خواندن QR کد
    @client.on(events.NewMessage(pattern=get_command_pattern('read_qr', 'convert', lang)))
    async def handle_read_qr(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            if not event.message.is_reply:
                await send_message(event, get_message('reply_required'))
                return
            reply_msg = await event.get_reply_message()
            if not reply_msg.photo:
                await send_message(event, get_message('no_photo'))
                return
            file_path = await reply_msg.download_media()
            from pyzbar.pyzbar import decode
            image = Image.open(file_path)
            decoded = decode(image)
            if decoded:
                text = decoded[0].data.decode('utf-8')
                await send_message(event, get_message('qr_read', text=text))
            else:
                await send_message(event, get_message('no_qr_found'))
            os.remove(file_path)
        except Exception as e:
            logger.error(f"Error reading QR: {e}")
            await send_message(event, get_message('error_occurred'))

    # تبدیل به ویدئو نوت
    @client.on(events.NewMessage(pattern=get_command_pattern('to_video_note', 'convert', lang)))
    async def handle_to_video_note(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            if not event.message.is_reply:
                await send_message(event, get_message('reply_required'))
                return
            reply_msg = await event.get_reply_message()
            if not reply_msg.video:
                await send_message(event, get_message('no_video'))
                return
            file_path = await reply_msg.download_media()
            video = VideoFileClip(file_path).resize((360, 360)).set_duration(min(60, reply_msg.video.attributes[0].duration))
            video.write('output.mp4')
            await client.send_file(event.chat_id, 'output.mp4', video_note=True)
            await send_message(event, get_message('converted_to_video_note'))
            os.remove(file_path)
            os.remove('output.mp4')
        except Exception as e:
            logger.error(f"Error converting to video note: {e}")
            await send_message(event, get_message('error_occurred'))

    # تبدیل به ویدئو
    @client.on(events.NewMessage(pattern=get_command_pattern('to_video', 'convert', lang)))
    async def handle_to_video(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            if not event.message.is_reply:
                await send_message(event, get_message('reply_required'))
                return
            reply_msg = await event.get_reply_message()
            if not reply_msg.video_note:
                await send_message(event, get_message('no_video_note'))
                return
            file_path = await reply_msg.download_media()
            video = VideoFileClip(file_path)
            video.write('output.mp4')
            await client.send_file(event.chat_id, 'output.mp4')
            await send_message(event, get_message('converted_to_video'))
            os.remove(file_path)
            os.remove('output.mp4')
        except Exception as e:
            logger.error(f"Error converting to video: {e}")
            await send_message(event, get_message('error_occurred'))

    await db.close()