import json, os, pytz
import logging

from deep_translator import GoogleTranslator

logger = logging.getLogger(__name__)

def save_data(filename, data):
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"Successfully saved {filename}")
        return True
    except Exception as e:
        print(f"Error saving {filename}: {e}")
        return False

def load_data(filename, default=None):
    try:
        print(f"Attempting to load file: {os.path.abspath(filename)}")
        if not os.path.exists(filename):
            raise FileNotFoundError(f"{filename} does not exist")
        with open(filename, 'r', encoding='utf-8') as f:
            data = json.load(f)
        print(f"Loaded data from {filename}: {data}")
        return data if data else (default or {})
    except Exception as e:
        print(f"Error loading {filename}: {e}")
        return default or {}

def load_json(filename,default=None):
    """
Load JSON file with fallback paths.
    First tries absolute path from main folder, then tries relative path.
    """
    # Absolute path from main folder (original approach)
    main_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../main'))
    file_path = os.path.join(main_dir, filename)
    
    # Try absolute path first
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            print(f"Loaded {filename}: {len(data)} keys") # Debug
            return data
        except Exception as e:
            print(f"Warning: Failed to load {file_path}, error: {e}")
    
    # Fallback to relative path
    if os.path.exists(filename):
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return data if data else (default or {})
        except Exception as e:
            print(f"Warning: Failed to load {filename} with relative path, error: {e}")
    
    print(f"Warning: {filename} not found in any path, returning default")
    return default or {}

def get_message(key, lang='fa', **kwargs):
    messages = load_json('msg.json')
    text = messages.get(lang, {}).get(key, key)
    return text.format(**kwargs)

def get_command_pattern(key, module='profile', lang='fa'):
    commands = load_json('cmd.json')
    return commands.get(lang, {}).get(module, {}).get(key, '')

def get_persian_date():
    try:
        import jdatetime
        now = jdatetime.datetime.now()
        return now.strftime('%Y/%m/%d')
    except ImportError:
        return "نیاز به نصب jdatetime"

def format_duration(seconds):
    if seconds < 60:
        return f"{seconds} ثانیه"
    elif seconds < 3600:
        return f"{seconds // 60} دقیقه"
    else:
        return f"{seconds // 3600} ساعت"

def translate_text(text, dest='fa'):
    try:
        translator= GoogleTranslator(source='auto', target=dest)
        return translator.translate(text)
    except:
        return get_message('error_occurred', lang='fa')

async def send_message(event, text, parse_mode=None, reply_markup=None,**kwargs):
    """
ارسال پیام با پشتیبانی از parse_mode و reply_markup
    """
    try:
        if isinstance(event, int):  # اگر event یک chat_id است
            await event.send_message(text, parse_mode=parse_mode, reply_markup=reply_markup,**kwargs)
        else:
            await event.respond(text, parse_mode=parse_mode, reply_markup=reply_markup, **kwargs)
        return True
    except Exception as e:
        logger.error(f"Error sending message: {e}")
        return False

def get_language(settings, default='fa'):
    """
   دریافت زبان از تنظیماتیا مقدار پیش‌فرض
    """
    return settings.get('lang', default)

async def upload_to_backup_channel(client, channel_id, file_path, caption=None):
    """
    آپلود فایلبه کانال پشتیبان و برگرداندن IDفایل
    """
    try:
        if caption:
            message = await client.send_file(channel_id, file_path, caption=caption)
        else:
            message = await client.send_file(channel_id, file_path)
        return message.file.id if message and message.file else None
    except Exception as e:
        logger.error(f"Error uploading to backup channel: {e}")
        return None