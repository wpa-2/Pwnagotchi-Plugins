#!/usr/bin/env python3
import os
import logging
import subprocess
import threading
import asyncio
from time import sleep, time

# CRITICAL: Monkey-patch APScheduler BEFORE importing telegram.ext
# Python 3.13 changed timezone handling, but APScheduler still requires pytz
try:
    import pytz
    
    # Patch apscheduler.util functions
    import apscheduler.util
    
    def patched_astimezone(obj):
        """Always return pytz.UTC for Python 3.13 compatibility"""
        return pytz.UTC
    
    def patched_get_localzone():
        """Always return pytz.UTC for Python 3.13 compatibility"""
        return pytz.UTC
    
    # Apply patches
    apscheduler.util.astimezone = patched_astimezone
    apscheduler.util.get_localzone = patched_get_localzone
    
    print("[TelePwn] APScheduler patched for Python 3.13")
except Exception as e:
    print(f"[TelePwn] FAILED to patch APScheduler: {e}")
    import traceback
    traceback.print_exc()

# NOW import telegram (which will use the patched APScheduler)
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import pwnagotchi
import pwnagotchi.plugins as plugins
import pwnagotchi.ui.view as view
import toml
import requests
import psutil
import schedule
from datetime import datetime

# Suppress verbose HTTP logging from telegram library
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.WARNING)

# Constants
CONFIG_FILE = "/etc/pwnagotchi/config.toml"
HANDSHAKE_DIR = "/home/pi/handshakes/"
MAX_MESSAGE_LENGTH = 4096 // 2
LOG_PATH = "/etc/pwnagotchi/log/pwnagotchi.log"
COOLDOWN_SECONDS = 2
PLUGIN_DIRS = [
    "/usr/local/share/pwnagotchi/custom-plugins/",
    "/home/pi/.pwn/lib/python3.13/site-packages/pwnagotchi/plugins/default/"
]

SHARE_COOLDOWN = 300
MAX_SHARES_PER_DAY = 10
MILESTONE_LEVELS = [100, 500, 1000, 5000, 10000]

WEBHOOK_FILE = "/etc/pwnagotchi/telepwn_webhooks.toml"
SCHEDULE_FILE = "/etc/pwnagotchi/telepwn_schedules.toml"

INITIAL_MENU = [[InlineKeyboardButton("📋 Menu", callback_data="show_menu")]]

MAIN_MENU = [
    [
        InlineKeyboardButton("🔄 Reboot", callback_data="reboot"),
        InlineKeyboardButton("⏏️ Shutdown", callback_data="shutdown"),
        InlineKeyboardButton("⏳ Uptime", callback_data="uptime"),
    ],
    [
        InlineKeyboardButton("🤝 Handshakes", callback_data="handshake_count"),
        InlineKeyboardButton("📸 Screenshot", callback_data="take_screenshot"),
        InlineKeyboardButton("💾 Backup", callback_data="create_backup"),
    ],
    [
        InlineKeyboardButton("🔧 Manual Restart", callback_data="restart_manual"),
        InlineKeyboardButton("🤖 Auto Restart", callback_data="restart_auto"),
        InlineKeyboardButton("🗡️ Kill", callback_data="pwnkill"),
    ],
    [
        InlineKeyboardButton("🖌️ Clear", callback_data="clear"),
        InlineKeyboardButton("📜 Logs", callback_data="logs"),
        InlineKeyboardButton("📥 Inbox", callback_data="inbox"),
    ],
    [
        InlineKeyboardButton("🔩 Plugins", callback_data="plugins"),
        InlineKeyboardButton("⬅️ Back", callback_data="back_to_initial"),
    ],
]


