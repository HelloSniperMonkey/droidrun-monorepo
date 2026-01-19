"""
Telegram Bot module for Iron Claw.
Handles user interaction and HITL notifications.
"""
import asyncio
import base64
import io
import logging

from ..services.hitl_service import get_hitl_service
from ..utils.config import get_settings

logger = logging.getLogger("ironclaw.modules.telegram_bot")

# Store chat_id for notifications (in production, use a database)
_registered_chat_ids: set[int] = set()


class TelegramBotService:
    """
    Telegram bot for user interaction with Iron Claw.

    Commands:
    - /start - Introduction and register for notifications
    - /apply <query> - Start job search
    - /alarm <time> - Set an alarm
    - /wake - Trigger wake-up call
    - /status - Check task status
    - /screenshot - Get current device screen
    - /hitl - View pending HITL requests
    """

    def __init__(self):
        self.settings = get_settings()
        self._app = None
        self._bot = None

    async def start(self):
        """Start the Telegram bot."""
        if not self.settings.telegram_bot_token:
            logger.warning("TELEGRAM_BOT_TOKEN not configured - bot disabled")
            return

        try:
            from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
            from telegram.ext import (
                Application,
                CallbackQueryHandler,
                CommandHandler,
                MessageHandler,
                filters,
            )

            self._app = Application.builder().token(self.settings.telegram_bot_token).build()
            self._bot = self._app.bot

            # Register command handlers
            self._app.add_handler(CommandHandler("start", self._handle_start))
            self._app.add_handler(CommandHandler("apply", self._handle_apply))
            self._app.add_handler(CommandHandler("alarm", self._handle_alarm))
            self._app.add_handler(CommandHandler("wake", self._handle_wake))
            self._app.add_handler(CommandHandler("status", self._handle_status))
            self._app.add_handler(CommandHandler("screenshot", self._handle_screenshot))
            self._app.add_handler(CommandHandler("hitl", self._handle_hitl_list))
            self._app.add_handler(MessageHandler(filters.Document.PDF, self._handle_resume))

            # HITL callback handlers
            self._app.add_handler(CallbackQueryHandler(self._handle_hitl_callback, pattern="^hitl:"))

            # Register HITL notification callback
            hitl_service = get_hitl_service()
            hitl_service.register_callback(self._send_hitl_notification)

            logger.info("Telegram bot started")
            self._app.run_polling()

        except ImportError:
            logger.error("python-telegram-bot not installed")

    async def _send_hitl_notification(self, request: dict):
        """
        Send HITL notification to all registered chats.
        This is called by the HITL service when intervention is needed.
        """
        if not self._bot:
            logger.warning("Bot not initialized, cannot send HITL notification")
            return

        from telegram import InlineKeyboardButton, InlineKeyboardMarkup

        request_id = request["request_id"]
        message = (
            f"🚨 *Human Intervention Required*\n\n"
            f"*Type:* {request['hitl_type']}\n"
            f"*Task:* {request['task_id']}\n\n"
            f"*Message:* {request['message']}\n"
        )

        # Build inline keyboard with options
        buttons = []
        for option in request["options"]:
            callback_data = f"hitl:{request_id}:{option}"
            buttons.append([InlineKeyboardButton(option, callback_data=callback_data)])

        keyboard = InlineKeyboardMarkup(buttons)

        # Send to all registered chats
        for chat_id in _registered_chat_ids:
            try:
                # Send screenshot if available
                if request.get("screenshot_base64"):
                    screenshot_bytes = base64.b64decode(request["screenshot_base64"])
                    await self._bot.send_photo(
                        chat_id,
                        photo=io.BytesIO(screenshot_bytes),
                        caption=message,
                        parse_mode="Markdown",
                        reply_markup=keyboard,
                    )
                else:
                    await self._bot.send_message(
                        chat_id,
                        message,
                        parse_mode="Markdown",
                        reply_markup=keyboard,
                    )
            except Exception as e:
                logger.error(f"Failed to send HITL notification to {chat_id}: {e}")

    async def _handle_hitl_callback(self, update, context):
        """Handle HITL button presses."""
        query = update.callback_query
        await query.answer()

        # Parse callback data: hitl:<request_id>:<action>
        parts = query.data.split(":", 2)
        if len(parts) != 3:
            return

        _, request_id, action = parts

        # Respond to HITL
        hitl_service = get_hitl_service()
        success = await hitl_service.respond_hitl(request_id, action)

        if success:
            await query.edit_message_text(
                f"✅ Response recorded: *{action}*\n"
                f"Request: `{request_id}`",
                parse_mode="Markdown",
            )
        else:
            await query.edit_message_text(
                "❌ Failed to respond - request may have expired or already been handled."
            )

    async def _handle_start(self, update, context):
        """Handle /start command."""
        chat_id = update.effective_chat.id
        _registered_chat_ids.add(chat_id)

        await update.message.reply_text(
            "🦾 *Iron Claw* - Mobile-First Autonomous Agent\n\n"
            "You are now registered for notifications.\n\n"
            "*Commands:*\n"
            "• `/apply <query>` - Search and apply for jobs\n"
            "• `/alarm <HH:MM>` - Set an alarm\n"
            "• `/wake` - Trigger wake-up call now\n"
            "• `/screenshot` - See device screen\n"
            "• `/hitl` - View pending interventions\n"
            "• Send a PDF to upload your resume\n",
            parse_mode="Markdown",
        )

    async def _handle_apply(self, update, context):
        """Handle /apply command."""
        query = " ".join(context.args) if context.args else None
        if not query:
            await update.message.reply_text("Usage: /apply Senior Python Developer remote")
            return

        await update.message.reply_text(f"🔍 Starting job search: {query}")

        from .job_hunter import JobHunterService
        service = JobHunterService()

        import uuid
        task_id = str(uuid.uuid4())[:8]

        # Run in background
        asyncio.create_task(
            self._run_job_search(update.effective_chat.id, context.bot, service, query, task_id)
        )

    async def _run_job_search(self, chat_id, bot, service, query, task_id):
        """Run job search and report back."""
        result = await service.search_and_apply(query=query, task_id=task_id)
        await bot.send_message(
            chat_id,
            f"✅ Job search completed!\nSuccess: {result.get('success')}\n"
            f"Details: {result.get('reason', 'See logs')}",
        )

    async def _handle_alarm(self, update, context):
        """Handle /alarm command."""
        time_str = context.args[0] if context.args else None
        if not time_str or ":" not in time_str:
            await update.message.reply_text("Usage: /alarm 07:00")
            return

        try:
            hour, minute = map(int, time_str.split(":"))
        except ValueError:
            await update.message.reply_text("Invalid time format. Use HH:MM")
            return

        from .temporal_guardian import TemporalGuardianService
        service = TemporalGuardianService()
        result = await service.set_alarm(hour, minute)

        if result:
            await update.message.reply_text(f"⏰ Alarm set for {time_str}")
        else:
            await update.message.reply_text("❌ Failed to set alarm")

    async def _handle_wake(self, update, context):
        """Handle /wake command."""
        await update.message.reply_text("📞 Triggering wake-up call...")

        from .vapi_interrupter import VapiInterrupterService
        service = VapiInterrupterService()

        try:
            call_id = await service.trigger_wake_call(self.settings.user_phone_number)
            await update.message.reply_text(f"✅ Wake-up call initiated!\nCall ID: {call_id}")
        except Exception as e:
            await update.message.reply_text(f"❌ Failed: {e}")

    async def _handle_status(self, update, context):
        """Handle /status command."""
        # Get pending HITL requests
        hitl_service = get_hitl_service()
        pending = await hitl_service.get_pending_requests()

        status_text = "📊 *Status*\n\n"

        if pending:
            status_text += f"⚠️ *{len(pending)} pending HITL requests*\n"
            for req in pending[:3]:
                status_text += f"  • `{req['request_id']}`: {req['hitl_type']}\n"
        else:
            status_text += "✅ No pending interventions\n"

        await update.message.reply_text(status_text, parse_mode="Markdown")

    async def _handle_hitl_list(self, update, context):
        """Handle /hitl command - list pending HITL requests."""
        hitl_service = get_hitl_service()
        pending = await hitl_service.get_pending_requests()

        if not pending:
            await update.message.reply_text("✅ No pending HITL requests.")
            return

        for req in pending:
            await self._send_hitl_notification(req)

    async def _handle_screenshot(self, update, context):
        """Handle /screenshot command."""
        from ..agents.adb_connection import ADBConnection
        adb = ADBConnection()

        try:
            _, screenshot = await adb.take_screenshot()
            await update.message.reply_photo(screenshot, caption="📱 Current device screen")
        except Exception as e:
            await update.message.reply_text(f"❌ Screenshot failed: {e}")

    async def _handle_resume(self, update, context):
        """Handle PDF file upload (resume)."""
        document = update.message.document
        if not document.file_name.endswith(".pdf"):
            await update.message.reply_text("Please send a PDF file")
            return

        await update.message.reply_text("📄 Processing resume...")

        # Download file
        file = await context.bot.get_file(document.file_id)
        file_path = f"/tmp/{document.file_name}"
        await file.download_to_drive(file_path)

        await update.message.reply_text("✅ Resume received and saved!")


# Convenience function to start the bot
async def start_telegram_bot():
    """Start the Telegram bot service."""
    bot = TelegramBotService()
    await bot.start()
