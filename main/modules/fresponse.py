import asyncio
import logging
import re
from datetime import datetime

from models import get_database, load_settings, update_settings
from telethon import events
from telethon.errors import FloodWaitError
from telethon.tl.functions.messages import SendReactionRequest
from telethon.tl.types import InputMediaUploadedDocument
from utils import get_command_pattern, load_json, send_message

logger = logging.getLogger(__name__)


async def register_fast_response_handlers(client, session_name, owner_id):
    db = await get_database(session_name)
    settings = await load_settings(db)
    if not settings:
        logger.error("Failed to load settings for fast response handlers")
        await db.close()
        return

    lang = settings.get("lang", "fa")
    messages = load_json("msg.json")
    commands = load_json("cmd.json")

    def get_message(key, **kwargs):
        try:
            return messages[lang]["fast_response"].get(key, "").format(**kwargs)
        except KeyError:
            # Fallback to English if the language key doesn't exist
            return (
                messages.get("en", {})
                .get("fast_response", {})
                .get(key, "")
                .format(**kwargs)
            )

    # تنظیمات اولیه fast_response
    if "fast_response" not in settings:
        settings["fast_response"] = {
            "enabled": True,
            "response_time": 1,  # زمان تأخیر پیش‌فرض (ثانیه)
            "mode": "normal",  # normal, sudo, others, edit, multi, search, reply, command
            "responses": {},  # {word: {'response': str/list, 'mode': str, 'sticker': str, 'voice': str}}
        }
        await update_settings(db, settings)

    # ایجاد جدول برای پاسخ‌های سریع (در صورت پشتیبانی DB)
    has_db_exec = hasattr(db, "execute")
    if has_db_exec:
        await db.execute("""
                         CREATE TABLE IF NOT EXISTS fast_responses (
                                                                   word TEXT,
                                                                   response TEXT,
                                                                   mode TEXT,
                                                                   sticker TEXT,
                                                                   voice TEXT,
                                                                   PRIMARY KEY (word, mode)
                           )
                         """)
        if hasattr(db, "commit"):
            await db.commit()

    async def save_response(word, response, mode, sticker=None, voice=None):
        """ذخیره پاسخ سریع در پایگاه داده"""
        try:
            if has_db_exec:
                await db.execute(
                    """
                    INSERT OR REPLACE INTO fast_responses (word, response, mode, sticker, voice)
                    VALUES (?, ?, ?, ?, ?)
                """,
                    (word, str(response), mode, sticker, voice),
                )
                if hasattr(db, "commit"):
                    await db.commit()
            settings["fast_response"]["responses"][word] = {
                "response": response,
                "mode": mode,
                "sticker": sticker,
                "voice": voice,
            }
            await update_settings(db, settings)
        except Exception as e:
            logger.error(f"Error saving response: {e}")

    async def get_response(word, mode):
        """دریافت پاسخ سریع از پایگاه داده"""
        try:
            if has_db_exec:
                cursor = await db.execute(
                    "SELECT response, sticker, voice FROM fast_responses WHERE word = ? AND mode = ?",
                    (word, mode),
                )
                result = await cursor.fetchone()
                await cursor.close()
                return result
            # بدون DB → از settings درون حافظه
            data = settings["fast_response"]["responses"].get(word)
            if data and data.get("mode") == mode:
                return (data.get("response"), data.get("sticker"), data.get("voice"))
            return None
        except Exception as e:
            logger.error(f"Error getting response: {e}")
            return None

    async def delete_response(word, mode):
        """حذف پاسخ سریع"""
        try:
            if has_db_exec:
                await db.execute(
                    "DELETE FROM fast_responses WHERE word = ? AND mode = ?",
                    (word, mode),
                )
                if hasattr(db, "commit"):
                    await db.commit()
            if word in settings["fast_response"]["responses"]:
                del settings["fast_response"]["responses"][word]
                await update_settings(db, settings)
        except Exception as e:
            logger.error(f"Error deleting response: {e}")

    async def list_responses():
        """لیست تمام پاسخ‌های سریع"""
        try:
            if has_db_exec:
                cursor = await db.execute(
                    "SELECT word, response, mode FROM fast_responses"
                )
                rows = await cursor.fetchall()
                await cursor.close()
                return [(row[0], row[1], row[2]) for row in rows]
            # بدون DB از settings استفاده کن
            return [
                (w, d.get("response"), d.get("mode"))
                for w, d in settings["fast_response"]["responses"].items()
            ]
        except Exception as e:
            logger.error(f"Error listing responses: {e}")
            return []

    # غیرفعال کردن پاسخ‌های سریع
    @client.on(
        events.NewMessage(
            pattern=get_command_pattern("fast_response_off", "fast_response", lang)
        )
    )
    async def handle_fast_response_off(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message("unauthorized"))
                return
            settings["fast_response"]["enabled"] = False
            await update_settings(db, settings)
            await send_message(event, get_message("fast_response_disabled"))
        except Exception as e:
            logger.error(f"Error disabling fast response: {e}")
            await send_message(event, get_message("error_occurred"))

    # فعال کردن پاسخ‌های سریع
    @client.on(
        events.NewMessage(
            pattern=get_command_pattern("fast_response_on", "fast_response", lang)
        )
    )
    async def handle_fast_response_on(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message("unauthorized"))
                return
            settings["fast_response"]["enabled"] = True
            await update_settings(db, settings)
            await send_message(event, get_message("fast_response_enabled"))
        except Exception as e:
            logger.error(f"Error enabling fast response: {e}")
            await send_message(event, get_message("error_occurred"))

    # تنظیم زمان پاسخ
    @client.on(
        events.NewMessage(
            pattern=get_command_pattern("set_response_time", "fast_response", lang)
        )
    )
    async def handle_set_response_time(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message("unauthorized"))
                return
            delay = int(event.pattern_match.group(1))
            settings["fast_response"]["response_time"] = delay
            await update_settings(db, settings)
            await send_message(event, get_message("response_time_set", delay=delay))
        except ValueError:
            await send_message(event, get_message("invalid_response_format"))
        except Exception as e:
            logger.error(f"Error setting response time: {e}")
            await send_message(event, get_message("error_occurred"))

    # افزودن پاسخ سریع
    @client.on(
        events.NewMessage(
            pattern=get_command_pattern("add_response", "fast_response", lang)
        )
    )
    async def handle_add_response(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message("unauthorized"))
                return
            match = re.match(r"'([^']+)'\s+(.+)", event.pattern_match.group(1))
            if not match:
                await send_message(event, get_message("invalid_response_format"))
                return
            word, response = match.groups()
            mode = settings["fast_response"]["mode"]
            if mode in ["edit", "multi"]:
                response = response.split(",")
            await save_response(word, response, mode)
            await send_message(
                event,
                get_message(
                    f"{mode}_response_added", word=word, response=response, mode=mode
                ),
            )
        except Exception as e:
            logger.error(f"Error adding response: {e}")
            await send_message(event, get_message("error_occurred"))

    # حذف پاسخ سریع
    @client.on(
        events.NewMessage(
            pattern=get_command_pattern("delete_response", "fast_response", lang)
        )
    )
    async def handle_delete_response(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message("unauthorized"))
                return
            word = event.pattern_match.group(1)
            mode = settings["fast_response"]["mode"]
            if await get_response(word, mode):
                await delete_response(word, mode)
                await send_message(
                    event, get_message(f"{mode}_response_deleted", word=word)
                )
            else:
                await send_message(event, get_message("response_not_found", word=word))
        except Exception as e:
            logger.error(f"Error deleting response: {e}")
            await send_message(event, get_message("error_occurred"))

    # نمایش لیست پاسخ‌ها
    @client.on(
        events.NewMessage(
            pattern=get_command_pattern("list_responses", "fast_response", lang)
        )
    )
    async def handle_list_responses(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message("unauthorized"))
                return
            responses = await list_responses()
            if responses:
                response_list = "\n".join(
                    [
                        f"{word}: {response} ({mode})"
                        for word, response, mode in responses
                    ]
                )
                await send_message(
                    event, get_message("responses_list", list=response_list)
                )
            else:
                await send_message(event, get_message("no_responses"))
        except Exception as e:
            logger.error(f"Error listing responses: {e}")
            await send_message(event, get_message("error_occurred"))

    # پاکسازی پاسخ‌ها
    @client.on(
        events.NewMessage(
            pattern=get_command_pattern("clear_responses", "fast_response", lang)
        )
    )
    async def handle_clear_responses(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message("unauthorized"))
                return
            if has_db_exec:
                await db.execute("DELETE FROM fast_responses")
                if hasattr(db, "commit"):
                    await db.commit()
            settings["fast_response"]["responses"] = {}
            await update_settings(db, settings)
            await send_message(event, get_message("responses_cleared"))
        except Exception as e:
            logger.error(f"Error clearing responses: {e}")
            await send_message(event, get_message("error_occurred"))

    # دریافت اطلاعات پاسخ
    @client.on(
        events.NewMessage(
            pattern=get_command_pattern("get_response", "fast_response", lang)
        )
    )
    async def handle_get_response(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message("unauthorized"))
                return
            word = event.pattern_match.group(1)
            mode = settings["fast_response"]["mode"]
            result = await get_response(word, mode)
            if result:
                response, sticker, voice = result
                await send_message(
                    event,
                    get_message(
                        "response_info", word=word, mode=mode, response=response
                    ),
                )
            else:
                await send_message(
                    event, get_message("response_info_not_found", word=word)
                )
        except Exception as e:
            logger.error(f"Error getting response info: {e}")
            await send_message(event, get_message("error_occurred"))

    # تنظیم حالت‌ها
    @client.on(
        events.NewMessage(
            pattern=get_command_pattern("set_sudo_mode", "fast_response", lang)
        )
    )
    async def handle_set_sudo_mode(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message("unauthorized"))
                return
            settings["fast_response"]["mode"] = "sudo"
            await update_settings(db, settings)
            await send_message(event, get_message("sundo_mode_enabled"))
        except Exception as e:
            logger.error(f"Error setting sudo mode: {e}")
            await send_message(event, get_message("error_occurred"))

    @client.on(
        events.NewMessage(
            pattern=get_command_pattern("set_others_mode", "fast_response", lang)
        )
    )
    async def handle_set_others_mode(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message("unauthorized"))
                return
            settings["fast_response"]["mode"] = "others"
            await update_settings(db, settings)
            await send_message(event, get_message("others_mode_enabled"))
        except Exception as e:
            logger.error(f"Error setting others mode: {e}")
            await send_message(event, get_message("error_occurred"))

    @client.on(
        events.NewMessage(
            pattern=get_command_pattern("set_normal_mode", "fast_response", lang)
        )
    )
    async def handle_set_normal_mode(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message("unauthorized"))
                return
            settings["fast_response"]["mode"] = "normal"
            await update_settings(db, settings)
            await send_message(event, get_message("normal_mode_enabled"))
        except Exception as e:
            logger.error(f"Error setting normal mode: {e}")
            await send_message(event, get_message("error_occurred"))

    @client.on(
        events.NewMessage(
            pattern=get_command_pattern("set_edit_mode", "fast_response", lang)
        )
    )
    async def handle_set_edit_mode(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message("unauthorized"))
                return
            settings["fast_response"]["mode"] = "edit"
            await update_settings(db, settings)
            await send_message(event, get_message("edit_mode_enabled"))
        except Exception as e:
            logger.error(f"Error setting edit mode: {e}")
            await send_message(event, get_message("error_occurred"))

    @client.on(
        events.NewMessage(
            pattern=get_command_pattern("set_multi_mode", "fast_response", lang)
        )
    )
    async def handle_set_multi_mode(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message("unauthorized"))
                return
            settings["fast_response"]["mode"] = "multi"
            await update_settings(db, settings)
            await send_message(event, get_message("multi_mode_enabled"))
        except Exception as e:
            logger.error(f"Error setting multi mode: {e}")
            await send_message(event, get_message("error_occurred"))

    @client.on(
        events.NewMessage(
            pattern=get_command_pattern("set_search_mode", "fast_response", lang)
        )
    )
    async def handle_set_search_mode(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message("unauthorized"))
                return
            settings["fast_response"]["mode"] = "search"
            await update_settings(db, settings)
            await send_message(event, get_message("search_mode_enabled"))
        except Exception as e:
            logger.error(f"Error setting search mode: {e}")
            await send_message(event, get_message("error_occurred"))

    @client.on(
        events.NewMessage(
            pattern=get_command_pattern("set_reply_mode", "fast_response", lang)
        )
    )
    async def handle_set_reply_mode(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message("unauthorized"))
                return
            settings["fast_response"]["mode"] = "reply"
            await update_settings(db, settings)
            await send_message(event, get_message("reply_mode_enabled"))
        except Exception as e:
            logger.error(f"Error setting reply mode: {e}")
            await send_message(event, get_message("error_occurred"))

    @client.on(
        events.NewMessage(
            pattern=get_command_pattern("set_command_mode", "fast_response", lang)
        )
    )
    async def handle_set_command_mode(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message("unauthorized"))
                return
            settings["fast_response"]["mode"] = "command"
            await update_settings(db, settings)
            await send_message(event, get_message("command_mode_enabled"))
        except Exception as e:
            logger.error(f"Error setting command mode: {e}")
            await send_message(event, get_message("error_occurred"))

    # افزودن استیکر یا ویس
    @client.on(
        events.NewMessage(
            pattern=get_command_pattern("add_response", "fast_response", lang)
        )
    )
    async def handle_add_sticker_voice(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message("unauthorized"))
                return
            if event.message.sticker or event.message.voice:
                word = event.pattern_match.group(1).split()[0]
                mode = settings["fast_response"]["mode"]
                sticker = event.message.sticker.id if event.message.sticker else None
                voice = event.message.voice.id if event.message.voice else None
                await save_response(word, None, mode, sticker=sticker, voice=voice)
                if sticker:
                    await send_message(
                        event, get_message("sticker_response_added", word=word)
                    )
                elif voice:
                    await send_message(
                        event, get_message("voice_response_added", word=word)
                    )
        except Exception as e:
            logger.error(f"Error adding sticker/voice response: {e}")
            await send_message(event, get_message("error_occurred"))

    # پاسخ‌های آماده
    @client.on(
        events.NewMessage(
            pattern=get_command_pattern("sun_response", "fast_response", lang)
        )
    )
    async def handle_sun_response(event):
        try:
            await send_message(event, "☀️")
            await send_message(event, get_message("sun_response_triggered"))
        except Exception as e:
            logger.error(f"Error triggering sun response: {e}")

    @client.on(
        events.NewMessage(
            pattern=get_command_pattern("heart_response", "fast_response", lang)
        )
    )
    async def handle_heart_response(event):
        try:
            await client(
                SendReactionRequest(
                    peer=event.chat_id, msg_id=event.message.id, reaction="❤️"
                )
            )
            await send_message(event, get_message("heart_response_triggered"))
        except Exception as e:
            logger.error(f"Error triggering heart response: {e}")

    @client.on(
        events.NewMessage(
            pattern=get_command_pattern("edit_response_1", "fast_response", lang)
        )
    )
    async def handle_edit_response_1(event):
        try:
            msg = await send_message(event, "پاسخ 1")
            for text in ["پاسخ 2", "پاسخ 3"]:
                await asyncio.sleep(settings["fast_response"]["response_time"])
                await msg.edit(text)
            await send_message(event, get_message("edit_response_1_triggered"))
        except Exception as e:
            logger.error(f"Error triggering edit response 1: {e}")

    @client.on(
        events.NewMessage(
            pattern=get_command_pattern("edit_response_2", "fast_response", lang)
        )
    )
    async def handle_edit_response_2(event):
        try:
            msg = await send_message(event, "آغاز")
            for text in ["ادامه", "پایان"]:
                await asyncio.sleep(settings["fast_response"]["response_time"])
                await msg.edit(text)
            await send_message(event, get_message("edit_response_2_triggered"))
        except Exception as e:
            logger.error(f"Error triggering edit response 2: {e}")

    # حالت بندری
    @client.on(
        events.NewMessage(pattern=get_command_pattern("bandari", "fast_response", lang))
    )
    async def handle_bandari(event):
        try:
            actions = [
                client.send_message(event.chat_id, action="typing"),
                client.send_message(event.chat_id, action="playing"),
                client.send_message(event.chat_id, action="recording"),
                client.send_message(event.chat_id, action="uploading_video"),
            ]
            for _ in range(15):
                for action in actions:
                    await action
                    await asyncio.sleep(1)
            await send_message(event, get_message("bandari_triggered"))
        except Exception as e:
            logger.error(f"Error triggering bandari: {e}")
            await send_message(event, get_message("error_occurred"))

    # مدیریت پیام‌های ورودی برای پاسخ سریع
    @client.on(events.NewMessage)
    async def handle_incoming_message(event):
        try:
            if not settings["fast_response"]["enabled"]:
                return

            # بررسی اینکه آیا پیام یک command است یا نه
            from utils import is_command_message

            if await is_command_message(event.message.text or "", lang):
                return
            mode = settings["fast_response"]["mode"]
            text = event.message.text.lower() if event.message.text else ""
            responses = settings["fast_response"]["responses"]

            for word, data in responses.items():
                if data["mode"] == "sudo" and event.sender_id != owner_id:
                    continue
                if data["mode"] == "others" and event.sender_id == owner_id:
                    continue
                if data["mode"] == "reply" and not event.message.is_reply:
                    continue
                if data["mode"] == "search" and word.lower() not in text:
                    continue
                if (
                    data["mode"] in ["normal", "sudo", "others", "reply", "command"]
                    and text != word.lower()
                ):
                    continue

                if data["sticker"]:
                    await client.send_file(event.chat_id, data["sticker"])
                elif data["voice"]:
                    await client.send_file(event.chat_id, data["voice"])
                elif data["mode"] == "edit":
                    msg = await send_message(event, data["response"][0])
                    for response in data["response"][1:]:
                        await asyncio.sleep(settings["fast_response"]["response_time"])
                        await msg.edit(response)
                elif data["mode"] == "multi":
                    for response in data["response"]:
                        await send_message(event, response)
                        await asyncio.sleep(settings["fast_response"]["response_time"])
                else:
                    await send_message(event, data["response"])
        except FloodWaitError as e:
            logger.error(f"Flood wait error: {e.seconds} seconds")
            await asyncio.sleep(e.seconds)
        except Exception as e:
            logger.error(f"Error handling incoming message: {e}")

    await db.close()
