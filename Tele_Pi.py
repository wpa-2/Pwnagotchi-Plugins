#!/usr/bin/env python3

import os
import logging
import asyncio
import time
import requests
import psutil
from functools import wraps
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# --- Script Metadata ---
__version__ = "1.3.1"
__author__ = "WPA2"

# --- Configuration ---
# Set logging level from environment variable or default to INFO
log_level = os.environ.get("TELEGRAM_LOG_LEVEL", "INFO").upper()
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=log_level)
logger = logging.getLogger(__name__)

# Load sensitive data from environment variables
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
WEATHER_API_KEY = os.environ.get("WEATHER_API_KEY")
ALLOWED_USER_ID = int(os.environ.get("ALLOWED_USER_ID", 0))

if not all([TELEGRAM_TOKEN, WEATHER_API_KEY, ALLOWED_USER_ID]):
    logger.error("FATAL: Missing one or more environment variables: TELEGRAM_TOKEN, WEATHER_API_KEY, ALLOWED_USER_ID")
    exit(1)

# Monitoring thresholds
THRESHOLD_TEMP = 62.0  # Celsius
THRESHOLD_RAM = 80.0   # Percent

# Cooldown settings
COOLDOWN_SECONDS = 60
last_command_time = {}

# --- Command Definitions ---
system_commands = [
    {"name": "/update", "description": "Update the system", "emoji": "🔄"},
    {"name": "/reboot", "description": "Reboots the system", "emoji": "🔄"},
    {"name": "/shutdown", "description": "Shuts the system down", "emoji": "⏹️"},
    {"name": "/disk_usage", "description": "Show disk usage", "emoji": "💾"},
    {"name": "/free_memory", "description": "Show free memory", "emoji": "🧠"},
    {"name": "/show_processes", "description": "Show all processes", "emoji": "⚙️"},
    {"name": "/show_system_services", "description": "Show system services", "emoji": "🛠️"},
    {"name": "/start_monitoring", "description": "Start CPU temp monitoring", "emoji": "🌡️"},
    {"name": "/stop_monitoring", "description": "Stop CPU temp monitoring", "emoji": "❄️"},
    {"name": "/start_monitoring_ram", "description": "Start RAM usage monitoring", "emoji": "📈"},
    {"name": "/stop_monitoring_ram", "description": "Stop RAM usage monitoring", "emoji": "📉"},
    {"name": "/temp", "description": "Show current CPU temperature", "emoji": "🌡️"},
    {"name": "/status", "description": "Show a brief system status", "emoji": "📊"}
]

network_commands = [
    {"name": "/ip", "description": "Show IP addresses", "emoji": "📍"},
    {"name": "/external_ip", "description": "Show external IP address", "emoji": "🌍"},
    {"name": "/wifi", "description": "Scan for WiFi networks", "emoji": "📶"},
    {"name": "/ping", "description": "Ping a remote host", "emoji": "🏓"},
    {"name": "/show_network_info", "description": "Show detailed network stats", "emoji": "�"}
]

utility_commands = [
    {"name": "/speedtest", "description": "Run an internet speed test", "emoji": "⚡"},
    {"name": "/uptime", "description": "Show system uptime", "emoji": "⏰"},
    {"name": "/weather", "description": "Get weather for a city", "emoji": "☁️"},
    {"name": "/joke", "description": "Tell a random joke", "emoji": "😂"}
]

# --- Helper Functions and Decorators ---
def restricted(func):
    """Decorator to restrict access to the allowed user ID."""
    @wraps(func)
    async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user = update.effective_user
        if not user or user.id != ALLOWED_USER_ID:
            if update.callback_query:
                await update.callback_query.answer("🚫 You are not authorized to use this bot.", show_alert=True)
            logger.warning(f"Unauthorized access attempt by user {user.id if user else 'Unknown'}.")
            return
        return await func(update, context, *args, **kwargs)
    return wrapped

def cooldown(seconds: int):
    """Decorator to enforce a cooldown on a command."""
    def decorator(func):
        @wraps(func)
        async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
            command_key = func.__name__
            now = time.time()
            last_time = last_command_time.get(command_key, 0)

            if now - last_time < seconds:
                remaining = int(seconds - (now - last_time))
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=f"Please wait {remaining} more seconds to use this command again."
                )
                return
            
            last_command_time[command_key] = now
            return await func(update, context, *args, **kwargs)
        return wrapped
    return decorator

