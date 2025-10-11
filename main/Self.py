import asyncio, json, os, sys
from datetime import datetime
import sqlite3
import aiosqlite
from telethon import TelegramClient, connection
from telethon.errors import SessionPasswordNeededError, PhoneCodeExpiredError, PhoneCodeInvalidError

# مسیرها
current_dir = os.path.dirname(__file__)
root_dir = os.path.abspath(os.path.join(current_dir, '../../'))
main_path = os.path.join(root_dir, 'main')
if main_path not in sys.path:
    sys.path.insert(0, main_path)

# ابزارها و هندلرها (بعد از init DB import می‌شن تا DB آماده باشه)
from modules.utils import load_json

# ذخیره credentials
async def save_credentials(credentials, filename='credentials.json'):
    with open(filename, 'w') as f:
        json.dump(credentials, f, indent=2)

# لاگ لاگین موفق
def log_login_success(session_name):
    with open('login_log.txt', 'a') as f:
        f.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - لاگین موفق برای {session_name}\n")
    print("✅ لاگین لاگ شد.")

# فیکس permissions recursive
def fix_permissions(dir_path):
    for root, dirs, files in os.walk(dir_path):
        for d in dirs:
            os.chmod(os.path.join(root, d), 0o777)
        for f in files:
            os.chmod(os.path.join(root, f), 0o666)
    print(f"Permissions fixed for {dir_path}.")

# مقداردهی اولیه دیتابیس SQLite (sync)
def init_sqlite_db(db_path):
    # Fix permissions for DB file and directory
    user_dir = os.path.dirname(db_path)
    fix_permissions(user_dir)
    if os.path.exists(db_path):
        os.chmod(db_path, 0o666)
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
    os.chmod(db_path, 0o666)  # Ensure writable
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

    proxy = ("54.38.136.78", 4044, "eeff0ce99b756ea156e1774d930f40bd21")
    client = TelegramClient(session_name, api_id, api_hash, connection=connection.ConnectionTcpMTProxyRandomizedIntermediate, proxy=proxy)

    try:
        await client.connect()
        if not await client.is_user_authorized():
            if code and phone_code_hash:
                try:
                    await client.sign_in(phone=phone, code=code, phone_code_hash=phone_code_hash)
                    print("✅ لاگین موفق.")
                    credentials['code'] = None
                    credentials['phone_code_hash'] = None
                    await save_credentials(credentials, credentials_file)
                    log_login_success(session_name)  # لاگ لاگین
                    # Fix readonly session file
                    session_file = f"{session_name}.session"
                    if os.path.exists(session_file):
                        os.chmod(session_file, 0o666)
                        print("Session file permissions fixed.")
                except (PhoneCodeExpiredError, PhoneCodeInvalidError, SessionPasswordNeededError) as e:
                    print(f"⚠️ خطا در کد/رمز: {e}. ارسال کد جدید...")
                    # پاک کردن session
                    session_file = f"{session_name}.session"
                    if os.path.exists(session_file):
                        os.remove(session_file)
                    # ارسال کد جدید
                    try:
                        result = await client.send_code_request(phone)
                        credentials['phone_code_hash'] = result.phone_code_hash
                        credentials['code'] = None  # reset code
                        await save_credentials(credentials, credentials_file)
                        print("✅ کد جدید ارسال شد. ربات restart می‌شود.")
                        await client.disconnect()
                        return
                    except Exception as e:
                        print(f"خطا در ارسال کد جدید: {e}")
                        await client.disconnect()
                        return
                except Exception as e:
                    print(f"خطا در لاگین: {e}. ارسال کد جدید...")
                    # پاک کردن session
                    session_file = f"{session_name}.session"
                    if os.path.exists(session_file):
                        os.remove(session_file)
                    # ارسال کد جدید
                    try:
                        result = await client.send_code_request(phone)
                        credentials['phone_code_hash'] = result.phone_code_hash
                        credentials['code'] = None
                        await save_credentials(credentials, credentials_file)
                        print("✅ کد جدید ارسال شد. ربات restart می‌شود.")
                        await client.disconnect()
                        return
                    except Exception as e:
                        print(f"خطا در ارسال کد جدید: {e}")
                        await client.disconnect()
                        return
            else:
                print("⚠️ کد لاگین یا phone_code_hash در credentials.json وجود ندارد. ارسال کد...")
                try:
                    result = await client.send_code_request(phone)
                    print("✅ کد SMS ارسال شد.")
                    credentials['phone_code_hash'] = result.phone_code_hash
                    await save_credentials(credentials, credentials_file)
                except Exception as e:
                    print(f"خطا در ارسال کد: {e}")
                finally:
                    await client.disconnect()
                return
        else:
            print("✅ اکانت قبلاً لاگین شده است.")
            log_login_success(session_name)  # لاگ برای session موجود
    except Exception as e:
        print(f"خطا در اتصال: {e}")
        return

    me = await client.get_me()
    print(f"🚀 سلف‌بات راه‌اندازی شد برای: {me.first_name}")

    # اتصال async به دیتابیس
    async with aiosqlite.connect(db_path) as db:
        await db.commit()

    # import modules بعد از init DB
    from modules.profile import register_profile_handlers
    from modules.settings import setup_settings
    from modules.manage import register_manage_handlers
    from modules.group import register_group_handlers
    from modules.convert import register_convert_handlers
    from modules.download import register_download_handlers
    from modules.edit import register_edit_handlers
    from modules.enemy import register_enemy_handlers
    from modules.fresponse import register_fast_response_handlers
    from modules.fun import register_fun_handlers
    from modules.private import register_private_handlers
    from modules.vars import register_vars_handlers

    # ثبت هندلرها
    await register_profile_handlers(client, session_name, owner_id)
    await setup_settings(client, db_path)
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

    try:
        await client.run_until_disconnected()
    except KeyboardInterrupt:
        print("Shutting down...")
    finally:
        try:
            await client.disconnect()
        except:
            pass

# اجرای برنامه
if __name__ == '__main__':
    asyncio.run(main())