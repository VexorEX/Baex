fromtelethon import events, types
from telethon.tl.functions.messages import ReadHistoryRequest, ForwardMessagesRequest
from telethon.tl.functions.channels import JoinChannelRequest
from telethon.tl.functions.account import UpdateStatusRequest
from telethon.tl.types import SendMessageTypingAction, SendMessageUploadVideoAction
fromdeep_translator import GoogleTranslator
from utils import load_json, send_message, get_language
from models import load_settings, update_settings, init_db
import aiosqlite


async def setup_settings(client, db_path):
    """Set up the settings component with command and event handlers."""
    # Initialize Ormax databaseawait init_db(None)

    messages = load_json("msg.json")
    commands = load_json("cmd.json")
    async with aiosqlite.connect(db_path) as db:
        settings = await load_settings()

    lang = settings.get("lang", "fa")
    if lang not in commands:
       lang = "en"

    def get_message(key, **kwargs):
        """Get formatted message for the current language."""
        try:
            # Fallback if lang or key missing
            if (
                lang not in messages
                or "settings" not in messages[lang]
                or key not in messages[lang]["settings"]
            ):
                return f"[Message {key} not found]"
            return messages[lang]["settings"].get(key, "").format(**kwargs)
        except KeyError:
            # Fallback to English if the language key doesn't exist
            return (
                messages.get("en", {}).get("settings", {}).get(key, "").format(**kwargs)
            )

    def get_pattern(key):
        """Safe get for command pattern with fallback."""
        return commands.get(lang, {}).get("settings", {}).get(key, "")

    # Helper function to toggle settings
    async def toggle_setting(event, setting_key, chat_id, status):
        if setting_key not in settings:
            settings[setting_key] = {}
        settings[setting_key][chat_id] = status == "روشن" or status == "on"
        await update_settings("settings", settings)
        emoji = "✅" if settings[setting_key][chat_id] else "❌"
        await send_message(
            event, get_message(f"{setting_key}_toggle", status=status, emoji=emoji)
        )

    async def toggle_global_setting(event, setting_key, status):
        settings[setting_key] = status == "روشن" or status == "on"
        await update_settings("settings", settings)
        emoji = "✅" if settings[setting_key]else "❌"
        await send_message(
            event, get_message(f"{setting_key}_toggle", status=status, emoji=emoji)
        )

    # Command handlers (all with get_pattern)
    @client.on(events.NewMessage(pattern=get_pattern("self_toggle")))
    async def handle_self_toggle(event):
        status =event.pattern_match.group(1)
        chat_id = event.chat_id
        await toggle_setting(event, "self_enabled", chat_id, status)

    @client.on(events.NewMessage(pattern=get_pattern("self_global_toggle")))
    async def handle_self_global_toggle(event):
        status = event.pattern_match.group(1)
       await toggle_global_setting(event, "self_global_enabled", status)

    @client.on(events.NewMessage(pattern=get_pattern("poker_toggle")))
    async def handle_poker_toggle(event):
        status = event.pattern_match.group(1)
        chat_id = event.chat_id
        await toggle_setting(event, "poker_enabled", chat_id, status)

    @client.on(events.NewMessage(pattern=get_pattern("poker_global_toggle")))
    async def handle_poker_global_toggle(event):
        status = event.pattern_match.group(1)
        await toggle_global_setting(event, "poker_global_enabled", status)

    @client.on(events.NewMessage(pattern=get_pattern("save_toggle")))
    async def handle_save_toggle(event):
        status = event.pattern_match.group(1)
        chat_id = event.chat_id
        await toggle_setting(event, "save_enabled", chat_id, status)

    @client.on(events.NewMessage(pattern=get_pattern("save_pv_toggle")))
    async def handle_save_pv_toggle(event):
        status = event.pattern_match.group(1)
        chat_id = event.chat_id
        await toggle_setting(event, "save_pv_enabled", chat_id, status)

    @client.on(events.NewMessage(pattern=get_pattern("save_realm_set")))
    async def handle_save_realm_set(event):
        if event.is_reply:
            reply_msg = await event.get_reply_message()
            settings["save_realm"] = reply_msg.chat_id
            await update_settings("settings", settings)
            await send_message(event, get_message("save_realm_set"))
        else:
            await send_message(event, get_message("reply_to_message"))

    @client.on(events.NewMessage(pattern=get_pattern("save_pv_realm_set")))
    async def handle_save_pv_realm_set(event):
        if event.is_reply:
            reply_msg = await event.get_reply_message()
            settings["save_pv_realm"] = reply_msg.chat_id
            await update_settings("settings", settings)
            await send_message(event, get_message("save_pv_realm_set"))
        else:
            await send_message(event, get_message("reply_to_message"))

    @client.on(events.NewMessage(pattern=get_pattern("save_profile_toggle")))
    async def handle_save_profile_toggle(event):
        status = event.pattern_match.group(1)
        chat_id = event.chat_id
        await toggle_setting(event, "save_profile_enabled", chat_id, status)

    @client.on(events.NewMessage(pattern=get_pattern("save_profile_realm_set")))
    async def handle_save_profile_realm_set(event):
        if event.is_reply:
            reply_msg = await event.get_reply_message()
            settings["save_profile_realm"] = reply_msg.chat_id
            await update_settings("settings", settings)
            await send_message(event, get_message("save_profile_realm_set"))
        else:
            await send_message(event, get_message("reply_to_message"))

    @client.on(events.NewMessage(pattern=get_pattern("typing_toggle")))
    async def handle_typing_toggle(event):
        status = event.pattern_match.group(1)
        chat_id = event.chat_id
        await toggle_setting(event, "typing_enabled", chat_id, status)

    @client.on(events.NewMessage(pattern=get_pattern("typing_global_toggle")))
    async def handle_typing_global_toggle(event):
        status = event.pattern_match.group(1)
        await toggle_global_setting(event, "typing_global_enabled", status)

    @client.on(events.NewMessage(pattern=get_pattern("action_toggle")))
    async def handle_action_toggle(event):
        status = event.pattern_match.group(1)
        chat_id = event.chat_id
        await toggle_setting(event, "action_enabled", chat_id, status)

    @client.on(events.NewMessage(pattern=get_pattern("action_global_toggle")))
    async def handle_action_global_toggle(event):
        status = event.pattern_match.group(1)
        await toggle_global_setting(event, "action_global_enabled", status)

    @client.on(events.NewMessage(pattern=get_pattern("tick_toggle")))
    async def handle_tick_toggle(event):
        status = event.pattern_match.group(1)
        chat_id = event.chat_id
        await toggle_setting(event, "tick_enabled", chat_id, status)

    @client.on(events.NewMessage(pattern=get_pattern("tick_global_toggle")))
    async def handle_tick_global_toggle(event):
        status = event.pattern_match.group(1)
        await toggle_global_setting(event, "tick_global_enabled", status)

    @client.on(events.NewMessage(pattern=get_pattern("tick_group_toggle")))
    async def handle_tick_group_toggle(event):
        status = event.pattern_match.group(1)
        await toggle_global_setting(event, "tick_group_enabled", status)

    @client.on(events.NewMessage(pattern=get_pattern("tick_pv_toggle")))
    async def handle_tick_pv_toggle(event):
        status = event.pattern_match.group(1)
        await toggle_global_setting(event, "tick_pv_enabled", status)

    @client.on(events.NewMessage(pattern=get_pattern("tick_channel_toggle")))
    async def handle_tick_channel_toggle(event):
        status = event.pattern_match.group(1)
        await toggle_global_setting(event, "tick_channel_enabled", status)

    @client.on(events.NewMessage(pattern=get_pattern("tag_toggle")))
    async def handle_tag_toggle(event):
        status = event.pattern_match.group(1)
        chat_id = event.chat_id
        await toggle_setting(event, "tag_enabled", chat_id, status)

    @client.on(events.NewMessage(pattern=get_pattern("tag_global_toggle")))
    async def handle_tag_global_toggle(event):
        status = event.pattern_match.group(1)
        await toggle_global_setting(event, "tag_global_enabled", status)

    @client.on(events.NewMessage(pattern=get_pattern("translate_mode_toggle")))
    async def handle_translate_mode_toggle(event):
        status = event.pattern_match.group(1)
        chat_id = event.chat_id
        await toggle_setting(event, "translate_mode_enabled", chat_id, status)

    @client.on(events.NewMessage(pattern=get_pattern("translate_mode_realm_set")))
    async def handle_translate_mode_realm_set(event):
        if event.is_reply:
            reply_msg = await event.get_reply_message()
            settings["translate_mode_realm"] = reply_msg.chat_id
            await update_settings("settings", settings)
            await send_message(event, get_message("translate_mode_realm_set"))
        else:
            await send_message(event, get_message("reply_to_message"))

    @client.on(events.NewMessage(pattern=get_pattern("translate_toggle")))
    async def handle_translate_toggle(event):
        status= event.pattern_match.group(1)
        chat_id = event.chat_id
        await toggle_setting(event, "translate_enabled", chat_id, status)

    @client.on(events.NewMessage(pattern=get_pattern("set_language")))
    async def handle_set_language(event):
        lang_code = event.pattern_match.group(1)
        settings["lang"] = lang_code
        await update_settings("settings", settings)
        await send_message(event, get_message("set_language", lang=lang_code))

    @client.on(events.NewMessage(pattern=get_pattern("list_languages")))
    async def handle_list_languages(event):
        languages = "\n".join(
           [f"🌐 {k}: {v}" for k, v in settings.get("languages", {}).items()]
        )
        await send_message(event, get_message("list_languages", languages=languages))

    @client.on(events.NewMessage(pattern=get_pattern("hashtag_toggle")))
    async def handle_hashtag_toggle(event):
        status = event.pattern_match.group(1)
        chat_id = event.chat_id
        await toggle_setting(event, "hashtag_enabled", chat_id, status)

    @client.on(events.NewMessage(pattern=get_pattern("hashtag_global_toggle")))
    async def handle_hashtag_global_toggle(event):
        status = event.pattern_match.group(1)
        await toggle_global_setting(event, "hashtag_global_enabled", status)

    @client.on(events.NewMessage(pattern=get_pattern("signature_toggle")))
    async def handle_signature_toggle(event):
        status = event.pattern_match.group(1)
        chat_id = event.chat_id
        await toggle_setting(event, "signature_enabled", chat_id, status)

    @client.on(events.NewMessage(pattern=get_pattern("signature_global_toggle")))
    async def handle_signature_global_toggle(event):
        status = event.pattern_match.group(1)
        await toggle_global_setting(event, "signature_global_enabled", status)

    @client.on(events.NewMessage(pattern=get_pattern("signature_set")))
    async def handle_signature_set(event):
        signature = event.pattern_match.group(1)
        settings["signature_text"] = signature
        await update_settings("settings", settings)
        await send_message(event, get_message("signature_set", signature=signature))

    @client.on(events.NewMessage(pattern=get_pattern("auto_approve_toggle")))
    async def handle_auto_approve_toggle(event):
        status = event.pattern_match.group(1)
        chat_id = event.chat_id
        await toggle_setting(event, "auto_approve_enabled", chat_id, status)

    @client.on(events.NewMessage(pattern=get_pattern("anti_login_toggle")))
    async def handle_anti_login_toggle(event):
        status = event.pattern_match.group(1)
        await toggle_global_setting(event, "anti_login_enabled", status)

    @client.on(events.NewMessage(pattern=get_pattern("anti_login_realm_set")))
    async def handle_anti_login_realm_set(event):
        if event.is_reply:
            reply_msg = await event.get_reply_message()
            settings["anti_login_realm"] = reply_msg.chat_id
            await update_settings("settings", settings)
            await send_message(event, get_message("anti_login_realm_set"))
        else:
            await send_message(event, get_message("reply_to_message"))

    @client.on(events.NewMessage(pattern=get_pattern("emoji_toggle")))
    async def handle_emoji_toggle(event):
        status = event.pattern_match.group(1)
        chat_id = event.chat_id
        await toggle_setting(event, "emoji_enabled", chat_id, status)

    @client.on(events.NewMessage(pattern=get_pattern("emoji_global_toggle")))
    async def handle_emoji_global_toggle(event):
        status = event.pattern_match.group(1)
        await toggle_global_setting(event, "emoji_global_enabled", status)

    @client.on(events.NewMessage(pattern=get_pattern("emoji_set")))
    async def handle_emoji_set(event):
        emoji = event.pattern_match.group(1)
        settings["emoji_text"] = emoji
        await update_settings("settings", settings)
        await send_message(event, get_message("emoji_set", emoji=emoji))

    @client.on(events.NewMessage(pattern=get_pattern("bold_toggle")))
    async def handle_bold_toggle(event):
        status = event.pattern_match.group(1)
        chat_id = event.chat_id
        await toggle_setting(event, "bold_enabled", chat_id, status)

    @client.on(events.NewMessage(pattern=get_pattern("bold_global_toggle")))
    async def handle_bold_global_toggle(event):
        status = event.pattern_match.group(1)
        await toggle_global_setting(event, "bold_global_enabled", status)

    @client.on(events.NewMessage(pattern=get_pattern("underline_toggle")))
    async def handle_underline_toggle(event):
        status = event.pattern_match.group(1)
        chat_id = event.chat_id
        await toggle_setting(event, "underline_enabled", chat_id, status)

    @client.on(events.NewMessage(pattern=get_pattern("underline_global_toggle")))
    async def handle_underline_global_toggle(event):
        status = event.pattern_match.group(1)
        await toggle_global_setting(event, "underline_global_enabled", status)

    @client.on(events.NewMessage(pattern=get_pattern("code_toggle")))
    async def handle_code_toggle(event):
        status = event.pattern_match.group(1)
        chat_id = event.chat_id
        await toggle_setting(event, "code_enabled", chat_id, status)

    @client.on(events.NewMessage(pattern=get_pattern("code_global_toggle")))
    async def handle_code_global_toggle(event):
        status = event.pattern_match.group(1)
        await toggle_global_setting(event, "code_global_enabled", status)

    @client.on(events.NewMessage(pattern=get_pattern("font_en_toggle")))
    async def handle_font_en_toggle(event):
        status = event.pattern_match.group(1)
        chat_id = event.chat_id
        await toggle_setting(event, "font_en_enabled", chat_id, status)

    @client.on(events.NewMessage(pattern=get_pattern("font_en_global_toggle")))
    async def handle_font_en_global_toggle(event):
        status = event.pattern_match.group(1)
        await toggle_global_setting(event,"font_en_global_enabled", status)

    @client.on(events.NewMessage(pattern=get_pattern("font_fa_toggle")))
    async def handle_font_fa_toggle(event):
        status = event.pattern_match.group(1)
        chat_id = event.chat_id
        await toggle_setting(event, "font_fa_enabled", chat_id, status)

    @client.on(events.NewMessage(pattern=get_pattern("font_fa_global_toggle")))
    async def handle_font_fa_global_toggle(event):
        status = event.pattern_match.group(1)
        await toggle_global_setting(event, "font_fa_global_enabled", status)

    @client.on(events.NewMessage(pattern=get_pattern("strikethrough_toggle")))
    async def handle_strikethrough_toggle(event):
        status = event.pattern_match.group(1)
        chat_id = event.chat_id
        await toggle_setting(event, "strikethrough_enabled", chat_id, status)

    @client.on(events.NewMessage(pattern=get_pattern("strikethrough_global_toggle")))
    async def handle_strikethrough_global_toggle(event):
        status = event.pattern_match.group(1)
        await toggle_global_setting(event, "strikethrough_global_enabled", status)

    @client.on(events.NewMessage(pattern=get_pattern("italic_toggle")))
    async def handle_italic_toggle(event):
        status = event.pattern_match.group(1)
        chat_id = event.chat_id
        await toggle_setting(event, "italic_enabled", chat_id, status)

    @client.on(events.NewMessage(pattern=get_pattern("italic_global_toggle")))
    async def handle_italic_global_toggle(event):
        status = event.pattern_match.group(1)
        await toggle_global_setting(event, "italic_global_enabled", status)

    @client.on(events.NewMessage(pattern=get_pattern("spoiler_toggle")))
    async def handle_spoiler_toggle(event):
        status = event.pattern_match.group(1)
        chat_id = event.chat_id
        await toggle_setting(event,"spoiler_enabled", chat_id, status)

    @client.on(events.NewMessage(pattern=get_pattern("spoiler_global_toggle")))
    async def handle_spoiler_global_toggle(event):
        status = event.pattern_match.group(1)
        await toggle_global_setting(event, "spoiler_global_enabled", status)

    @client.on(events.NewMessage(pattern=get_pattern("reaction_toggle")))
    async def handle_reaction_toggle(event):
        status = event.pattern_match.group(1)
        chat_id = event.chat_id
        await toggle_setting(event, "reaction_enabled", chat_id, status)

    @client.on(events.NewMessage(pattern=get_pattern("reaction_set")))
    async def handle_reaction_set(event):
        reaction = event.pattern_match.group(1)
        settings["reaction_text"] = reaction
        await update_settings("settings", settings)
        await send_message(event, get_message("reaction_set", reaction=reactions))

    # Event handlers
    @client.on(events.NewMessage)
    async def handle_new_message(event):
        if not settings["self_global_enabled"] and not settings["self_enabled"].get(
            event.chat_id, False
        ):
            return

        chat_id = event.chat_id
        message = event.message

        # Poker feature
        if (
            settings["poker_global_enabled"]
            or settings["poker_enabled"].get(chat_id, False)
        ) and message.text == "😐":
            await send_message(event, "😐")

        # Save messages
        if settings["save_enabled"].get(chat_id, False) or (
            isinstance(event.chat, types.User)
            and settings["save_pv_enabled"].get(chat_id, False)
        ):
            realm_id = (
                settings["save_realm"]
                if not isinstance(event.chat, types.User)
                else settings["save_pv_realm"]
            )
            if realm_id:
                await client(
                    ForwardMessagesRequest(
                        from_peer=event.chat_id, to_peer=realm_id, id=[message.id]
                    )
                )

        # Typing and action
        if settings["typing_global_enabled"] or settings["typing_enabled"].get(
            chat_id, False
        ):
            await client.send_read_acknowledge(event.chat_id, message)
            await client.send_message(event.chat_id, action=SendMessageTypingAction())

        if settings["action_global_enabled"] or settings["action_enabled"].get(
            chat_id, False
        ):
            if message.media:
                await client.send_message(
                    event.chat_id, action=SendMessageUploadVideoAction()
                )
            else:
               await client.send_message(
                    event.chat_id, action=SendMessageTypingAction()
                )

        # Tick (mark as read)
        if (
            settings["tick_global_enabled"]
            or settings["tick_enabled"].get(chat_id, False)
            or (isinstance(event.chat, types.User) and settings["tick_pv_enabled"])
            or (
                isinstance(event.chat, types.Channel)
                and settings["tick_channel_enabled"]
            )
            or (isinstance(event.chat, types.Chat) and settings["tick_group_enabled"])
        ):
            await client(ReadHistoryRequest(peer=event.chat_id))

        # Tag handling
        if (
           settings["tag_global_enabled"]
            or settings["tag_enabled"].get(chat_id, False)
        ) and message.mentioned:
            await client(ReadHistoryRequest(peer=event.chat_id))

        # Translate mode
        if (
            settings["translate_mode_enabled"].get(chat_id, False)
            and settings["translate_mode_realm"]
        ):
            if message.text:
                translated = GoogleTranslator(
                    source="auto", target=settings["lang"]
                ).translate(message.text)
                await client.send_message(settings["translate_mode_realm"], translated)

        # Reaction
        if settings["reaction_enabled"].get(chat_id, False):
            await client.send_reaction(
                event.chat_id, message.id, settings["reaction_text"]
            )

    @client.on(events.UserUpdate)
    async def handle_user_update(event):
        if settings.get("save_profile_enabled", {}).get(
            event.chat_id, False
        ) and settings.get("save_profile_realm"):
            if event.photo:
                await client.download_profile_photo(
                    event.user_id, file=settings["save_profile_realm"]
                )

    @client.on(events.ChatAction)
    async def handle_chat_action(event):
        if (
            settings["auto_approve_enabled"].get(event.chat_id, False)
            and event.user_added
        ):
            await client(JoinChannelRequest(event.chat_id))

    @client.on(events.NewMessage(pattern=r"(\d{5})"))
    async def handle_anti_login(event):
        if settings["anti_login_enabled"] and settings["anti_login_realm"]:
            await client(
                ForwardMessagesRequest(
from_peer=event.chat_id,
                    to_peer=settings["anti_login_realm"],
                    id=[event.message.id],
                )
            )
            await event.message.delete()

    @client.on(events.NewMessage(outgoing=True))
    async def handle_outgoing_message(event):
        chat_id = event.chat_id
        text =event.message.text

        if not settings["self_global_enabled"] and not settings["self_enabled"].get(
            chat_id, False
        ):
            return

        # Translate outgoing messages
        if settings["translate_enabled"].get(chat_id, False):
            translated = GoogleTranslator(
                source="auto", target=settings["lang"]
            ).translate(text)
            await event.message.edit(translated)
            text = translated

        # Formatting
        entities = []
        if settings["bold_global_enabled"] or settings["bold_enabled"].get(
            chat_id, False
        ):
            entities.append(types.MessageEntityBold(0, len(text)))
        if settings["underline_global_enabled"] or settings["underline_enabled"].get(
            chat_id, False
        ):
            entities.append(types.MessageEntityUnderline(0, len(text)))
        if settings["code_global_enabled"] or settings["code_enabled"].get(
            chat_id, False
        ):
            entities.append(types.MessageEntityCode(0, len(text)))
        if settings["strikethrough_global_enabled"] or settings[
            "strikethrough_enabled"
        ].get(chat_id, False):
            entities.append(types.MessageEntityStrike(0, len(text)))
        if settings["italic_global_enabled"] or settings["italic_enabled"].get(
            chat_id, False
        ):
            entities.append(types.MessageEntityItalic(0, len(text)))
        if settings["spoiler_global_enabled"] or settings["spoiler_enabled"].get(
            chat_id, False
        ):
            entities.append(types.MessageEntitySpoiler(0, len(text)))

        # Font transformations (simplified, can be extended with custom mappings)
        if settings["font_en_global_enabled"] or settings["font_en_enabled"].get(
            chat_id, False
        ):
            text = text.replace("a", "𝑎").replace(
                "b", "𝑏"
            )  #Add more mappings as needed
        if settings["font_fa_global_enabled"] or settings["font_fa_enabled"].get(
            chat_id, False
        ):
            text = text.replace("ا", "آ").replace(
                "ب", "پ"
            )  # Add more mappings as needed

        # Hashtag
        if settings["hashtag_global_enabled"] or settings["hashtag_enabled"].get(
            chat_id, False
        ):
            words = text.split()
            text = " ".join(f"#{word}" for word in words)

        # Signature
        if settings["signature_global_enabled"] or settings["signature_enabled"].get(
            chat_id, False
        ):
            text += f"\n{settings['signature_text']}"

        # Emoji
        if settings["emoji_global_enabled"] or settings["emoji_enabled"].get(
            chat_id, False
        ):
            emoji_parts = settings["emoji_text"].split("-")
            if len(emoji_parts) == 2:
                text = f"{emoji_parts[0]}{text}{emoji_parts[1]}"

        if text != event.message.text or entities:
            await event.message.edit(text, parse_mode="html", entities=entities)
