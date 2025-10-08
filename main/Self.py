import asyncio, json,os ,sys
import aiosqlite
from telethon import TelegramClient,connection

current_dir = os.path.dirname(__file__)  # users/123456
root_dir = os.path.abspath(os.path.join(current_dir, '../../'))  # root/
main_path = os.path.join(root_dir, 'main')
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
    proxy = (
        "54.38.136.78", 4044,
        "eeff0ce99b756ea156e1774d930f40bd21"
    )
    client = TelegramClient(session_name, api_id, api_hash,connection=connection.ConnectionTcpMTProxyRandomizedIntermediate,proxy=proxy)

    phone = credentials.get("phone")
    code = credentials.get("code")

    if not phone:
        print("⚠️ شماره تلفن در credentials.json پیدا نشد.")
        return

    await client.connect()

    if not await client.is_user_authorized():
        if code:
            try:
                await client.sign_in(phone=phone, code=code)
                print("✅ لاگین با موفقیت انجام شد.")
                await client.session.save()

                credentials["authorized"] = True
                with open('credentials.json', 'w') as f:
                    json.dump(credentials, f, indent=2, ensure_ascii=False)


            except Exception as e:
                print(f"خطا در ورود: {e}")
                await client.disconnect()
                return
        else:
            print("⚠️ کد لاگین هنوز در credentials.json وجود ندارد. لطفاً با ربات کد را وارد کنید.")
            try:
                await client.send_code_request(phone)
                print("✅ کد SMS ارسال شد.")
            except Exception as e:
                print(f"خطا در ارسال کد: {e}")
            finally:
                await client.disconnect()
            return
    else:
        print("✅ اکانت قبلاً لاگین شده است.")

    me = await client.get_me()
    print(f"Credentials loaded: {json.dumps(credentials, indent=2, ensure_ascii=False)}")
    print("🚀 سلف ربات با موفقیت راه‌اندازی شد!")
    print(f"📱 اکانت: {me.first_name}")

    # Initialize database
    async with aiosqlite.connect('selfbot.db') as db:
        await db.execute('''
                         CREATE TABLE IF NOT EXISTS settings (
                                                                 id INTEGER PRIMARY KEY,
                                                                 bio TEXT DEFAULT '',
                                                                 username TEXT DEFAULT '',
                                                                 first_name TEXT DEFAULT '',
                                                                 last_name TEXT DEFAULT '',
                                                                 profile_photo INTEGER DEFAULT 0
                         )
                         ''')
        cursor = await db.execute('SELECT COUNT(*) FROM settings')
        count = (await cursor.fetchone())[0]
        if count == 0:
            await db.execute('INSERT INTO settings (id) VALUES (1)')
        await db.commit()
    print("Database initialized.")

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
    print("📴 ارتباط با تلگرام قطع شد. در حال خروج از برنامه...")
    await client.disconnect()
    sys.exit(0)



if __name__ == '__main__':
    asyncio.run(main())