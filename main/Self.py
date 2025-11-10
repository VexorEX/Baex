import asyncio, json, os, sys, sqlite3, aiosqlite
from datetime import datetime
from telethon import TelegramClient, events
from telethon.errors import SessionPasswordNeededError, PhoneCodeExpiredError, PhoneCodeInvalidError

# مسیرها
current_dir = os.path.dirname(__file__)
root_dir = os.path.abspath(os.path.join(current_dir, '../../'))
main_path = os.path.join(root_dir, 'main')
if main_path not in sys.path:
    sys.path.insert(0, main_path)

# ابزارها و هندلرها (بعد از init DB importمی‌شن تا DB آماده باشه)
from utils import load_json, is_command_message  # Import utils برای چک command

# ذخیره credentials
async def save_credentials(credentials, filename):
    with open(filename, 'w') as f:
        json.dump(credentials, f, indent=2)

# لاگ لاگین موفق
def log_login_success(session_name):
    with open('login_log.txt', 'a') as f:
        f.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - لاگین موفق برای {session_name}\n")
    print("✅ لاگینلاگ شد.")

# فیکس permissions recursive
def fix_permissions(dir_path):
    for root, dirs, files in os.walk(dir_path):
        for d in dirs:
            os.chmod(os.path.join(root, d), 0o777)
        for f in files:
            os.chmod(os.path.join(root, f), 0o666)
    print(f"Permissions fixed for {dir_path}.")

# مقداردهی اولیه دیتابیس SQLite (sync) with WAL mode for concurrency
def init_sqlite_db(db_path):
    # Fix permissions forDB file and directory
    user_dir = os.path.dirname(db_path)
    fix_permissions(user_dir)
    if os.path.exists(db_path):
        os.chmod(db_path, 0o666)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    # Enable WAL mode for concurrentaccess (prevents lock)
    cursor.execute("PRAGMA journal_mode=WAL;")
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
    conn.close()  # Ensure closed
    os.chmod(db_path, 0o666)  # Ensure writable
    print("✅ دیتابیس SQLite مقداردهی شد (WAL mode enabled).")

