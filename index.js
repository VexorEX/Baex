import { Telegraf, Markup } from 'telegraf';
import fs from 'fs';
import path from 'path';
import { spawn } from 'child_process';
import { fileURLToPath } from "url";
import { dirname } from "path";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

// Load bot token from environment or config
const botToken = "7929231471:AAGpVMENXvMCkQzz7NWgK0i2Zzhf4bhGIow"; // Set this in your environment
const bot = new Telegraf(botToken);

// Map to keep track of running processes per user
const userProcesses = new Map();

// Map for pending newself requests
const pendingNewSelf = new Map();

// Map for users waiting for code
const pendingCode = new Map();

// Map for users needing password
const pendingPassword = new Map();

// Helper function to create user folder and credentials.json
function createUserFolder(userId, apiId, apiHash, phone) {
    const userDir = path.join(__dirname, 'users', userId.toString());
    if (!fs.existsSync(userDir)) fs.mkdirSync(userDir, { recursive: true });

    const credentials = {
        api_id: parseInt(apiId),
        api_hash: apiHash,
        session_name: `selfbot_${userId}`,
        owner_id: userId,
        phone: phone,
        code: null,
        phone_code_hash: null,
        needs_password: false,
        password: null
    };

    const credentialsPath = path.join(userDir, 'credentials.json');
    fs.writeFileSync(credentialsPath, JSON.stringify(credentials, null, 2));

    const sourceSelf = path.join(__dirname, 'main', 'Self.py'); // مسیر فایل اصلی
    const targetSelf = path.join(userDir, 'Self.py');
    if (!fs.existsSync(targetSelf)) {
        fs.copyFileSync(sourceSelf, targetSelf);
        console.log(`Self.py copied to ${targetSelf}`);
    }

    return userDir;
}

// Function to start a self-bot process for a user
function startSelfBot(userId, userDir) {
    console.log(`Starting self-bot for user ${userId} in ${userDir}...`);
    if (userProcesses.has(userId)) {
        stopSelfBot(userId); // Stop existing if any
    }

    const selfProcess = spawn('python3', ['Self.py'], {
        cwd: userDir,
        stdio: ['inherit', 'inherit', 'inherit'] // Inherit stdin/stdout/stderr for logging
    });

    selfProcess.on('error', (err) => {
        console.error(`Error starting self-bot for user ${userId}:`, err);
    });

    selfProcess.on('close', (code) => {
        console.log(`Self-bot for user ${userId} exited with code ${code}`);
        userProcesses.delete(userId);
        if (code === 0) {
            const userDirFull = path.join(__dirname, 'users', userId.toString());
            const credPath = path.join(userDirFull, 'credentials.json');
            if (fs.existsSync(credPath)) {
                const credentials = JSON.parse(fs.readFileSync(credPath, 'utf-8'));
                if (!credentials.code || !credentials.phone_code_hash) {
                    bot.telegram.sendMessage(userId, '⚠️ کد جدید ارسال شد. لطفاً کد SMS جدید را بفرستید. 🔑');
                }
            }
        }
    });

    userProcesses.set(userId, selfProcess);
    console.log(`Self-bot process started for user ${userId}, PID: ${selfProcess.pid}`);
    return { success: true, message: 'Self-bot started successfully.' };
}

// Function to stop a self-bot process for a user
function stopSelfBot(userId) {
    console.log(`Stopping self-bot for user ${userId}...`);
    if (!userProcesses.has(userId)) {
        console.warn(`No running self-bot found for user ${userId}`);
        return { success: false, message: 'No running self-bot found.' };
    }

    const selfProcess = userProcesses.get(userId);
    selfProcess.kill('SIGTERM');
    userProcesses.delete(userId);
    console.log(`Self-bot stopped for user ${userId}`);
    return { success: true, message: 'Self-bot stopped.' };
}

