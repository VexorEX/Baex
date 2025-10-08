import asyncio
import logging
import re
import random
from datetime import datetime
import jdatetime
import pytz
import requests
from openai import AsyncOpenAI
from pydantic import BaseModel
import whois
import pycares
from telethon import events,Button
from telethon.errors import FloodWaitError
from utils import load_json, send_message, get_command_pattern
from models import get_database, load_settings, update_settings

logger = logging.getLogger(__name__)

async def register_fun_handlers(client, session_name, owner_id):
    db = await get_database(session_name)
    settings = await load_settings(db)
    if not settings:
        logger.error("Failed to load settings for fun handlers")
        await db.close()
        return

    lang = settings.get('lang', 'fa')
    messages = load_json('msg.json')
    commands = load_json('cmd.json')

    def get_message(key, **kwargs):
        return messages[lang]['fun'].get(key, '').format(**kwargs)

    # ایجاد جداول برای تنظیمات
    await db.execute('''
        CREATE TABLE IF NOT EXISTS fun_settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')
    await db.execute('''
        CREATE TABLE IF NOT EXISTS mygpt_history (
            user_id INTEGER,
            message TEXT,
            role TEXT,
            timestamp INTEGER
        )
    ''')
    await db.commit()

    # تنظیمات اولیه fun
    if 'fun' not in settings:
        settings['fun'] = {'chatgpt_token': None}
        await update_settings(db, settings)

    # تابع برای تبدیل عدد به حروف (فارسی)
    def number_to_words(number):
        units = ['', 'یک', 'دو', 'سه', 'چهار', 'پنج', 'شش', 'هفت', 'هشت', 'نه']
        teens = ['ده', 'یازده', 'دوازده', 'سیزده', 'چهارده', 'پانزده', 'شانزده', 'هفده', 'هجده', 'نوزده']
        tens = ['', '', 'بیست', 'سی', 'چهل', 'پنجاه', 'شصت', 'هفتاد', 'هشتاد', 'نود']
        if number == 0:
            return 'صفر'
        if number < 10:
            return units[number]
        if number < 20:
            return teens[number - 10]
        if number < 100:
            return f"{tens[number // 10]}{' و ' + units[number % 10] if number % 10 else ''}"
        return str(number)  # برای اعداد بزرگتر، فعلاً خود عدد

    # نمایش زمان
    @client.on(events.NewMessage(pattern=get_command_pattern('time', lang["fun"])))
    async def handle_time(event):
        try:
            city = event.pattern_match.group(1)
            if not city:
                tehran_tz = pytz.timezone('Asia/Tehran')
                utc_tz = pytz.timezone('UTC')
                now_tehran = datetime.now(tehran_tz)
                now_utc = datetime.now(utc_tz)
                now_shamsi = jdatetime.datetime.now()
                response = (
                    f"🕒 زمان میلادی: {now_tehran.strftime('%Y/%m/%d %H:%M:%S')}\n"
                    f"📅 تاریخ شمسی: {now_shamsi.strftime('%Y/%m/%d %H:%M:%S')}\n"
                    f"🌐 زمان UTC: {now_utc.strftime('%Y/%m/%d %H:%M:%S')}"
                )
            else:
                cities = {'Tokyo': 'Asia/Tokyo', 'London': 'Europe/London', 'New York': 'America/New_York'}
                timezone = cities.get(city, 'Asia/Tehran')
                tz = pytz.timezone(timezone)
                now = datetime.now(tz)
                response = f"🕒 زمان در {city}: {now.strftime('%Y/%m/%d %H:%M:%S')}"
            await send_message(event, response)
        except Exception as e:
            logger.error(f"Error getting time: {e}")
            await send_message(event, get_message('error_occurred'))

    # نمایش تقویم
    @client.on(events.NewMessage(pattern=get_command_pattern('calendar', lang["fun"])))
    async def handle_calendar(event):
        try:
            now_shamsi = jdatetime.datetime.now()
            now_miladi = datetime.now()
            response = (
                f"📅 تقویم شمسی: {now_shamsi.strftime('%Y/%m/%d')}\n"
                f"📅 تقویم میلادی: {now_miladi.strftime('%Y/%m/%d')}"
            )
            await send_message(event, response)
        except Exception as e:
            logger.error(f"Error getting calendar: {e}")
            await send_message(event, get_message('error_occurred'))

    # زمان اذان
    @client.on(events.NewMessage(pattern=get_command_pattern('azan', lang["fun"])))
    async def handle_azan(event):
        try:
            city = event.pattern_match.group(1) or 'Tehran'
            response = requests.get(f'http://api.aladhan.com/v1/timingsByCity?city={city}&country=Iran')
            data = response.json()['data']['timings']
            prayers = ['Fajr', 'Dhuhr', 'Asr', 'Maghrib', 'Isha']
            result = f"🕌 زمان اذان در {city}:\n"
            for prayer in prayers:
                result += f"{prayer}: {data[prayer]}\n"
            await send_message(event, result)
        except Exception as e:
            logger.error(f"Error getting azan: {e}")
            await send_message(event, get_message('error_occurred'))

    # وضعیت فوتبال
    @client.on(events.NewMessage(pattern=get_command_pattern('football', lang["fun"])))
    async def handle_football(event):
        try:
            response = requests.get('https://api.football-data.org/v4/matches', headers={'X-Auth-Token': 'YOUR_API_KEY'})
            matches = response.json()['matches']
            result = "⚽ وضعیت لیگ‌های فوتبال:\n"
            for match in matches[:5]:  # محدود به 5 بازی
                result += f"{match['homeTeam']['name']} vs {match['awayTeam']['name']}: {match['score']['fullTime']['home']} - {match['score']['fullTime']['away']}\n"
            await send_message(event, result)
        except Exception as e:
            logger.error(f"Error getting football data: {e}")
            await send_message(event, get_message('error_occurred'))

    # پخش زنده تلویزیون
    @client.on(events.NewMessage(pattern=get_command_pattern('tv', lang["fun"])))
    async def handle_tv(event):
        try:
            response = "📺 لینک‌های پخش زنده شبکه‌های ایران:\n"
            channels = {
                'IRIB 1': 'https://telewebion.com/live/irib1',
                'IRIB 3': 'https://telewebion.com/live/irib3',
                'Varzesh': 'https://telewebion.com/live/varzesh'
            }
            for name, link in channels.items():
                response += f"{name}: {link}\n"
            await send_message(event, response)
        except Exception as e:
            logger.error(f"Error getting TV links: {e}")
            await send_message(event, get_message('error_occurred'))

    # قیمت ارزهای سنتی
    @client.on(events.NewMessage(pattern=get_command_pattern('sarz', lang["fun"])))
    async def handle_sarz(event):
        try:
            response = requests.get('https://api.exchangerate-api.com/v4/latest/USD')
            rates = response.json()['rates']
            result = "💸 قیمت ارزها (بر اساس دلار):\n"
            for currency in ['EUR', 'GBP', 'IRR']:
                result += f"{currency}: {rates.get(currency, 'N/A')}\n"
            await send_message(event, result)
        except Exception as e:
            logger.error(f"Error getting currency rates: {e}")
            await send_message(event, get_message('error_occurred'))

    # اطلاعات ارز دیجیتال
    @client.on(events.NewMessage(pattern=get_command_pattern('crypto', lang["fun"])))
    async def handle_crypto(event):
        try:
            coin = event.pattern_match.group(1) or 'bitcoin'
            response = requests.get(f'https://api.coingecko.com/api/v3/coins/{coin}')
            data = response.json()
            price = data['market_data']['current_price']['usd']
            await send_message(event, f"💰 قیمت {coin}: ${price}")
        except Exception as e:
            logger.error(f"Error getting crypto data: {e}")
            await send_message(event, get_message('invalid_crypto'))

    # اطلاعات دامنه
    @client.on(events.NewMessage(pattern=get_command_pattern('domain', lang["fun"])))
    async def handle_domain(event):
        try:
            domain = event.pattern_match.group(1)
            if not domain:
                await send_message(event, get_message('no_domain'))
                return
            w = whois.whois(domain)
            response = f"🌐 اطلاعات دامنه {domain}:\n"
            response += f"ثبت‌کننده: {w.registrar or 'N/A'}\n"
            response += f"تاریخ ثبت: {w.creation_date or 'N/A'}\n"
            response += f"تاریخ انقضا: {w.expiration_date or 'N/A'}\n"
            await send_message(event, response)
        except Exception as e:
            logger.error(f"Error getting domain info: {e}")
            await send_message(event, get_message('error_occurred'))

    # اطلاعات IP
    @client.on(events.NewMessage(pattern=get_command_pattern('ip_info', lang["fun"])))
    async def handle_ip_info(event):
        try:
            ip = event.pattern_match.group(1)
            if not ip or not re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', ip):
                await send_message(event, get_message('invalid_ip'))
                return
            response = requests.get(f'http://ip-api.com/json/{ip}')
            data = response.json()
            response = f"🌍 اطلاعات IP {ip}:\n"
            response += f"کشور: {data.get('country', 'N/A')}\n"
            response += f"شهر: {data.get('city', 'N/A')}\n"
            response += f"ISP: {data.get('isp', 'N/A')}\n"
            await send_message(event, response)
        except Exception as e:
            logger.error(f"Error getting IP info: {e}")
            await send_message(event, get_message('error_occurred'))

    # اطلاعات کانفیگ Vmess/Vless
    @client.on(events.NewMessage(pattern=get_command_pattern('config_info', lang["fun"])))
    async def handle_config_info(event):
        try:
            config = event.pattern_match.group(1)
            if not config and not event.message.is_reply:
                await send_message(event, get_message('no_config'))
                return
            if event.message.is_reply:
                reply_msg = await event.get_reply_message()
                config = reply_msg.text
            if not config.startswith(('vmess://', 'vless://')):
                await send_message(event, get_message('invalid_config'))
                return
            response = f"🔌 اطلاعات کانفیگ:\nنوع: {config[:5]}\nلینک: {config[:30]}..."
            await send_message(event, response)
        except Exception as e:
            logger.error(f"Error getting config info: {e}")
            await send_message(event, get_message('error_occurred'))

    # دریافت پروکسی
    @client.on(events.NewMessage(pattern=get_command_pattern('proxy', lang["fun"])))
    async def handle_proxy(event):
        try:
            proxies = ['mtproto://proxy1', 'mtproto://proxy2']  # لیست نمونه
            response = "📡 لیست پروکسی‌های تلگرام:\n" + '\n'.join(proxies)
            await send_message(event, response)
        except Exception as e:
            logger.error(f"Error getting proxies: {e}")
            await send_message(event, get_message('error_occurred'))

    # عضویت در کانال‌های اجباری
    @client.on(events.NewMessage(pattern=get_command_pattern('join_all', lang["fun"])))
    async def handle_join_all(event):
        try:
            if not event.message.is_reply:
                await send_message(event, get_message('reply_required'))
                return
            reply_msg = await event.get_reply_message()
            if not reply_msg.reply_markup:
                await send_message(event, get_message('no_buttons'))
                return
            for row in reply_msg.reply_markup.rows:
                for button in row.buttons:
                    if button.url:
                        await client(JoinChannelRequest(button.url))
            await send_message(event, get_message('joined_all'))
        except FloodWaitError as e:
            await send_message(event, get_message('flood_wait', seconds=e.seconds))
        except Exception as e:
            logger.error(f"Error joining channels: {e}")
            await send_message(event, get_message('error_occurred'))

    # عضویت و خروج از کانال‌ها
    @client.on(events.NewMessage(pattern=get_command_pattern('join_and_leave', lang["fun"])))
    async def handle_join_and_leave(event):
        try:
            if not event.message.is_reply:
                await send_message(event, get_message('reply_required'))
                return
            reply_msg = await event.get_reply_message()
            if not reply_msg.reply_markup:
                await send_message(event, get_message('no_buttons'))
                return
            for row in reply_msg.reply_markup.rows:
                for button in row.buttons:
                    if button.url:
                        await client(JoinChannelRequest(button.url))
                        if button.button_id:
                            await client(ClickInlineButtonRequest(reply_msg, button.button_id))
                        await client(LeaveChannelRequest(button.url))
            await send_message(event, get_message('joined_and_left'))
        except FloodWaitError as e:
            await send_message(event, get_message('flood_wait', seconds=e.seconds))
        except Exception as e:
            logger.error(f"Error joining and leaving channels: {e}")
            await send_message(event, get_message('error_occurred'))

    # تبدیل عدد به حروف
    @client.on(events.NewMessage(pattern=get_command_pattern('to_word', lang["fun"])))
    async def handle_to_word(event):
        try:
            number = event.pattern_match.group(1)
            if not number and not event.message.is_reply:
                await send_message(event, get_message('no_number'))
                return
            if event.message.is_reply:
                reply_msg = await event.get_reply_message()
                number = reply_msg.text
            if not number.isdigit():
                await send_message(event, get_message('invalid_number'))
                return
            result = number_to_words(int(number))
            await send_message(event, f"📝 {number} = {result}")
        except Exception as e:
            logger.error(f"Error converting number to word: {e}")
            await send_message(event, get_message('error_occurred'))

    # دریافت فال
    @client.on(events.NewMessage(pattern=get_command_pattern('fortune', lang["fun"])))
    async def handle_fortune(event):
        try:
            fortunes = ['امروز روز خوبی برای شماست!', 'موفقیت در انتظار شماست.', 'مراقب تصمیمات خود باشید.']
            await send_message(event, f"🔮 فال شما: {random.choice(fortunes)}")
        except Exception as e:
            logger.error(f"Error getting fortune: {e}")
            await send_message(event, get_message('error_occurred'))

    # دریافت جوک
    @client.on(events.NewMessage(pattern=get_command_pattern('joke', lang["fun"])))
    async def handle_joke(event):
        try:
            jokes = ['چرا برنامه‌نویس تاریکی رو ترجیح میده؟ چون نور باگ‌ها رو نشون میده!', 'یه روز ادیسون به دوستش گفت: من یه لامپ ساختم! دوستش گفت: روشنم کن!']
            await send_message(event, f"😂 جوک: {random.choice(jokes)}")
        except Exception as e:
            logger.error(f"Error getting joke: {e}")
            await send_message(event, get_message('error_occurred'))

    # تنظیم توکن ChatGPT
    @client.on(events.NewMessage(pattern=get_command_pattern('set_chatgpt_token', lang["fun"])))
    async def handle_set_chatgpt_token(event):
        try:
            if event.sender_id != owner_id:
                await send_message(event, get_message('unauthorized'))
                return
            token = event.pattern_match.group(1)
            if not token:
                await send_message(event, get_message('no_token'))
                return
            settings['fun']['chatgpt_token'] = token
            await update_settings(db, settings)
            await db.execute('INSERT OR REPLACE INTO fun_settings (key, value) VALUES (?, ?)', ('chatgpt_token', token))
            await db.commit()
            await send_message(event, get_message('token_set'))
        except Exception as e:
            logger.error(f"Error setting ChatGPT token: {e}")
            await send_message(event, get_message('error_occurred'))

    # پرس‌وجو از ChatGPT
    @client.on(events.NewMessage(pattern=get_command_pattern('chatgpt', lang["fun"])))
    async def handle_chatgpt(event):
        try:
            question = event.pattern_match.group(1)
            if not question:
                await send_message(event, get_message('no_question'))
                return
            token = settings['fun'].get('chatgpt_token')
            if not token:
                await send_message(event, get_message('no_token_set'))
                return
            client_openai = AsyncOpenAI(api_key=token)
            response = await client_openai.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": question}]
            )
            answer = response.choices[0].message.content
            await send_message(event, f"🤖 پاسخ ChatGPT: {answer}")
        except Exception as e:
            logger.error(f"Error querying ChatGPT: {e}")
            await send_message(event, get_message('error_occurred'))

    # چت مداوم با ChatGPT
    @client.on(events.NewMessage(pattern=get_command_pattern('mygpt', lang["fun"])))
    async def handle_mygpt(event):
        try:
            question = event.pattern_match.group(1)
            if not question:
                await send_message(event, get_message('no_question'))
                return
            token = settings['fun'].get('chatgpt_token')
            if not token:
                await send_message(event, get_message('no_token_set'))
                return
            # ذخیره پیام کاربر
            await db.execute(
                'INSERT INTO mygpt_history (user_id, message, role, timestamp) VALUES (?, ?, ?, ?)',
                (event.sender_id, question, 'user', int(datetime.now().timestamp()))
            )
            # دریافت تاریخچه چت
            cursor = await db.execute(
                'SELECT message, role FROM mygpt_history WHERE user_id = ? ORDER BY timestamp',
                (event.sender_id,)
            )
            history = await cursor.fetchall()
            await cursor.close()
            client_openai = AsyncOpenAI(api_key=token)
            messages = [{"role": role, "content": msg} for msg, role in history]
            response = await client_openai.chat.completions.create(
                model="gpt-4o",
                messages=messages
            )
            answer = response.choices[0].message.content
            await db.execute(
                'INSERT INTO mygpt_history (user_id, message, role, timestamp) VALUES (?, ?, ?, ?)',
                (event.sender_id, answer, 'assistant', int(datetime.now().timestamp()))
            )
            await db.commit()
            await send_message(event, f"🤖 پاسخ ChatGPT: {answer}")
        except Exception as e:
            logger.error(f"Error in mygpt: {e}")
            await send_message(event, get_message('error_occurred'))

    # پاکسازی تاریخچه mygpt
    @client.on(events.NewMessage(pattern=get_command_pattern('clean_mygpt', lang["fun"])))
    async def handle_clean_mygpt(event):
        try:
            await db.execute('DELETE FROM mygpt_history WHERE user_id = ?', (event.sender_id,))
            await db.commit()
            await send_message(event, get_message('mygpt_cleared'))
        except Exception as e:
            logger.error(f"Error cleaning mygpt history: {e}")
            await send_message(event, get_message('error_occurred'))

    await db.close()