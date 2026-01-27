#!/usr/bin/env python3
import os
import logging
import subprocess
import threading
from time import sleep, time
import telegram
import pwnagotchi
import pwnagotchi.fs as fs
import pwnagotchi.ui.view as view
import pwnagotchi.plugins as plugins
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import CommandHandler, CallbackQueryHandler, Updater, MessageHandler, Filters
import toml
import requests
import psutil  # For system stats
import schedule  # For scheduled tasks
from datetime import datetime
import re

# Constants
CONFIG_FILE = "/etc/pwnagotchi/config.toml"
HANDSHAKE_DIR = "/home/pi/handshakes/"
MAX_MESSAGE_LENGTH = 4096 // 2
LOG_PATH = "/etc/pwnagotchi/log/pwnagotchi.log"
COOLDOWN_SECONDS = 2
PLUGIN_DIRS = [
    "/home/pi/.pwn/lib/python3.11/site-packages/pwnagotchi/plugins/default/",
    "/usr/local/share/pwnagotchi/custom-plugins/"
]

# Change storage files to TOML for consistency
WEBHOOK_FILE = "/etc/pwnagotchi/telepwn_webhooks.toml"
SCHEDULE_FILE = "/etc/pwnagotchi/telepwn_schedules.toml"

# Initial menu with just a "Menu" button
INITIAL_MENU = [
    [InlineKeyboardButton("📋 Menu", callback_data="show_menu")]
]

