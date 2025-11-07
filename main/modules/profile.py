import asyncio
import logging
import os
import random
import sys
from datetime import datetime

# Add the main directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

import pytz
from models import get_database, load_settings, update_settings
from telethon import events
from telethon.tl.functions.account import (
    UpdateProfileRequest,
    UpdateStatusRequest,
    UpdateUsernameRequest,
)
from telethon.tl.functions.channels import (
    UpdateUsernameRequest as UpdateChannelUsername,
)
from telethon.tl.functions.photos import DeletePhotosRequest, UploadProfilePhotoRequest
from utils import get_command_pattern, get_message

BASE_DIR = os.path.dirname(__file__)
logger = logging.getLogger(__name__)


async def update_dynamic_text(text, timezone="UTC"):
    """Replace dynamic variables like time and date"""
    tz = pytz.timezone(timezone)
    now = datetime.now(tz)
    replacements = {
        "time": now.strftime("%H:%M"),
        "date": now.strftime("%Y-%m-%d"),
        "day": now.strftime("%A"),
        "month": now.strftime("%B"),
    }

    for key, value in replacements.items():
        text = text.replace(key, value)
    return text


async def update_profile_loop(client,settings, owner_id):
    """Main loop for updating name, bio, and title with dynamic variables"""
    while True:
        try:
            if (
                settings["profile_settings"]["name_enabled"]
                and settings["profile_settings"]["names"]
            ):
                name = random.choice(settings["profile_settings"]["names"])
                name = await update_dynamic_text(
                    name, settings.get("clock_timezone", "UTC")
                )
                await client(UpdateProfileRequest(last_name=name))

            if (
                settings["profile_settings"]["bio_enabled"]
                and settings["profile_settings"]["bios"]
            ):
                bio = random.choice(settings["profile_settings"]["bios"])
                bio = await update_dynamic_text(
                    bio, settings.get("clock_timezone", "UTC")
                )
                await client(UpdateProfileRequest(about=bio))

            if (
                settings["profile_settings"]["title_enabled"]
                and settings["profile_settings"]["title"]
            ):
                title = random.choice(settings["profile_settings"]["title"])
                title = await update_dynamic_text(
                    title, settings.get("clock_timezone", "UTC")
                )
                # Update channel title if user is creator of any channel
                async for dialog in client.iter_dialogs():
                    if (
                        dialog.is_group
                        and hasattr(dialog.entity, "creator")
                        and dialog.entity.creator
                        and dialog.entity.id == owner_id
                    ):
                        try:
                            await client(
                                UpdateChannelUsername(
                                    channel=dialog.entity, username=title
                                )
                            )
                        except Exception as e:
                            logger.error(f"Failed to update channel title: {e}")
                            continue

            if settings["profile_settings"]["online_enabled"]:
                await client(UpdateStatusRequest(offline=False))
            else:
                await client(UpdateStatusRequest(offline=True))

            await asyncio.sleep(60)  # Update every minute
        except Exception as e:
            logger.error(f"Error in profile update loop: {e}")
            await asyncio.sleep(60)