// Function to save code and restart selfbot
function saveCodeAndRestart(userId, code) {
    const userDir = path.join(__dirname, 'users', userId.toString());
    const credPath = path.join(userDir, 'credentials.json');

    if (!fs.existsSync(credPath)) {
        return { success: false, message: 'No self-bot found.' };
    }

    const credentials = JSON.parse(fs.readFileSync(credPath, 'utf-8'));
    credentials.code = code;
    fs.writeFileSync(credPath, JSON.stringify(credentials, null, 2));

    // Restart selfbot
    const userDirFull = path.join(__dirname, 'users', userId.toString());
    const result = startSelfBot(userId, userDirFull);
    return { success: true, message: 'کد ذخیره شد و self-bot دوباره راه‌اندازی شد.' };
}

// Function to save password and restart
function savePasswordAndRestart(userId, password) {
    const userDir = path.join(__dirname, 'users', userId.toString());
    const credPath = path.join(userDir, 'credentials.json');

    if (!fs.existsSync(credPath)) {
        return { success: false, message: 'No self-bot found.' };
    }

    const credentials = JSON.parse(fs.readFileSync(credPath, 'utf-8'));
    credentials.password = password;
    fs.writeFileSync(credPath, JSON.stringify(credentials, null, 2));

    // Restart selfbot
    const userDirFull = path.join(__dirname, 'users', userId.toString());
    const result = startSelfBot(userId, userDirFull);
    return { success: true, message: 'رمز ذخیره شد و self-bot دوباره راه‌اندازی شد.' };
}

// Function to start all self-bots
function startAllSelfBots() {
    const usersDir = path.join(__dirname, 'users');
    if (!fs.existsSync(usersDir)) {
        return { success: false, message: 'No users directory found.' };
    }

    const users = fs.readdirSync(usersDir);
    let startedCount = 0;
    let errorCount = 0;

    for (const userId of users) {
        try {
            const userDir = path.join(usersDir, userId);
            const credPath = path.join(userDir, 'credentials.json');
            
            if (fs.existsSync(credPath)) {
                const result = startSelfBot(parseInt(userId), userDir);
                if (result.success) {
                    startedCount++;
                } else {
                    errorCount++;
                }
            }
        } catch (err) {
            console.error(`Error starting self-bot for user ${userId}:`, err);
            errorCount++;
        }
    }

    return { 
        success: true, 
        message: `Started ${startedCount} self-bots. ${errorCount} errors occurred.` 
    };
}

// Function to stop all self-bots
function stopAllSelfBots() {
    let stoppedCount = 0;
    let errorCount = 0;

    for (const userId of userProcesses.keys()) {
        try {
            const result = stopSelfBot(userId);
            if (result.success) {
                stoppedCount++;
            } else {
                errorCount++;
            }
        } catch (err) {
            console.error(`Error stopping self-bot for user ${userId}:`, err);
            errorCount++;
        }
    }

    return { 
        success: true, 
        message: `Stopped ${stoppedCount} self-bots. ${errorCount} errors occurred.` 
    };
}

// Function to restart all self-bots
function restartAllSelfBots() {
    const stopResult = stopAllSelfBots();
    // Give some time for processes to fully stop
    setTimeout(() => {
        const startResult = startAllSelfBots();
        console.log(`Restart completed: ${startResult.message}`);
    }, 2000);
    
    return { 
        success: true, 
        message: `Restart initiated. Stopping ${stopResult.message}` 
    };
}

// Bot commands
bot.start((ctx) => {
    ctx.reply('Welcome! Use /newself <api_id> <api_hash> to create your self-bot and then share your contact.');
});

bot.command('newself', (ctx) => {
    const userId = ctx.from.id;
    const args = ctx.message.text.split(' ').slice(1);
    if (args.length < 2) {
        return ctx.reply('Usage: /newself <api_id> <api_hash>\nThen share your contact when prompted.');
    }
    const [apiId, apiHash] = args;

    pendingNewSelf.set(userId, { apiId, apiHash });
    const keyboard = Markup.keyboard([Markup.button.contactRequest('📱 Share My Contact')]).oneTime().resize();
    ctx.reply('لطفاً شماره تلفن خود را با دکمه زیر به اشتراک بگذارید: 📱', keyboard.reply_markup);
});

