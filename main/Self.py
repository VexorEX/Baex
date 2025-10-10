import asyncio, json,os ,sys
from ormax import Model
from ormax.fields import IntegerField, CharField, BooleanField, JSONField
from ormax import Database  # Import Database
from telethon import TelegramClient,connection
from telethon.errors import SessionPasswordNeededError, PhoneCodeExpiredError, PhoneCodeInvalidError

current_dir = os.path.dirname(__file__)  # users/123456
root_dir = os.path.abspath(os.path.join(current_dir, '../../'))  # root/
main_path = os.path.join(root_dir, 'main')
if main_path not in sys.path:
    sys.path.insert(0, main_path)

# Create Database instance
db = Database("sqlite:///selfbot.db")

# Define Settings model with Ormax
class Settings(Model):
    class Meta:
        database = db  # Use the Database instance
        table = "settings"

    id = IntegerField(primary_key=True)
    bio = CharField(max_length=500, default="")
    username = CharField(max_length=100, default="")
    first_name = CharField(max_length=100, default="")
    last_name = CharField(max_length=100, default="")
    profile_photo = IntegerField(default=0)

# Init Ormax DB (create tables)
async def init_ormax_db():
    await db.connect()
    await db.create_tables([Settings])  # Remove 'safe=True' as it's not supported
    # Insert default if not exists
    try:
        default_setting = await Settings.get(id=1)
    except:
        default_setting = await Settings.create(id=1, bio="", username="", first_name="", last_name="", profile_photo=0)
    print("Database initialized with Ormax.")

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
    await init_ormax_db()  # Init Ormax first

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

    await client.connect()

    if not await client.is_user_authorized():
        if code and phone_code_hash:
            try:
                await client.sign_in(phone=phone, code=code, phone_code_hash=phone_code_hash)
                print("✅ لاگین با موفقیت انجام شد.")
                # Clear temp fields after successful login
                credentials['code'] = None
                credentials['phone_code_hash'] = None
                await save_credentials(credentials, credentials_file)
                # Fix readonly session file
                session_file = f"{session_name}.session"
                if os.path.exists(session_file):
                    os.chmod(session_file, 0o666)
                    print("Session file permissions fixed.")
            except SessionPasswordNeededError:
                print("❌ رمز عبور 2FA مورد نیاز است.")
                password = input("Enter 2FA password: ")
                await client.sign_in(password=password)
                credentials['code'] = None
                credentials['phone_code_hash'] = None
                await save_credentials(credentials, credentials_file)
                # Fix readonly
                session_file = f"{session_name}.session"
                if os.path.exists(session_file):
                    os.chmod(session_file, 0o666)
            except (PhoneCodeExpiredError, PhoneCodeInvalidError) as e:
                print(f"⚠️ خطا در کد: {e}. پاک کردن session و ارسال کد جدید...")
                session_file = f"{session_name}.session"
                if os.path.exists(session_file):
                    os.remove(session_file)
                try:
                    result = await client.send_code_request(phone)
                    credentials['phone_code_hash'] = result.phone_code_hash
                    await save_credentials(credentials, credentials_file)
                    print("✅ کد جدید ارسال شد. لطفاً کد جدید را از ربات وارد کنید.")
                    await client.disconnect()
                    return
                except Exception as e:
                    print(f"خطا در ارسال کد: {e}")
                    await client.disconnect()
                    return
            except Exception as e:
                print(f"خطا در ورود: {e}")
                try:
                    await client.disconnect()
                except:
                    pass
                return
        else:
            print("⚠️ کد لاگین یا phone_code_hash در credentials.json وجود ندارد. لطفاً با ربات کد را وارد کنید.")
            try:
                result = await client.send_code_request(phone)
                print("✅ کد SMS ارسال شد.")
                credentials['phone_code_hash'] = result.phone_code_hash
                await save_credentials(credentials, credentials_file)
            except Exception as e:
                print(f"خطا در ارسال کد: {e}")
            finally:
                try:
                    await client.disconnect()
                except:
                    pass
            return
    else:
        print("✅ اکانت قبلاً لاگین شده است.")

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

    try:
        await client.run_until_disconnected()
    except KeyboardInterrupt:
        print("Shutting down...")
    finally:
        try:
            await client.disconnect()
        except:
            pass
        await db.disconnect()


if __name__ == '__main__':
    asyncio.run(main())