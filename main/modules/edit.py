import asyncio
import logging
import os
import re
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter
from pydub import AudioSegment
from moviepy.video.io.VideoFileClip import VideoFileClip
from moviepy.video.VideoClip import TextClip
from moviepy.video.compositing.CompositeVideoClip import CompositeVideoClip
from telethon import events
from telethon.errors import FloodWaitError
from utils import load_json, send_message, get_command_pattern, upload_to_backup_channel
from models import get_database, load_settings, update_settings

logger = logging.getLogger(__name__)

async def register_edit_handlers(client, session_name, owner_id):
    db = await get_database(session_name)
    settings = await load_settings(db)
    if not settings:
        logger.error("Failed to load settings for edit handlers")
        await db.close()
        return

    lang = settings.get('lang', 'fa')
    messages = load_json('msg.json')
    commands = load_json('cmd.json')

    def get_message(key, **kwargs):
        data = messages.get(lang) or messages.get('fa') or messages.get('en') or {}
        section = data.get('edit', {})
        text = section.get(key) or key
        try:
            return text.format(**kwargs)
        except Exception:
            return text

    # تنظیمات اولیه edit
    if 'edit' not in settings:
        settings['edit'] = {'logo': None}  # مسیر لوگوی پیش‌فرض
        await update_settings(db, settings)

    # ایجاد جدول برای تنظیمات ویرایش (در صورت پشتیبانی DB)
    has_db_exec = hasattr(db, 'execute')
    if has_db_exec:
        await db.execute('''
                         CREATE TABLE IF NOT EXISTS edit_settings (
                                                                  key TEXT PRIMARY KEY,
                                                                  value TEXT
                         )
                         ''')
        if hasattr(db, 'commit'):
            await db.commit()

    async def save_logo(logo_path):
        """ذخیره لوگوی پیش‌فرض"""
        try:
            if has_db_exec:
                await db.execute('INSERT OR REPLACE INTO edit_settings (key, value) VALUES (?, ?)', ('logo', logo_path))
                if hasattr(db, 'commit'):
                    await db.commit()
            settings['edit']['logo'] = logo_path
            await update_settings(db, settings)
        except Exception as e:
            logger.error(f"Error saving logo: {e}")

    async def get_logo():
        """دریافت لوگوی پیش‌فرض"""
        try:
            if has_db_exec:
                cursor = await db.execute('SELECT value FROM edit_settings WHERE key = ?', ('logo',))
                result = await cursor.fetchone()
                await cursor.close()
                return result[0] if result else None
            return settings['edit'].get('logo')
        except Exception as e:
            logger.error(f"Error getting logo: {e}")
            return None

    # دموی آهنگ (30 ثانیه)
    @client.on(events.NewMessage(pattern=get_command_pattern('to_demo', 'edit', lang)))
    async def handle_to_demo(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            if not event.message.is_reply:
                await send_message(event, get_message('reply_required'))
                return
            reply_msg = await event.get_reply_message()
            if not reply_msg.audio:
                await send_message(event, get_message('no_audio'))
                return
            file_path = await reply_msg.download_media()
            audio = AudioSegment.from_file(file_path)[:30 * 1000]
            audio.export('output.mp3', format='mp3')
            await client.send_file(event.chat_id, 'output.mp3', attributes=reply_msg.audio.attributes)
            await send_message(event, get_message('demo_created', duration=30))
            os.remove(file_path)
            os.remove('output.mp3')
        except Exception as e:
            logger.error(f"Error creating demo: {e}")
            await send_message(event, get_message('error_occurred'))

    # دموی بلند آهنگ (60 ثانیه)
    @client.on(events.NewMessage(pattern=get_command_pattern('to_long_demo', 'edit', lang)))
    async def handle_to_long_demo(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            if not event.message.is_reply:
                await send_message(event, get_message('reply_required'))
                return
            reply_msg = await event.get_reply_message()
            if not reply_msg.audio:
                await send_message(event, get_message('no_audio'))
                return
            file_path = await reply_msg.download_media()
            audio = AudioSegment.from_file(file_path)[:60 * 1000]
            audio.export('output.mp3', format='mp3')
            await client.send_file(event.chat_id, 'output.mp3', attributes=reply_msg.audio.attributes)
            await send_message(event, get_message('demo_created', duration=60))
            os.remove(file_path)
            os.remove('output.mp3')
        except Exception as e:
            logger.error(f"Error creating long demo: {e}")
            await send_message(event, get_message('error_occurred'))

    # برش آهنگ یا ویدئو
    @client.on(events.NewMessage(pattern=get_command_pattern('cut', 'edit', lang)))
    async def handle_cut(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            if not event.message.is_reply:
                await send_message(event, get_message('reply_required'))
                return
            times = event.pattern_match.group(1)
            if not times or not re.match(r'^\d+-\d+$', times):
                await send_message(event, get_message('invalid_time_format'))
                return
            start, end = map(int, times.split('-'))
            if start >= end:
                await send_message(event, get_message('invalid_time_range'))
                return
            reply_msg = await event.get_reply_message()
            if not reply_msg.audio and not reply_msg.video:
                await send_message(event, get_message('no_audio_or_video'))
                return
            file_path = await reply_msg.download_media()
            if reply_msg.audio:
                audio = AudioSegment.from_file(file_path)[start * 1000:end * 1000]
                audio.export('output.mp3', format='mp3')
                await client.send_file(event.chat_id, 'output.mp3', attributes=reply_msg.audio.attributes)
                os.remove('output.mp3')
            else:
                if os.path.getsize(file_path) > 20 * 1024 * 1024:  # 20 مگابایت
                    await send_message(event, get_message('file_too_large'))
                    os.remove(file_path)
                    return
                video = VideoFileClip(file_path).subclip(start, end)
                video.write('output.mp4')
                await client.send_file(event.chat_id, 'output.mp4')
                video.close()
                os.remove('output.mp4')
            await send_message(event, get_message('cut_done', start=start, end=end))
            os.remove(file_path)
        except Exception as e:
            logger.error(f"Error cutting media: {e}")
            await send_message(event, get_message('error_occurred'))

    # چرخش عکس
    @client.on(events.NewMessage(pattern=get_command_pattern('rotate_left', 'edit', lang)))
    async def handle_rotate_left(event):
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
            image = Image.open(file_path).rotate(90, expand=True)
            image.save('output.png')
            await client.send_file(event.chat_id, 'output.png')
            await send_message(event, get_message('rotated_left'))
            os.remove(file_path)
            os.remove('output.png')
        except Exception as e:
            logger.error(f"Error rotating left: {e}")
            await send_message(event, get_message('error_occurred'))

    @client.on(events.NewMessage(pattern=get_command_pattern('rotate_right', 'edit', lang)))
    async def handle_rotate_right(event):
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
            image = Image.open(file_path).rotate(-90, expand=True)
            image.save('output.png')
            await client.send_file(event.chat_id, 'output.png')
            await send_message(event, get_message('rotated_right'))
            os.remove(file_path)
            os.remove('output.png')
        except Exception as e:
            logger.error(f"Error rotating right: {e}")
            await send_message(event, get_message('error_occurred'))

    @client.on(events.NewMessage(pattern=get_command_pattern('rotate_up', 'edit', lang)))
    async def handle_rotate_up(event):
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
            image = Image.open(file_path).rotate(180, expand=True)
            image.save('output.png')
            await client.send_file(event.chat_id, 'output.png')
            await send_message(event, get_message('rotated_up'))
            os.remove(file_path)
            os.remove('output.png')
        except Exception as e:
            logger.error(f"Error rotating up: {e}")
            await send_message(event, get_message('error_occurred'))

    @client.on(events.NewMessage(pattern=get_command_pattern('rotate_45', 'edit', lang)))
    async def handle_rotate_45(event):
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
            image = Image.open(file_path).rotate(45, expand=True)
            image.save('output.png')
            await client.send_file(event.chat_id, 'output.png')
            await send_message(event, get_message('rotated_45'))
            os.remove(file_path)
            os.remove('output.png')
        except Exception as e:
            logger.error(f"Error rotating 45: {e}")
            await send_message(event, get_message('error_occurred'))

    # افکت‌های تصویری
    @client.on(events.NewMessage(pattern=get_command_pattern('black_white', 'edit', lang)))
    async def handle_black_white(event):
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
            image = Image.open(file_path).convert('L')
            image.save('output.png')
            await client.send_file(event.chat_id, 'output.png')
            await send_message(event, get_message('black_white_applied'))
            os.remove(file_path)
            os.remove('output.png')
        except Exception as e:
            logger.error(f"Error applying black and white: {e}")
            await send_message(event, get_message('error_occurred'))

    @client.on(events.NewMessage(pattern=get_command_pattern('negative', 'edit', lang)))
    async def handle_negative(event):
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
            image = Image.open(file_path)
            image = Image.fromarray(255 - np.array(image))
            image.save('output.png')
            await client.send_file(event.chat_id, 'output.png')
            await send_message(event, get_message('negative_applied'))
            os.remove(file_path)
            os.remove('output.png')
        except Exception as e:
            logger.error(f"Error applying negative: {e}")
            await send_message(event, get_message('error_occurred'))

    @client.on(events.NewMessage(pattern=get_command_pattern('to_rgb', 'edit', lang)))
    async def handle_to_rgb(event):
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
            image = Image.open(file_path).convert('RGB')
            image.save('output.png')
            await client.send_file(event.chat_id, 'output.png')
            await send_message(event, get_message('rgb_applied'))
            os.remove(file_path)
            os.remove('output.png')
        except Exception as e:
            logger.error(f"Error applying RGB: {e}")
            await send_message(event, get_message('error_occurred'))

    @client.on(events.NewMessage(pattern=get_command_pattern('to_green', 'edit', lang)))
    async def handle_to_green(event):
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
            image = Image.open(file_path).convert('RGB')
            array = np.array(image)
            array[:, :, 0] = 0  # حذف قرمز
            array[:, :, 2] = 0  # حذف آبی
            Image.fromarray(array).save('output.png')
            await client.send_file(event.chat_id, 'output.png')
            await send_message(event, get_message('green_applied'))
            os.remove(file_path)
            os.remove('output.png')
        except Exception as e:
            logger.error(f"Error applying green: {e}")
            await send_message(event, get_message('error_occurred'))

    @client.on(events.NewMessage(pattern=get_command_pattern('to_blue', 'edit', lang)))
    async def handle_to_blue(event):
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
            image = Image.open(file_path).convert('RGB')
            array = np.array(image)
            array[:, :, 0] = 0  # حذف قرمز
            array[:, :, 1] = 0  # حذف سبز
            Image.fromarray(array).save('output.png')
            await client.send_file(event.chat_id, 'output.png')
            await send_message(event, get_message('blue_applied'))
            os.remove(file_path)
            os.remove('output.png')
        except Exception as e:
            logger.error(f"Error applying blue: {e}")
            await send_message(event, get_message('error_occurred'))

    @client.on(events.NewMessage(pattern=get_command_pattern('to_red', 'edit', lang)))
    async def handle_to_red(event):
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
            image = Image.open(file_path).convert('RGB')
            array = np.array(image)
            array[:, :, 1] = 0  # حذف سبز
            array[:, :, 2] = 0  # حذف آبی
            Image.fromarray(array).save('output.png')
            await client.send_file(event.chat_id, 'output.png')
            await send_message(event, get_message('red_applied'))
            os.remove(file_path)
            os.remove('output.png')
        except Exception as e:
            logger.error(f"Error applying red: {e}")
            await send_message(event, get_message('error_occurred'))

    @client.on(events.NewMessage(pattern=get_command_pattern('blur', 'edit', lang)))
    async def handle_blur(event):
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
            image = Image.open(file_path).filter(ImageFilter.GaussianBlur(5))
            image.save('output.png')
            await client.send_file(event.chat_id, 'output.png')
            await send_message(event, get_message('blur_applied'))
            os.remove(file_path)
            os.remove('output.png')
        except Exception as e:
            logger.error(f"Error applying blur: {e}")
            await send_message(event, get_message('error_occurred'))

    @client.on(events.NewMessage(pattern=get_command_pattern('sharpen', 'edit', lang)))
    async def handle_sharpen(event):
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
            image = Image.open(file_path).filter(ImageFilter.UnsharpMask(radius=2, percent=150, threshold=3))
            image.save('output.png')
            await client.send_file(event.chat_id, 'output.png')
            await send_message(event, get_message('sharpen_applied'))
            os.remove(file_path)
            os.remove('output.png')
        except Exception as e:
            logger.error(f"Error sharpening image: {e}")
            await send_message(event, get_message('error_occurred'))

    # تغییر اندازه عکس (ارتفاع)
    @client.on(events.NewMessage(pattern=get_command_pattern('resize_height', 'edit', lang)))
    async def handle_resize_height(event):
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
            height = int(event.pattern_match.group(1)) if event.pattern_match.group(1) else 512
            file_path = await reply_msg.download_media()
            image = Image.open(file_path)
            aspect_ratio = image.width / image.height
            new_width = int(height * aspect_ratio)
            image = image.resize((new_width, height))
            image.save('output.png')
            await client.send_file(event.chat_id, 'output.png')
            await send_message(event, get_message('resized_height', height=height))
            os.remove(file_path)
            os.remove('output.png')
        except ValueError:
            await send_message(event, get_message('invalid_size_format'))
        except Exception as e:
            logger.error(f"Error resizing height: {e}")
            await send_message(event, get_message('error_occurred'))

    # تغییر اندازه عکس (طول و عرض)
    @client.on(events.NewMessage(pattern=get_command_pattern('resize', 'edit', lang)))
    async def handle_resize(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            if not event.message.is_reply:
                await send_message(event, get_message('reply_required'))
                return
            sizes = event.pattern_match.group(1)
            if not sizes or not re.match(r'^\d+,\d+$', sizes):
                await send_message(event, get_message('invalid_size_format'))
                return
            width, height = map(int, sizes.split(','))
            reply_msg = await event.get_reply_message()
            if not reply_msg.photo:
                await send_message(event, get_message('no_photo'))
                return
            file_path = await reply_msg.download_media()
            image = Image.open(file_path).resize((width, height))
            image.save('output.png')
            await client.send_file(event.chat_id, 'output.png')
            await send_message(event, get_message('resized', width=width, height=height))
            os.remove(file_path)
            os.remove('output.png')
        except Exception as e:
            logger.error(f"Error resizing: {e}")
            await send_message(event, get_message('error_occurred'))

    # تنظیم لوگو
    @client.on(events.NewMessage(pattern=get_command_pattern('set_logo', 'edit', lang)))
    async def handle_set_logo(event):
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
            if not settings['edit'].get('backup_channel'):
                await send_message(event, get_message('no_backup_channel'))
                return
            file_path = await reply_msg.download_media()
            logo_path = await upload_to_backup_channel(client, settings['edit']['backup_channel'], file_path)
            await save_logo(logo_path)
            await send_message(event, get_message('logo_set'))
            os.remove(file_path)
        except Exception as e:
            logger.error(f"Error setting logo: {e}")
            await send_message(event, get_message('error_occurred'))

    # چاپ لوگو روی عکس
    @client.on(events.NewMessage(pattern=get_command_pattern('apply_logo', 'edit', lang)))
    async def handle_apply_logo(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            if not event.message.is_reply:
                await send_message(event, get_message('reply_required'))
                return
            position = event.pattern_match.group(1)
            if not position or not re.match(r'^\d+,\d+$', position):
                await send_message(event, get_message('invalid_position_format'))
                return
            x, y = map(int, position.split(','))
            reply_msg = await event.get_reply_message()
            if not reply_msg.photo:
                await send_message(event, get_message('no_photo'))
                return
            logo_path = await get_logo()
            if not logo_path:
                await send_message(event, get_message('no_logo_set'))
                return
            file_path = await reply_msg.download_media()
            image = Image.open(file_path).convert('RGBA')
            logo = Image.open(logo_path).convert('RGBA')
            logo = logo.resize((int(image.width * 0.2), int(image.height * 0.2)))  # تغییر اندازه لوگو به 20% تصویر
            image.paste(logo, (x, y), logo)
            image.save('output.png')
            await client.send_file(event.chat_id, 'output.png')
            await send_message(event, get_message('logo_applied', x=x, y=y))
            os.remove(file_path)
            os.remove('output.png')
        except Exception as e:
            logger.error(f"Error applying logo: {e}")
            await send_message(event, get_message('error_occurred'))

    # جایگزینی متن
    @client.on(events.NewMessage(pattern=get_command_pattern('replace_text', 'edit', lang)))
    async def handle_replace_text(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            if not event.message.is_reply:
                await send_message(event, get_message('reply_required'))
                return
            replace_pair = event.pattern_match.group(1)
            if not replace_pair or not re.match(r'^[^,]+,[^,]+$', replace_pair):
                await send_message(event, get_message('invalid_replace_format'))
                return
            old_text, new_text = replace_pair.split(',')
            reply_msg = await event.get_reply_message()
            if not reply_msg.text:
                await send_message(event, get_message('no_text'))
                return
            new_message = reply_msg.text.replace(old_text, new_text)
            await send_message(event, new_message)
            await send_message(event, get_message('text_replaced', old_text=old_text, new_text=new_text))
        except Exception as e:
            logger.error(f"Error replacing text: {e}")
            await send_message(event, get_message('error_occurred'))

    # ویرایش سریع متن
    @client.on(events.NewMessage(pattern=get_command_pattern('quick_edit', 'edit', lang)))
    async def handle_quick_edit(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            if not event.message.is_reply:
                await send_message(event, get_message('reply_required'))
                return
            correct_text = event.pattern_match.group(1)
            if not correct_text:
                await send_message(event, get_message('no_correct_text'))
                return
            reply_msg = await event.get_reply_message()
            if not reply_msg.text:
                await send_message(event, get_message('no_text'))
                return
            # فرض می‌کنیم کلمه اشتباه مشابه کلمه درست است (مثل صلام و سلام)
            words = reply_msg.text.split()
            new_words = []
            for word in words:
                if len(word) >= len(correct_text) - 1 and len(word) <= len(correct_text) + 1:
                    new_words.append(correct_text)
                else:
                    new_words.append(word)
            new_message = ' '.join(new_words)
            await send_message(event, new_message)
            await send_message(event, get_message('text_edited', correct_text=correct_text))
        except Exception as e:
            logger.error(f"Error quick editing text: {e}")
            await send_message(event, get_message('error_occurred'))

    # واترمارک روی ویدئو
    @client.on(events.NewMessage(pattern=get_command_pattern('watermark', 'edit', lang)))
    async def handle_watermark(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            if not event.message.is_reply:
                await send_message(event, get_message('reply_required'))
                return
            watermark_text = event.pattern_match.group(1)
            reply_msg = await event.get_reply_message()
            if not reply_msg.video:
                await send_message(event, get_message('no_video'))
                return
            file_path = await reply_msg.download_media()
            if os.path.getsize(file_path) > 20 * 1024 * 1024:  # 20 مگابایت
                await send_message(event, get_message('file_too_large'))
                os.remove(file_path)
                return
            video = VideoFileClip(file_path)
            if watermark_text:
                watermark = TextClip(watermark_text, fontsize=24, color='white', bg_color='black').set_position(('center', 'bottom')).set_duration(video.duration)
                final_video = CompositeVideoClip([video, watermark])
            else:
                logo_path = await get_logo()
                if not logo_path:
                    await send_message(event, get_message('no_logo_set'))
                    video.close()
                    os.remove(file_path)
                    return
                logo = Image.open(logo_path).convert('RGBA')
                logo = logo.resize((int(video.w * 0.2), int(video.h * 0.2)))
                logo.save('logo.png')
                logo_clip = ImageClip('logo.png').set_position(('center', 'bottom')).set_duration(video.duration)
                final_video = CompositeVideoClip([video, logo_clip])
            final_video.write('output.mp4')
            await client.send_file(event.chat_id, 'output.mp4')
            await send_message(event, get_message('watermark_applied', text=watermark_text or 'لوگو'))
            video.close()
            final_video.close()
            os.remove(file_path)
            os.remove('output.mp4')
            if not watermark_text:
                os.remove('logo.png')
        except Exception as e:
            logger.error(f"Error applying watermark: {e}")
            await send_message(event, get_message('error_occurred'))

    await db.close()