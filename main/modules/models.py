import aiosqlite
import json

async def get_database(session_name):
    return await aiosqlite.connect(f'selfbot_{session_name}.db')

async def init_db(db):
    async with db.cursor() as cursor:
        await cursor.execute('''
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
        await cursor.execute('''
                             CREATE TABLE IF NOT EXISTS mute_list (
                                                                      id INTEGER PRIMARY KEY,
                                                                      user_id INTEGER,
                                                                      mute_until INTEGER DEFAULT 0
                             )
                             ''')
        await cursor.execute('''
                             CREATE TABLE IF NOT EXISTS spam_protection (
                                                                            id INTEGER PRIMARY KEY,
                                                                            user_id INTEGER,
                                                                            messages TEXT DEFAULT '[]',
                                                                            mute_until INTEGER DEFAULT 0,
                                                                            violations INTEGER DEFAULT 0
                             )
                             ''')
        await db.commit()

async def load_settings(db):
    async with db.cursor() as cursor:
        await cursor.execute('SELECT * FROM settings WHERE id = 1')
        row = await cursor.fetchone()
        if not row:
            await cursor.execute('''
                                 INSERT INTO settings (
                                     id, lang, welcome_enabled, welcome_text, welcome_delete_time,
                                     clock_enabled, clock_location, clock_bio_text, clock_fonts,
                                     clock_timezone, action_enabled, action_types, text_format_enabled,
                                     text_formats, locks, antilog_enabled, first_comment_enabled,
                                     first_comment_text
                                 ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                 ''', (1, 'fa', False, '', 0, False, 'name', '', '[1]', 'Asia/Tehran',
                                       False, '{}', False, '{}', '{}', False, False, ''))
            await db.commit()
            await cursor.execute('SELECT * FROM settings WHERE id = 1')
            row = await cursor.fetchone()
        return {
            'id': row[0],
            'lang': row[1],
            'welcome_enabled': bool(row[2]),
            'welcome_text': row[3],
            'welcome_delete_time': row[4],
            'clock_enabled': bool(row[5]),
            'clock_location': row[6],
            'clock_bio_text': row[7],
            'clock_fonts': json.loads(row[8]),
            'clock_timezone': row[9],
            'action_enabled': bool(row[10]),
            'action_types': json.loads(row[11]),
            'text_format_enabled': bool(row[12]),
            'text_formats': json.loads(row[13]),
            'locks': json.loads(row[14]),
            'antilog_enabled': bool(row[15]),
            'first_comment_enabled': bool(row[16]),
            'first_comment_text': row[17]
        }

async def update_settings(db, settings):
    async with db.cursor() as cursor:
        await cursor.execute('''
                             UPDATE settings SET
                                                 lang = ?, welcome_enabled = ?, welcome_text = ?,
                                                 welcome_delete_time = ?, clock_enabled = ?, clock_location = ?,
                                                 clock_bio_text = ?, clock_fonts = ?, clock_timezone = ?,
                                                 action_enabled = ?, action_types = ?, text_format_enabled = ?,
                                                 text_formats = ?, locks = ?, antilog_enabled = ?,
                                                 first_comment_enabled = ?, first_comment_text = ?
                             WHERE id = 1
                             ''', (
                                 settings['lang'], settings['welcome_enabled'], settings['welcome_text'],
                                 settings['welcome_delete_time'], settings['clock_enabled'], settings['clock_location'],
                                 settings['clock_bio_text'], json.dumps(settings['clock_fonts']), settings['clock_timezone'],
                                 settings['action_enabled'], json.dumps(settings['action_types']),
                                 settings['text_format_enabled'], json.dumps(settings['text_formats']),
                                 json.dumps(settings['locks']), settings['antilog_enabled'],
                                 settings['first_comment_enabled'], settings['first_comment_text']
                             ))
        await db.commit()

async def load_spam_protection(db, user_id):
    async with db.cursor() as cursor:
        await cursor.execute('SELECT * FROM spam_protection WHERE user_id = ?', (user_id,))
        row = await cursor.fetchone()
        if not row:
            await cursor.execute('''
                                 INSERT INTO spam_protection (user_id, messages, mute_until, violations)
                                 VALUES (?, ?, ?, ?)
                                 ''', (user_id, '[]', 0, 0))
            await db.commit()
            await cursor.execute('SELECT * FROM spam_protection WHERE user_id = ?', (user_id,))
            row = await cursor.fetchone()
        return {
            'id': row[0],
            'user_id': row[1],
            'messages': json.loads(row[2]),
            'mute_until': row[3],
            'violations': row[4]
        }

async def update_spam_protection(db, spam_data):
    async with db.cursor() as cursor:
        await cursor.execute('''
                             UPDATE spam_protection SET
                                                        messages = ?, mute_until = ?, violations = ?
                             WHERE user_id = ?
                             ''', (json.dumps(spam_data['messages']), spam_data['mute_until'],
                                   spam_data['violations'], spam_data['user_id']))
        await db.commit()