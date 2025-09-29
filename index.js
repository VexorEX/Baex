import { Telegraf } from 'telegraf';
import fs from 'fs';
import path from 'path';
import { spawn } from 'child_process';

// Load bot token from environment or config
const botToken = "7929231471:AAGpVMENXvMCkQzz7NWgK0i2Zzhf4bhGIow"; // Set this in your environment
const bot = new Telegraf(botToken);

// Map to keep track of running processes per user
const userProcesses = new Map();

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
        code: null
    };

    const credentialsPath = path.join(userDir, 'credentials.json');
    fs.writeFileSync(credentialsPath, JSON.stringify(credentials, null, 2));
    return userDir;
}

// Function to start a self-bot process for a user
function startSelfBot(userId, userDir) {
    console.log(`Starting self-bot for user ${userId} in ${userDir}...`);
    if (userProcesses.has(userId)) {
        console.warn(`Self-bot already running for user ${userId}`);
        return { success: false, message: 'Self-bot is already running.' };
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

// Bot commands
bot.start((ctx) => {
    ctx.reply('Welcome! Use /newself <api_id> <api_hash> to create and start your self-bot.');
});
bot.command('code', (ctx) => {
    const userId = ctx.from.id;
    const args = ctx.message.text.split(' ').slice(1);
    if (args.length !== 1) return ctx.reply('Usage: /code <SMS_code>');
    const code = args[0];

    const userDir = path.join(__dirname, 'users', userId.toString());
    const credPath = path.join(userDir, 'credentials.json');

    if (!fs.existsSync(credPath)) return ctx.reply('No self-bot found. Please run /newself first.');

    const credentials = JSON.parse(fs.readFileSync(credPath, 'utf-8'));
    credentials.code = code;
    fs.writeFileSync(credPath, JSON.stringify(credentials, null, 2));

    ctx.reply('✅ کد ذخیره شد. Self.py حالا می‌تواند login کند.');
});

bot.command('newself', async (ctx) => {
    const userId = ctx.from.id;
    const args = ctx.message.text.split(' ').slice(1);
    if (args.length < 3) {
        return ctx.reply('Usage: /newself <api_id> <api_hash> <phone_number>');
    }
    const [apiId, apiHash, phone] = args;

    const userDir = createUserFolder(userId, apiId, apiHash, phone);

    const result = startSelfBot(userId, userDir);
    ctx.reply(result.message);

    if (result.success) {
        ctx.reply('✅ لطفاً وقتی کد SMS برات اومد، با /code <your_code> وارد کن.');
    }
});


bot.command('stopself', (ctx) => {
    const userId = ctx.from.id;
    console.log(`Received /stopself command from user ${userId}`);
    const result = stopSelfBot(userId);
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