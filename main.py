import asyncio
import logging
from contextlib import asynccontextmanager
import uvicorn
from fastapi import FastAPI

from config import WEB_HOST, WEB_PORT, BOT_TOKEN, ADMIN_BOT_TOKEN
from database import init_db, get_setting
from bot.bot_instance import init_bot, get_bot, get_dp
from bot.handlers import router as bot_router
from bot.admin_bot import init_admin_bot, get_admin_bot
from web.app import web_app

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("FoxzenBot")

bot_task: asyncio.Task = None
admin_bot_task: asyncio.Task = None

async def start_bot_service():
    """Initializes and runs Telegram Bot polling in the background"""
    global bot_task
    # Stop existing task if running
    if bot_task and not bot_task.done():
        bot_task.cancel()
        try:
            await bot_task
        except asyncio.CancelledError:
            pass
        bot = get_bot()
        if bot:
            await bot.session.close()

    token = await get_setting("telegram_bot_token", BOT_TOKEN)
    if not token or not token.strip():
        logger.warning("Telegram Bot Token is not set. Bot is waiting for configuration in Web Admin Dashboard.")
        return

    bot, dp = init_bot(token.strip())
    if bot and dp:
        # Avoid duplicate router registration
        if bot_router not in dp.sub_routers:
            dp.include_router(bot_router)
        
        async def poll_runner():
            try:
                logger.info("Starting Telegram Bot polling...")
                # Delete webhook in case one was active previously
                await bot.delete_webhook(drop_pending_updates=True)
                
                # Set native menu shortcuts
                from aiogram.types import BotCommand, BotCommandScopeDefault
                await bot.set_my_commands([
                    BotCommand(command="start", description="Open the home menu"),
                    BotCommand(command="shop", description="Browse the shop"),
                    BotCommand(command="wallet", description="View your wallet & balance"),
                    BotCommand(command="orders", description="View your orders"),
                    BotCommand(command="channel", description="Join our reseller channel"),
                    BotCommand(command="freebies", description="Free rewards & referrals"),
                    BotCommand(command="referral", description="Referral store & rewards"),
                    BotCommand(command="profile", description="View your profile"),
                    BotCommand(command="support", description="Contact support"),
                    BotCommand(command="help", description="Help & FAQ")
                ], scope=BotCommandScopeDefault())
                logger.info("Bot commands menu shortcuts registered successfully.")
                
                await dp.start_polling(bot)
            except asyncio.CancelledError:
                logger.info("Telegram Bot polling stopped.")
            except Exception as e:
                logger.error(f"Telegram Bot polling error: {e}")

        bot_task = asyncio.create_task(poll_runner())

async def start_admin_bot_service():
    """Initializes and runs dedicated Private Admin Bot (@foxzenadmin_bot)"""
    global admin_bot_task
    if admin_bot_task and not admin_bot_task.done():
        admin_bot_task.cancel()
        try:
            await admin_bot_task
        except asyncio.CancelledError:
            pass
        adm_bot = get_admin_bot()
        if adm_bot:
            await adm_bot.session.close()

    token = ADMIN_BOT_TOKEN
    if not token or not token.strip():
        logger.info("Admin Bot Token is not set. Dedicated Admin Bot is disabled.")
        return

    adm_bot, adm_dp = init_admin_bot(token.strip())
    if adm_bot and adm_dp:
        async def admin_poll_runner():
            try:
                logger.info("Starting Dedicated Admin Bot (@foxzenadmin_bot) polling...")
                await adm_bot.delete_webhook(drop_pending_updates=True)
                
                from aiogram.types import BotCommand, BotCommandScopeDefault
                await adm_bot.set_my_commands([
                    BotCommand(command="start", description="Open Master Admin Dashboard"),
                    BotCommand(command="menu", description="Open Master Admin Dashboard"),
                    BotCommand(command="stats", description="View live store analytics"),
                    BotCommand(command="orders", description="View recent customer orders"),
                    BotCommand(command="supplier", description="Check supplier wallet balance"),
                    BotCommand(command="products", description="View active products & stock"),
                    BotCommand(command="users", description="Customer wallet management"),
                    BotCommand(command="broadcast", description="Broadcast message to all customers")
                ], scope=BotCommandScopeDefault())
                logger.info("Admin Bot commands shortcuts registered successfully.")
                
                await adm_dp.start_polling(adm_bot)
            except asyncio.CancelledError:
                logger.info("Admin Bot polling stopped.")
            except Exception as e:
                logger.error(f"Admin Bot polling error: {e}")

        admin_bot_task = asyncio.create_task(admin_poll_runner())

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Initializing database...")
    await init_db()
    logger.info("Database initialized successfully.")
    
    # Start store bot and admin bot
    await start_bot_service()
    await start_admin_bot_service()
    
    yield
    
    # Shutdown
    logger.info("Shutting down...")
    global bot_task, admin_bot_task
    for task in [bot_task, admin_bot_task]:
        if task and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    bot = get_bot()
    if bot:
        await bot.session.close()
    adm_bot = get_admin_bot()
    if adm_bot:
        await adm_bot.session.close()
        
    logger.info("Application stopped gracefully.")

# Attach lifespan to web_app
web_app.router.lifespan_context = lifespan

if __name__ == "__main__":
    print(f"\n=======================================================")
    print(f"🚀 Foxzen Bot & Web Admin Dashboard Starting...")
    print(f"🌐 Web Admin URL: http://localhost:{WEB_PORT}")
    print(f"👤 Default Login: admin / admin123")
    print(f"=======================================================\n")
    uvicorn.run("main:web_app", host=WEB_HOST, port=WEB_PORT, reload=False)
