import json
import logging
import os

import pytz
from deep_translator import GoogleTranslator

logger = logging.getLogger(__name__)


def save_data(filename, data):
    try:
        with open(filename, "w", encoding="utf-8") as f:
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
        with open(filename, "r", encoding="utf-8") as f:
            data = json.load(f)
        print(f"Loaded data from {filename}: {data}")
        return data if data else (default or {})
    except Exception as e:
        print(f"Error loading {filename}: {e}")
        return default or {}


def load_json(filename, default=None):
    """
    Load a JSON file trying multiple likely locations:
    - Absolute path as given
    - CWD-relative (as given)
    - Next to this utils.py (main/modules/<filename>)
    - One directory up (main/<filename>)
    Returns default ({} by default) if not found or on error.
    """
    candidates = []
    try:
        if os.path.isabs(filename):
            candidates.append(filename)
        else:
            # as given (CWD relative)
            candidates.append(filename)
            base_dir = os.path.dirname(__file__)  # .../main/modules
            # next to utils.py (main/modules)
            candidates.append(os.path.join(base_dir, filename))
            # parent directory (main)
            candidates.append(os.path.join(os.path.dirname(base_dir), filename))

        for path in candidates:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return data if data else (default or {})
            except FileNotFoundError:
                continue
            except Exception:
                continue
        return default or {}
    except Exception:
        return default or {}


def get_message(key, lang="fa", **kwargs):
    messages = load_json("msg.json", {})
    text = messages.get(lang, {}).get(key, key)
    return text.format(**kwargs)


def get_command_pattern(key, section=None, lang="fa"):
    """
    Fetch a command regex pattern from cmd.json.

    Supports two calling styles:
    - New: get_command_pattern(key, section, lang)
    - Legacy: get_command_pattern(key, lang) → section is None
    """
    commands = load_json("cmd.json", {})
    # New style with explicit section
    if section is not None:
        return commands.get(lang, {}).get(section, {}).get(key, r"^(?!)$")
    # Legacy style where only key and lang were provided
    return commands.get(lang, {}).get(key, r"^(?!)$")


def get_persian_date():
    try:
        import jdatetime

        now = jdatetime.datetime.now()
        return now.strftime("%Y/%m/%d")
    except ImportError:
        return "نیاز به نصب jdatetime"


def format_duration(seconds):
    if seconds < 60:
        return f"{seconds} ثانیه"
    elif seconds < 3600:
        return f"{seconds // 60} دقیقه"
    else:
        return f"{seconds // 3600} ساعت"


def translate_text(text, dest="fa"):
    try:
        translator = GoogleTranslator(source="auto", target=dest)
        return translator.translate(text)
    except:
        return get_message("error_occurred", lang="fa")


async def send_message(event, text, parse_mode=None, buttons=None, **kwargs):
    """
    ارسال پیام با پشتیبانی از parse_mode و buttons (بدون reply_markup برای Telethon)
    """
    try:
        if hasattr(event, "respond"):
            await event.respond(text, parse_mode=parse_mode, buttons=buttons, **kwargs)
            return True
        # fallback
        return False
    except Exception as e:
        logger.error(f"Error sending message: {e}")
        return False


def get_language(settings, default="fa"):
    """
    دریافت زبان از تنظیمات یا مقدار پیش‌فرض
    """
    return settings.get("lang", default)


async def is_command_message(message_text, lang, commands_data=None):
    """
    بررسی می‌کند که آیا متن پیام با الگوی هر command منطبق است یا نه
    """
    if not message_text:
        return False

    if commands_data is None:
        commands_data = load_json("cmd.json", {})

    import re

    all_commands = commands_data.get(lang, {})

    # بررسی همه sections های command
    for section_name, section_commands in all_commands.items():
        if isinstance(section_commands, dict):
            for command_key, pattern in section_commands.items():
                if pattern and re.match(pattern, message_text.strip(), re.IGNORECASE):
                    return True
    return False


async def upload_to_backup_channel(client, channel_id, file_path, caption=None):
    """
    آپلود فایل به کانال پشتیبان و برگرداندن ID فایل
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


def command_handler(commands_data, lang="fa"):
    """
    Decorator برای command handlerها که از اجرای تکراری جلوگیری می‌کند
    """

    def decorator(func):
        async def wrapper(event):
            message_text = event.message.text or ""

            # بررسی اینکه آیا پیام یک command است یا نه
            if await is_command_message(message_text, lang, commands_data):
                # اگر پیام یک command است، اجازه بده که handler مخصوص خودش اجرا بشه
                # و جلوی handlerهای عمومی رو بگیر
                try:
                    from telethon.events import StopPropagation

                    raise StopPropagation
                except ImportError:
                    # اگر StopPropagation در دسترس نیست، از return استفاده کن
                    return await func(event)

            # اگر پیام command نیست، اجازه بده که handler عمومی اون رو پردازش کنه
            return await func(event)

        return wrapper

    return decorator