async def register_profile_handlers(client, session_name, owner_id):

    @client.on(events.NewMessage('check'))
    async def check(event):
        print(event)

    db = await get_database(session_name)

    # Initialize the database
    from models import init_db

    await init_db(db)

    settings = await load_settings()
    if not settings:
        logger.error("Failed to load settings, cannot register profile handlers")
        await db.close()
        return

    lang = settings.get("lang", "fa")

    # Initialize profile settings if not present
    if "profile_settings" not in settings:
        settings["profile_settings"] = {
            "name_enabled": False,
            "bio_enabled": False,
            "status_enabled": False,
            "online_enabled": False,
            "title_enabled": False,
            "names": [],
            "bios": [],
            "statuses": [],
            "title": [],
        }
        await update_settings(settings)

    # Ensure profile_settings exists with default values
    profile_settings = settings.get("profile_settings", {})
    if not isinstance(profile_settings, dict):
        profile_settings = {
            "name_enabled": False,
            "bio_enabled": False,
            "status_enabled": False,
            "online_enabled": False,
            "title_enabled": False,
            "names": [],
            "bios": [],
            "statuses": [],
            "title": [],
        }
        settings["profile_settings"] = profile_settings

    # Start the profile update loop if any feature is enabled
    profile_settings = settings.get("profile_settings", {})
    if (
        profile_settings.get("name_enabled", False)
        or profile_settings.get("bio_enabled", False)
        or profile_settings.get("title_enabled", False)
    ):
        asyncio.create_task(update_profile_loop(client, settings, owner_id))

    @client.on(events.NewMessage(pattern=get_command_pattern("check", lang)))
    async def check(event):
        try:
            await event.reply("✅ Bot is working!")
            logger.info("Check command executed")
        except Exception as e:
            logger.error(f"Error in check command: {e}")

    @client.on(events.NewMessage(pattern=get_command_pattern("name_toggle", lang)))
    async def toggle_name(event):
        try:
            if event.sender_id != owner_id:
                await event.edit(get_message("unauthorized", lang), parse_mode="html")
                return

            db = await get_database(session_name)
            settings = await load_settings()
            status = event.pattern_match.group(1)
            status_value = status == "روشن" if lang == "fa" else status == "on"

            settings["profile_settings"]["name_enabled"] = status_value
            await update_settings(settings)

            status_text = (
                "روشن"
                if lang == "fa" and status_value
                else "خاموش"
                if lang == "fa"
                else "on"
                if status_value
                else "off"
            )
            emoji = "✅" if status_value else "❌"

            await event.edit(
                get_message("name_toggle", lang, status=status_text, emoji=emoji),
                parse_mode="html",
            )
            await db.close()
        except Exception as e:
            logger.error(f"Error toggling name: {e}")

    @client.on(events.NewMessage(pattern=get_command_pattern("add_name", lang)))
    async def add_name(event):
        try:
            if event.sender_id != owner_id:
                await event.edit(get_message("unauthorized", lang), parse_mode="html")
                return

            db = await get_database(session_name)
            settings = await load_settings()
            name = event.pattern_match.group(1)

            settings["profile_settings"]["names"].append(name)
            await update_settings(settings)

            await event.edit(
                get_message("name_added", lang, name=name), parse_mode="html"
            )
            await db.close()
        except Exception as e:
            logger.error(f"Error adding name: {e}")

    @client.on(events.NewMessage(pattern=get_command_pattern("delete_name", lang)))
    async def delete_name(event):
        try:
            if event.sender_id != owner_id:
                await event.edit(get_message("unauthorized", lang), parse_mode="html")
                return

            db = await get_database(session_name)
            settings = await load_settings()
            name = event.pattern_match.group(1)

            if name in settings["profile_settings"]["names"]:
                settings["profile_settings"]["names"].remove(name)
                await update_settings(settings)
                await event.edit(
                    get_message("name_deleted", lang, name=name), parse_mode="html"
                )
            else:
                await event.edit(
                    get_message("name_not_found", lang, name=name), parse_mode="html"
                )

            await db.close()
        except Exception as e:
            logger.error(f"Error deleting name: {e}")

    @client.on(events.NewMessage(pattern=get_command_pattern("clear_names", lang)))
    async def clear_names(event):
        try:
            if event.sender_id != owner_id:
                await event.edit(get_message("unauthorized", lang), parse_mode="html")
                return

            db = await get_database(session_name)
            settings = await load_settings()
            settings["profile_settings"]["names"] = []
            await update_settings(settings)

            await event.edit(get_message("names_cleared", lang), parse_mode="html")
            await db.close()
        except Exception as e:
            logger.error(f"Error clearing names: {e}")

    @client.on(events.NewMessage(pattern=get_command_pattern("list_names", lang)))
    async def list_names(event):
        try:
            if event.sender_id != owner_id:
                await event.edit(get_message("unauthorized", lang), parse_mode="html")
                return

            db = await get_database(session_name)
            settings = await load_settings()
            names = settings["profile_settings"]["names"]

            if names:
                names_list = "\n".join(
                    f"{i + 1}. {name}" for i, name in enumerate(names)
                )
                await event.edit(
                    get_message("names_list", lang, names=names_list), parse_mode="html"
                )
            else:
                await event.edit(get_message("no_names", lang), parse_mode="html")

            await db.close()
        except Exception as e:
            logger.error(f"Error listing names: {e}")

    @client.on(events.NewMessage(pattern=get_command_pattern("bio_toggle", lang)))
    async def toggle_bio(event):
        try:
            if event.sender_id != owner_id:
                await event.edit(get_message("unauthorized", lang), parse_mode="html")
                return

            db = await get_database(session_name)
            settings = await load_settings()
            status = event.pattern_match.group(1)
            status_value = status == "روشن" if lang == "fa" else status == "on"

            settings["profile_settings"]["bio_enabled"] = status_value
            await update_settings(settings)

            status_text = (
                "روشن"
                if lang == "fa" and status_value
                else "خاموش"
                if lang == "fa"
                else "on"
                if status_value
                else "off"
            )
            emoji = "✅" if status_value else "❌"

            await event.edit(
                get_message("bio_toggle", lang, status=status_text, emoji=emoji),
                parse_mode="html",
            )
            await db.close()
        except Exception as e:
            logger.error(f"Error toggling bio: {e}")

    @client.on(events.NewMessage(pattern=get_command_pattern("add_bio", lang)))
    async def add_bio(event):
        try:
            if event.sender_id != owner_id:
                await event.edit(get_message("unauthorized", lang), parse_mode="html")
                return

            db = await get_database(session_name)
            settings = await load_settings()
            bio = event.pattern_match.group(1)

            settings["profile_settings"]["bios"].append(bio)
            await update_settings(settings)

            await event.edit(get_message("bio_added", lang, bio=bio), parse_mode="html")
            await db.close()
        except Exception as e:
            logger.error(f"Error adding bio: {e}")

    @client.on(events.NewMessage(pattern=get_command_pattern("delete_bio", lang)))
    async def delete_bio(event):
        try:
            if event.sender_id != owner_id:
                await event.edit(get_message("unauthorized", lang), parse_mode="html")
                return

            db = await get_database(session_name)
            settings = await load_settings()
            bio = event.pattern_match.group(1)

            if bio in settings["profile_settings"]["bios"]:
                settings["profile_settings"]["bios"].remove(bio)
                await update_settings(settings)
                await event.edit(
                    get_message("bio_deleted", lang, bio=bio), parse_mode="html"
                )
            else:
                await event.edit(
                    get_message("bio_not_found", lang, bio=bio), parse_mode="html"
                )

            await db.close()
        except Exception as e:
            logger.error(f"Error deleting bio: {e}")

    @client.on(events.NewMessage(pattern=get_command_pattern("clear_bios", lang)))
    async def clear_bios(event):
        try:
            if event.sender_id != owner_id:
                await event.edit(get_message("unauthorized", lang), parse_mode="html")
                return

            db = await get_database(session_name)
            settings = await load_settings()
            settings["profile_settings"]["bios"] = []
            await update_settings(settings)

            await event.edit(get_message("bios_cleared", lang), parse_mode="html")
            await db.close()
        except Exception as e:
            logger.error(f"Error clearing bios: {e}")

    @client.on(events.NewMessage(pattern=get_command_pattern("list_bios", lang)))
    async def list_bios(event):
        try:
            if event.sender_id != owner_id:
                await event.edit(get_message("unauthorized", lang), parse_mode="html")
                return

            db = await get_database(session_name)
            settings = await load_settings()
            bios = settings["profile_settings"]["bios"]

            if bios:
                bios_list = "\n".join(f"{i + 1}. {bio}" for i, bio in enumerate(bios))
                await event.edit(
                    get_message("bios_list", lang, bios=bios_list), parse_mode="html"
                )
            else:
                await event.edit(get_message("no_bios", lang), parse_mode="html")

            await db.close()
        except Exception as e:
            logger.error(f"Error listing bios: {e}")

    @client.on(events.NewMessage(pattern=get_command_pattern("status_toggle", lang)))
    async def toggle_status(event):
        try:
            if event.sender_id != owner_id:
                await event.edit(get_message("unauthorized", lang), parse_mode="html")
                return

            db = await get_database(session_name)
            settings = await load_settings()
            status = event.pattern_match.group(1)
            status_value = status == "روشن" if lang == "fa" else status == "on"

            settings["profile_settings"]["status_enabled"] = status_value
            await update_settings(settings)

            status_text = (
                "روشن"
                if lang == "fa" and status_value
                else "خاموش"
                if lang == "fa"
                else "on"
                if status_value
                else "off"
            )
            emoji = "✅" if status_value else "❌"

            await event.edit(
                get_message("status_toggle", lang, status=status_text, emoji=emoji),
                parse_mode="html",
            )
            await db.close()
        except Exception as e:
            logger.error(f"Error toggling status: {e}")

    @client.on(events.NewMessage(pattern=get_command_pattern("add_status", lang)))
    async def add_status(event):
        try:
            if event.sender_id != owner_id:
                await event.edit(get_message("unauthorized", lang), parse_mode="html")
                return

            db = await get_database(session_name)
            settings = await load_settings()
            status = event.pattern_match.group(1)

            settings["profile_settings"]["statuses"].append(status)
            await update_settings(settings)

            await event.edit(
                get_message("status_added", lang, status=status), parse_mode="html"
            )
            await db.close()
        except Exception as e:
            logger.error(f"Error adding status: {e}")

    @client.on(events.NewMessage(pattern=get_command_pattern("delete_status", lang)))
    async def delete_status(event):
        try:
            if event.sender_id != owner_id:
                await event.edit(get_message("unauthorized", lang), parse_mode="html")
                return

            db = await get_database(session_name)
            settings = await load_settings()
            status = event.pattern_match.group(1)

            if status in settings["profile_settings"]["statuses"]:
                settings["profile_settings"]["statuses"].remove(status)
                await update_settings(settings)
                await event.edit(
                    get_message("status_deleted", lang, status=status),
                    parse_mode="html",
                )
            else:
                await event.edit(
                    get_message("status_not_found", lang, status=status),
                    parse_mode="html",
                )

            await db.close()
        except Exception as e:
            logger.error(f"Error deleting status: {e}")

    @client.on(events.NewMessage(pattern=get_command_pattern("clear_statuses", lang)))
    async def clear_statuses(event):
        try:
            if event.sender_id != owner_id:
                await event.edit(get_message("unauthorized", lang), parse_mode="html")
                return

            db = await get_database(session_name)
            settings = await load_settings()
            settings["profile_settings"]["statuses"] = []
            await update_settings(settings)

            await event.edit(get_message("statuses_cleared", lang), parse_mode="html")
            await db.close()
        except Exception as e:
            logger.error(f"Error clearing statuses: {e}")

    @client.on(events.NewMessage(pattern=get_command_pattern("list_statuses", lang)))
    async def list_statuses(event):
        try:
            if event.sender_id != owner_id:
                await event.edit(get_message("unauthorized", lang), parse_mode="html")
                return

            db = await get_database(session_name)
            settings = await load_settings()
            statuses = settings["profile_settings"]["statuses"]

            if statuses:
                statuses_list = "\n".join(
                    f"{i + 1}. {status}" for i, status in enumerate(statuses)
                )
                await event.edit(
                    get_message("statuses_list", lang, statuses=statuses_list),
                    parse_mode="html",
                )
            else:
                await event.edit(get_message("no_statuses", lang), parse_mode="html")

            await db.close()
        except Exception as e:
            logger.error(f"Error listing statuses: {e}")

    @client.on(events.NewMessage(pattern=get_command_pattern("online_toggle", lang)))
    async def toggle_online(event):
        try:
            if event.sender_id != owner_id:
                await event.edit(get_message("unauthorized", lang), parse_mode="html")
                return

            db = await get_database(session_name)
            settings = await load_settings()
            status = event.pattern_match.group(1)
            status_value = status == "روشن" if lang == "fa" else status == "on"

            settings["profile_settings"]["online_enabled"] = status_value
            await client(UpdateStatusRequest(offline=not status_value))
            await update_settings(settings)

            status_text = (
                "روشن"
                if lang == "fa" and status_value
                else "خاموش"
                if lang == "fa"
                else "on"
                if status_value
                else "off"
            )
            emoji = "✅" if status_value else "❌"

            await event.edit(
                get_message("online_toggle", lang, status=status_text, emoji=emoji),
                parse_mode="html",
            )
            await db.close()
        except Exception as e:
            logger.error(f"Error toggling online status: {e}")

    @client.on(events.NewMessage(pattern=get_command_pattern("title_toggle", lang)))
    async def toggle_title(event):
        try:
            if event.sender_id != owner_id:
                await event.edit(get_message("unauthorized", lang), parse_mode="html")
                return

            db = await get_database(session_name)
            settings = await load_settings()
            status = event.pattern_match.group(1)
            status_value = status == "روشن" if lang == "fa" else status == "on"

            settings["profile_settings"]["title_enabled"] = status_value
            await update_settings(settings)

            status_text = (
                "روشن"
                if lang == "fa" and status_value
                else "خاموش"
                if lang == "fa"
                else "on"
                if status_value
                else "off"
            )
            emoji = "✅" if status_value else "❌"

            await event.edit(
                get_message("title_toggle", lang, status=status_text, emoji=emoji),
                parse_mode="html",
            )
            await db.close()
        except Exception as e:
            logger.error(f"Error toggling title: {e}")

    @client.on(events.NewMessage(pattern=get_command_pattern("add_title", lang)))
    async def add_title(event):
        try:
            if event.sender_id != owner_id:
                await event.edit(get_message("unauthorized", lang), parse_mode="html")
                return

            db = await get_database(session_name)
            settings = await load_settings()
            title = event.pattern_match.group(1)

            settings["profile_settings"]["title"].append(title)
            await update_settings(settings)

            await event.edit(
                get_message("title_added", lang, title=title), parse_mode="html"
            )
            await db.close()
        except Exception as e:
            logger.error(f"Error adding title: {e}")

    @client.on(events.NewMessage(pattern=get_command_pattern("delete_title", lang)))
    async def delete_title(event):
        try:
            if event.sender_id != owner_id:
                await event.edit(get_message("unauthorized", lang), parse_mode="html")
                return

            db = await get_database(session_name)
            settings = await load_settings()
            title = event.pattern_match.group(1)

            if title in settings["profile_settings"]["title"]:
                settings["profile_settings"]["title"].remove(title)
                await update_settings(settings)
                await event.edit(
                    get_message("title_deleted", lang, title=title), parse_mode="html"
                )
            else:
                await event.edit(
                    get_message("title_not_found", lang, title=title), parse_mode="html"
                )

            await db.close()
        except Exception as e:
            logger.error(f"Error deleting title: {e}")

    @client.on(events.NewMessage(pattern=get_command_pattern("clear_titles", lang)))
    async def clear_titles(event):
        try:
            if event.sender_id != owner_id:
                await event.edit(get_message("unauthorized", lang), parse_mode="html")
                return

            db = await get_database(session_name)
            settings = await load_settings()
            settings["profile_settings"]["title"] = []
            await update_settings(settings)

            await event.edit(get_message("titles_cleared", lang), parse_mode="html")
            await db.close()
        except Exception as e:
            logger.error(f"Error clearing titles: {e}")

    @client.on(events.NewMessage(pattern=get_command_pattern("list_titles", lang)))
    async def list_titles(event):
        try:
            if event.sender_id != owner_id:
                await event.edit(get_message("unauthorized", lang), parse_mode="html")
                return

            db = await get_database(session_name)
            settings = await load_settings()
            titles = settings["profile_settings"]["title"]

            if titles:
                titles_list = "\n".join(
                    f"{i + 1}. {title}" for i, title in enumerate(titles)
                )
                await event.edit(
                    get_message("titles_list", lang, titles=titles_list),
                    parse_mode="html",
                )
            else:
                await event.edit(get_message("no_titles", lang), parse_mode="html")

            await db.close()
        except Exception as e:
            logger.error(f"Error listing titles: {e}")

    @client.on(events.NewMessage(pattern=get_command_pattern("delete_profile", lang)))
    async def delete_profile(event):
        try:
            if event.sender_id != owner_id:
                await event.edit(get_message("unauthorized", lang), parse_mode="html")
                return

            # Clear all profile settings
            settings = await load_settings()
            settings["profile_settings"] = {
                "name_enabled": False,
                "bio_enabled": False,
                "status_enabled": False,
                "online_enabled": False,
                "title_enabled": False,
                "names": [],
                "bios": [],
                "statuses": [],
                "title": [],
            }
            await update_settings(settings)
            await event.edit(get_message("profile_deleted", lang), parse_mode="html")
        except Exception as e:
            logger.error(f"Error deleting profile: {e}")

    await db.close()
