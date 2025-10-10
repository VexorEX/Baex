import asyncio, json,os ,sys
import ormax
from ormax.fields import IntegerField, TextField, CharField
from telethon import TelegramClient,connection
from telethon.errors import SessionPasswordNeededError, PhoneCodeExpiredError, PhoneCodeInvalidError

# Define model before using
class Settings(ormax.Model):
    id = IntegerField(primary_key=True)
    bio = TextField(default='')
    username = CharField(max_length=100, default='')
    first_name = CharField(max_length=100, default='')
    last_name = CharField(max_length=100, default='')
    profile_photo = IntegerField(default=0)

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


async def save_credentials(credentials, filename='credentials.json'):
    with open(filename, 'w') as f:
        json.dump(credentials, f, indent=2)


async def init_db():
    db_path = 'sqlite:///selfbot.db'
    db = ormax.Database(db_path)
    await db.connect()
    db.register_model(Settings)
    await db.create_tables()

    # Insert initial data if empty
    if not await Settings.objects().count():
        await Settings.create(
            bio='',
            username='',
            first_name='',
            last_name='',
            profile_photo=0
        )
    print("Database initialized with Ormax.")


async def main():
    await init_db()  # Init DB first, before any module calls

    credentials_file = 'credentials.json'
    credentials = load_json(credentials_file)
    api_id = credentials['api_id']
    api_hash = credentials['api_hash']
    session_name = credentials['session_name']
    owner_id = credentials['owner_id']
    proxy = (
        "54.38.136.78", 4044,
        "eeff0ce99b756ea156e1774d930f40bd21"
    )
    client = TelegramClient(session_name, api_id, api_hash, connection=connection.ConnectionTcpMTProxyRandomizedIntermediate, proxy=proxy)
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