class TelePwn(plugins.Plugin):
    __author__ = "WPA2"
    __version__ = "2.0.0"
    __license__ = "GPL3"
    __description__ = "Telegram interface for Pwnagotchi - Python 3.13 compatible"
    __dependencies__ = ("python-telegram-bot>=20.0", "requests>=2.28.0", "psutil>=5.9.0", "schedule>=1.2.0", "toml>=0.10.0", "pytz")

    _instance = None
    _lock = threading.Lock()

    def __init__(self):
        self.logger = logging.getLogger("TelePwn")
        self.options = {
            "bot_token": "",
            "chat_id": "",
            "auto_start": True,
            "send_message": True,
            "send_handshake_file": True,  # Always send files - they're tiny anyway!
            "community_enabled": False,
            "community_chat_id": ""  # Optional: Telegram channel/group for sharing
        }
        self.screen_rotation = 0
        self.application = None
        self.agent = None
        self.plugin_states = {}
        self.webhooks = self._load_webhooks()
        self.schedules = self._load_schedules()
        self.running = False
        self.user_last_share = {}
        self.user_share_count = {}
        self.pending_screenshots = {}
        self.last_handshake_count = 0
        self.last_plugin_list = []
        self.user_states = {}
        self.schedule_thread = None
        self.bot_loop = None  # Store the bot's event loop
        self.bot_initializing = False  # Prevent multiple simultaneous starts

    def _load_webhooks(self):
        try:
            if os.path.exists(WEBHOOK_FILE) and os.path.getsize(WEBHOOK_FILE) > 0:
                with open(WEBHOOK_FILE, "r") as f:
                    return toml.load(f)
            return {}
        except Exception as e:
            self.logger.error(f"[TelePwn] Failed to load webhooks: {e}")
            return {}

    def _save_webhooks(self):
        try:
            with open(WEBHOOK_FILE, "w") as f:
                toml.dump(self.webhooks, f)
        except Exception as e:
            self.logger.error(f"[TelePwn] Failed to save webhooks: {e}")

    def _load_schedules(self):
        try:
            if os.path.exists(SCHEDULE_FILE) and os.path.getsize(SCHEDULE_FILE) > 0:
                with open(SCHEDULE_FILE, "r") as f:
                    return toml.load(f)
            return {}
        except Exception as e:
            self.logger.error(f"[TelePwn] Failed to load schedules: {e}")
            return {}

    def _save_schedules(self):
        try:
            with open(SCHEDULE_FILE, "w") as f:
                toml.dump(self.schedules, f)
        except Exception as e:
            self.logger.error(f"[TelePwn] Failed to save schedules: {e}")

    def on_loaded(self):
        self.logger.info("[TelePwn] Plugin loaded.")
        try:
            with open(CONFIG_FILE, "r") as f:
                config = toml.load(f)
                plugins_config = config.get("main", {}).get("plugins", {}).get("telepwn", {})
                self.options["bot_token"] = plugins_config.get("bot_token", "")
                self.options["chat_id"] = plugins_config.get("chat_id", "")
                self.options["send_message"] = plugins_config.get("send_message", True)
                self.options["send_handshake_file"] = plugins_config.get("send_handshake_file", True)  # Default: enabled
                self.options["auto_start"] = plugins_config.get("auto_start", True)
                self.options["community_enabled"] = plugins_config.get("community_enabled", False)
                self.options["community_chat_id"] = plugins_config.get("community_chat_id", "")
        except Exception as e:
            self.logger.error(f"[TelePwn] Failed to load config: {e}")
            return

        if not self.options.get("bot_token") or not self.options.get("chat_id"):
            self.logger.error("[TelePwn] Missing bot_token or chat_id in config.toml.")
            return

        with TelePwn._lock:
            if TelePwn._instance:
                TelePwn._instance.stop_bot()
            TelePwn._instance = self

        self.load_config()
        self.start_scheduler()
        
        if self.options.get("community_enabled"):
            self.logger.info("[TelePwn] Community features ENABLED")
        else:
            self.logger.info("[TelePwn] Community features DISABLED")

    def on_unload(self, ui=None):
        self.logger.info("[TelePwn] Plugin unloading...")
        with TelePwn._lock:
            if TelePwn._instance is self:
                self.stop_bot()
                self.stop_scheduler()
                TelePwn._instance = None

    def load_config(self):
        try:
            with open(CONFIG_FILE, "r") as f:
                config = toml.load(f)
                self.screen_rotation = int(config.get("ui", {}).get("display", {}).get("rotation", 0))
                plugins_config = config.get("main", {}).get("plugins", {})
                for plugin, settings in plugins_config.items():
                    self.plugin_states[plugin] = settings.get("enabled", False)
        except Exception as e:
            self.logger.warning(f"Failed to load config: {e}")

    def on_agent(self, agent):
        self.agent = agent
        if self.options.get("auto_start", False):
            self.on_internet_available(agent)

    def on_handshake(self, agent, filename, access_point, client_station):
        try:
            if self.application and self.bot_loop and self.options.get("send_message", False):
                ap_name = access_point.get('hostname', 'Unknown')
                client_mac = client_station.get('mac', 'Unknown')
                message = f"🤝 New handshake: {ap_name} - {client_mac}"
                
                # Send notification message
                asyncio.run_coroutine_threadsafe(
                    self.application.bot.send_message(
                        chat_id=int(self.options["chat_id"]),
                        text=message
                    ),
                    self.bot_loop
                )
                
                # Send the .pcap file if enabled
                if self.options.get("send_handshake_file", False) and filename:
                    handshake_path = os.path.join(HANDSHAKE_DIR, filename)
                    if os.path.exists(handshake_path):
                        asyncio.run_coroutine_threadsafe(
                            self._send_handshake_file(handshake_path, ap_name, client_mac),
                            self.bot_loop
                        )
                
            if self.options.get("community_enabled"):
                self.check_milestone(agent)
        except Exception as e:
            self.logger.error(f"Error sending handshake: {e}")

    async def _send_handshake_file(self, filepath, ap_name, client_mac):
        """Send the handshake .pcap file to Telegram"""
        try:
            with open(filepath, 'rb') as pcap_file:
                caption = f"🤝 {ap_name} - {client_mac}"
                await self.application.bot.send_document(
                    chat_id=int(self.options["chat_id"]),
                    document=pcap_file,
                    caption=caption
                )
            self.logger.info(f"[TelePwn] Sent handshake file: {filepath}")
        except Exception as e:
            self.logger.error(f"[TelePwn] Failed to send handshake file: {e}")

    def check_milestone(self, agent):
        try:
            current_count = len([f for f in os.listdir(HANDSHAKE_DIR) if os.path.isfile(os.path.join(HANDSHAKE_DIR, f))])
            
            if current_count in MILESTONE_LEVELS and current_count != self.last_handshake_count:
                self.last_handshake_count = current_count
                
                message = f"🎉 MILESTONE UNLOCKED! 🎉\n\nYou just captured your {current_count}th handshake!\n\nShare this achievement with the community?"
                keyboard = [
                    [InlineKeyboardButton("📤 Share Milestone!", callback_data="share_milestone")],
                    [InlineKeyboardButton("🙈 Keep Private", callback_data="cancel")]
                ]
                
                if self.bot_loop:
                    asyncio.run_coroutine_threadsafe(
                        self.application.bot.send_message(
                            chat_id=int(self.options["chat_id"]),
                            text=message,
                            reply_markup=InlineKeyboardMarkup(keyboard)
                        ),
                        self.bot_loop
                    )
                
                self.logger.info(f"[TelePwn] Milestone {current_count} detected!")
        except Exception as e:
            self.logger.error(f"[TelePwn] Milestone check failed: {e}")

    def on_internet_available(self, agent):
        if self.bot_initializing:
            self.logger.debug("[TelePwn] Already initializing...")
            return
        if self.application and self.application.running:
            self.logger.debug("[TelePwn] Already connected.")
            return
        self.logger.info("[TelePwn] Starting Telegram bot...")
        self.agent = agent
        self.bot_initializing = True
        try:
            self.start_bot()
        except Exception as e:
            self.logger.error(f"[TelePwn] Error connecting to Telegram: {e}")
            self.bot_initializing = False

    def start_bot(self):
        # Start bot in background thread
        def run_bot():
            try:
                # Create event loop FIRST
                self.bot_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self.bot_loop)
                
                self.logger.info("[TelePwn] Event loop created, building application...")
                
                # NOW build application (in thread with event loop)
                self.application = (
                    Application.builder()
                    .token(self.options["bot_token"])
                    .build()
                )
                
                self.logger.info("[TelePwn] Application built, registering handlers...")
                
                # Register handlers
                self.application.add_handler(CommandHandler("start", self.start))
                self.application.add_handler(CommandHandler("menu", self.start))  # /menu = /start
                self.application.add_handler(CommandHandler("help", self.help_command))
                self.application.add_handler(CommandHandler("reboot", self.reboot))
                self.application.add_handler(CommandHandler("shutdown", self.shutdown))
                self.application.add_handler(CommandHandler("uptime", self.uptime))
                self.application.add_handler(CommandHandler("handshakes", self.handshake_count))
                self.application.add_handler(CommandHandler("screenshot", self.take_screenshot))
                self.application.add_handler(CommandHandler("backup", self.create_backup))
                self.application.add_handler(CommandHandler("restart_manual", self.restart_manual))
                self.application.add_handler(CommandHandler("restart_auto", self.restart_auto))
                self.application.add_handler(CommandHandler("kill", self.pwnkill))
                self.application.add_handler(CommandHandler("clear", self.clear))
                self.application.add_handler(CommandHandler("logs", self.logs))
                self.application.add_handler(CommandHandler("inbox", self.inbox))
                self.application.add_handler(CommandHandler("plugins", self.plugins_menu))
                self.application.add_handler(CommandHandler("stats", self.system_stats))
                self.application.add_handler(CallbackQueryHandler(self.button_handler))
                self.application.add_handler(MessageHandler(filters.Document.ALL, self.handle_document_upload))
                
                # Add error handler to suppress network errors during retries
                async def error_handler(update, context):
                    """Log errors but don't crash"""
                    if "httpx.ConnectError" in str(context.error):
                        # Network errors are normal during startup/retries
                        pass
                    else:
                        self.logger.error(f"Update {update} caused error: {context.error}")
                
                self.application.add_error_handler(error_handler)
                
                # Schedule startup message
                self.bot_loop.create_task(self._send_startup_message())
                
                # Mark as initialized
                self.bot_initializing = False
                self.logger.info("[TelePwn] Bot initialization complete, starting polling...")
                
                # Run bot (disable signal handlers - we're in a background thread!)
                self.application.run_polling(
                    drop_pending_updates=True,
                    stop_signals=None  # CRITICAL: No signal handlers in daemon thread
                )
                self.logger.info("[TelePwn] Bot polling started successfully!")
                
            except Exception as e:
                self.logger.error(f"[TelePwn] FATAL ERROR in bot thread: {e}")
                import traceback
                self.logger.error(f"[TelePwn] Traceback: {traceback.format_exc()}")
                self.bot_initializing = False
        
        bot_thread = threading.Thread(target=run_bot, daemon=True)
        bot_thread.start()
        
        # Wait a moment for application to be built
        sleep(0.5)

    async def _send_startup_message(self):
        await asyncio.sleep(3)  # Wait for bot to fully initialize
        try:
            self.logger.info("[TelePwn] Setting bot commands...")
            await self.application.bot.set_my_commands([
                BotCommand("start", "Open the main menu"),
                BotCommand("menu", "Show the main menu"),
                BotCommand("help", "Show help and commands"),
                BotCommand("reboot", "Reboot the device"),
                BotCommand("shutdown", "Shutdown device"),
                BotCommand("uptime", "Check uptime"),
                BotCommand("handshakes", "Count handshakes"),
                BotCommand("screenshot", "Take a screenshot"),
                BotCommand("backup", "Create backup"),
                BotCommand("restart_manual", "Restart in manual mode"),
                BotCommand("restart_auto", "Restart in auto mode"),
                BotCommand("kill", "Kill daemon"),
                BotCommand("clear", "Clear screen"),
                BotCommand("logs", "View logs"),
                BotCommand("inbox", "Check inbox"),
                BotCommand("plugins", "Manage plugins"),
                BotCommand("stats", "System stats"),
            ])
            self.logger.info("[TelePwn] Bot commands set successfully!")
            
            status_msg = f"🖐 TelePwn v{self.__version__} is online!"
            if self.options.get("community_enabled"):
                status_msg += "\n\n🌟 Community features enabled!"
            
            self.logger.info("[TelePwn] Sending startup message...")
            await self.application.bot.send_message(
                chat_id=int(self.options["chat_id"]),
                text=status_msg,
                reply_markup=InlineKeyboardMarkup(INITIAL_MENU)
            )
            self.logger.info("[TelePwn] Startup message sent successfully!")
        except Exception as e:
            self.logger.error(f"[TelePwn] Failed to send startup message: {e}")

    def stop_bot(self):
        if self.application and self.application.running:
            try:
                if self.bot_loop:
                    asyncio.run_coroutine_threadsafe(self.application.stop(), self.bot_loop)
                self.logger.info("[TelePwn] Bot stopped.")
            except Exception as e:
                self.logger.error(f"[TelePwn] Error stopping bot: {e}")

    def start_scheduler(self):
        self.running = True
        self.schedule_thread = threading.Thread(target=self.run_scheduler, daemon=True)
        self.schedule_thread.start()

    def stop_scheduler(self):
        self.running = False
        schedule.clear()

    def run_scheduler(self):
        for task_id, task in self.schedules.items():
            action = task["action"]
            interval = task["interval"]
            if action == "reboot":
                schedule.every(interval).hours.do(lambda: subprocess.run(["sudo", "reboot"]))
            elif action == "backup":
                schedule.every(interval).hours.do(self._scheduled_backup)
        while self.running:
            schedule.run_pending()
            sleep(60)

    def _scheduled_backup(self):
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = f"/home/pi/telepwn_backup_{timestamp}.tar.gz"
            subprocess.run(["sudo", "tar", "czf", backup_path, "/etc/pwnagotchi/", "/home/pi/handshakes/"], check=True)
            if self.bot_loop:
                asyncio.run_coroutine_threadsafe(
                    self.application.bot.send_document(
                        chat_id=int(self.options["chat_id"]),
                        document=open(backup_path, 'rb')
                    ),
                    self.bot_loop
                )
        except Exception as e:
            self.logger.error(f"Scheduled backup failed: {e}")

    async def send_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE, text: str, keyboard=None):
        try:
            if len(text) > MAX_MESSAGE_LENGTH:
                for chunk in [text[i:i + MAX_MESSAGE_LENGTH] for i in range(0, len(text), MAX_MESSAGE_LENGTH)]:
                    await context.bot.send_message(chat_id=update.effective_chat.id, text=chunk)
            else:
                if update.callback_query:
                    await update.callback_query.edit_message_text(
                        text=text,
                        reply_markup=InlineKeyboardMarkup(keyboard) if keyboard else None
                    )
                else:
                    await update.effective_message.reply_text(
                        text=text,
                        reply_markup=InlineKeyboardMarkup(keyboard) if keyboard else None
                    )
        except Exception as e:
            self.logger.error(f"Error sending message: {e}")
            await context.bot.send_message(chat_id=update.effective_chat.id, text=str(e))

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self.send_message(update, context, f"🖐 TelePwn v{self.__version__}\nSelect an option:", MAIN_MENU)

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        help_text = f"""🖐 TelePwn v{self.__version__} Help

**Quick Commands:**
/start or /menu - Show main menu
/help - Show this help
/uptime - System uptime
/handshakes - Handshake count  
/screenshot - Take screenshot
/backup - Create backup
/stats - System statistics

**Tip:** Use the menu buttons for easier navigation!"""
        
        keyboard = [[InlineKeyboardButton("📋 Back to Menu", callback_data="show_menu")]]
        await self.send_message(update, context, help_text, keyboard)

    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_chat.id != int(self.options.get("chat_id")):
            return
        
        query = update.callback_query
        await query.answer()

        actions = {
            "reboot": self.reboot,
            "confirm_reboot": self.confirm_reboot,
            "shutdown": self.shutdown,
            "confirm_shutdown": self.confirm_shutdown,
            "uptime": self.uptime,
            "handshake_count": self.handshake_count,
            "take_screenshot": self.take_screenshot,
            "create_backup": self.create_backup,
            "restart_manual": self.restart_manual,
            "restart_auto": self.restart_auto,
            "pwnkill": self.pwnkill,
            "clear": self.clear,
            "logs": self.logs,
            "inbox": self.inbox,
            "plugins": self.plugins_menu,
            "cancel": self.start,
            "show_menu": self.start,
            "back_to_initial": lambda u, c: self.send_message(u, c, f"🖐 TelePwn v{self.__version__}", INITIAL_MENU),
            "offer_community_share": self.offer_community_share,
            "confirm_community_share": self.confirm_community_share,
            "cancel_share": self.cancel_share,
            "share_milestone": self.share_milestone_screenshot,
        }

        if query.data.startswith("toggle_plugin_"):
            plugin_name = query.data[len("toggle_plugin_"):]
            await self.toggle_plugin(update, context, plugin_name)
        elif query.data in actions:
            await actions[query.data](update, context)

    async def reboot(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        keyboard = [
            [InlineKeyboardButton("✅ Confirm", callback_data="confirm_reboot")],
            [InlineKeyboardButton("❌ Cancel", callback_data="cancel")],
        ]
        await self.send_message(update, context, "⚠️ Confirm reboot?", keyboard)

    async def confirm_reboot(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self.send_message(update, context, "🔄 Rebooting...")
        subprocess.run(["sudo", "reboot"], check=True)

    async def shutdown(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        keyboard = [
            [InlineKeyboardButton("✅ Confirm", callback_data="confirm_shutdown")],
            [InlineKeyboardButton("❌ Cancel", callback_data="cancel")],
        ]
        await self.send_message(update, context, "⚠️ Confirm shutdown?", keyboard)

    async def confirm_shutdown(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self.send_message(update, context, "⏏️ Shutting down...")
        subprocess.run(["sudo", "systemctl", "stop", "pwnagotchi"], check=True)
        subprocess.run(["sudo", "shutdown", "-h", "now"], check=True)

    async def uptime(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            with open("/proc/uptime", "r") as f:
                uptime_seconds = float(f.readline().split()[0])
            hours = int(uptime_seconds // 3600)
            minutes = int((uptime_seconds % 3600) // 60)
            
            keyboard = [[InlineKeyboardButton("📋 Back to Menu", callback_data="show_menu")]]
            await self.send_message(update, context, f"⏳ Uptime: {hours}h {minutes}m", keyboard)
        except Exception as e:
            await self.send_message(update, context, f"⛔ Error: {e}")

    async def handshake_count(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            count = len([f for f in os.listdir(HANDSHAKE_DIR) if os.path.isfile(os.path.join(HANDSHAKE_DIR, f))])
            
            keyboard = [[InlineKeyboardButton("📋 Back to Menu", callback_data="show_menu")]]
            await self.send_message(update, context, f"🤝 Handshakes: {count}", keyboard)
        except Exception as e:
            await self.send_message(update, context, f"⛔ Error: {e}")

    async def take_screenshot(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="upload_photo")
            
            display = self.agent.view()
            screenshot_path = "/root/telepwn_screenshot.png"
            display.image().rotate(self.screen_rotation).save(screenshot_path, "png")
            
            user_id = update.effective_user.id
            self.pending_screenshots[user_id] = screenshot_path
            
            keyboard = []
            if self.options.get("community_enabled"):
                keyboard = [
                    [InlineKeyboardButton("📤 Share to Community", callback_data="offer_community_share")],
                    [InlineKeyboardButton("❌ No Thanks", callback_data="cancel_share")]
                ]
            
            with open(screenshot_path, "rb") as photo:
                await context.bot.send_photo(
                    chat_id=update.effective_chat.id,
                    photo=photo,
                    caption="📸 Your screenshot",
                    reply_markup=InlineKeyboardMarkup(keyboard) if keyboard else None
                )
        except Exception as e:
            await self.send_message(update, context, f"⛔ Error: {e}")

    async def offer_community_share(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        # Check if community chat is configured
        if not self.options.get("community_chat_id"):
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="⚠️ Community sharing not configured. Add community_chat_id to config."
            )
            return
        
        user_id = update.effective_user.id
        
        if user_id not in self.pending_screenshots:
            await context.bot.send_message(chat_id=update.effective_chat.id, text="⛔ Screenshot expired.")
            return
        
        can_share, message = self.check_share_limits(user_id)
        if not can_share:
            await context.bot.send_message(chat_id=update.effective_chat.id, text=message)
            return
        
        community_name = self.options["community_chat_id"]
        keyboard = [
            [InlineKeyboardButton("✅ Yes, Share", callback_data="confirm_community_share")],
            [InlineKeyboardButton("❌ Cancel", callback_data="cancel_share")]
        ]
        
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"⚠️ Share to {community_name}?\n\n{message}",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    def check_share_limits(self, user_id):
        current_time = time()
        today = datetime.now().date()
        
        last_share = self.user_last_share.get(user_id, 0)
        if current_time - last_share < SHARE_COOLDOWN:
            wait_time = SHARE_COOLDOWN - (current_time - last_share)
            return False, f"⏰ Wait {int(wait_time // 60)}m {int(wait_time % 60)}s"
        
        if user_id not in self.user_share_count:
            self.user_share_count[user_id] = {}
        
        self.user_share_count[user_id] = {
            date: count for date, count in self.user_share_count[user_id].items()
            if date >= today
        }
        
        shares_today = self.user_share_count[user_id].get(today, 0)
        if shares_today >= MAX_SHARES_PER_DAY:
            return False, f"🚫 Daily limit reached ({shares_today}/{MAX_SHARES_PER_DAY})"
        
        return True, f"✅ Shares today: {shares_today}/{MAX_SHARES_PER_DAY}"

    async def confirm_community_share(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        username = update.effective_user.username or "Anonymous"
        
        screenshot_path = self.pending_screenshots.get(user_id)
        if not screenshot_path or not os.path.exists(screenshot_path):
            await context.bot.send_message(chat_id=update.effective_chat.id, text="⛔ Screenshot not found.")
            return
        
        try:
            handshakes = len([f for f in os.listdir(HANDSHAKE_DIR) if os.path.isfile(os.path.join(HANDSHAKE_DIR, f))])
            caption = f"📸 Shared by @{username}\n\n#screenshot #pwnagotchi"
            
            with open(screenshot_path, "rb") as photo:
                await context.bot.send_photo(
                    chat_id=self.options["community_chat_id"],
                    photo=photo,
                    caption=caption
                )
            
            current_time = time()
            today = datetime.now().date()
            self.user_last_share[user_id] = current_time
            if today not in self.user_share_count[user_id]:
                self.user_share_count[user_id][today] = 0
            self.user_share_count[user_id][today] += 1
            
            del self.pending_screenshots[user_id]
            
            community_name = self.options["community_chat_id"]
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"✅ Shared to {community_name}!"
            )
        except Exception as e:
            await context.bot.send_message(chat_id=update.effective_chat.id, text=f"⛔ Failed: {e}")

    async def share_milestone_screenshot(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        username = update.effective_user.username or "Anonymous"
        
        can_share, message = self.check_share_limits(user_id)
        if not can_share:
            await context.bot.send_message(chat_id=update.effective_chat.id, text=message)
            return
        
        try:
            display = self.agent.view()
            screenshot_path = "/root/telepwn_milestone.png"
            display.image().rotate(self.screen_rotation).save(screenshot_path, "png")
            
            handshakes = len([f for f in os.listdir(HANDSHAKE_DIR) if os.path.isfile(os.path.join(HANDSHAKE_DIR, f))])
            caption = f"📸 Shared by @{username}\n🎉 Milestone: {handshakes} handshakes!\n\n#milestone #{handshakes}handshakes #pwnagotchi"
            
            with open(screenshot_path, "rb") as photo:
                await context.bot.send_photo(
                    chat_id=self.options["community_chat_id"],
                    photo=photo,
                    caption=caption
                )
            
            current_time = time()
            today = datetime.now().date()
            self.user_last_share[user_id] = current_time
            if user_id not in self.user_share_count:
                self.user_share_count[user_id] = {}
            if today not in self.user_share_count[user_id]:
                self.user_share_count[user_id][today] = 0
            self.user_share_count[user_id][today] += 1
            
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"🎉 Milestone shared!"
            )
        except Exception as e:
            await context.bot.send_message(chat_id=update.effective_chat.id, text=f"⛔ Failed: {e}")

    async def cancel_share(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        if user_id in self.pending_screenshots:
            del self.pending_screenshots[user_id]
        
        await context.bot.send_message(chat_id=update.effective_chat.id, text="✅ Cancelled")

    async def create_backup(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self.send_message(update, context, "💾 Creating backup...")
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = f"/home/pi/telepwn_backup_{timestamp}.tar.gz"
            subprocess.run(["sudo", "tar", "czf", backup_path, "/etc/pwnagotchi/", "/home/pi/handshakes/"], check=True)
            
            with open(backup_path, "rb") as backup:
                await context.bot.send_document(chat_id=update.effective_chat.id, document=backup)
            
            keyboard = [[InlineKeyboardButton("📋 Back to Menu", callback_data="show_menu")]]
            await self.send_message(update, context, "✅ Backup sent", keyboard)
        except Exception as e:
            keyboard = [[InlineKeyboardButton("📋 Back to Menu", callback_data="show_menu")]]
            await self.send_message(update, context, f"⛔ Failed: {e}", keyboard)

    async def restart_manual(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            await self.send_message(update, context, "🔧 Restarting in manual mode...")
            subprocess.run(["sudo", "touch", "/root/.pwnagotchi-manual"], check=True)
            subprocess.run(["sudo", "systemctl", "restart", "pwnagotchi"], check=True)
        except Exception as e:
            keyboard = [[InlineKeyboardButton("📋 Back to Menu", callback_data="show_menu")]]
            await self.send_message(update, context, f"⛔ Failed: {e}", keyboard)

    async def restart_auto(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            await self.send_message(update, context, "🤖 Restarting in auto mode...")
            subprocess.run(["sudo", "touch", "/root/.pwnagotchi-auto"], check=True)
            subprocess.run(["sudo", "systemctl", "restart", "pwnagotchi"], check=True)
        except Exception as e:
            keyboard = [[InlineKeyboardButton("📋 Back to Menu", callback_data="show_menu")]]
            await self.send_message(update, context, f"⛔ Failed: {e}", keyboard)

    async def pwnkill(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            await self.send_message(update, context, "🗡️ Killing daemon...")
            subprocess.run(["sudo", "killall", "-USR1", "pwnagotchi"], check=True)
            keyboard = [[InlineKeyboardButton("📋 Back to Menu", callback_data="show_menu")]]
            await self.send_message(update, context, "✅ Daemon killed", keyboard)
        except Exception as e:
            keyboard = [[InlineKeyboardButton("📋 Back to Menu", callback_data="show_menu")]]
            await self.send_message(update, context, f"⛔ Failed: {e}", keyboard)

    async def clear(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            # Check if agent and view are available
            if not self.agent:
                keyboard = [[InlineKeyboardButton("📋 Back to Menu", callback_data="show_menu")]]
                await self.send_message(update, context, "⚠️ Running in headless mode (no display to clear)", keyboard)
                return
                
            display = self.agent.view()
            if not display:
                keyboard = [[InlineKeyboardButton("📋 Back to Menu", callback_data="show_menu")]]
                await self.send_message(update, context, "⚠️ No display available", keyboard)
                return
                
            # Clear display
            display.clear()
            display.update(force=True)
            keyboard = [[InlineKeyboardButton("📋 Back to Menu", callback_data="show_menu")]]
            await self.send_message(update, context, "🖌️ Display cleared!", keyboard)
        except AttributeError as e:
            # Handle missing clear() method
            keyboard = [[InlineKeyboardButton("📋 Back to Menu", callback_data="show_menu")]]
            await self.send_message(update, context, "⚠️ Clear not supported (headless mode)", keyboard)
        except Exception as e:
            self.logger.error(f"Clear failed: {e}")
            keyboard = [[InlineKeyboardButton("📋 Back to Menu", callback_data="show_menu")]]
            await self.send_message(update, context, f"⛔ Failed: {e}", keyboard)

    async def logs(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            log_output = subprocess.check_output(["tail", "-n", "50", LOG_PATH], text=True)
            keyboard = [[InlineKeyboardButton("📋 Back to Menu", callback_data="show_menu")]]
            await self.send_message(update, context, f"📜 Logs:\n```\n{log_output}\n```", keyboard)
        except Exception as e:
            await self.send_message(update, context, f"⛔ Failed: {e}")

    async def inbox(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            inbox_output = subprocess.check_output(["pwngrid", "--inbox"], text=True)
            keyboard = [[InlineKeyboardButton("📋 Back to Menu", callback_data="show_menu")]]
            await self.send_message(update, context, f"📥 Inbox:\n```\n{inbox_output}\n```", keyboard)
        except Exception as e:
            await self.send_message(update, context, f"⛔ Failed: {e}")

    async def plugins_menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        plugins_found = self.get_plugins()
        if not plugins_found:
            await self.send_message(update, context, "⚠ No plugins found")
            return

        keyboard = []
        for plugin in plugins_found:
            state = self.plugin_states.get(plugin, False)
            emoji = "✅" if state else "❌"
            keyboard.append([InlineKeyboardButton(f"{emoji} {plugin}", callback_data=f"toggle_plugin_{plugin}")])
        keyboard.append([InlineKeyboardButton("📋 Back to Menu", callback_data="show_menu")])
        await self.send_message(update, context, "🔩 Plugins:", keyboard)

    def get_plugins(self):
        plugins_found = set()
        for directory in PLUGIN_DIRS:
            try:
                if os.path.exists(directory):
                    for filename in os.listdir(directory):
                        if filename.endswith(".py") and filename != "__init__.py":
                            plugins_found.add(filename[:-3])
            except Exception as e:
                self.logger.error(f"Failed to scan {directory}: {e}")

        try:
            with open(CONFIG_FILE, "r") as f:
                config = toml.load(f)
                plugins_config = config.get("main", {}).get("plugins", {})
                for plugin in plugins_found:
                    self.plugin_states[plugin] = plugins_config.get(plugin, {}).get("enabled", False)
        except Exception as e:
            self.logger.error(f"Failed to load plugin states: {e}")

        self.last_plugin_list = sorted(plugins_found)
        return self.last_plugin_list

    async def toggle_plugin(self, update: Update, context: ContextTypes.DEFAULT_TYPE, plugin_name):
        current_state = self.plugin_states.get(plugin_name, False)
        new_state = not current_state
        
        try:
            with open(CONFIG_FILE, "r") as f:
                config = toml.load(f)

            if "main" not in config:
                config["main"] = {}
            if "plugins" not in config["main"]:
                config["main"]["plugins"] = {}

            if plugin_name not in config["main"]["plugins"]:
                config["main"]["plugins"][plugin_name] = {}
            config["main"]["plugins"][plugin_name]["enabled"] = new_state

            with open(CONFIG_FILE, "w") as f:
                toml.dump(config, f)

            self.plugin_states[plugin_name] = new_state
            subprocess.run(["sudo", "killall", "-USR1", "pwnagotchi"], check=True)
            
            # Refresh the plugins menu to show updated state
            await self.plugins_menu(update, context)
        except Exception as e:
            keyboard = [[InlineKeyboardButton("📋 Back to Menu", callback_data="show_menu")]]
            await self.send_message(update, context, f"⛔ Failed: {e}", keyboard)

    async def system_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            cpu_usage = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            try:
                with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
                    temp = int(f.read().strip()) / 1000
            except:
                temp = "N/A"
            msg = f"📊 Stats:\nCPU: {cpu_usage}%\nMemory: {memory.percent}%\nTemp: {temp}°C"
            keyboard = [[InlineKeyboardButton("📋 Back to Menu", callback_data="show_menu")]]
            await self.send_message(update, context, msg, keyboard)
        except Exception as e:
            await self.send_message(update, context, f"⛔ Failed: {e}")

    async def handle_document_upload(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = update.effective_chat.id
        if chat_id not in self.user_states or self.user_states[chat_id] != "waiting_for_upload":
            return

        del self.user_states[chat_id]

        if not update.message.document:
            await update.message.reply_text("⛔ Please send a file")
            return

        document = update.message.document
        file_name = document.file_name

        if not (file_name.endswith('.pcap') or file_name.endswith('.pcapng')):
            await update.message.reply_text("⛔ Only .pcap or .pcapng files")
            return

        try:
            file = await context.bot.get_file(document.file_id)
            file_path = os.path.join(HANDSHAKE_DIR, file_name)

            if os.path.exists(file_path):
                await update.message.reply_text(f"⛔ {file_name} already exists")
                return

            await file.download_to_drive(file_path)
            os.chmod(file_path, 0o644)
            os.chown(file_path, 1000, 1000)

            await update.message.reply_text(f"✅ Uploaded {file_name}")
        except Exception as e:
            await update.message.reply_text(f"⛔ Failed: {e}")