# تابع اصلی
async def main():
    # Fix: absolute path for credentials
    credentials_file = os.path.join(os.path.dirname(__file__), 'credentials.json')
    if not os.path.exists(credentials_file):
        print(f"❌ credentials.json یافت نشد در {credentials_file}")
        return

    try:
        with open(credentials_file, 'r') as f:
            credentials = json.load(f)
    except json.JSONDecodeError as e:
        print(f"❌ خطا در خواندنcredentials.json: {e}")
        return

    api_id = credentials.get('api_id')
    api_hash = credentials.get('api_hash')
    session_name = credentials.get('session_name')
    owner_id = credentials.get('owner_id')
    phone = credentials.get("phone")
    code = credentials.get("code")
    phone_code_hash = credentials.get("phone_code_hash")

    if not phone:
        print("⚠️ شماره تلفن در credentials.json پیدا نشد.")
        return

    if not api_id or not api_hash:
        print("❌ api_id یا api_hash در credentials.json موجودنیست.")
        return

    db_path = os.path.join(os.path.dirname(__file__), f'selfbot_{session_name}.db')  # Absolute for DB
    print(f"🔌 اتصال به دیتابیس: {db_path}")
    init_sqlite_db(db_path)
    print("✅ دیتابیس SQLite مقداردهی شد (WAL mode enabled).")

    client = TelegramClient(session_name, api_id, api_hash)

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
                    session_file = os.path.join(os.path.dirname(__file__), f"{session_name}.session")
                    if os.path.exists(session_file):
                        os.chmod(session_file, 0o666)
                        print("Session file permissions fixed.")
                except (PhoneCodeExpiredError, PhoneCodeInvalidError, SessionPasswordNeededError) as e:
                    print(f"⚠️ خطا در کد/رمز: {e}. ارسال کد جدید...")
                    # پاک کردن session
                    session_file = os.path.join(os.path.dirname(__file__), f"{session_name}.session")
                    if os.path.exists(session_file):
                        os.remove(session_file)
                    # ارسال کد جدید
                    try:
                        result = await client.send_code_request(phone)
                        credentials['phone_code_hash'] = result.phone_code_hash
                        credentials['code'] = None  # reset code
                        await save_credentials(credentials, credentials_file)
                        print("✅کد جدید ارسال شد. ربات restart می‌شود.")
                        await client.disconnect()
                        return
                    except Exception as e:
                        print(f"خطا در ارسال کد جدید: {e}")
                        await client.disconnect()
                        return
                except Exception as e:
                    print(f"خطا در لاگین: {e}.ارسال کد جدید...")
                    # پاک کردن session
                    session_file = os.path.join(os.path.dirname(__file__), f"{session_name}.session")
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
                    credentials['phone_code_hash']=result.phone_code_hash
                    await save_credentials(credentials, credentials_file)
                except Exception as e:
                    print(f"خطا در ارسال کد: {e}")
                finally:
                    await client.disconnect()
                return
        else:
            print("✅ اکانت قبلاً لاگینشده است.")
            log_login_success(session_name)  # لاگ برای session موجود
    except Exception as e:
        print(f"خطا در اتصال: {e}")
        return

    me = await client.get_me()
    print(f"🚀 سلف‌بات راه‌اندازی شد برای: {me.first_name}")

    # تغییر 1: ارسال پیام به owner که self run شده
    if owner_id:
        try:
            await client.send_message(owner_id, f"✅ سلف‌بات راه‌اندازی شد برای {me.first_name} (Session: {session_name})")
            print(f"✅ پیام راه‌اندازی به owner ({owner_id}) ارسال شد.")
        except Exception as e:
            print(f"⚠️ خطا در ارسال پیام به owner: {e}")

    # اتصال async به دیتابیس
    async with aiosqlite.connect(db_path) as db:
        await db.commit()

    # import modules بعد از init DB
    # from modules.profile import register_profile_handlers
    # from modules.settings import setup_settings
    # from modules.manage import register_manage_handlers
    # from modules.group import register_group_handlers
    # from modules.convert import register_convert_handlers
    # from modules.download import register_download_handlers
    # from modules.edit import register_edit_handlers
    # from modules.enemy import register_enemy_handlers
    # from modules.fresponse import register_fast_response_handlers
    # from modules.fun import register_fun_handlers
    # from modules.private import register_private_handlers
    # from modules.vars import register_vars_handlers

    # ثبت هندلرها
    # await register_profile_handlers(client, session_name, owner_id)
    # await setup_settings(client, db_path)
    # await register_manage_handlers(client, session_name, owner_id)
    # await register_group_handlers(client, session_name, owner_id)
    # await register_vars_handlers(client, session_name, owner_id)
    # await register_private_handlers(client, session_name, owner_id)
    # await register_fun_handlers(client, session_name, owner_id)
    # await register_fast_response_handlers(client, session_name, owner_id)
    # await register_enemy_handlers(client, session_name, owner_id)
    # await register_edit_handlers(client, session_name, owner_id)
    # await register_download_handlers(client, session_name, owner_id)
    # await register_convert_handlers(client, session_name, owner_id)

    # تغییر 2: Handler برای print هر پیام incoming (بدون تداخل با commands)
    @client.on(events.NewMessage(incoming=True))
    async def log_incoming_messages(event):
        text = event.message.text
        if text:  # فقط اگر متن داشته باشه
            # Skip اگر command باشه (از utils)
            commands = load_json("cmd.json")
            lang = "fa"  # یا از settings بگیر
            if await is_command_message(text, lang, commands):
                return  # Skip commands برای جلوگیری از تداخل
            # Print پیام (chat_id, sender, text)
            sender = await event.get_sender()
            print(f"📨 Incoming [{event.chat_id} from {sender.first_name if sender else 'Unknown'}]: {text}")

    print("✅ سلف‌بات کاملاً راه‌اندازی شد")
    try:
        await client.run_until_disconnected()
        print("🛑 سلف‌بات به صورت طبیعی متوقف شد")
    except KeyboardInterrupt:
        print("🛑 متوقف شدنتوسط کاربر (Ctrl+C)")
    except Exception as e:
        print(f"❌ خطای نامشخص در اجرای سلف‌بات: {e}")
        import traceback
        traceback.print_exc()
    finally:
        try:
            await client.disconnect()
            print("🔌 اتصال سلف‌بات قطع شد")
        except Exception as e:
            print(f"❌ خطا در قطع اتصال: {e}")

# اجرای برنامه
if __name__ == '__main__':
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"❌ خطا در اجرای برنامه اصلی: {e}")
        import traceback
        traceback.print_exc() 