async def run_subprocess(command: list[str]) -> tuple[str, str]:
    """Asynchronously run a subprocess and return its output."""
    process = await asyncio.create_subprocess_exec(
        *command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await process.communicate()
    return stdout.decode('utf-8').strip(), stderr.decode('utf-8').strip()

async def send_message_in_chunks(context: ContextTypes.DEFAULT_TYPE, chat_id: int, text: str, header: str = ""):
    """Sends a message in chunks if it's too long."""
    full_text = f"*{header}*\n```\n{text}\n```" if header else f"```\n{text}\n```"
    
    if len(full_text) <= 4096:
        await context.bot.send_message(chat_id=chat_id, text=full_text, parse_mode="Markdown")
    else:
        # Send header separately if it exists
        if header:
            await context.bot.send_message(chat_id=chat_id, text=f"*{header}*", parse_mode="Markdown")
        
        # Send the rest of the text in chunks
        for i in range(0, len(text), 4000):
            chunk = text[i:i+4000]
            await context.bot.send_message(chat_id=chat_id, text=f"```\n{chunk}\n```", parse_mode="Markdown")
            await asyncio.sleep(0.2)


# --- Command Handlers ---
@restricted
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Displays the main menu."""
    keyboard = [
        [InlineKeyboardButton("⚙️ System", callback_data="system_menu")],
        [InlineKeyboardButton("🌐 Network", callback_data="network_menu")],
        [InlineKeyboardButton("🛠️ Utility", callback_data="utility_menu")],
        [InlineKeyboardButton("📋 All Commands", callback_data="help_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    start_message = (
        f"🤖 *Pi Manager Bot v{__version__}*\n"
        f"Created by {__author__}\n\n"
        "Choose a category to get started."
    )
    # If called from a button, edit the message. Otherwise, send a new one.
    if update.callback_query:
        await update.callback_query.edit_message_text(start_message, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        await update.message.reply_text(start_message, reply_markup=reply_markup, parse_mode="Markdown")

@restricted
@cooldown(300) # 5 minute cooldown
async def update_system(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    await context.bot.send_message(chat_id=chat_id, text="🔄 Updating system packages... This may take a while.")
    
    update_out, update_err = await run_subprocess(["sudo", "apt", "update"])
    if "Err:" in update_out or update_err:
        await send_message_in_chunks(context, chat_id, update_out + "\n" + update_err, "Update Error")
        return
    
    await context.bot.send_message(chat_id=chat_id, text="✅ Update check complete. Now upgrading...")
    upgrade_out, upgrade_err = await run_subprocess(["sudo", "apt", "upgrade", "-y"])
    response = f"--- UPDATE ---\n{update_out}\n\n--- UPGRADE ---\n{upgrade_out or 'No packages to upgrade.'}"
    if upgrade_err:
        response += f"\n\n--- UPGRADE ERROR ---\n{upgrade_err}"

    await send_message_in_chunks(context, chat_id, response, "System Update Complete")

@restricted
async def reboot(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await context.bot.send_message(chat_id=update.effective_chat.id, text="🔄 System is rebooting now...")
    await run_subprocess(["sudo", "reboot"])

@restricted
async def shutdown(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await context.bot.send_message(chat_id=update.effective_chat.id, text="⏹️ System is shutting down now...")
    await run_subprocess(["sudo", "shutdown", "-h", "now"])

@restricted
async def disk_usage(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    output, _ = await run_subprocess(["df", "-h"])
    await send_message_in_chunks(context, update.effective_chat.id, output, "💾 Disk Usage")

@restricted
async def free_memory(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    output, _ = await run_subprocess(["free", "-m"])
    await send_message_in_chunks(context, update.effective_chat.id, output, "🧠 Free Memory")

@restricted
async def show_processes(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    output, _ = await run_subprocess(["ps", "-ef"])
    await send_message_in_chunks(context, update.effective_chat.id, output, "⚙️ Processes")

@restricted
async def show_system_services(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    output, _ = await run_subprocess(["systemctl", "list-units", "--type=service", "--no-pager"])
    await send_message_in_chunks(context, update.effective_chat.id, output, "🛠️ System Services")
    
@restricted
async def temp(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    try:
        temps = psutil.sensors_temperatures()
        for key in ["cpu_thermal", "coretemp", "k10temp", "zenpower"]:
            if key in temps:
                cpu_temp = temps[key][0]
                await context.bot.send_message(chat_id=chat_id, text=f"🌡️ CPU Temperature: {cpu_temp.current}°C")
                return
        await context.bot.send_message(chat_id=chat_id, text="Could not read CPU temperature (sensor not found).")
    except Exception as e:
        await context.bot.send_message(chat_id=chat_id, text=f"Error reading temperature: {e}")

@restricted
async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        cpu_temp_str = "N/A"
        temps = psutil.sensors_temperatures()
        for key in ["cpu_thermal", "coretemp", "k10temp", "zenpower"]:
            if key in temps:
                cpu_temp_str = f"{temps[key][0].current}°C"
                break
        
        ram = f"{psutil.virtual_memory().percent}%"
        disk = f"{psutil.disk_usage('/').percent}%"
        
        uptime_seconds = time.time() - psutil.boot_time()
        days = int(uptime_seconds // (24 * 3600))
        hours = int((uptime_seconds % (24 * 3600)) // 3600)
        minutes = int((uptime_seconds % 3600) // 60)
        uptime_str = f"{days}d {hours}h {minutes}m"

        status_text = (
            f"🌡️ CPU Temp : {cpu_temp_str}\n"
            f"🧠 RAM Usage: {ram}\n"
            f"💾 Disk Usage: {disk}\n"
            f"⏰ Uptime   : {uptime_str}"
        )
        await send_message_in_chunks(context, update.effective_chat.id, status_text, "📊 System Status")
    except Exception as e:
        await send_message_in_chunks(context, update.effective_chat.id, f"Error retrieving status: {e}")

# --- Network Commands ---
@restricted
async def ip(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    output, _ = await run_subprocess(["ip", "a"])
    await send_message_in_chunks(context, update.effective_chat.id, output, "📍 IP Addresses")

@restricted
async def external_ip(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    try:
        response = requests.get('https://api.ipify.org', timeout=10)
        response.raise_for_status()
        await context.bot.send_message(chat_id=chat_id, text=f"🌍 External IP: {response.text}")
    except requests.RequestException as e:
        await context.bot.send_message(chat_id=chat_id, text=f"Could not retrieve external IP: {e}")

@restricted
async def wifi(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    await context.bot.send_message(chat_id=chat_id, text="📶 Scanning for WiFi networks...")
    output, error = await run_subprocess(["nmcli", "dev", "wifi", "list", "--rescan", "yes"])
    if error:
        await context.bot.send_message(chat_id=chat_id, text=f"Error scanning WiFi: {error}")
    elif not output:
        await context.bot.send_message(chat_id=chat_id, text="No WiFi networks found.")
    else:
        await send_message_in_chunks(context, chat_id, output, "Available WiFi Networks")

@restricted
async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    if not context.args:
        await context.bot.send_message(chat_id=chat_id, text="Please provide a host to ping, e.g., `/ping 8.8.8.8`")
        return
    host = context.args[0]
    output, error = await run_subprocess(["ping", "-c", "4", host])
    await send_message_in_chunks(context, chat_id, output or error, f"🏓 Pinging {host}")

@restricted
async def show_network_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    output, _ = await run_subprocess(["ip", "-s", "link"])
    await send_message_in_chunks(context, update.effective_chat.id, output, "🌐 Network Info")

# --- Utility Commands ---
@restricted
@cooldown(60)
async def speedtest(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    await context.bot.send_message(chat_id=chat_id, text="⚡ Running speedtest... This can take a minute.")
    output, error = await run_subprocess(["speedtest-cli", "--secure"])
    await send_message_in_chunks(context, chat_id, output or error, "Speedtest Results")

@restricted
async def uptime(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    output, _ = await run_subprocess(["uptime"])
    await send_message_in_chunks(context, update.effective_chat.id, output, "⏰ Uptime")

@restricted
async def weather(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    if not context.args:
        await context.bot.send_message(chat_id=chat_id, text="Usage: /weather <city>")
        return
    city = " ".join(context.args)
    url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={WEATHER_API_KEY}&units=metric"
    try:
        response = requests.get(url, timeout=10).json()
        if response.get("cod") == 200:
            main = response["main"]
            weather_desc = response["weather"][0]["description"]
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"☁️ Weather in {city.title()}: {main['temp']}°C, {weather_desc.capitalize()}"
            )
        else:
            await context.bot.send_message(chat_id=chat_id, text="City not found.")
    except requests.RequestException as e:
        await context.bot.send_message(chat_id=chat_id, text=f"Error fetching weather: {e}")

@restricted
async def joke(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    try:
        response = requests.get("https://official-joke-api.appspot.com/random_joke", timeout=10).json()
        await context.bot.send_message(chat_id=chat_id, text=f"😂\n{response['setup']}\n\n{response['punchline']}")
    except requests.RequestException as e:
        await context.bot.send_message(chat_id=chat_id, text=f"Error fetching joke: {e}")

# --- Monitoring ---
async def monitor_cpu_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        temps = psutil.sensors_temperatures()
        for key in ["cpu_thermal", "coretemp", "k10temp", "zenpower"]:
            if key in temps and temps[key][0].current > THRESHOLD_TEMP:
                await context.bot.send_message(
                    chat_id=context.job.chat_id,
                    text=f"🚨 HIGH CPU TEMP ALERT: {temps[key][0].current}°C"
                )
                return
    except Exception as e:
        logger.error(f"Error in CPU monitoring job: {e}")

async def monitor_ram_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        ram_usage = psutil.virtual_memory().percent
        if ram_usage > THRESHOLD_RAM:
            await context.bot.send_message(
                chat_id=context.job.chat_id,
                text=f"🚨 HIGH RAM USAGE ALERT: {ram_usage}%"
            )
    except Exception as e:
        logger.error(f"Error in RAM monitoring job: {e}")

@restricted
async def start_monitoring(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    for job in context.job_queue.get_jobs_by_name("monitor_cpu"):
        job.schedule_removal()
    
    context.job_queue.run_repeating(monitor_cpu_job, interval=60, first=10, chat_id=chat_id, name="monitor_cpu")
    await context.bot.send_message(chat_id=chat_id, text="🌡️ Started monitoring CPU temperature.")

@restricted
async def stop_monitoring(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    jobs = context.job_queue.get_jobs_by_name("monitor_cpu")
    if not jobs:
        await context.bot.send_message(chat_id=chat_id, text="CPU monitoring is not running.")
        return
    for job in jobs:
        job.schedule_removal()
    await context.bot.send_message(chat_id=chat_id, text="❄️ Stopped monitoring CPU temperature.")

@restricted
async def start_monitoring_ram(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    for job in context.job_queue.get_jobs_by_name("monitor_ram"):
        job.schedule_removal()
    
    context.job_queue.run_repeating(monitor_ram_job, interval=60, first=10, chat_id=chat_id, name="monitor_ram")
    await context.bot.send_message(chat_id=chat_id, text="📈 Started monitoring RAM usage.")

@restricted
async def stop_monitoring_ram(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    jobs = context.job_queue.get_jobs_by_name("monitor_ram")
    if not jobs:
        await context.bot.send_message(chat_id=chat_id, text="RAM monitoring is not running.")
        return
    for job in jobs:
        job.schedule_removal()
    await context.bot.send_message(chat_id=chat_id, text="📉 Stopped monitoring RAM usage.")

# --- Help and Menu Callbacks ---
@restricted
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Displays a formatted help message with all commands."""
    message = "*Available Commands*\n\n"
    
    message += "*System Commands*\n"
    for cmd in system_commands:
        message += f"{cmd['emoji']} {cmd['name']} - {cmd['description']}\n"
    
    message += "\n*Network Commands*\n"
    for cmd in network_commands:
        message += f"{cmd['emoji']} {cmd['name']} - {cmd['description']}\n"
        
    message += "\n*Utility Commands*\n"
    for cmd in utility_commands:
        message += f"{cmd['emoji']} {cmd['name']} - {cmd['description']}\n"
    
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=message,
        parse_mode="Markdown"
    )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles all button presses from inline keyboards."""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    menu_map = {
        "system_menu": ("⚙️ System Commands:", system_commands),
        "network_menu": ("🌐 Network Commands:", network_commands),
        "utility_menu": ("🛠️ Utility Commands:", utility_commands),
    }

    if data in menu_map:
        title, commands = menu_map[data]
        keyboard = [[InlineKeyboardButton(f"{cmd['emoji']} {cmd['name']}", callback_data=cmd["name"][1:])] for cmd in commands]
        keyboard.append([InlineKeyboardButton("⬅️ Back to Main Menu", callback_data="main_menu")])
        await query.edit_message_text(title, reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif data == "main_menu":
        await start(update, context)
    
    elif data == "help_menu":
        await help_command(update, context)

    else:
        command_func = COMMAND_MAP.get(data)
        if command_func:
            await command_func(update, context)
        else:
            await query.edit_message_text("Unknown command.")

def main() -> None:
    """Start the bot."""
    application = Application.builder().token(TELEGRAM_TOKEN).build()

    global COMMAND_MAP
    COMMAND_MAP = {
        "update": update_system, "reboot": reboot, "shutdown": shutdown,
        "disk_usage": disk_usage, "free_memory": free_memory, "show_processes": show_processes,
        "show_system_services": show_system_services, "start_monitoring": start_monitoring,
        "stop_monitoring": stop_monitoring, "start_monitoring_ram": start_monitoring_ram,
        "stop_monitoring_ram": stop_monitoring_ram, "temp": temp, "status": status,
        "ip": ip, "external_ip": external_ip, "wifi": wifi, "ping": ping,
        "show_network_info": show_network_info, "speedtest": speedtest,
        "uptime": uptime, "weather": weather, "joke": joke
    }
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    
    # Register handlers for both underscore and non-underscore commands
    for cmd_name, cmd_func in COMMAND_MAP.items():
        application.add_handler(CommandHandler(cmd_name, cmd_func))
        if "_" in cmd_name:
            application.add_handler(CommandHandler(cmd_name.replace("_", ""), cmd_func))

    application.add_handler(CallbackQueryHandler(button_callback))

    logger.info(f"Bot v{__version__} is running...")
    application.run_polling()

if __name__ == "__main__":
    main()