import asyncio, json,os ,sys
from telethon import TelegramClient

current_dir = os.path.dirname(__file__)  # users/123456
root_dir = os.path.abspath(os.path.join(current_dir, '../../'))  # root/
main_path = os.path.join(root_dir, 'self')
if main_path not in sys.path:
    sys.path.insert(0, main_path)

from modules.profile import register_profile_handlers
from modules.settings import setup_settings
from modules.manage import register_manage_handlers
from modules.group import register_group_handlers
from modules.utils import load_json
from modules.convert import register_convert_handlers
from modules.download import register_download_handlers
from modules.edit import register_edit_handlers
from modules.enemy import register_enemy_handlers
from modules.fresponse import register_fast_response_handlers
from modules.fun import register_fun_handlers
from modules.private import register_private_handlers
from modules.vars import register_vars_handlers


async def main():
    credentials = load_json('credentials.json')
    api_id = credentials['api_id']
    api_hash = credentials['api_hash']
    session_name = credentials['session_name']
    owner_id = credentials['owner_id']

    client = TelegramClient(session_name, api_id, api_hash)

    async with client:
        # اگر لاگین نشده، مستقیم از credentials.json بخون
        if not await client.is_user_authorized():
            phone = credentials.get("phone")
            code = credentials.get("code")

            if not phone:
                raise Exception("⚠️ شماره تلفن در credentials.json پیدا نشد.")
            await client.send_code_request(phone)

            if not code:
                raise Exception("⚠️ کد لاگین در credentials.json پیدا نشد. لطفاً اضافه کن و دوباره اجرا کن.")
            await client.sign_in(phone, code)

        me = await client.get_me()
        print(f"Credentials loaded: {json.dumps(credentials, indent=2, ensure_ascii=False)}")
        print("🚀 سلف ربات با موفقیت راه‌اندازی شد!")
        print(f"📱 اکانت: {me.first_name}")

        # ثبت هندلرها
        await register_profile_handlers(client, session_name, owner_id)
        await setup_settings(client)
        await register_manage_handlers(client, session_name, owner_id)
        await register_group_handlers(client, session_name, owner_id)
        await register_vars_handlers(client, session_name, owner_id)
        await register_private_handlers(client, session_name, owner_id)
        await register_fun_handlers(client, session_name, owner_id)
        await register_fast_response_handlers(client, session_name, owner_id)
        await register_enemy_handlers(client, session_name, owner_id)
        await register_edit_handlers(client, session_name, owner_id)
        await register_download_handlers(client, session_name, owner_id)
        await register_convert_handlers(client, session_name, owner_id)

        await client.run_until_disconnected()


if __name__ == '__main__':
    asyncio.run(main())