bot.command('stopself', (ctx) => {
    const userId = ctx.from.id;
    console.log(`Received /stopself command from user ${userId}`);
    const result = stopSelfBot(userId);
    ctx.reply(result.message);
});

// New command to stop all self-bots
bot.command('stopall', (ctx) => {
    console.log(`Received /stopall command from user ${ctx.from.id}`);
    const result = stopAllSelfBots();
    ctx.reply(result.message);
});

// New command to start all self-bots
bot.command('startall', (ctx) => {
    console.log(`Received /startall command from user ${ctx.from.id}`);
    const result = startAllSelfBots();
    ctx.reply(result.message);
});

// New command to restart all self-bots
bot.command('restartall', (ctx) => {
    console.log(`Received /restartall command from user ${ctx.from.id}`);
    const result = restartAllSelfBots();
    ctx.reply(result.message);
});

bot.command('status', (ctx) => {
    const userId = ctx.from.id;
    console.log(`Received /status command from user ${userId}`);
    if (userProcesses.has(userId)) {
        ctx.reply('Your self-bot is running.');
    } else {
        ctx.reply('Your self-bot is not running.');
    }
});

bot.on('contact', async (ctx,next) => {
    const userId = ctx.from.id;
    if (!pendingNewSelf.has(userId)) {
        return ctx.reply('ابتدا /newself را ارسال کنید.');
    }

    const contact = ctx.message.contact;
    if (contact.user_id !== userId) {
        return ctx.reply('لطفاً تماس خود را به اشتراک بگذارید، نه دیگران.');
    }

    const { apiId, apiHash } = pendingNewSelf.get(userId);
    pendingNewSelf.delete(userId);

    const phone = contact.phone_number;

    const userDir = createUserFolder(userId, apiId, apiHash, phone);

    const result = startSelfBot(userId, userDir);
    ctx.reply(result.message);

    if (result.success) {
        pendingCode.set(userId, true);
        const codeKeyboard = Markup.keyboard([Markup.button.text('🔑 Send Code')]).oneTime().resize();
        ctx.reply('✅ self-bot راه‌اندازی شد. حالا کد SMS را مستقیماً ارسال کنید. 🔑', codeKeyboard.reply_markup);
    }
    await next()
});

bot.on('text', async (ctx,next) => {
    const userId = ctx.from.id;
    const text = ctx.message.text.trim();
    if (pendingCode.has(userId)) {
        // Parse formatted code (remove dots, dashes, spaces)
        let cleanCode = text.replace(/[\.\-\s]/g, '');  // Remove dots, dashes, spaces
        if (/^\d{5}$/.test(cleanCode)) {
            pendingCode.delete(userId);
            const result = saveCodeAndRestart(userId, cleanCode);  // Save clean code
            ctx.reply(`✅ کد ذخیره شد (فرمت امن: ${text}). self-bot restart شد.`);
        } else {
            ctx.reply('❌ کد نامعتبر است. 5 رقم بفرستید (مثل 12345 یا 1.2.3.4.5).');
        }
    } else if (pendingPassword.has(userId)) {
        pendingPassword.delete(userId);
        const result = savePasswordAndRestart(userId, text);
        ctx.reply(result.message);
    }
    await next()
});


// Launch the bot
bot.launch()
    .then(() => console.log('Bot is running...'))
    .catch((err) => console.error('Error launching bot:', err));

// Graceful stop
process.once('SIGINT', () => {
    console.log('Received SIGINT, stopping bot and self-bot processes...');
    bot.stop('SIGINT');
    userProcesses.forEach(proc => proc.kill('SIGTERM'));
});
process.once('SIGTERM', () => {
    console.log('Received SIGTERM, stopping bot and self-bot processes...');
    bot.stop('SIGTERM');
    userProcesses.forEach(proc => proc.kill('SIGTERM'));
});