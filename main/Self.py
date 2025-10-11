import asyncio, json, os, sys
import sqlite3
import aiosqlite
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError, PhoneCodeExpiredError, PhoneCodeInvalidError

# مسیرها
current_dir = os.path.dirname(__file__)
root_dir = os.path.abspath(os.path.join(current_dir, '../../'))
main_path = os.path.join(root_dir, 'main')
if main_path not in sys.path:
    sys.path.insert(0, main_path)

# ابزارها و هندلرها
from modules.utils import load_json
from modules.profile import register_profile_handlers
from modules.settings import setup_settings
from modules.manage import register_manage_handlers
from modules.group import register_group_handlers
from modules.convert import register_convert_handlers
from modules.download import register_download_handlers
from modules.edit import register_edit_handlers
from modules.enemy import register_enemy_handlers
from modules.fun import register_fun_handlers
from modules.private import register_private_handlers
from modules.vars import register_vars_handlers
from modules.fresponse import register_fast_response_handlers

# ذخیره credentials
async def save_credentials(credentials, filename='credentials.json'):
    with open(filename, 'w') as f:
        json.dump(credentials, f, indent=2)

# مقداردهی اولیه دیتابیس SQLite (sync)
def init_sqlite_db(db_path):
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
    # بررسی وجود رکورد با id=1
    cursor.execute('SELECT id FROM settings WHERE id = 1')
    if cursor.fetchone() is None:
        cursor.execute('INSERT INTO settings (id) VALUES (1)')
    conn.commit()
    conn.close()
    print("✅ دیتابیس SQLite مقداردهی شد.")

# تابع اصلی
async def main():
    credentials_file = 'credentials.json'
    credentials = load_json(credentials_file)
    api_id = credentials['api_id']
    api_hash = credentials['api_hash']
    session_name = credentials['session_name']
    owner_id = credentials['owner_id']
    phone = credentials.get("phone")
    code = credentials.get("code")
    phone_code_hash = credentials.get("phone_code_hash")

    if not phone:
        print("⚠️ شماره تلفن در credentials.json پیدا نشد.")
        return

    db_path = f'selfbot_{session_name}.db'
    init_sqlite_db(db_path)

    client = TelegramClient(session_name, api_id, api_hash)
    try:
        if code and phone_code_hash:
            await client.start(phone=phone, code_callback=lambda: code, code_hash_callback=lambda: phone_code_hash)
        else:
            await client.start(phone=phone)
        print("✅ لاگین موفق.")
        credentials['code'] = None
        credentials['phone_code_hash'] = None
        await save_credentials(credentials, credentials_file)
    except SessionPasswordNeededError:
        password = input("رمز 2FA را وارد کنید: ")
        await client.sign_in(password=password)
        credentials['code'] = None
        credentials['phone_code_hash'] = None
        await save_credentials(credentials, credentials_file)
    except (PhoneCodeExpiredError, PhoneCodeInvalidError) as e:
        print(f"⚠️ خطا در کد: {e}")
        session_file = f"{session_name}.session"
        if os.path.exists(session_file):
            os.remove(session_file)
        try:
            result = await client.send_code_request(phone)
            credentials['phone_code_hash'] = result.phone_code_hash
            await save_credentials(credentials, credentials_file)
            print("✅ کد جدید ارسال شد.")
            return
        except Exception as e:
            print(f"خطا در ارسال کد: {e}")
            return
    except Exception as e:
        print(f"خطا در لاگین: {e}")
        return

    me = await client.get_me()
    print(f"🚀 سلف‌بات راه‌اندازی شد برای: {me.first_name}")

    # اتصال async به دیتابیس
    async with aiosqlite.connect(db_path) as db:
        await db.commit()

    # ثبت هندلرها
    await register_profile_handlers(client, session_name, owner_id)
    await setup_settings(client,db_path)
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

# اجرای برنامه
if __name__ == '__main__':
    asyncio.run(main())
