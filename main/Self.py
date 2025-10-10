import asyncio, json,os ,sys
import sqlite3  # Sync for init
import aiosqlite
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError, PhoneCodeExpiredError, PhoneCodeInvalidError

current_dir = os.path.dirname(__file__)  # users/123456
root_dir = os.path.abspath(os.path.join(current_dir, '../../'))  # root/
main_path = os.path.join(root_dir, 'main')
if main_path not in sys.path:
    sys.path.insert(0, main_path)

# Import load_json function
from modules.utils import load_json

# Load credentials first to get session_name
credentials = load_json('credentials.json')
session_name = credentials['session_name']
db_path = f'selfbot_{session_name}.db'
conn = sqlite3.connect(db_path)
cursor = conn.cursor()
cursor.execute('''
               CREATE TABLE IF NOT EXISTS settings (
                                                       id INTEGER PRIMARY KEY,
                                                       lang TEXT DEFAULT 'fa',
                                                       welcome_enabled BOOLEAN DEFAULT 0,
                                                       welcome_text TEXT DEFAULT '',
                                                       welcome_delete_time INTEGER DEFAULT 0,
                                                       clock_enabled BOOLEAN DEFAULT 0,
                                                       clock_location TEXT DEFAULT 'name',
                                                       clock_bio_text TEXT DEFAULT '',
                                                       clock_fonts TEXT DEFAULT '[1]',
                                                       clock_timezone TEXT DEFAULT 'Asia/Tehran',
                                                       action_enabled BOOLEAN DEFAULT 0,
                                                       action_types TEXT DEFAULT '{}',
                                                       text_format_enabled BOOLEAN DEFAULT 0,
                                                       text_formats TEXT DEFAULT '{}',
                                                       locks TEXT DEFAULT '{}',
                                                       antilog_enabled BOOLEAN DEFAULT 0,
                                                       first_comment_enabled BOOLEAN DEFAULT 0,
                                                       first_comment_text TEXT DEFAULT ''
               )
               ''')
cursor.execute('SELECT COUNT(*) FROM settings')
count = cursor.fetchone()[0]
if count == 0:
    cursor.execute('INSERT INTO settings (id) VALUES (1)')
conn.commit()
conn.close()
print("Database initialized (sync).")

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


async def save_credentials(credentials, filename='credentials.json'):
    with open(filename, 'w') as f:
        json.dump(credentials, f, indent=2)


async def main():
    credentials_file = 'credentials.json'
    credentials = load_json(credentials_file)
    api_id = credentials['api_id']
    api_hash = credentials['api_hash']
    session_name = credentials['session_name']
    owner_id = credentials['owner_id']
    client = TelegramClient(session_name, api_id, api_hash)
    phone = credentials.get("phone")
    code = credentials.get("code")
    phone_code_hash = credentials.get("phone_code_hash")

    if not phone:
        print("⚠️ شماره تلفن در credentials.json پیدا نشد.")
        return

    # Use client.start to handle session automatically
    try:
        if code and phone_code_hash:
            # Custom start with code
            await client.start(phone=phone, code_callback=lambda: code, code_hash_callback=lambda: phone_code_hash)
        else:
            await client.start(phone=phone)
        print("✅ لاگین با موفقیت انجام شد یا session موجود است.")
        # Clear temp fields after successful login
        credentials['code'] = None
        credentials['phone_code_hash'] = None
        await save_credentials(credentials, credentials_file)
    except SessionPasswordNeededError:
        print("❌ رمز عبور 2FA مورد نیاز است.")
        password = input("Enter 2FA password: ")
        await client.sign_in(password=password)
        credentials['code'] = None
        credentials['phone_code_hash'] = None
        await save_credentials(credentials, credentials_file)
    except (PhoneCodeExpiredError, PhoneCodeInvalidError) as e:
        print(f"⚠️ خطا در کد: {e}. پاک کردن session و ارسال کد جدید...")
        # Delete session file to force re-login
        session_file = f"{session_name}.session"
        if os.path.exists(session_file):
            os.remove(session_file)
        try:
            result = await client.send_code_request(phone)
            credentials['phone_code_hash'] = result.phone_code_hash
            await save_credentials(credentials, credentials_file)
            print("✅ کد جدید ارسال شد. لطفاً کد جدید را از ربات وارد کنید.")
            return  # Exit to wait for restart
        except Exception as e:
            print(f"خطا در ارسال کد: {e}")
            return
    except Exception as e:
        print(f"خطا در لاگین: {e}")
        return

    me = await client.get_me()
    print(f"Credentials loaded: {json.dumps(credentials, indent=2, ensure_ascii=False)}")
    print("🚀 سلف ربات با موفقیت راه‌اندازی شد!")
    print(f"📱 اکانت: {me.first_name}")

    # Async DB check (optional, since sync init done)
    async with aiosqlite.connect(db_path) as db:
        await db.commit()  # Ensure
    print("Database ready.")

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