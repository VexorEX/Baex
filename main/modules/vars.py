import asyncio
import logging
import random
import re
from datetime import datetime

import pytz
from models import get_database, load_settings, update_settings
from ormax_models import init_db as init_ormax_db
from telethon import events
from telethon.errors import FloodWaitError
from utils import get_command_pattern, load_json, send_message

logger = logging.getLogger(__name__)


async def register_vars_handlers(client, session_name, owner_id):
    # Initialize Ormax database
    await init_ormax_db()
    db = await get_database(session_name)
    settings = await load_settings()
    if not settings:
        logger.error("Failed to load settings for vars handlers")
        return

    lang = settings.get("lang", "fa")
    messages = load_json("msg.json")
    commands = load_json("cmd.json")

    def get_message(key, **kwargs):
        return messages.get(lang, {}).get("vars", {}).get(key, key).format(**kwargs)

    # Note: These tables are not migrated to Ormax yet
    # They will continue to use the old database connection
    pass

    # متغیرهای پیش‌فرض
    if "vars" not in settings:
        settings["vars"] = {"timezone": "Asia/Tehran"}  # منطقه زمانی پیش‌فرض
        await update_settings(settings)

    # لیست قلب‌های تصادفی
    hearts = ["❤️", "🧡", "💛", "💚", "💙", "💜", "💓", "💞", "💕", "💗"]

    # تابع جایگزینی متغیرها
    async def replace_vars(text, event):
        try:
            user = await event.get_sender()
            timezone = settings["vars"].get("timezone", "Asia/Tehran")
            tz = pytz.timezone(timezone)
            now = datetime.now(tz)

            # متغیرهای زمانی
            replacements = {
                "STRDAY": now.strftime("%A"),  # روز به حروف
                "STRMONTH": now.strftime("%B"),  # ماه به حروف
                "YEAR": str(now.year),  # سال
                "MONTH": str(now.month).zfill(2),  # ماه به عدد
                "DATE": now.strftime("%Y/%m/%d"),  # تاریخ کامل
                "TIME": now.strftime("%H:%M:%S"),  # زمان کامل
                "SEC": str(now.second).zfill(2),  # ثانیه
                "MIN": str(now.minute).zfill(2),  # دقیقه
                "HOUR": str(now.hour).zfill(2),  # ساعت
                "DAY": str(now.day).zfill(2),  # روز به عدد
                "ID": str(user.id),  # شناسه کاربر
                "USERNAME": user.username or "None",  # نام کاربری
                "NAME": user.first_name or "Unknown",  # نام کاربر
                "HEART": random.choice(hearts),  # قلب تصادفی
            }

            # متغیر RANDNUM
            randnum_matches = re.findall(r"RANDNUM(\d+)-(\d+)", text)
            for start, end in randnum_matches:
                try:
                    num = random.randint(int(start), int(end))
                    text = text.replace(f"RANDNUM{start}-{end}", str(num))
                except ValueError:
                    continue

            # متغیر RANK
            if "RANK" in text:
                # Note: ranks table operations are not migrated to Ormax yet
                rank = None
                text = text.replace("RANK", rank if rank else get_message("no_rank"))

            # متغیر WARNS
            if "WARNS" in text:
                # Note: warns table operations are not migrated to Ormax yet
                warn_count = None
                text = text.replace("WARNS", str(warn_count if warn_count else 0))

            # جایگزینی سایر متغیرها
            for key, value in replacements.items():
                text = text.replace(key, value)

            return text
        except Exception as e:
            logger.error(f"Error replacing vars: {e}")
            return text

    # نمایش لیست مناطق زمانی
    @client.on(events.NewMessage(pattern=get_command_pattern("list_timezones", lang)))
    async def handle_list_timezones(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message("unauthorized"))
                return
            timezones = pytz.all_timezones
            response = get_message("timezone_list") + "\n".join(
                timezones[:50]
            )  # محدود به 50 مورد برای جلوگیری از پیام طولانی
            await send_message(event, response)
        except Exception as e:
            logger.error(f"Error listing timezones: {e}")
            await send_message(event, get_message("error_occurred"))

    # تنظیم منطقه زمانی
    @client.on(events.NewMessage(pattern=get_command_pattern("set_timezone", lang)))
    async def handle_set_timezone(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message("unauthorized"))
                return
            timezone = event.pattern_match.group(1)
            if not timezone or timezone not in pytz.all_timezones:
                await send_message(event, get_message("invalid_timezone"))
                return
            settings["vars"]["timezone"] = timezone
            await update_settings(settings)
            # Note: vars_settings table operations are not migrated to Ormax yet
            await send_message(event, get_message("timezone_set", timezone=timezone))
        except Exception as e:
            logger.error(f"Error setting timezone: {e}")
            await send_message(event, get_message("error_occurred"))

    # تنظیم مقام
    @client.on(events.NewMessage(pattern=get_command_pattern("set_rank", lang)))
    async def handle_set_rank(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message("unauthorized"))
                return
            if not event.message.is_reply:
                await send_message(event, get_message("reply_required"))
                return
            rank = event.pattern_match.group(1)
            if not rank:
                await send_message(event, get_message("no_rank_provided"))
                return
            reply_msg = await event.get_reply_message()
            user_id = reply_msg.sender_id
            # Note: ranks table operations are not migrated to Ormax yet
            pass
            await send_message(
                event, get_message("rank_set", user_id=user_id, rank=rank)
            )
        except FloodWaitError as e:
            await send_message(event, get_message("flood_wait", seconds=e.seconds))
        except Exception as e:
            logger.error(f"Error setting rank: {e}")
            await send_message(event, get_message("error_occurred"))

    # نمایش لیست مقام‌ها
    @client.on(events.NewMessage(pattern=get_command_pattern("list_ranks", lang)))
    async def handle_list_ranks(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message("unauthorized"))
                return
            # Note: ranks table operations are not migrated to Ormax yet
            ranks = []
            if not ranks:
                await send_message(event, get_message("no_ranks"))
                return
            response = get_message("rank_list") + "\n"
            for user_id, rank in ranks:
                user = await client.get_entity(user_id)
                response += f"@{user.username or user_id}: {rank}\n"
            await send_message(event, response)
        except FloodWaitError as e:
            await send_message(event, get_message("flood_wait", seconds=e.seconds))
        except Exception as e:
            logger.error(f"Error listing ranks: {e}")
            await send_message(event, get_message("error_occurred"))

    # تابع عمومی برای پردازش متغیرها در پیام‌ها
    @client.on(events.NewMessage)
    async def handle_message_with_vars(event):
        try:
            if event.sender_id != owner_id:
                return

            # بررسی اینکه آیا پیام یک command است یا نه
            from utils import is_command_message

            if await is_command_message(event.text or "", lang):
                return

            text = event.text
            if any(
                var in text
                for var in [
                    "STRDAY",
                    "STRMONTH",
                    "YEAR",
                    "MONTH",
                    "DATE",
                    "TIME",
                    "SEC",
                    "MIN",
                    "HOUR",
                    "DAY",
                    "ID",
                    "USERNAME",
                    "NAME",
                    "HEART",
                    "RANDNUM",
                    "RANK",
                    "WARNS",
                ]
            ):
                processed_text = await replace_vars(text, event)
                await send_message(event, processed_text)
        except Exception as e:
            logger.error(f"Error processing message with vars: {e}")

    # db.close() not needed with Ormax