# Main menu layout (compact grid style, with Back button)
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
    __version__ = "0.1.0_Beta"
    __license__ = "GPL3"
    __description__ = "A streamlined Telegram interface for Pwnagotchi"
    __dependencies__ = ("python-telegram-bot==13.15",
                        "requests>=2.28.0", "psutil>=5.9.0", "schedule>=1.2.0")

    _instance = None
    _lock = threading.Lock()

    def __init__(self):
        self.logger = logging.getLogger("TelePwn")
        self.options = {
            "bot_token": "",
            "chat_id": "",
            "auto_start": True,
            "send_message": True
        }
        self.screen_rotation = 0
        self.updater = None
        self.plugin_states = {}
        self.webhooks = self._load_webhooks()
        self.schedules = self._load_schedules()
        self.last_plugin_list = []
        self.schedule_thread = None
        self.running = False
        self.user_states = {}  # Track user states (e.g., waiting for upload)

    def _load_webhooks(self):
        try:
            if os.path.exists(WEBHOOK_FILE) and os.path.getsize(WEBHOOK_FILE) > 0:
                with open(WEBHOOK_FILE, "r", encoding="utf-8") as f:
                    loaded = toml.load(f)
                    self.logger.info(f"[TelePwn] Loaded webhooks: {loaded}")
                    return loaded
            self.logger.info("[TelePwn] Webhook file empty or missing, starting fresh")
            return {}
        except Exception as e:
            self.logger.error(f"[TelePwn] Failed to load webhooks: {e}")
            return {}

    def _save_webhooks(self):
        try:
            with open(WEBHOOK_FILE, "w", encoding="utf-8") as f:
                toml.dump(self.webhooks, f)
            self.logger.info(f"[TelePwn] Webhooks saved to {WEBHOOK_FILE}: {self.webhooks}")
        except Exception as e:
            self.logger.error(f"[TelePwn] Failed to save webhooks: {e}")
            raise

    def _load_schedules(self):
        try:
            if os.path.exists(SCHEDULE_FILE) and os.path.getsize(SCHEDULE_FILE) > 0:
                with open(SCHEDULE_FILE, "r", encoding="utf-8") as f:
                    loaded = toml.load(f)
                    self.logger.info(f"[TelePwn] Loaded schedules: {loaded}")
                    return loaded
            self.logger.info("[TelePwn] Schedule file empty or missing, starting fresh")
            return {}
        except Exception as e:
            self.logger.error(f"[TelePwn] Failed to load schedules: {e}")
            return {}

    def _save_schedules(self):
        try:
            with open(SCHEDULE_FILE, "w", encoding="utf-8") as f:
                toml.dump(self.schedules, f)
            self.logger.info(f"[TelePwn] Schedules saved to {SCHEDULE_FILE}: {self.schedules}")
        except Exception as e:
            self.logger.error(f"[TelePwn] Failed to save schedules: {e}")
            raise

    def on_loaded(self):
        self.logger.info("[TelePwn] Plugin loaded.")
        # Load options from config.toml
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                config = toml.load(f)
                plugins_config = config.get("main", {}).get("plugins", {}).get("telepwn", {})
                self.options["bot_token"] = plugins_config.get("bot_token", "")
                self.options["chat_id"] = plugins_config.get("chat_id", "")
                self.options["send_message"] = plugins_config.get("send_message", True)
                self.options["auto_start"] = plugins_config.get("auto_start", True)
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

    def on_unload(self, ui=None):
        self.logger.info("[TelePwn] Plugin unloading...")
        with TelePwn._lock:
            if TelePwn._instance is self:
                self.stop_bot()
                self.stop_scheduler()
                TelePwn._instance = None
        self.logger.info("[TelePwn] Plugin fully unloaded.")

    def load_config(self):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                config = toml.load(f)
                self.screen_rotation = int(config.get("ui", {}).get("display", {}).get("rotation", 0))
                plugins_config = config.get("main", {}).get("plugins", {})
                for plugin, settings in plugins_config.items():
                    self.plugin_states[plugin] = settings.get("enabled", False)
        except Exception as e:
            self.logger.warning(f"Failed to load config: {e}")

    def on_agent(self, agent):
        if self.options.get("auto_start", False):
            self.on_internet_available(agent)

    def on_handshake(self, agent, filename, access_point, client_station):
        display = agent.view()
        try:
            bot = telegram.Bot(self.options["bot_token"])
            message = f"\ud83e\udd1d New handshake: {access_point['hostname']} - {client_station['mac']}"
            if self.options.get("send_message", False):
                bot.send_message(
                    chat_id=int(self.options["chat_id"]),
                    text=message,
                    disable_web_page_preview=True,
                )
                self.logger.info(f"Sent handshake notification: {message}")
            display.set("status", "Handshake sent to Telegram!")
            display.update(force=True)
        except Exception as e:
            self.logger.error(f"Error sending handshake: {e}")

    def on_internet_available(self, agent):
        if self.updater and self.updater.running:
            self.logger.debug("[TelePwn] Already connected, skipping initialization.")
            return
        self.logger.info("[TelePwn] Starting Telegram bot...")
        try:
            self.start_bot(agent)
        except Exception as e:
            self.logger.error(f"[TelePwn] Error connecting to Telegram: {e}")
            if self.updater:
                self.updater.stop()
                self.updater = None

    def start_bot(self, agent):
        self.updater = Updater(self.options["bot_token"], use_context=True)
        self.register_handlers(agent, self.updater.dispatcher)
        self.updater.start_polling()
        self.logger.info("[TelePwn] Telegram polling started.")

        bot = telegram.Bot(self.options["bot_token"])
        bot.set_my_commands(
            commands=[
                BotCommand("start", "Open the main menu"),
                BotCommand("reboot", "Reboot the device"),
                BotCommand("shutdown", "Shutdown with clear"),
                BotCommand("uptime", "Check uptime"),
                BotCommand("handshakes", "Count captured handshakes"),
                BotCommand("screenshot", "Take a screenshot"),
                BotCommand("backup", "Create and send a backup"),
                BotCommand("restart_manual", "Restart daemon in manual mode"),
                BotCommand("restart_auto", "Restart daemon in auto mode"),
                BotCommand("kill", "Kill the daemon"),
                BotCommand("clear", "Clear the screen"),
                BotCommand("logs", "View recent logs"),
                BotCommand("inbox", "Check Pwngrid inbox"),
                BotCommand("plugins", "List plugins"),
                BotCommand("toggle", "Toggle a plugin"),
                BotCommand("setwebhook", "Set a webhook command"),
                BotCommand("webhook", "Trigger a custom webhook action"),
                BotCommand("config", "Edit config.toml (view/set/list)"),
                BotCommand("stats", "Show system stats"),
                BotCommand("pwngrid", "Pwngrid actions (send/clear)"),
                BotCommand("files", "Manage files (list/download/upload)"),
                BotCommand("schedule", "Manage scheduled tasks (add/remove/list)"),
                BotCommand("shell", "Run shell commands (with confirmation)"),
            ],
            scope=telegram.BotCommandScopeAllPrivateChats(),
        )

        bot.send_message(
            chat_id=int(self.options["chat_id"]),
            text="\ud83d\udd90 TelePwn 2025 Edition is online!",
            reply_markup=InlineKeyboardMarkup(INITIAL_MENU),
            parse_mode="HTML",
        )

    def stop_bot(self):
        if self.updater:
            if self.updater.running:
                self.updater.stop()
                self.logger.info("[TelePwn] Telegram polling stopped.")
            self.updater = None

    def start_scheduler(self):
        self.running = True
        self.schedule_thread = threading.Thread(target=self.run_scheduler)
        self.schedule_thread.daemon = True
        self.schedule_thread.start()
        self.logger.info("[TelePwn] Scheduler started.")

    def stop_scheduler(self):
        self.running = False
        if self.schedule_thread:
            self.schedule_thread.join()
        schedule.clear()
        self.logger.info("[TelePwn] Scheduler stopped.")

    def run_scheduler(self):
        for task_id, task in self.schedules.items():
            action = task["action"]
            interval = task["interval"]
            if action == "reboot":
                schedule.every(interval).hours.do(lambda: self._scheduled_reboot())
            elif action == "backup":
                schedule.every(interval).hours.do(lambda: self._scheduled_backup())
        while self.running:
            schedule.run_pending()
            sleep(60)

    def _scheduled_reboot(self):
        try:
            bot = telegram.Bot(self.options["bot_token"])
            bot.send_message(
                chat_id=int(self.options["chat_id"]),
                text="\ud83d\udd04 Scheduled reboot triggered...",
                parse_mode="HTML",
            )
            subprocess.run(["sudo", "reboot"], check=True)
        except Exception as e:
            self.logger.error(f"[TelePwn] Scheduled reboot failed: {e}")

    def _scheduled_backup(self):
        try:
            bot = telegram.Bot(self.options["bot_token"])
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = f"/home/pi/telepwn_scheduled_backup_{timestamp}.tar.gz"
            backup_files = [
                "/root/settings.yaml",
                "/root/client_secrets.json",
                "/home/pi/handshakes/",
                "/root/.api-report.json",
                "/root/.ssh",
                "/root/.bashrc",
                "/root/.profile",
                "/root/peers",
                "/etc/pwnagotchi/",
                "/usr/local/share/pwnagotchi/custom-plugins",
                "/etc/ssh/",
                "/home/pi/.bashrc",
                "/home/pi/.profile",
                "/root/.auto-update",
                "/home/pi/.wpa_sec_Uploads",
            ]
            existing_files = [f for f in backup_files if os.path.exists(f)]
            if not existing_files:
                bot.send_message(
                    chat_id=int(self.options["chat_id"]),
                    text="\u26a0 No files found for scheduled backup.",
                    parse_mode="HTML",
                )
                return
            subprocess.run(["sudo", "tar", "czf", backup_path] + existing_files, check=True)
            size_mb = round(os.path.getsize(backup_path) / (1024 * 1024), 2)
            with open(backup_path, "rb") as backup:
                bot.send_document(chat_id=int(self.options["chat_id"]), document=backup)
            bot.send_message(
                chat_id=int(self.options["chat_id"]),
                text=f"\u2705 Scheduled backup created and sent ({size_mb} MB)",
                parse_mode="HTML",
            )
        except Exception as e:
            self.logger.error(f"[TelePwn] Scheduled backup failed: {e}")
            bot = telegram.Bot(self.options["bot_token"])
            bot.send_message(
                chat_id=int(self.options["chat_id"]),
                text=f"\u26d4 Scheduled backup failed: {e}",
                parse_mode="HTML",
            )

    def register_handlers(self, agent, dispatcher):
        dispatcher.add_handler(CommandHandler("start", lambda update, context: self.start(agent, update, context)))
        dispatcher.add_handler(CommandHandler("reboot", lambda update, context: self.reboot(agent, update, context)))
        dispatcher.add_handler(CommandHandler("shutdown", lambda update, context: self.shutdown(agent, update, context)))
        dispatcher.add_handler(CommandHandler("uptime", lambda update, context: self.uptime(agent, update, context)))
        dispatcher.add_handler(CommandHandler("handshakes", lambda update, context: self.handshake_count(agent, update, context)))
        dispatcher.add_handler(CommandHandler("screenshot", lambda update, context: self.take_screenshot(agent, update, context)))
        dispatcher.add_handler(CommandHandler("backup", lambda update, context: self.create_backup(agent, update, context)))
        dispatcher.add_handler(CommandHandler("restart_manual", lambda update, context: self.restart_manual(agent, update, context)))
        dispatcher.add_handler(CommandHandler("restart_auto", lambda update, context: self.restart_auto(agent, update, context)))
        dispatcher.add_handler(CommandHandler("kill", lambda update, context: self.pwnkill(agent, update, context)))
        dispatcher.add_handler(CommandHandler("clear", lambda update, context: self.clear(agent, update, context)))
        dispatcher.add_handler(CommandHandler("logs", lambda update, context: self.logs(agent, update, context)))
        dispatcher.add_handler(CommandHandler("inbox", lambda update, context: self.inbox(agent, update, context)))
        dispatcher.add_handler(CommandHandler("plugins", lambda update, context: self.plugins_menu(agent, update, context)))
        dispatcher.add_handler(CommandHandler("toggle", lambda update, context: self.toggle_plugin_command(agent, update, context)))
        dispatcher.add_handler(CommandHandler("setwebhook", lambda update, context: self.set_webhook(agent, update, context)))
        dispatcher.add_handler(CommandHandler("webhook", lambda update, context: self.webhook(agent, update, context)))
        dispatcher.add_handler(CommandHandler("config", lambda update, context: self.config_editor(agent, update, context)))
        dispatcher.add_handler(CommandHandler("stats", lambda update, context: self.system_stats(agent, update, context)))
        dispatcher.add_handler(CommandHandler("pwngrid", lambda update, context: self.pwngrid_actions(agent, update, context)))
        dispatcher.add_handler(CommandHandler("files", lambda update, context: self.file_manager(agent, update, context)))
        dispatcher.add_handler(CommandHandler("schedule", lambda update, context: self.schedule_manager(agent, update, context)))
        dispatcher.add_handler(CommandHandler("shell", lambda update, context: self.shell_command(agent, update, context)))
        dispatcher.add_handler(CallbackQueryHandler(lambda update, context: self.button_handler(agent, update, context)))
        # Add handler for document uploads
        dispatcher.add_handler(MessageHandler(Filters.document, lambda update, context: self.handle_document_upload(agent, update, context)))

    def start(self, agent, update, context):
        if update.callback_query and update.callback_query.data == "cancel":
            self.send_message(update, context, "\u2705 Action cancelled.")
        self.send_message(update, context, "\ud83d\udd90 TelePwn 2025 Edition\nSelect an option:", MAIN_MENU)

    def button_handler(self, agent, update, context):
        if update.effective_chat.id != int(self.options.get("chat_id")):
            return
        query = update.callback_query
        query.answer()

        current_time = time()
        last_action = context.user_data.get("last_action", 0)
        if current_time - last_action < COOLDOWN_SECONDS:
            self.send_message(update, context, "\u26a0 Slow down! Wait a moment.")
            return
        context.user_data["last_action"] = current_time

        actions = {
            "reboot": self.reboot,
            "reboot_manual": lambda a, u, c: self.reboot_mode("manual", u, c),
            "reboot_auto": lambda a, u, c: self.reboot_mode("auto", u, c),
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
            "back_to_initial": lambda a, u, c: self.send_message(u, c, "\ud83d\udd90 TelePwn 2025 Edition", INITIAL_MENU),
        }

        if query.data.startswith("toggle_plugin_"):
            plugin_name = query.data[len("toggle_plugin_"):]
            self.toggle_plugin(agent, update, context, plugin_name)
        elif query.data.startswith("confirm_shell_"):
            command = query.data[len("confirm_shell_"):]
            self.execute_shell_command(agent, update, context, command)
        elif query.data in actions:
            actions[query.data](agent, update, context)

    def send_message(self, update, context, text, keyboard=None):
        if update.effective_chat.id != int(self.options.get("chat_id")):
            return
        try:
            if len(text) > MAX_MESSAGE_LENGTH:
                for chunk in [text[i:i + MAX_MESSAGE_LENGTH] for i in range(0, len(text), MAX_MESSAGE_LENGTH)]:
                    context.bot.send_message(chat_id=update.effective_chat.id, text=chunk, parse_mode="HTML")
            else:
                if update.callback_query:
                    update.callback_query.edit_message_text(
                        text=text,
                        reply_markup=InlineKeyboardMarkup(keyboard) if keyboard else None,
                        parse_mode="HTML",
                    )
                else:
                    update.effective_message.reply_text(
                        text=text,
                        reply_markup=InlineKeyboardMarkup(keyboard) if keyboard else None,
                        parse_mode="HTML",
                    )
        except Exception as e:
            self.logger.error(f"Error sending message: {e}")
            context.bot.send_message(chat_id=update.effective_chat.id, text=str(e))

    def reboot(self, agent, update, context):
        keyboard = [
            [InlineKeyboardButton("✅ Confirm Manual", callback_data="reboot_manual")],
            [InlineKeyboardButton("✅ Confirm Auto", callback_data="reboot_auto")],
            [InlineKeyboardButton("❌ Cancel", callback_data="cancel")],
        ]
        self.send_message(update, context, "\u26a0\ufe0f Confirm reboot? SSH/Bluetooth will disconnect.", keyboard)

    def reboot_mode(self, mode, update, context):
        self.send_message(update, context, f"\ud83d\udd04 Rebooting in {mode} mode...")
        try:
            if view.ROOT:
                view.ROOT.on_custom(f"Rebooting to {mode}")
                sleep(5)
            subprocess.run(["sudo", "touch", f"/root/.pwnagotchi-{mode}"], check=True)
            if mode == "manual":
                subprocess.run(["sudo", "rm", "-f", "/root/.pwnagotchi-auto"], check=True)
            else:
                subprocess.run(["sudo", "rm", "-f", "/root/.pwnagotchi-manual"], check=True)
            subprocess.run(["sudo", "sync"], check=True)
            subprocess.run(["sudo", "reboot"], check=True)
        except subprocess.CalledProcessError as e:
            self.send_message(update, context, f"\u26d4 Reboot failed: {e}")

    def shutdown(self, agent, update, context):
        keyboard = [
            [InlineKeyboardButton("✅ Confirm", callback_data="confirm_shutdown")],
            [InlineKeyboardButton("❌ Cancel", callback_data="cancel")],
        ]
        self.send_message(update, context, "\u26a0\ufe0f Confirm shutdown? Device will power off.", keyboard)

    def confirm_shutdown(self, agent, update, context):
        self.send_message(update, context, "\ud83d\udce4 Stopping daemon, clearing screen, and shutting down...")
        try:
            subprocess.run(["sudo", "systemctl", "stop", "pwnagotchi"], check=True)
            subprocess.run(["sudo", "pwnagotchi", "--clear"], check=True)
            if view.ROOT:
                view.ROOT.on_shutdown()
                sleep(5)
            subprocess.run(["sudo", "sync"], check=True)
            subprocess.run(["sudo", "shutdown", "-h", "now"], check=True)
        except subprocess.CalledProcessError as e:
            self.send_message(update, context, f"\u26d4 Shutdown failed: {e}")

    def uptime(self, agent, update, context):
        try:
            with open("/proc/uptime", "r", encoding="utf-8") as f:
                uptime_seconds = float(f.readline().split()[0])
            hours = int(uptime_seconds // 3600)
            minutes = int((uptime_seconds % 3600) // 60)
            self.send_message(update, context, f"\u23f0 Uptime: {hours}h {minutes}m")
        except Exception as e:
            self.send_message(update, context, f"\u26d4 Error: {e}")

    def handshake_count(self, agent, update, context):
        try:
            count = len([f for f in os.listdir(HANDSHAKE_DIR) if os.path.isfile(os.path.join(HANDSHAKE_DIR, f))])
            self.send_message(update, context, f"\ud83e\udd1d Handshakes captured: {count}")
        except Exception as e:
            self.send_message(update, context, f"\u26d4 Error: {e}")

    def take_screenshot(self, agent, update, context):
        try:
            context.bot.send_chat_action(chat_id=update.effective_chat.id, action="upload_photo")
            display = agent.view()
            screenshot_path = "/root/telepwn_screenshot.png"
            display.image().rotate(self.screen_rotation).save(screenshot_path, "png")
            with open(screenshot_path, "rb") as photo:
                context.bot.send_photo(chat_id=update.effective_chat.id, photo=photo)
            self.send_message(update, context, "\u2705 Screenshot sent!")
        except Exception as e:
            self.send_message(update, context, f"\u26d4 Error: {e}")

    def create_backup(self, agent, update, context):
        self.send_message(update, context, "\ud83d\udcbe Creating backup...")
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = f"/home/pi/telepwn_backup_{timestamp}.tar.gz"
            backup_files = [
                "/root/settings.yaml",
                "/root/client_secrets.json",
                "/home/pi/handshakes/",
                "/root/.api-report.json",
                "/root/.ssh",
                "/root/.bashrc",
                "/root/.profile",
                "/root/peers",
                "/etc/pwnagotchi/",
                "/usr/local/share/pwnagotchi/custom-plugins",
                "/etc/ssh/",
                "/home/pi/.bashrc",
                "/home/pi/.profile",
                "/root/.auto-update",
                "/home/pi/.wpa_sec_Uploads",
            ]
            existing_files = [f for f in backup_files if os.path.exists(f)]
            if not existing_files:
                self.send_message(update, context, "\u26a0 No files found to back up.")
                return
            subprocess.run(["sudo", "tar", "czf", backup_path] + existing_files, check=True)
            size_mb = round(os.path.getsize(backup_path) / (1024 * 1024), 2)
            with open(backup_path, "rb") as backup:
                context.bot.send_document(chat_id=update.effective_chat.id, document=backup)
            self.send_message(update, context, f"\u2705 Backup created and sent ({size_mb} MB)")
        except subprocess.CalledProcessError as e:
            self.send_message(update, context, f"\u26d4 Backup failed: {e}")
        except Exception as e:
            self.send_message(update, context, f"\u26d4 Error: {e}")

    def restart_manual(self, agent, update, context):
        self.send_message(update, context, "\ud83d\udd01 Restarting daemon in manual mode...")
        try:
            if view.ROOT:
                view.ROOT.on_custom("Restarting to manual")
                sleep(5)
            subprocess.run(["sudo", "touch", "/root/.pwnagotchi-manual"], check=True)
            subprocess.run(["sudo", "rm", "-f", "/root/.pwnagotchi-auto"], check=True)
            subprocess.run(["sudo", "systemctl", "restart", "pwnagotchi"], check=True)
        except subprocess.CalledProcessError as e:
            self.send_message(update, context, f"\u26d4 Restart failed: {e}")

    def restart_auto(self, agent, update, context):
        self.send_message(update, context, "\ud83d\udd01 Restarting daemon in auto mode...")
        try:
            if view.ROOT:
                view.ROOT.on_custom("Restarting to auto")
                sleep(5)
            subprocess.run(["sudo", "touch", "/root/.pwnagotchi-auto"], check=True)
            subprocess.run(["sudo", "rm", "-f", "/root/.pwnagotchi-manual"], check=True)
            subprocess.run(["sudo", "systemctl", "restart", "pwnagotchi"], check=True)
        except subprocess.CalledProcessError as e:
            self.send_message(update, context, f"\u26d4 Restart failed: {e}")

    def pwnkill(self, agent, update, context):
        self.send_message(update, context, "\ud83d\udde1\ufe0f Killing daemon...")
        try:
            subprocess.run(["sudo", "killall", "-USR1", "pwnagotchi"], check=True)
            self.send_message(update, context, "\u2705 Daemon killed and plugins reloaded.", INITIAL_MENU)
        except subprocess.CalledProcessError as e:
            self.send_message(update, context, f"\u26d4 Kill failed: {e}")

    def clear(self, agent, update, context):
        self.send_message(update, context, "\ud83d\udda5\ufe0f Clearing screen...")
        try:
            subprocess.run(["sudo", "pwnagotchi", "--clear"], check=True)
            if view.ROOT:
                view.ROOT.on_custom("Screen cleared")
                sleep(2)
            self.send_message(update, context, "\u2705 Screen cleared!")
        except subprocess.CalledProcessError as e:
            self.send_message(update, context, f"\u26d4 Clear failed: {e}")

    def logs(self, agent, update, context):
        try:
            log_output = subprocess.check_output(["tail", "-n", "50", LOG_PATH], text=True)
            msg = f"\ud83d\udcdc Last 50 log lines:\n```\n{log_output}\n```"
            self.send_message(update, context, msg)
        except subprocess.CalledProcessError as e:
            self.send_message(update, context, f"\u26d4 Log fetch failed: {e}")

    def inbox(self, agent, update, context):
        self.send_message(update, context, "\ud83d\udce5 Checking Pwngrid inbox...")
        try:
            inbox_output = subprocess.check_output(["pwngrid", "--inbox"], text=True)
            msg = f"\ud83d\udce5 Pwngrid Inbox:\n```\n{inbox_output}\n```"
            self.send_message(update, context, msg)
        except subprocess.CalledProcessError as e:
            self.send_message(update, context, f"\u26d4 Inbox fetch failed: {e}")

    def plugins_menu(self, agent, update, context):
        plugins_found = self.get_plugins()
        if not plugins_found:
            self.send_message(update, context, "\u26a0 No plugins found.")
            return

        keyboard = []
        for plugin in plugins_found:
            state = self.plugin_states.get(plugin, False)
            emoji = "✅" if state else "❌"
            keyboard.append([InlineKeyboardButton(f"{emoji} {plugin}", callback_data=f"toggle_plugin_{plugin}")])
        keyboard.append([InlineKeyboardButton("Back", callback_data="start")])
        self.send_message(update, context, "\ud83d\udd27 Toggle Plugins:", keyboard)

    def get_plugins(self):
        plugins_found = set()
        for directory in PLUGIN_DIRS:
            try:
                if os.path.exists(directory):
                    for filename in os.listdir(directory):
                        if filename.endswith(".py") and filename != "__init__.py":
                            plugin_name = filename[:-3]
                            plugins_found.add(plugin_name)
            except Exception as e:
                self.logger.error(f"Failed to scan {directory}: {e}")

        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                config = toml.load(f)
                plugins_config = config.get("main", {}).get("plugins", {})
                for plugin in plugins_found:
                    self.plugin_states[plugin] = plugins_config.get(plugin, {}).get("enabled", False)
        except Exception as e:
            self.logger.error(f"Failed to load plugin states: {e}")

        self.last_plugin_list = sorted(plugins_found)
        return self.last_plugin_list

    def toggle_plugin_command(self, agent, update, context):
        if not context.args:
            plugins_list = self.last_plugin_list or self.get_plugins()
            if plugins_list:
                msg = "Available plugins:\n" + "\n".join([f"- {p} ({'enabled' if self.plugin_states.get(p, False) else 'disabled'})" for p in plugins_list])
            else:
                msg = "\u26a0 No plugins found."
            self.send_message(update, context, f"Usage: /toggle <plugin_name>\n{msg}")
            return

        plugin_name = context.args[0].strip()
        if plugin_name not in (self.last_plugin_list or self.get_plugins()):
            self.send_message(update, context, f"\u26d4 Plugin {plugin_name} not found.")
            return

        self.toggle_plugin(agent, update, context, plugin_name)

    def toggle_plugin(self, agent, update, context, plugin_name):
        current_state = self.plugin_states.get(plugin_name, False)
        new_state = not current_state
        self.send_message(update, context, f"\ud83d\udd27 Toggling {plugin_name} to {'enabled' if new_state else 'disabled'}...")
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                config = toml.load(f)

            if "main" not in config:
                config["main"] = {}
            if "plugins" not in config["main"]:
                config["main"]["plugins"] = {}

            if plugin_name not in config["main"]["plugins"]:
                config["main"]["plugins"][plugin_name] = {}
            config["main"]["plugins"][plugin_name]["enabled"] = new_state

            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                toml.dump(config, f)

            self.plugin_states[plugin_name] = new_state
            subprocess.run(["sudo", "killall", "-USR1", "pwnagotchi"], check=True)
            self.send_message(update, context, f"\u2705 {plugin_name} {'enabled' if new_state else 'disabled'}. Plugins reloaded.")
        except Exception as e:
            self.send_message(update, context, f"\u26d4 Failed to toggle {plugin_name}: {e}")

    def set_webhook(self, agent, update, context):
        if len(context.args) < 2:
            self.send_message(update, context, "Usage: /setwebhook <action> <url> [type] [request/command]\nExample: /setwebhook ping https://discord.com/api/webhooks/12345/abcde notify\nFor plugin_toggle: /setwebhook toggle_memtemp none plugin_toggle")
            return

        action = context.args[0].strip()
        url = context.args[1].strip() if context.args[1].strip() != "none" else ""
        action_type = context.args[2].strip() if len(context.args) > 2 else "notify"
        extra = " ".join(context.args[3:]).strip() if len(context.args) > 3 else ""

        self.logger.info(f"[TelePwn] Setting webhook: action={action}, url={url}, type={action_type}, extra={extra}")
        try:
            # For HTTP webhooks, validate the request format if extra is provided
            if action_type == "http" and extra:
                parts = extra.format(degrees="{degrees}").split(" ", 1)
                if len(parts) != 2:
                    self.send_message(update, context, "\u26d4 Invalid HTTP request format. Expected format: METHOD <URL>")
                    return

            self.webhooks[action] = {"url": url, "type": action_type}
            if action_type == "http" and extra:
                self.webhooks[action]["request"] = extra
            elif action_type == "shell" and extra:
                self.webhooks[action]["command"] = extra
            elif action_type in ("plugin_toggle", "notify"):
                pass
            else:
                self.send_message(update, context, "\u26d4 Invalid type or missing request/command")
                return

            self._save_webhooks()
            self.send_message(update, context, f"\u2705 Webhook set for {action}: {url if url else 'none'}")
            self.logger.info(f"[TelePwn] Webhook set in memory: {self.webhooks}")
        except Exception as e:
            self.send_message(update, context, f"\u26d4 Failed to set webhook: {str(e)}")
            self.logger.error(f"[TelePwn] Set webhook failed: {e}")

    def webhook(self, agent, update, context):
        if not context.args:
            self.send_message(update, context, "Usage: /webhook <action> [extra]\nExample: /webhook ping\nFor plugin_toggle: /webhook toggle_memtemp memtemp")
            return

        action = context.args[0].strip()
        extra = " ".join(context.args[1:]).strip() if len(context.args) > 1 else ""

        if action not in self.webhooks:
            self.send_message(update, context, f"\u26d4 No webhook set for {action}")
            return

        webhook_config = self.webhooks[action]
        action_type = webhook_config.get("type", "notify")
        self.send_message(update, context, f"\ud83d\udd27 Executing {action}...")

        try:
            if action_type == "plugin_toggle":
                plugin_name = extra if extra else action.replace("toggle_", "")
                self.toggle_plugin(agent, update, context, plugin_name)
            elif action_type == "http" and "request" in webhook_config:
                request_template = webhook_config["request"]
                request_str = request_template.format(degrees=extra or "0")
                parts = request_str.split(" ", 1)
                if len(parts) != 2:
                    self.send_message(update, context, "\u26d4 Invalid HTTP request format in webhook configuration.")
                    return
                method, url = parts
                response = requests.request(method, url, timeout=5)
                response.raise_for_status()
                self.send_message(update, context, f"\u2705 {action} executed!")
            elif action_type == "shell" and "command" in webhook_config:
                command = webhook_config["command"]
                # Log the raw command for debugging.
                self.logger.info(f"[TelePwn] Raw command from config: {repr(command)}")
                command = command.strip()
                # Explicitly remove the first and last character if they are quotes.
                if command and (command[0] == '"' or command[0] == "'"):
                    command = command[1:]
                if command and (command[-1] == '"' or command[-1] == "'"):
                    command = command[:-1]
                self.logger.info(f"[TelePwn] Command after quote removal: {repr(command)}")
                
                # Parse extra parameters into a dictionary.
                params = {}
                if extra:
                    for part in extra.split():
                        if '=' in part:
                            key, value = part.split('=', 1)
                            params[key] = value
                    if not params:
                        params = {'value': extra}
                try:
                    command = command.format(**params)
                except KeyError as ke:
                    self.send_message(update, context, f"Missing placeholder for {ke}")
                    return
                self.logger.info(f"[TelePwn] Final command to execute: {repr(command)}")
                result = subprocess.run(
                    command,
                    shell=True,
                    executable="/bin/bash",
                    check=True,
                    capture_output=True,
                    text=True
                )
                self.send_message(update, context, f"\u2705 {action} executed!\nOutput:\n```\n{result.stdout}\n```")
            elif action_type == "notify":
                self.send_message(update, context, f"\u2705 {action} triggered!")
            else:
                self.send_message(update, context, "\u26d4 Invalid webhook config")
                return

            if action_type != "plugin_toggle" and webhook_config.get("url"):
                self.trigger_webhook(action, {
                    "action": action,
                    "extra": extra,
                    "chat_id": update.effective_chat.id
                })
        except subprocess.CalledProcessError as e:
            error_msg = f"\u26d4 {action} failed:\nError:\n```\n{e.stderr}\n```"
            self.send_message(update, context, error_msg)
            self.logger.error(f"[TelePwn] Webhook {action} failed: {error_msg}")
        except Exception as e:
            self.send_message(update, context, f"\u26d4 {action} failed: {str(e)}")
            self.logger.error(f"[TelePwn] Webhook {action} failed: {e}")

    def config_editor(self, agent, update, context):
        if not context.args:
            self.send_message(update, context, "Usage:\n/config view <section> <key>\n/config set <section> <key> <value>\n/config list\nExample: /config set main.plugins.memtemp enabled true")
            return

        action = context.args[0].lower()
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                config = toml.load(f)

            if action == "list":
                msg = "Config sections and keys:\n"
                for section, values in config.items():
                    msg += f"\n[{section}]\n"
                    if isinstance(values, dict):
                        for key, val in values.items():
                            if isinstance(val, dict):
                                for subkey, subval in val.items():
                                    msg += f"  {key}.{subkey} = {subval}\n"
                            else:
                                msg += f"  {key} = {val}\n"
                self.send_message(update, context, msg)
                return

            if len(context.args) < 3:
                self.send_message(update, context, "Please provide section and key.")
                return

            section = context.args[1]
            key_path = context.args[2].split(".")
            if action == "view":
                current = config
                for key in section.split("."):
                    current = current.get(key, {})
                for key in key_path:
                    current = current.get(key, None)
                    if current is None:
                        self.send_message(update, context, f"\u26d4 Key {section}.{context.args[2]} not found.")
                        return
                self.send_message(update, context, f"\ud83d\udd0d {section}.{context.args[2]} = {current}")
            elif action == "set":
                if len(context.args) < 4:
                    self.send_message(update, context, "Please provide a value to set.")
                    return
                value = context.args[3].lower()
                if value in ("true", "false"):
                    value = value == "true"
                elif value.isdigit():
                    value = int(value)
                elif value.replace(".", "").isdigit():
                    value = float(value)

                current = config
                sections = section.split(".")
                for i, key in enumerate(sections[:-1]):
                    if key not in current:
                        current[key] = {}
                    current = current[key]
                last_section = sections[-1]
                if last_section not in current:
                    current[last_section] = {}

                target = current[last_section]
                for key in key_path[:-1]:
                    if key not in target:
                        target[key] = {}
                    target = target[key]
                target[key_path[-1]] = value

                with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                    toml.dump(config, f)
                self.send_message(update, context, f"\u2705 Set {section}.{context.args[2]} = {value}")
                subprocess.run(["sudo", "systemctl", "restart", "pwnagotchi"], check=True)
                self.send_message(update, context, "\u2705 Pwnagotchi restarted to apply changes.")
        except Exception as e:
            self.send_message(update, context, f"\u26d4 Failed to edit config: {e}")

    def system_stats(self, agent, update, context):
        try:
            cpu_usage = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            memory_usage = memory.percent
            try:
                with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
                    temp = int(f.read().strip()) / 1000
            except:
                temp = "N/A"
            msg = f"\ud83d\udcca System Stats:\nCPU Usage: {cpu_usage}%\nMemory Usage: {memory_usage}%\nTemperature: {temp}°C"
            self.send_message(update, context, msg)
        except Exception as e:
            self.send_message(update, context, f"\u26d4 Failed to fetch stats: {e}")

    def pwngrid_actions(self, agent, update, context):
        if not context.args:
            self.send_message(update, context, "Usage:\n/pwngrid send <message>\n/pwngrid clear\nExample: /pwngrid send Hello from TelePwn")
            return

        action = context.args[0].lower()
        try:
            if action == "send":
                if len(context.args) < 2:
                    self.send_message(update, context, "Please provide a message to send.")
                    return
                message = " ".join(context.args[1:])
                subprocess.run(["pwngrid", "--send", message], check=True)
                self.send_message(update, context, f"\u2705 Sent to Pwngrid: {message}")
            elif action == "clear":
                subprocess.run(["pwngrid", "--clear"], check=True)
                self.send_message(update, context, "\u2705 Pwngrid inbox cleared.")
            else:
                self.send_message(update, context, "Invalid action. Use 'send' or 'clear'.")
        except subprocess.CalledProcessError as e:
            self.send_message(update, context, f"\u26d4 Pwngrid action failed: {e}")

    def file_manager(self, agent, update, context):
        if not context.args:
            self.send_message(update, context, "Usage:\n/files list\n/files download <filename>\n/files upload\nExample: /files download handshake.pcap")
            return

        action = context.args[0].lower()
        try:
            if action == "list":
                files = [f for f in os.listdir(HANDSHAKE_DIR) if os.path.isfile(os.path.join(HANDSHAKE_DIR, f))]
                if not files:
                    self.send_message(update, context, "\u26a0 No files found in handshake directory.")
                    return
                msg = "Files in handshake directory:\n" + "\n".join([f"- {f}" for f in files])
                self.send_message(update, context, msg)
            elif action == "download":
                if len(context.args) < 2:
                    self.send_message(update, context, "Please provide a filename to download.")
                    return
                filename = context.args[1]
                file_path = os.path.join(HANDSHAKE_DIR, filename)
                if not os.path.exists(file_path):
                    self.send_message(update, context, f"\u26d4 File {filename} not found.")
                    return
                with open(file_path, "rb") as f:
                    context.bot.send_document(chat_id=update.effective_chat.id, document=f)
                self.send_message(update, context, f"\u2705 Sent file: {filename}")
            elif action == "upload":
                # Set the user's state to "waiting for upload"
                chat_id = update.effective_chat.id
                self.user_states[chat_id] = "waiting_for_upload"
                self.send_message(update, context, "Please send the handshake file to upload to /home/pi/handshakes/.\nOnly .pcap or .pcapng files are allowed.")
            else:
                self.send_message(update, context, "Invalid action. Use 'list', 'download', or 'upload'.")
        except Exception as e:
            self.send_message(update, context, f"\u26d4 File action failed: {e}")

    def handle_document_upload(self, agent, update, context):
        chat_id = update.effective_chat.id
        # Check if the user is in "upload mode"
        if chat_id not in self.user_states or self.user_states[chat_id] != "waiting_for_upload":
            self.send_message(update, context, "Please use /files upload to start the upload process.")
            return

        # Clear the user's state
        del self.user_states[chat_id]

        # Check if the message contains a document
        if not update.message.document:
            self.send_message(update, context, "\u26d4 Please send a file (document).")
            return

        document = update.message.document
        file_name = document.file_name

        # Validate file type (only allow .pcap or .pcapng for handshakes)
        if not (file_name.endswith('.pcap') or file_name.endswith('.pcapng')):
            self.send_message(update, context, "\u26d4 Only .pcap or .pcapng files are allowed for handshakes.")
            return

        try:
            # Download the file
            file = context.bot.get_file(document.file_id)
            file_path = os.path.join(HANDSHAKE_DIR, file_name)

            # Check if file already exists
            if os.path.exists(file_path):
                self.send_message(update, context, f"\u26d4 File {file_name} already exists in {HANDSHAKE_DIR}.")
                return

            # Download and save the file
            file.download(file_path)

            # Set appropriate permissions (readable/writable by pi user)
            os.chmod(file_path, 0o644)
            os.chown(file_path, 1000, 1000)  # pi user and group (uid 1000, gid 1000)

            # Confirm success
            self.send_message(update, context, f"\u2705 File {file_name} uploaded to {HANDSHAKE_DIR}.")
            self.logger.info(f"[TelePwn] Uploaded file {file_name} to {HANDSHAKE_DIR}")
        except Exception as e:
            self.send_message(update, context, f"\u26d4 Failed to upload file: {str(e)}")
            self.logger.error(f"[TelePwn] Failed to upload file {file_name}: {e}")

    def schedule_manager(self, agent, update, context):
        if not context.args:
            self.send_message(update, context, "Usage:\n/schedule add <action> <interval_hours>\n/schedule remove <task_id>\n/schedule list\nExample: /schedule add reboot 24")
            return

        action = context.args[0].lower()
        try:
            if action == "list":
                if not self.schedules:
                    self.send_message(update, context, "\u26a0 No scheduled tasks.")
                    return
                msg = "Scheduled tasks:\n"
                for task_id, task in self.schedules.items():
                    msg += f"ID: {task_id} - {task['action']} every {task['interval']} hours\n"
                self.send_message(update, context, msg)
            elif action == "add":
                if len(context.args) < 3:
                    self.send_message(update, context, "Please provide action and interval (in hours).")
                    return
                task_action = context.args[1].lower()
                if task_action not in ("reboot", "backup"):
                    self.send_message(update, context, "Invalid action. Use 'reboot' or 'backup'.")
                    return
                interval = int(context.args[2])
                if interval <= 0:
                    self.send_message(update, context, "Interval must be a positive number.")
                    return
                task_id = str(len(self.schedules) + 1)
                self.schedules[task_id] = {"action": task_action, "interval": interval}
                self._save_schedules()
                self.stop_scheduler()
                self.start_scheduler()
                self.send_message(update, context, f"\u2705 Scheduled {task_action} every {interval} hours (ID: {task_id})")
            elif action == "remove":
                if len(context.args) < 2:
                    self.send_message(update, context, "Please provide the task ID to remove.")
                    return
                task_id = context.args[1]
                if task_id not in self.schedules:
                    self.send_message(update, context, f"\u26d4 Task ID {task_id} not found.")
                    return
                del self.schedules[task_id]
                self._save_schedules()
                self.stop_scheduler()
                self.start_scheduler()
                self.send_message(update, context, f"\u2705 Removed scheduled task (ID: {task_id})")
            else:
                self.send_message(update, context, "Invalid action. Use 'add', 'remove', or 'list'.")
        except Exception as e:
            self.send_message(update, context, f"\u26d4 Schedule action failed: {e}")

    def shell_command(self, agent, update, context):
        if not context.args:
            self.send_message(update, context, "Usage: /shell <command>\nExample: /shell ls -la")
            return

        command = " ".join(context.args)
        keyboard = [
            [InlineKeyboardButton("✅ Confirm", callback_data=f"confirm_shell_{command}")],
            [InlineKeyboardButton("❌ Cancel", callback_data="cancel")],
        ]
        self.send_message(update, context, f"\u26a0\ufe0f Confirm running shell command?\nCommand: {command}", keyboard)

    def execute_shell_command(self, agent, update, context, command):
        try:
            output = subprocess.check_output(command, shell=True, text=True, stderr=subprocess.STDOUT)
            msg = f"\ud83d\udcbb Shell command executed:\nCommand: {command}\nOutput:\n```\n{output}\n```"
            self.send_message(update, context, msg)
        except subprocess.CalledProcessError as e:
            self.send_message(update, context, f"\u26d4 Shell command failed:\nCommand: {command}\nError:\n```\n{e.output}\n```")

if __name__ == "__main__":
    plugin = TelePwn()
    plugin.on_loaded()
