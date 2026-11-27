from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage
import logging

logger = logging.getLogger(__name__)

bot_instance: Bot = None
dp_instance: Dispatcher = None

def get_bot() -> Bot:
    return bot_instance

def get_dp() -> Dispatcher:
    return dp_instance

def init_bot(token: str):
    global bot_instance, dp_instance
    if not token:
        logger.warning("No BOT_TOKEN provided. Bot is disabled until configured in settings.")
        bot_instance = None
        dp_instance = None
        return None, None
        
    bot_instance = Bot(
        token=token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp_instance = Dispatcher(storage=MemoryStorage())
    return bot_instance, dp_instance

async def send_user_notification(telegram_id: int, message: str, reply_markup=None):
    """Safely sends a message to a Telegram user"""
    if not bot_instance:
        return False
    try:
        await bot_instance.send_message(
            chat_id=telegram_id,
            text=message,
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML
        )
        return True
    except Exception as e:
        logger.error(f"Failed to send message to {telegram_id}: {e}")
        return False

async def notify_admin(message: str, reply_markup=None):
    """Sends notification to Admin via @foxzenadmin_bot and store bot"""
    try:
        from bot.admin_bot import send_admin_alert
        await send_admin_alert(message, reply_markup)
    except Exception as e:
        logger.debug(f"Admin push alert via admin bot: {e}")

    from database import get_setting
    admin_id = await get_setting("admin_telegram_id")
    if admin_id and admin_id.strip():
        try:
            await send_user_notification(int(admin_id.strip()), message, reply_markup)
        except Exception as e:
            logger.error(f"Failed to notify admin on store bot: {e}")
