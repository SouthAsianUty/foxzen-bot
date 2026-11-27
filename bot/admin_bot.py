import logging
import asyncio
from typing import Optional
from aiogram import Bot, Dispatcher, Router, F, BaseMiddleware
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    BotCommand,
    BotCommandScopeDefault
)

from config import ADMIN_BOT_TOKEN, ADMIN_TELEGRAM_ID
from database import (
    get_dashboard_stats,
    get_all_orders,
    get_order,
    get_products,
    get_product,
    add_product,
    delete_product,
    set_product_image,
    get_categories,
    get_category,
    add_stock_items,
    get_providers,
    get_all_users,
    get_user_profile,
    update_user_balance,
    fulfill_order_and_get_stock,
    complete_order,
    cancel_order,
    get_all_user_ids,
    get_setting,
    update_settings
)
from reseller_api import check_provider_balance, fetch_provider_products
from binance import test_binance_api_credentials, verify_binance_pay_transaction
from bot.bot_instance import send_user_notification

logger = logging.getLogger("AdminBot")

admin_bot: Optional[Bot] = None
admin_dp: Optional[Dispatcher] = None
admin_router = Router()

# Whitelist Guard: Only this Telegram ID can interact with the Admin Bot
ALLOWED_ADMIN_IDS = set()
if ADMIN_TELEGRAM_ID and ADMIN_TELEGRAM_ID.strip():
    try:
        ALLOWED_ADMIN_IDS.add(int(ADMIN_TELEGRAM_ID.strip()))
    except ValueError:
        pass
# Default user ID
ALLOWED_ADMIN_IDS.add(6443134339)

def is_admin(user_id: int) -> bool:
    return user_id in ALLOWED_ADMIN_IDS

# --- Security Filter Middleware ---
class AdminWhitelistMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        user = getattr(event, "from_user", None)
        if not user or not is_admin(user.id):
            logger.warning(f"Unauthorized access to Admin Bot from user: {user.id if user else 'unknown'}")
            if isinstance(event, CallbackQuery):
                await event.answer("⛔ Access Denied: Private Admin Bot.", show_alert=True)
            return None
        return await handler(event, data)

# --- Keyboards ---
def admin_main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📊 Live Analytics", callback_data="adm_stats"),
            InlineKeyboardButton(text="🛒 Recent Orders", callback_data="adm_orders")
        ],
        [
            InlineKeyboardButton(text="🔌 Supplier Balance", callback_data="adm_supplier"),
            InlineKeyboardButton(text="📦 Products & Stock", callback_data="adm_products")
        ],
        [
            InlineKeyboardButton(text="👥 User & Wallets", callback_data="adm_users"),
            InlineKeyboardButton(text="📢 Send Broadcast", callback_data="adm_broadcast_prompt")
        ],
        [
            InlineKeyboardButton(text="💳 Binance Pay API", callback_data="adm_binance_menu"),
            InlineKeyboardButton(text="🔄 Refresh", callback_data="adm_refresh")
        ]
    ])

def admin_back_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Back to Admin Menu", callback_data="adm_menu")]
    ])

# --- Dashboard Message Renderer ---
async def render_admin_dashboard_text() -> str:
    stats = await get_dashboard_stats()
    
    # Get provider balance summary
    providers = await get_providers(active_only=True)
    supplier_status = "Not Connected"
    if providers:
        p = providers[0]
        bal_text = f"${p['balance']:.2f} USDT" if p.get('balance') is not None else "Tap to Check"
        supplier_status = f"{p['name']} ({bal_text})"

    binance_secret = await get_setting("binance_api_secret")
    binance_status = "Active ✅" if binance_secret else "Secret Missing ⚠️"

    return (
        f"👑 <b>Foxzen Master Admin Control</b>\n"
        f"<i>Secure Control Panel for @foxzen_bot</i>\n\n"
        f"💰 <b>Today's Revenue:</b> <code>${stats.get('revenue_today', 0.0):.2f} USDT</code> ({stats.get('orders_today', 0)} sales)\n"
        f"📈 <b>Total All-Time Revenue:</b> <code>${stats.get('revenue_total', 0.0):.2f} USDT</code>\n"
        f"🛒 <b>Total Completed Orders:</b> <code>{stats.get('completed_orders', 0)}</code>\n"
        f"👥 <b>Registered Customers:</b> <code>{stats.get('total_users', 0)}</code>\n"
        f"📦 <b>Active Products:</b> <code>{stats.get('total_products', 0)}</code>\n"
        f"🔌 <b>Supplier:</b> <code>{supplier_status}</code>\n"
        f"💳 <b>Binance Auto-Verify:</b> <code>{binance_status}</code>\n\n"
        f"⚡ <i>Select an option below to manage your store:</i>"
    )

# --- Commands ---
@admin_router.message(F.text == "/start")
@admin_router.message(F.text == "/menu")
@admin_router.message(F.text == "/admin")
async def cmd_admin_start(message: Message):
    text = await render_admin_dashboard_text()
    await message.answer(text, reply_markup=admin_main_menu_keyboard(), parse_mode=ParseMode.HTML)

@admin_router.callback_query(F.data == "adm_menu")
@admin_router.callback_query(F.data == "adm_refresh")
async def cb_admin_menu(callback: CallbackQuery):
    text = await render_admin_dashboard_text()
    try:
        await callback.message.edit_text(text, reply_markup=admin_main_menu_keyboard(), parse_mode=ParseMode.HTML)
    except Exception:
        pass
    await callback.answer("Dashboard updated!")

# --- 1. Analytics & Stats ---
@admin_router.message(F.text == "/stats")
async def cmd_admin_stats_msg(message: Message):
    stats = await get_dashboard_stats()
    all_users = await get_all_users()
    total_cust_balance = sum((u.get("balance") or 0.0) for u in all_users)
    active_wallets = sum(1 for u in all_users if (u.get("balance") or 0.0) > 0)
    
    text = (
        f"📊 <b>Detailed Store Analytics</b>\n\n"
        f"💵 <b>Revenue Today:</b> ${stats.get('revenue_today', 0.0):.2f} USDT\n"
        f"💰 <b>Total Sales:</b> ${stats.get('revenue_total', 0.0):.2f} USDT\n\n"
        f"📦 <b>Orders Breakdown:</b>\n"
        f"  • Completed: <code>{stats.get('completed_orders', 0)}</code>\n"
        f"  • Pending Review: <code>{stats.get('pending_orders', 0)}</code>\n"
        f"  • Today's Orders: <code>{stats.get('orders_today', 0)}</code>\n\n"
        f"👥 <b>Customer Wallets:</b>\n"
        f"  • Total Registered: <code>{len(all_users)}</code>\n"
        f"  • Active Funded Wallets: <code>{active_wallets}</code>\n"
        f"  • Total Customer Funds in Wallets: <code>${total_cust_balance:.2f} USDT</code>\n"
    )
    await message.answer(text, reply_markup=admin_back_keyboard(), parse_mode=ParseMode.HTML)

@admin_router.callback_query(F.data == "adm_stats")
async def cb_admin_stats(callback: CallbackQuery):
    stats = await get_dashboard_stats()
    all_users = await get_all_users()
    total_cust_balance = sum((u.get("balance") or 0.0) for u in all_users)
    active_wallets = sum(1 for u in all_users if (u.get("balance") or 0.0) > 0)
    
    text = (
        f"📊 <b>Detailed Store Analytics</b>\n\n"
        f"💵 <b>Revenue Today:</b> ${stats.get('revenue_today', 0.0):.2f} USDT\n"
        f"💰 <b>Total Sales:</b> ${stats.get('revenue_total', 0.0):.2f} USDT\n\n"
        f"📦 <b>Orders Breakdown:</b>\n"
        f"  • Completed: <code>{stats.get('completed_orders', 0)}</code>\n"
        f"  • Pending Review: <code>{stats.get('pending_orders', 0)}</code>\n"
        f"  • Today's Orders: <code>{stats.get('orders_today', 0)}</code>\n\n"
        f"👥 <b>Customer Wallets:</b>\n"
        f"  • Total Registered: <code>{len(all_users)}</code>\n"
        f"  • Active Funded Wallets: <code>{active_wallets}</code>\n"
        f"  • Total Customer Funds in Wallets: <code>${total_cust_balance:.2f} USDT</code>\n"
    )
    await callback.message.edit_text(text, reply_markup=admin_back_keyboard(), parse_mode=ParseMode.HTML)
    await callback.answer()

# --- 2. Orders Manager ---
@admin_router.message(F.text == "/orders")
async def cmd_admin_orders_msg(message: Message):
    orders = await get_all_orders(limit=8)
    if not orders:
        await message.answer("🛒 <b>Recent Orders</b>\n\nNo orders recorded in database yet.", reply_markup=admin_back_keyboard(), parse_mode=ParseMode.HTML)
        return

    text = "🛒 <b>Recent Orders (Last 8)</b>\n<i>Tap an order to inspect credentials or approve:</i>"
    buttons = []
    for o in orders:
        status_emoji = "✅" if o["status"] == "COMPLETED" else ("⏳" if o["status"] == "PENDING" else "❌")
        btn_text = f"{status_emoji} #{o['order_id']} | ${o['amount']} | {o['product_name'][:18]}"
        buttons.append([InlineKeyboardButton(text=btn_text, callback_data=f"adm_ord_{o['order_id']}")])

    buttons.append([InlineKeyboardButton(text="🔙 Back to Admin Menu", callback_data="adm_menu")])
    await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode=ParseMode.HTML)

@admin_router.callback_query(F.data == "adm_orders")
async def cb_admin_orders(callback: CallbackQuery):
    orders = await get_all_orders(limit=8)
    if not orders:
        text = "🛒 <b>Recent Orders</b>\n\nNo orders recorded in database yet."
        await callback.message.edit_text(text, reply_markup=admin_back_keyboard(), parse_mode=ParseMode.HTML)
        await callback.answer()
        return

    text = "🛒 <b>Recent Orders (Last 8)</b>\n<i>Tap an order to inspect credentials or approve:</i>"
    buttons = []
    for o in orders:
        status_emoji = "✅" if o["status"] == "COMPLETED" else ("⏳" if o["status"] == "PENDING" else "❌")
        btn_text = f"{status_emoji} #{o['order_id']} | ${o['amount']} | {o['product_name'][:18]}"
        buttons.append([InlineKeyboardButton(text=btn_text, callback_data=f"adm_ord_{o['order_id']}")])

    buttons.append([InlineKeyboardButton(text="🔙 Back to Admin Menu", callback_data="adm_menu")])
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode=ParseMode.HTML)
    await callback.answer()

@admin_router.callback_query(F.data.startswith("adm_ord_"))
async def cb_admin_order_detail(callback: CallbackQuery):
    oid = callback.data.replace("adm_ord_", "")
    order = await get_order(oid)
    if not order:
        await callback.answer("Order not found!", show_alert=True)
        return

    delivered = order.get("delivered_data") or "No credentials delivered yet."
    tx_id = order.get("binance_tx_id") or "Wallet Balance"
    
    text = (
        f"📦 <b>Order #{order['id']} Details</b>\n\n"
        f"🛍️ <b>Product:</b> {order['product_name']}\n"
        f"🔢 <b>Quantity:</b> {order.get('quantity', 1)}x\n"
        f"💵 <b>Amount:</b> ${order['amount']} USDT\n"
        f"📊 <b>Status:</b> <b>{order['status']}</b>\n"
        f"💳 <b>Payment:</b> <code>{tx_id}</code>\n"
        f"👤 <b>Customer:</b> @{order.get('username') or 'N/A'} (ID: <code>{order['telegram_id']}</code>)\n"
        f"📅 <b>Date:</b> {order['created_at']}\n\n"
        f"🔑 <b>Delivered Data:</b>\n"
        f"<code>{delivered}</code>"
    )

    buttons = []
    if order["status"] in ("PENDING", "PENDING_VERIFICATION"):
        if order.get("binance_tx_id") and order.get("binance_tx_id") not in ("WALLET", "WALLET_BALANCE"):
            buttons.append([
                InlineKeyboardButton(text="🔍 Check Binance API", callback_data=f"adm_chk_binance_{order['id']}"),
                InlineKeyboardButton(text="✅ Approve & Deliver", callback_data=f"adm_appr_{order['id']}")
            ])
        else:
            buttons.append([
                InlineKeyboardButton(text="✅ Approve & Deliver", callback_data=f"adm_appr_{order['id']}")
            ])
        buttons.append([
            InlineKeyboardButton(text="❌ Reject Order", callback_data=f"adm_rej_{order['id']}")
        ])
    buttons.append([
        InlineKeyboardButton(text="🔙 Back to Orders", callback_data="adm_orders"),
        InlineKeyboardButton(text="🏠 Admin Menu", callback_data="adm_menu")
    ])

    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode=ParseMode.HTML)
    await callback.answer()

@admin_router.callback_query(F.data.startswith("adm_chk_binance_"))
async def cb_admin_check_binance_order(callback: CallbackQuery):
    oid = callback.data.replace("adm_chk_binance_", "")
    order = await get_order(oid)
    if not order:
        await callback.answer("Order not found!", show_alert=True)
        return

    api_key = await get_setting("binance_api_key")
    api_secret = await get_setting("binance_api_secret")

    if not api_key or not api_secret:
        await callback.answer("⚠️ Binance API Secret is missing! Use /setbinance to set it.", show_alert=True)
        return

    await callback.answer("Querying Binance API...")
    tx_id = order.get("binance_tx_id", "")
    res = await verify_binance_pay_transaction(
        api_key=api_key,
        api_secret=api_secret,
        submitted_tx_id=tx_id,
        expected_amount=order["amount"],
        expected_currency="USDT"
    )

    if res.get("verified") is True:
        fulfil_res = await fulfill_order_and_get_stock(oid)
        if fulfil_res.get("success"):
            delivered_data = fulfil_res["delivered_data"]
            await complete_order(oid, delivered_data=delivered_data)
            await send_user_notification(
                order["telegram_id"],
                f"🎉 <b>Payment Verified via Binance Pay!</b>\n\n"
                f"Order: <b>#{oid}</b>\n"
                f"Product: <b>{order['product_name']}</b>\n\n"
                f"🔑 <b>Your Delivered Credentials:</b>\n"
                f"<code>{delivered_data}</code>\n\n"
                f"<i>Thank you for your purchase!</i>"
            )
            await callback.answer("✅ Verified & Delivered successfully!", show_alert=True)
            callback.data = f"adm_ord_{oid}"
            await cb_admin_order_detail(callback)
            return
        else:
            await callback.answer(f"Payment verified but stock error: {fulfil_res.get('error')}", show_alert=True)
            return
    else:
        err = res.get("error", "Transaction not found")
        await callback.answer(f"❌ Not Verified: {err}", show_alert=True)

@admin_router.callback_query(F.data.startswith("adm_appr_"))
async def cb_admin_approve_order(callback: CallbackQuery):
    oid = callback.data.replace("adm_appr_", "")
    res = await fulfill_order_and_get_stock(oid)
    if res.get("success"):
        await callback.answer("✅ Order approved & delivered to customer!", show_alert=True)
        # Notify customer on store bot
        order = await get_order(oid)
        if order:
            await send_user_notification(
                order["telegram_id"],
                f"🎉 <b>Order #{oid} Approved!</b>\n\n"
                f"🛍️ <b>Product:</b> {order['product_name']}\n\n"
                f"🔑 <b>Your Credentials:</b>\n<code>{res['delivered_data']}</code>\n\n"
                f"<i>Thank you for shopping with us!</i>"
            )
    else:
        await callback.answer(f"❌ Failed: {res.get('error')}", show_alert=True)
    
    # Refresh view
    callback.data = f"adm_ord_{oid}"
    await cb_admin_order_detail(callback)

@admin_router.callback_query(F.data.startswith("adm_rej_"))
async def cb_admin_reject_order(callback: CallbackQuery):
    oid = callback.data.replace("adm_rej_", "")
    await cancel_order(oid, notes="Rejected via Telegram Admin Bot")
    await callback.answer("Order marked as cancelled.", show_alert=True)
    callback.data = f"adm_ord_{oid}"
    await cb_admin_order_detail(callback)

# --- 3. Supplier Balance ---
@admin_router.message(F.text == "/supplier")
async def cmd_admin_supplier_msg(message: Message):
    providers = await get_providers()
    if not providers:
        text = "🔌 <b>Supplier APIs</b>\n\nNo external supplier connected yet. Connect one in Web Admin Dashboard."
        await message.answer(text, reply_markup=admin_back_keyboard(), parse_mode=ParseMode.HTML)
        return

    text = "🔌 <b>Connected Suppliers & Balances</b>\n\n"
    for p in providers:
        bal = await check_provider_balance(p)
        bal_str = f"<b>${bal:.2f} USDT</b>" if bal is not None else "<i>Unavailable / Error</i>"
        text += (
            f"🏢 <b>{p['name']}</b>\n"
            f"💰 <b>Wallet Balance:</b> {bal_str}\n"
            f"🌐 <b>API URL:</b> <code>{p['api_url']}</code>\n"
            f"⚡ <b>Status:</b> {'Active ✅' if p['is_active'] else 'Disabled ⏸️'}\n\n"
        )

    buttons = [
        [InlineKeyboardButton(text="🔄 Re-Check Balance", callback_data="adm_supplier")],
        [InlineKeyboardButton(text="🔙 Back to Admin Menu", callback_data="adm_menu")]
    ]
    await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode=ParseMode.HTML)

@admin_router.callback_query(F.data == "adm_supplier")
async def cb_admin_supplier(callback: CallbackQuery):
    await callback.answer("Checking supplier balance...")
    providers = await get_providers()
    if not providers:
        text = "🔌 <b>Supplier APIs</b>\n\nNo external supplier connected yet. Connect one in Web Admin Dashboard."
        await callback.message.edit_text(text, reply_markup=admin_back_keyboard(), parse_mode=ParseMode.HTML)
        return

    text = "🔌 <b>Connected Suppliers & Balances</b>\n\n"
    for p in providers:
        bal = await check_provider_balance(p)
        bal_str = f"<b>${bal:.2f} USDT</b>" if bal is not None else "<i>Unavailable / Error</i>"
        text += (
            f"🏢 <b>{p['name']}</b>\n"
            f"💰 <b>Wallet Balance:</b> {bal_str}\n"
            f"🌐 <b>API URL:</b> <code>{p['api_url']}</code>\n"
            f"⚡ <b>Status:</b> {'Active ✅' if p['is_active'] else 'Disabled ⏸️'}\n\n"
        )

    buttons = [
        [InlineKeyboardButton(text="🔄 Re-Check Balance", callback_data="adm_supplier")],
        [InlineKeyboardButton(text="🔙 Back to Admin Menu", callback_data="adm_menu")]
    ]
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode=ParseMode.HTML)

# --- 3B. Binance Pay & Auto-Verification ---
async def render_binance_status_text() -> str:
    pay_id = await get_setting("binance_pay_id", "717053382")
    api_key = await get_setting("binance_api_key", "")
    api_secret = await get_setting("binance_api_secret", "")

    key_masked = f"{api_key[:6]}...{api_key[-6:]}" if len(api_key) > 12 else ("Not configured" if not api_key else api_key)
    secret_status = "Configured ✅" if api_secret else "MISSING ❌ (Auto-verification paused)"

    text = (
        f"💳 <b>Binance Payment Integration Status</b>\n\n"
        f"🆔 <b>Binance Pay UID / Pay ID:</b> <code>{pay_id}</code>\n"
        f"🔑 <b>API Key:</b> <code>{key_masked}</code>\n"
        f"🔒 <b>API Secret:</b> {secret_status}\n\n"
    )

    if not api_secret:
        text += (
            f"⚠️ <b>Action Required for Auto-Verification:</b>\n"
            f"Binance requires your <b>API Secret Key</b> to verify payments automatically.\n\n"
            f"👉 <b>How to set it right now:</b>\n"
            f"Send command:\n"
            f"<code>/setbinance &lt;your_secret_key&gt;</code>\n\n"
            f"<i>Example:</i>\n"
            f"<code>/setbinance abcdef1234567890abcdef1234567890</code>"
        )
    else:
        text += (
            f"✅ <b>Auto-Verification is ACTIVE!</b>\n"
            f"Whenever a customer sends their Binance TxID/Order ID, the bot verifies the payment in real-time."
        )
    return text

@admin_router.message(F.text == "/binance")
async def cmd_admin_binance(message: Message):
    text = await render_binance_status_text()
    buttons = [
        [InlineKeyboardButton(text="🔄 Test Binance Connection", callback_data="adm_test_binance")],
        [InlineKeyboardButton(text="🔙 Back to Admin Menu", callback_data="adm_menu")]
    ]
    await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode=ParseMode.HTML)

@admin_router.callback_query(F.data == "adm_binance_menu")
async def cb_admin_binance_menu(callback: CallbackQuery):
    text = await render_binance_status_text()
    buttons = [
        [InlineKeyboardButton(text="🔄 Test Binance Connection", callback_data="adm_test_binance")],
        [InlineKeyboardButton(text="🔙 Back to Admin Menu", callback_data="adm_menu")]
    ]
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode=ParseMode.HTML)
    await callback.answer()

@admin_router.callback_query(F.data == "adm_test_binance")
async def cb_admin_test_binance(callback: CallbackQuery):
    api_key = await get_setting("binance_api_key", "")
    api_secret = await get_setting("binance_api_secret", "")

    if not api_key or not api_secret:
        await callback.answer("❌ API Key or Secret is missing! Use /setbinance first.", show_alert=True)
        return

    await callback.answer("Testing connection with Binance API...")
    ok, msg = await test_binance_api_credentials(api_key, api_secret)
    if ok:
        await callback.message.answer(
            f"🎉 <b>Binance API Test Succeeded!</b>\n\n"
            f"✅ Connected to Binance Pay API successfully.\n"
            f"Automated verification is 100% operational.",
            parse_mode=ParseMode.HTML
        )
    else:
        await callback.message.answer(
            f"❌ <b>Binance Connection Failed</b>\n\n"
            f"<b>Error:</b> <code>{msg}</code>\n\n"
            f"Please verify that your Secret Key is correct and that 'Enable Reading' permission is checked in Binance API Management.",
            parse_mode=ParseMode.HTML
        )

@admin_router.message(F.text.startswith("/setbinance"))
async def cmd_set_binance_secret(message: Message):
    parts = message.text.strip().split()
    if len(parts) == 2:
        new_secret = parts[1].strip()
        new_key = await get_setting("binance_api_key", "")
    elif len(parts) == 3:
        new_key = parts[1].strip()
        new_secret = parts[2].strip()
    else:
        await message.answer(
            "⚠️ <b>Usage:</b>\n"
            "<code>/setbinance &lt;secret_key&gt;</code>\n"
            "<i>Or:</i>\n"
            "<code>/setbinance &lt;api_key&gt; &lt;secret_key&gt;</code>",
            parse_mode=ParseMode.HTML
        )
        return

    if not new_key:
        await message.answer("⚠️ API Key is not set. Please provide both: <code>/setbinance &lt;api_key&gt; &lt;secret_key&gt;</code>", parse_mode=ParseMode.HTML)
        return

    test_msg = await message.answer("⏳ <i>Testing API credentials with Binance...</i>", parse_mode=ParseMode.HTML)
    ok, err = await test_binance_api_credentials(new_key, new_secret)
    
    if not ok:
        await test_msg.edit_text(
            f"❌ <b>Invalid Credentials</b>\n\n"
            f"Binance rejected the test request:\n<code>{err}</code>\n\n"
            f"Please check your Secret Key in Binance API Management and ensure 'Enable Reading' is turned on.",
            parse_mode=ParseMode.HTML
        )
        return

    # Update database
    await update_settings({
        "binance_api_key": new_key,
        "binance_api_secret": new_secret
    })

    # Update local .env as well
    try:
        from config import BASE_DIR
        env_path = BASE_DIR / ".env"
        if env_path.exists():
            content = env_path.read_text()
            if "BINANCE_API_KEY=" in content:
                import re
                content = re.sub(r"BINANCE_API_KEY=.*", f"BINANCE_API_KEY={new_key}", content)
                content = re.sub(r"BINANCE_API_SECRET=.*", f"BINANCE_API_SECRET={new_secret}", content)
            else:
                content += f"\nBINANCE_API_KEY={new_key}\nBINANCE_API_SECRET={new_secret}\n"
            env_path.write_text(content)
    except Exception as e:
        logger.warning(f"Could not update .env file: {e}")

    await test_msg.edit_text(
        f"🎉 <b>Binance API Connected & Saved Successfully!</b>\n\n"
        f"✅ <b>API Key:</b> <code>{new_key[:6]}...{new_key[-6:]}</code>\n"
        f"✅ <b>Secret Key:</b> Saved & Verified\n\n"
        f"🚀 <b>Automated verification is now LIVE!</b>\n"
        f"When any customer submits their Binance Order ID / TxID, the bot will auto-verify and deliver products immediately.",
        parse_mode=ParseMode.HTML
    )

# --- FSM States for Product & Stock Management ---
class AddLocalProductStates(StatesGroup):
    waiting_for_category = State()
    waiting_for_name = State()
    waiting_for_price = State()
    waiting_for_description = State()
    waiting_for_stock = State()

class AddResellerProductStates(StatesGroup):
    waiting_for_category = State()
    waiting_for_price = State()

class AddStockStates(StatesGroup):
    waiting_for_stock_items = State()

class AdminProductImageState(StatesGroup):
    waiting_for_image = State()

SUPPLIER_CATALOG_CACHE: dict[int, list[dict]] = {}

# --- Cancel Active Action ---
@admin_router.message(F.text == "/cancel")
@admin_router.callback_query(F.data == "adm_cancel_fsm")
async def cb_cancel_fsm(event: Message | CallbackQuery, state: FSMContext):
    await state.clear()
    text = "❌ <b>Action cancelled.</b> Returning to Products menu."
    kb = products_menu_keyboard()
    if isinstance(event, CallbackQuery):
        try:
            await event.message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)
        except Exception:
            await event.message.answer(text, reply_markup=kb, parse_mode=ParseMode.HTML)
        await event.answer("Cancelled")
    else:
        await event.answer(text, reply_markup=kb, parse_mode=ParseMode.HTML)

# --- 4. Products & Stock ---
async def render_products_menu_text() -> str:
    products = await get_products()
    local_count = sum(1 for p in products if p.get("fulfillment_type") != "API")
    api_count = sum(1 for p in products if p.get("fulfillment_type") == "API")
    out_of_stock = sum(1 for p in products if p.get("fulfillment_type") != "API" and (p.get("in_stock") or 0) <= 0)
    
    return (
        f"📦 <b>Products & Inventory Manager</b>\n\n"
        f"📊 <b>Total Products in Store:</b> <code>{len(products)}</code>\n"
        f"📦 <b>Local Inventory Products:</b> <code>{local_count}</code>\n"
        f"🔌 <b>Supplier (API) Products:</b> <code>{api_count}</code>\n"
        f"⚠️ <b>Out of Stock (Local):</b> <code>{out_of_stock}</code>\n\n"
        f"⚡ <i>What would you like to do?</i>"
    )

def products_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="➕ Add Local Product", callback_data="adm_add_local_start"),
            InlineKeyboardButton(text="🔌 Import from Supplier", callback_data="adm_import_supp_start")
        ],
        [
            InlineKeyboardButton(text="📥 Add Stock to Existing", callback_data="adm_add_stock_select"),
            InlineKeyboardButton(text="📋 View All Products", callback_data="adm_view_all_prods:0")
        ],
        [
            InlineKeyboardButton(text="🔙 Back to Admin Menu", callback_data="adm_menu")
        ]
    ])

@admin_router.message(F.text == "/products")
async def cmd_admin_products_msg(message: Message, state: FSMContext):
    await state.clear()
    text = await render_products_menu_text()
    await message.answer(text, reply_markup=products_menu_keyboard(), parse_mode=ParseMode.HTML)

@admin_router.callback_query(F.data == "adm_products")
async def cb_admin_products(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    text = await render_products_menu_text()
    try:
        await callback.message.edit_text(text, reply_markup=products_menu_keyboard(), parse_mode=ParseMode.HTML)
    except Exception:
        await callback.message.answer(text, reply_markup=products_menu_keyboard(), parse_mode=ParseMode.HTML)
    await callback.answer()

# --- Flow A: Add Local Product ---
@admin_router.callback_query(F.data == "adm_add_local_start")
async def cb_add_local_start(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    categories = await get_categories()

    buttons = [
        [InlineKeyboardButton(text="⚡ No Category (Direct / General)", callback_data="adm_loc_cat:none")]
    ]
    for c in categories:
        icon = c.get("icon", "📁")
        buttons.append([InlineKeyboardButton(text=f"{icon} {c['name']}", callback_data=f"adm_loc_cat:{c['id']}")])
    buttons.append([InlineKeyboardButton(text="❌ Cancel", callback_data="adm_cancel_fsm")])

    await state.set_state(AddLocalProductStates.waiting_for_category)
    text = (
        "➕ <b>Add New Local Product</b>\n\n"
        "📁 <b>Step 1/4: Choose Category</b>\n"
        "Select a category below or tap <b>No Category</b>:"
    )
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode=ParseMode.HTML)
    await callback.answer()

@admin_router.callback_query(F.data.startswith("adm_loc_cat:"), AddLocalProductStates.waiting_for_category)
async def cb_loc_pick_cat(callback: CallbackQuery, state: FSMContext):
    cat_raw = callback.data.replace("adm_loc_cat:", "")
    if cat_raw in ("none", "0", "skip"):
        cat_id = None
        cat_name = "None (No Category)"
    else:
        cat_id = int(cat_raw)
        cat = await get_category(cat_id)
        cat_name = cat.get("name", "Category") if cat else "General"
    
    await state.update_data(category_id=cat_id, category_name=cat_name)
    await state.set_state(AddLocalProductStates.waiting_for_name)
    
    text = (
        f"➕ <b>Add New Local Product</b>\n"
        f"📁 Category: <b>{cat_name}</b>\n\n"
        f"📝 <b>Step 2/4: Product Title / Name</b>\n"
        f"Please send the title of the product:\n"
        f"<i>Example: NordVPN 1 Month Premium Private</i>\n\n"
        f"<i>(Send /cancel to abort)</i>"
    )
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Cancel", callback_data="adm_cancel_fsm")]
    ]), parse_mode=ParseMode.HTML)
    await callback.answer()

@admin_router.message(AddLocalProductStates.waiting_for_name)
async def msg_loc_name(message: Message, state: FSMContext):
    name = message.text.strip()
    if not name or len(name) < 2:
        await message.answer("⚠️ Please provide a valid product name (at least 2 characters):")
        return
    
    await state.update_data(product_name=name)
    await state.set_state(AddLocalProductStates.waiting_for_price)
    
    await message.answer(
        f"🛍️ <b>Product:</b> {name}\n\n"
        f"💵 <b>Step 3/4: Selling Price (USDT)</b>\n"
        f"Enter the price customers will pay in USDT:\n"
        f"<i>Example: <code>2.50</code> or <code>1.99</code></i>\n\n"
        f"<i>(Send /cancel to abort)</i>",
        parse_mode=ParseMode.HTML
    )

@admin_router.message(AddLocalProductStates.waiting_for_price)
async def msg_loc_price(message: Message, state: FSMContext):
    clean = message.text.replace("$", "").replace("USDT", "").replace("usdt", "").strip()
    try:
        price = float(clean)
        if price <= 0:
            raise ValueError
    except ValueError:
        await message.answer("⚠️ Please enter a valid positive price number, e.g. <code>2.50</code>:", parse_mode=ParseMode.HTML)
        return

    await state.update_data(price=price)
    await state.set_state(AddLocalProductStates.waiting_for_description)
    
    await message.answer(
        f"💵 <b>Price:</b> <code>${price:.2f} USDT</code>\n\n"
        f"📄 <b>Step 4/5: Description (Optional)</b>\n"
        f"Enter features or instructions for customers.\n"
        f"<i>Or send <code>skip</code> to use standard default description:</i>",
        parse_mode=ParseMode.HTML
    )

@admin_router.message(AddLocalProductStates.waiting_for_description)
async def msg_loc_desc(message: Message, state: FSMContext):
    raw = message.text.strip()
    data = await state.get_data()
    name = data.get("product_name", "Product")
    
    if raw.lower() == "skip":
        desc = f"Premium {name}. High quality, fast delivery and full warranty support."
    else:
        desc = raw

    await state.update_data(description=desc)
    await state.set_state(AddLocalProductStates.waiting_for_stock)
    
    await message.answer(
        f"🔑 <b>Step 5/5: Initial Stock Items (Optional)</b>\n\n"
        f"Paste your accounts or license keys below (<b>one per line</b>).\n"
        f"<i>Example:</i>\n"
        f"<code>user1@domain.com:pass123\nuser2@domain.com:pass456</code>\n\n"
        f"<i>Or send <code>skip</code> if you want to add stock later:</i>",
        parse_mode=ParseMode.HTML
    )

@admin_router.message(AddLocalProductStates.waiting_for_stock)
async def msg_loc_stock(message: Message, state: FSMContext):
    raw = message.text.strip()
    data = await state.get_data()
    
    cat_id = data.get("category_id")
    cat_name = data.get("category_name", "None (No Category)")
    name = data.get("product_name", "New Product")
    price = data.get("price", 1.0)
    desc = data.get("description", "")
    
    items = []
    if raw.lower() != "skip":
        items = [line.strip() for line in raw.split("\n") if line.strip()]

    # Save to database
    new_prod_id = await add_product(
        category_id=cat_id,
        name=name,
        description=desc,
        price=price,
        delivery_instructions="Delivered instantly. Use the credentials above to log in.",
        fulfillment_type="LOCAL"
    )
    
    if items and new_prod_id:
        await add_stock_items(new_prod_id, items)

    await state.clear()
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Add Another Product", callback_data="adm_add_local_start")],
        [InlineKeyboardButton(text="📦 Products & Stock", callback_data="adm_products")],
        [InlineKeyboardButton(text="🏠 Admin Menu", callback_data="adm_menu")]
    ])
    
    await message.answer(
        f"🎉 <b>Local Product Created Successfully!</b>\n\n"
        f"🆔 <b>ID:</b> <code>#{new_prod_id}</code>\n"
        f"🛍️ <b>Product:</b> {name}\n"
        f"📁 <b>Category:</b> {cat_name}\n"
        f"💵 <b>Selling Price:</b> <code>${price:.2f} USDT</code>\n"
        f"📦 <b>Stock Added:</b> <code>{len(items)} items</code>\n\n"
        f"✅ <i>This product is now live on @foxzen_bot for your customers!</i>",
        reply_markup=kb,
        parse_mode=ParseMode.HTML
    )

# --- Flow B: Import Supplier Product (API) ---
@admin_router.callback_query(F.data == "adm_import_supp_start")
async def cb_import_supp_start(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    providers = await get_providers(active_only=True)
    if not providers:
        await callback.answer("No active supplier connected! Add one first.", show_alert=True)
        return

    provider = providers[0]
    await callback.message.edit_text(
        f"🔄 <b>Connecting to {provider['name']}...</b>\n"
        f"Fetching live catalog and wholesale prices from supplier API. Please wait a moment...",
        parse_mode=ParseMode.HTML
    )
    
    res = await fetch_provider_products(provider)
    if not res.get("success") or not res.get("products"):
        err = res.get("error") or "Supplier returned empty catalog."
        await callback.message.edit_text(
            f"❌ <b>Failed to Fetch Supplier Catalog</b>\n\n"
            f"<b>Supplier:</b> {provider['name']}\n"
            f"<b>Details:</b> <code>{err}</code>\n\n"
            f"Make sure supplier API credentials and URL are valid.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Retry Fetch", callback_data="adm_import_supp_start")],
                [InlineKeyboardButton(text="🔙 Back to Products", callback_data="adm_products")]
            ]),
            parse_mode=ParseMode.HTML
        )
        return

    prods = res["products"]
    admin_id = callback.from_user.id
    SUPPLIER_CATALOG_CACHE[admin_id] = prods

    await show_supplier_page(callback.message, admin_id, 0, provider)
    await callback.answer()

async def show_supplier_page(message_or_event, admin_id: int, page: int, provider: dict):
    prods = SUPPLIER_CATALOG_CACHE.get(admin_id, [])
    if not prods:
        return

    page_size = 6
    total_pages = (len(prods) + page_size - 1) // page_size
    page = max(0, min(page, total_pages - 1))
    
    start_idx = page * page_size
    page_items = prods[start_idx : start_idx + page_size]
    
    text = (
        f"🔌 <b>Supplier Catalog: {provider['name']}</b>\n"
        f"Found <b>{len(prods)}</b> live products available for instant 1-tap import.\n\n"
        f"<i>Tap any product below to import to your store:</i>"
    )
    
    buttons = []
    for i, p in enumerate(page_items):
        actual_idx = start_idx + i
        price_str = f"${p['price']:.2f}" if p.get('price') else "Price TBD"
        label = f"{p['name'][:24]} | {price_str}"
        buttons.append([InlineKeyboardButton(text=label, callback_data=f"adm_supp_pick:{actual_idx}")])
        
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(text="◀️ Prev", callback_data=f"adm_supp_page:{page - 1}"))
    nav_row.append(InlineKeyboardButton(text=f"📄 {page + 1}/{total_pages}", callback_data="adm_noop"))
    if page + 1 < total_pages:
        nav_row.append(InlineKeyboardButton(text="Next ▶️", callback_data=f"adm_supp_page:{page + 1}"))
    
    if nav_row:
        buttons.append(nav_row)
    buttons.append([InlineKeyboardButton(text="🔙 Back to Products", callback_data="adm_products")])
    
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    try:
        await message_or_event.edit_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)
    except Exception:
        await message_or_event.answer(text, reply_markup=kb, parse_mode=ParseMode.HTML)

@admin_router.callback_query(F.data.startswith("adm_supp_page:"))
async def cb_supp_page(callback: CallbackQuery):
    page = int(callback.data.replace("adm_supp_page:", ""))
    admin_id = callback.from_user.id
    providers = await get_providers(active_only=True)
    if not providers:
        await callback.answer("Provider not found")
        return
    await show_supplier_page(callback.message, admin_id, page, providers[0])
    await callback.answer()

@admin_router.callback_query(F.data.startswith("adm_supp_pick:"))
async def cb_supp_pick_prod(callback: CallbackQuery, state: FSMContext):
    idx = int(callback.data.replace("adm_supp_pick:", ""))
    admin_id = callback.from_user.id
    prods = SUPPLIER_CATALOG_CACHE.get(admin_id, [])
    if idx >= len(prods):
        await callback.answer("Product not found!", show_alert=True)
        return
    
    prod = prods[idx]
    providers = await get_providers(active_only=True)
    provider_id = providers[0]["id"] if providers else None
    
    await state.update_data(
        supplier_prod=prod,
        provider_id=provider_id,
        supplier_name=providers[0]["name"] if providers else "Supplier"
    )
    
    categories = await get_categories()

    buttons = [
        [InlineKeyboardButton(text="⚡ No Category (Direct / General)", callback_data="adm_supp_cat:none")]
    ]
    for c in categories:
        icon = c.get("icon", "📁")
        buttons.append([InlineKeyboardButton(text=f"{icon} {c['name']}", callback_data=f"adm_supp_cat:{c['id']}")])
    buttons.append([InlineKeyboardButton(text="❌ Cancel", callback_data="adm_cancel_fsm")])

    await state.set_state(AddResellerProductStates.waiting_for_category)
    text = (
        f"🔌 <b>Importing: {prod['name']}</b>\n"
        f"💰 Wholesale Cost: <code>${prod['price']:.2f} USDT</code>\n\n"
        f"📁 <b>Step 1/2: Choose Category in your Store:</b>\n"
        f"Select a category below or tap <b>No Category</b>:"
    )
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode=ParseMode.HTML)
    await callback.answer()

@admin_router.callback_query(F.data.startswith("adm_supp_cat:"), AddResellerProductStates.waiting_for_category)
async def cb_supp_pick_cat(callback: CallbackQuery, state: FSMContext):
    cat_raw = callback.data.replace("adm_supp_cat:", "")
    if cat_raw in ("none", "0", "skip"):
        cat_id = None
        cat_name = "None (No Category)"
    else:
        cat_id = int(cat_raw)
        cat = await get_category(cat_id)
        cat_name = cat.get("name", "Category") if cat else "General"
    
    await state.update_data(category_id=cat_id, category_name=cat_name)
    data = await state.get_data()
    prod = data["supplier_prod"]
    
    await ask_supplier_retail_price(callback.message, prod, state)
    await callback.answer()

async def ask_supplier_retail_price(message, prod: dict, state: FSMContext):
    await state.set_state(AddResellerProductStates.waiting_for_price)
    cost = prod.get("price", 0.0)
    suggested = max(round(cost * 1.35, 2), round(cost + 0.50, 2)) if cost > 0 else 1.0
    
    text = (
        f"🔌 <b>Import Supplier Product</b>\n\n"
        f"🛍️ <b>Product:</b> {prod['name']}\n"
        f"🆔 <b>Supplier Variant/ID:</b> <code>{prod['id']}</code>\n"
        f"💰 <b>Supplier Wholesale Cost:</b> <code>${cost:.2f} USDT</code>\n\n"
        f"💵 <b>Step 2/2: Set Your Retail Selling Price</b>\n"
        f"What should customers on @foxzen_bot pay?\n"
        f"<i>(Suggested: <code>${suggested:.2f}</code> for healthy profit margin)</i>\n\n"
        f"👉 <i>Type your price in USDT (or send /cancel):</i>"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Cancel", callback_data="adm_cancel_fsm")]
    ])
    try:
        await message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)
    except Exception:
        await message.answer(text, reply_markup=kb, parse_mode=ParseMode.HTML)

@admin_router.message(AddResellerProductStates.waiting_for_price)
async def msg_supp_price(message: Message, state: FSMContext):
    clean = message.text.replace("$", "").replace("USDT", "").replace("usdt", "").strip()
    try:
        price = float(clean)
        if price <= 0:
            raise ValueError
    except ValueError:
        await message.answer("⚠️ Please enter a valid positive price number, e.g. <code>2.50</code>:", parse_mode=ParseMode.HTML)
        return

    data = await state.get_data()
    prod = data["supplier_prod"]
    provider_id = data.get("provider_id")
    provider_name = data.get("supplier_name", "Supplier")
    cat_id = data.get("category_id")
    cat_name = data.get("category_name", "None (No Category)")
    cost = prod.get("price", 0.0)
    profit = price - cost

    new_prod_id = await add_product(
        category_id=cat_id,
        name=prod["name"],
        description=f"Automated digital product delivered instantly via {provider_name}.",
        price=price,
        delivery_instructions="Delivery format: Account Credentials / License Key. Do not change login details.",
        fulfillment_type="API",
        provider_id=provider_id,
        provider_product_id=str(prod["id"]),
        provider_price=cost
    )

    await state.clear()
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔌 Import Another Product", callback_data="adm_import_supp_start")],
        [InlineKeyboardButton(text="📦 Products & Stock", callback_data="adm_products")],
        [InlineKeyboardButton(text="🏠 Admin Menu", callback_data="adm_menu")]
    ])

    await message.answer(
        f"🎉 <b>Supplier Product Successfully Imported!</b>\n\n"
        f"🆔 <b>Store ID:</b> <code>#{new_prod_id}</code>\n"
        f"🛍️ <b>Product:</b> {prod['name']}\n"
        f"📁 <b>Category:</b> {cat_name}\n"
        f"💰 <b>Supplier Cost:</b> <code>${cost:.2f} USDT</code>\n"
        f"💵 <b>Your Selling Price:</b> <code>${price:.2f} USDT</code>\n"
        f"📈 <b>Profit Margin:</b> <code>+${profit:.2f} USDT</code> per sale\n"
        f"⚡ <b>Delivery:</b> 100% Automated Instant Supplier API\n\n"
        f"✅ <i>This product is now live on @foxzen_bot for your customers!</i>",
        reply_markup=kb,
        parse_mode=ParseMode.HTML
    )

# --- Flow C: Add Stock to Existing Product ---
@admin_router.callback_query(F.data == "adm_add_stock_select")
async def cb_add_stock_select(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    products = await get_products()
    local_prods = [p for p in products if p.get("fulfillment_type") != "API"]
    
    if not local_prods:
        await callback.answer("No local products found. Add a local product first!", show_alert=True)
        return

    text = (
        f"📥 <b>Add Stock to Existing Product</b>\n\n"
        f"Select the product you want to add stock/keys to:"
    )
    buttons = []
    for p in local_prods:
        stock = p.get("in_stock", 0)
        label = f"{p['name'][:24]} ({stock} in stock)"
        buttons.append([InlineKeyboardButton(text=label, callback_data=f"adm_stock_for:{p['id']}")])
        
    buttons.append([InlineKeyboardButton(text="🔙 Back to Products", callback_data="adm_products")])
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode=ParseMode.HTML)
    await callback.answer()

@admin_router.callback_query(F.data.startswith("adm_stock_for:"))
async def cb_stock_for_prod(callback: CallbackQuery, state: FSMContext):
    pid = int(callback.data.replace("adm_stock_for:", ""))
    prod = await get_product(pid)
    if not prod:
        await callback.answer("Product not found!", show_alert=True)
        return

    await state.update_data(product_id=pid, product_name=prod["name"])
    await state.set_state(AddStockStates.waiting_for_stock_items)
    
    stock = prod.get("in_stock", 0)
    text = (
        f"📥 <b>Adding Stock for: {prod['name']}</b>\n"
        f"Current stock count: <code>{stock} items</code>\n\n"
        f"🔑 <b>Paste your accounts or license keys below (one per line):</b>\n\n"
        f"<i>Example:</i>\n"
        f"<code>email1:pass1\nemail2:pass2\nemail3:pass3</code>\n\n"
        f"<i>(Send /cancel to abort)</i>"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Cancel", callback_data="adm_cancel_fsm")]
    ])
    await callback.message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)
    await callback.answer()

@admin_router.message(AddStockStates.waiting_for_stock_items)
async def msg_add_stock_items(message: Message, state: FSMContext):
    raw = message.text.strip()
    lines = [line.strip() for line in raw.split("\n") if line.strip()]
    if not lines:
        await message.answer("⚠️ Please paste at least one valid line/account, or send /cancel.")
        return

    data = await state.get_data()
    pid = data.get("product_id")
    pname = data.get("product_name", "Product")
    
    added_count = await add_stock_items(pid, lines)
    prod = await get_product(pid)
    new_stock = prod.get("in_stock", 0) if prod else len(lines)
    
    await state.clear()
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📥 Add More Stock", callback_data="adm_add_stock_select")],
        [InlineKeyboardButton(text="📦 Products & Stock", callback_data="adm_products")],
        [InlineKeyboardButton(text="🏠 Admin Menu", callback_data="adm_menu")]
    ])
    
    await message.answer(
        f"🎉 <b>Stock Added Successfully!</b>\n\n"
        f"🛍️ <b>Product:</b> {pname}\n"
        f"➕ <b>Added:</b> <code>{added_count} new items</code>\n"
        f"📦 <b>Total Stock Now:</b> <code>{new_stock} items</code>\n\n"
        f"<i>Items are ready for immediate automatic delivery!</i>",
        reply_markup=kb,
        parse_mode=ParseMode.HTML
    )

# --- Flow D: View All Products & Delete ---
@admin_router.callback_query(F.data.startswith("adm_view_all_prods:"))
async def cb_view_all_prods(callback: CallbackQuery):
    page = int(callback.data.replace("adm_view_all_prods:", ""))
    products = await get_products()
    if not products:
        await callback.message.edit_text(
            "📦 <b>Store Products</b>\n\nNo products added yet.",
            reply_markup=products_menu_keyboard(),
            parse_mode=ParseMode.HTML
        )
        await callback.answer()
        return

    page_size = 6
    total_pages = (len(products) + page_size - 1) // page_size
    page = max(0, min(page, total_pages - 1))
    
    start_idx = page * page_size
    page_items = products[start_idx : start_idx + page_size]
    
    text = (
        f"📋 <b>All Store Products ({len(products)})</b>\n"
        f"<i>Tap any product to inspect details or delete:</i>"
    )
    
    buttons = []
    for p in page_items:
        mode_icon = "🔌" if p.get("fulfillment_type") == "API" else "📦"
        stock_text = "API" if p.get("fulfillment_type") == "API" else f"{p.get('in_stock', 0)} left"
        label = f"{mode_icon} #{p['id']} {p['name'][:18]} | ${p['price']} ({stock_text})"
        buttons.append([InlineKeyboardButton(text=label, callback_data=f"adm_prod_detail:{p['id']}")])
        
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(text="◀️ Prev", callback_data=f"adm_view_all_prods:{page - 1}"))
    nav_row.append(InlineKeyboardButton(text=f"📄 {page + 1}/{total_pages}", callback_data="adm_noop"))
    if page + 1 < total_pages:
        nav_row.append(InlineKeyboardButton(text="Next ▶️", callback_data=f"adm_view_all_prods:{page + 1}"))
    
    if nav_row:
        buttons.append(nav_row)
    buttons.append([InlineKeyboardButton(text="🔙 Back to Products Menu", callback_data="adm_products")])
    
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode=ParseMode.HTML)
    await callback.answer()

@admin_router.callback_query(F.data.startswith("adm_prod_detail:"))
async def cb_prod_detail(callback: CallbackQuery):
    pid = int(callback.data.replace("adm_prod_detail:", ""))
    prod = await get_product(pid)
    if not prod:
        await callback.answer("Product not found!", show_alert=True)
        return

    is_api = prod.get("fulfillment_type") == "API"
    type_str = "🔌 Supplier API (Instant Delivery)" if is_api else "📦 Local Stock (Uploaded Accounts)"
    stock_str = "⚡ Unlimited / Live API Stock" if is_api else f"<b>{prod.get('in_stock', 0)}</b> items available"
    prov_str = f"\n🏢 <b>Supplier:</b> {prod.get('provider_name', 'N/A')} (ID: <code>{prod.get('provider_product_id', 'N/A')}</code>)\n💰 <b>Wholesale Cost:</b> ${prod.get('provider_price', 0.0):.2f} USDT" if is_api else ""
    
    has_img = bool(prod.get("image_url") and prod.get("image_url").strip())
    img_status = "🖼️ <b>Banner:</b> Custom Photo / URL Set ✅" if has_img else "🖼️ <b>Banner:</b> Auto Brand Poster 🎨"

    text = (
        f"📦 <b>Product Details: #{prod['id']}</b>\n\n"
        f"🛍️ <b>Name:</b> {prod['name']}\n"
        f"📁 <b>Category:</b> {prod.get('category_name') or 'General'}\n"
        f"💵 <b>Selling Price:</b> <code>${prod['price']} USDT</code>\n"
        f"🏷️ <b>Fulfillment:</b> {type_str}\n"
        f"📊 <b>Stock Status:</b> {stock_str}\n"
        f"{img_status}"
        f"{prov_str}\n\n"
        f"📝 <b>Description:</b>\n<i>{prod.get('description') or 'None'}</i>"
    )
    
    buttons = []
    if not is_api:
        buttons.append([InlineKeyboardButton(text="📥 Add Stock Items", callback_data=f"adm_stock_for:{prod['id']}")])
    buttons.append([
        InlineKeyboardButton(text="🖼️ Set Banner / Photo", callback_data=f"adm_set_img:{prod['id']}")
    ])
    buttons.append([
        InlineKeyboardButton(text="🗑️ Delete Product", callback_data=f"adm_del_prod_confirm:{prod['id']}"),
        InlineKeyboardButton(text="🔙 Back to List", callback_data="adm_view_all_prods:0")
    ])
    
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode=ParseMode.HTML)
    await callback.answer()

@admin_router.callback_query(F.data.startswith("adm_set_img:"))
async def cb_admin_set_img(callback: CallbackQuery, state: FSMContext):
    pid = int(callback.data.replace("adm_set_img:", ""))
    prod = await get_product(pid)
    if not prod:
        await callback.answer("Product not found!", show_alert=True)
        return
        
    await state.set_state(AdminProductImageState.waiting_for_image)
    await state.update_data(product_id=pid)
    
    text = (
        f"🖼️ <b>Set Product Banner for: {prod['name']} (ID: #{pid})</b>\n\n"
        "Aap is product ke liye banner image set kar sakte hain:\n\n"
        "1. 📸 <b>Direct Photo bhejein:</b> Telegram chat me photo/image send karein.\n"
        "2. 🔗 <b>Image URL bhejein:</b> Direct web link paste karein (https://...).\n"
        "3. 🗑️ <b>Default par reset karein:</b> <code>/remove</code> likh kar bhejein.\n"
        "4. ❌ <b>Cancel karein:</b> <code>/cancel</code> likh kar bhejein."
    )
    buttons = [
        [InlineKeyboardButton(text="🔙 Cancel", callback_data=f"adm_prod_detail:{pid}")]
    ]
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode=ParseMode.HTML)
    await callback.answer()

@admin_router.message(AdminProductImageState.waiting_for_image, F.photo)
async def process_product_image_photo(message: Message, state: FSMContext):
    data = await state.get_data()
    pid = data.get("product_id")
    await state.clear()
    
    photo_file_id = message.photo[-1].file_id
    await set_product_image(pid, photo_file_id)
    prod = await get_product(pid)
    
    await message.answer(
        f"✅ <b>Product Banner Updated Successfully!</b>\n\n"
        f"Photo saved for <b>{prod['name'] if prod else f'Product #{pid}'}</b>.\n"
        f"Ab customer bot me is product par ye banner photo dikhegi!",
        parse_mode=ParseMode.HTML
    )

@admin_router.message(AdminProductImageState.waiting_for_image, F.text)
async def process_product_image_text(message: Message, state: FSMContext):
    text = message.text.strip()
    data = await state.get_data()
    pid = data.get("product_id")
    
    if text.lower() == "/cancel":
        await state.clear()
        await message.answer("❌ Cancelled.", parse_mode=ParseMode.HTML)
        return
        
    if text.lower() == "/remove":
        await state.clear()
        await set_product_image(pid, "")
        await message.answer("✅ <b>Custom image removed.</b> Ab automatic high-resolution brand banner use hoga!", parse_mode=ParseMode.HTML)
        return
        
    if text.startswith("http://") or text.startswith("https://"):
        await state.clear()
        await set_product_image(pid, text)
        prod = await get_product(pid)
        await message.answer(
            f"✅ <b>Image URL Saved!</b>\n\n"
            f"Banner set for <b>{prod['name'] if prod else f'Product #{pid}'}</b>:\n<code>{text}</code>",
            parse_mode=ParseMode.HTML
        )
        return
        
    await message.answer(
        "⚠️ Please send a <b>photo</b>, or a valid <b>https:// image URL</b>, or type <code>/remove</code> or <code>/cancel</code>.",
        parse_mode=ParseMode.HTML
    )

@admin_router.callback_query(F.data.startswith("adm_del_prod_confirm:"))
async def cb_del_prod_confirm(callback: CallbackQuery):
    pid = int(callback.data.replace("adm_del_prod_confirm:", ""))
    prod = await get_product(pid)
    if not prod:
        await callback.answer("Product not found!", show_alert=True)
        return

    text = (
        f"⚠️ <b>Confirm Product Deletion</b>\n\n"
        f"Are you sure you want to permanently delete <b>{prod['name']}</b> (ID: #{pid})?\n"
        f"This action cannot be undone."
    )
    buttons = [
        [
            InlineKeyboardButton(text="🔴 Yes, Delete", callback_data=f"adm_del_prod_do:{pid}"),
            InlineKeyboardButton(text="🔙 Cancel", callback_data=f"adm_prod_detail:{pid}")
        ]
    ]
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons), parse_mode=ParseMode.HTML)
    await callback.answer()

@admin_router.callback_query(F.data.startswith("adm_del_prod_do:"))
async def cb_del_prod_do(callback: CallbackQuery):
    pid = int(callback.data.replace("adm_del_prod_do:", ""))
    await delete_product(pid)
    await callback.answer("✅ Product deleted!", show_alert=True)
    
    text = await render_products_menu_text()
    await callback.message.edit_text(text, reply_markup=products_menu_keyboard(), parse_mode=ParseMode.HTML)

@admin_router.callback_query(F.data == "adm_noop")
async def cb_noop(callback: CallbackQuery):
    await callback.answer()

# --- 5. Users & Wallets ---
@admin_router.message(F.text == "/users")
async def cmd_admin_users_msg(message: Message):
    users = await get_all_users()
    total_balance = sum((u.get("balance") or 0.0) for u in users)
    
    text = (
        f"👥 <b>Customer Wallet Management</b>\n\n"
        f"Total Registered Users: <code>{len(users)}</code>\n"
        f"Total Wallet Balance in System: <code>${total_balance:.2f} USDT</code>\n\n"
        f"💡 <b>Quick Commands:</b>\n"
        f"• Add Balance: <code>/addbalance &lt;telegram_id&gt; &lt;amount&gt;</code>\n"
        f"  <i>Example:</i> <code>/addbalance 6443134339 5.00</code>\n\n"
        f"• Deduct Balance: <code>/deductbalance &lt;telegram_id&gt; &lt;amount&gt;</code>\n"
        f"• View User: <code>/user &lt;telegram_id&gt;</code>"
    )
    await message.answer(text, reply_markup=admin_back_keyboard(), parse_mode=ParseMode.HTML)

@admin_router.callback_query(F.data == "adm_users")
async def cb_admin_users(callback: CallbackQuery):
    users = await get_all_users()
    total_balance = sum((u.get("balance") or 0.0) for u in users)
    
    text = (
        f"👥 <b>Customer Wallet Management</b>\n\n"
        f"Total Registered Users: <code>{len(users)}</code>\n"
        f"Total Wallet Balance in System: <code>${total_balance:.2f} USDT</code>\n\n"
        f"💡 <b>Quick Commands:</b>\n"
        f"• Add Balance: <code>/addbalance &lt;telegram_id&gt; &lt;amount&gt;</code>\n"
        f"  <i>Example:</i> <code>/addbalance 6443134339 5.00</code>\n\n"
        f"• Deduct Balance: <code>/deductbalance &lt;telegram_id&gt; &lt;amount&gt;</code>\n"
        f"• View User: <code>/user &lt;telegram_id&gt;</code>"
    )
    await callback.message.edit_text(text, reply_markup=admin_back_keyboard(), parse_mode=ParseMode.HTML)
    await callback.answer()

@admin_router.message(F.text.startswith("/addbalance"))
async def cmd_addbalance(message: Message):
    parts = message.text.strip().split()
    if len(parts) != 3:
        await message.answer("⚠️ Usage: <code>/addbalance &lt;user_id&gt; &lt;amount&gt;</code>\nExample: <code>/addbalance 123456789 5.00</code>", parse_mode=ParseMode.HTML)
        return
    try:
        target_id = int(parts[1])
        amount = float(parts[2])
    except ValueError:
        await message.answer("❌ Invalid User ID or Amount format.", parse_mode=ParseMode.HTML)
        return

    new_bal = await update_user_balance(target_id, amount)
    await message.answer(f"✅ Successfully credited <b>${amount:.2f} USDT</b> to User <code>{target_id}</code>!\nNew Balance: <b>${new_bal:.2f} USDT</b>", parse_mode=ParseMode.HTML)
    
    # Notify customer
    await send_user_notification(
        target_id,
        f"🎉 <b>Wallet Balance Credited!</b>\n\n"
        f"💰 Added: <code>+${amount:.2f} USDT</code>\n"
        f"💳 Total Balance: <b>${new_bal:.2f} USDT</b>\n\n"
        f"<i>You can use this balance to purchase any product in the store!</i>"
    )

@admin_router.message(F.text.startswith("/deductbalance"))
async def cmd_deductbalance(message: Message):
    parts = message.text.strip().split()
    if len(parts) != 3:
        await message.answer("⚠️ Usage: <code>/deductbalance &lt;user_id&gt; &lt;amount&gt;</code>", parse_mode=ParseMode.HTML)
        return
    try:
        target_id = int(parts[1])
        amount = float(parts[2])
    except ValueError:
        await message.answer("❌ Invalid format.", parse_mode=ParseMode.HTML)
        return

    new_bal = await update_user_balance(target_id, -amount)
    await message.answer(f"✅ Deducted <b>${amount:.2f} USDT</b> from User <code>{target_id}</code>.\nNew Balance: <b>${new_bal:.2f} USDT</b>", parse_mode=ParseMode.HTML)

@admin_router.message(F.text.startswith("/user"))
async def cmd_view_user(message: Message):
    parts = message.text.strip().split()
    if len(parts) != 2:
        await message.answer("⚠️ Usage: <code>/user &lt;telegram_id&gt;</code>", parse_mode=ParseMode.HTML)
        return
    try:
        target_id = int(parts[1])
    except ValueError:
        await message.answer("❌ Invalid ID.", parse_mode=ParseMode.HTML)
        return

    profile = await get_user_profile(target_id)
    if not profile:
        await message.answer(f"User <code>{target_id}</code> not found in database.", parse_mode=ParseMode.HTML)
        return

    text = (
        f"👤 <b>Customer Profile:</b>\n"
        f"• ID: <code>{target_id}</code>\n"
        f"• Username: @{profile.get('username') or 'N/A'}\n"
        f"• Name: {profile.get('first_name', '')} {profile.get('last_name', '')}\n"
        f"• Wallet Balance: <b>${profile.get('balance', 0.0):.2f} USDT</b>\n"
        f"• Joined: {profile.get('created_at', 'N/A')}\n\n"
        f"<i>To credit funds:</i> <code>/addbalance {target_id} 5.00</code>"
    )
    await message.answer(text, parse_mode=ParseMode.HTML)

# --- 6. Broadcast Tool ---
@admin_router.callback_query(F.data == "adm_broadcast_prompt")
async def cb_admin_broadcast_prompt(callback: CallbackQuery):
    text = (
        f"📢 <b>Instant Store Broadcast</b>\n\n"
        f"You can send an announcement to all registered customers right from here!\n\n"
        f"<b>Command Format:</b>\n"
        f"<code>/broadcast Your message goes here...</code>\n\n"
        f"<i>Example:</i>\n"
        f"<code>/broadcast 🔥 Mega Sale! Flat 20% off on all Netflix & VPN accounts today only!</code>\n\n"
        f"HTML tags like <code>&lt;b&gt;bold&lt;/b&gt;</code> are supported."
    )
    await callback.message.edit_text(text, reply_markup=admin_back_keyboard(), parse_mode=ParseMode.HTML)
    await callback.answer()

@admin_router.message(F.text.startswith("/broadcast"))
async def cmd_broadcast(message: Message):
    text_to_send = message.text.replace("/broadcast", "", 1).strip()
    if not text_to_send:
        await message.answer("⚠️ Please provide text after /broadcast.\nExample: <code>/broadcast Hello all customers!</code>", parse_mode=ParseMode.HTML)
        return

    users = await get_all_user_ids()
    status_msg = await message.answer(f"📢 Starting broadcast to <b>{len(users)} users</b>...", parse_mode=ParseMode.HTML)
    
    sent_count = 0
    fail_count = 0
    for uid in users:
        success = await send_user_notification(uid, text_to_send)
        if success:
            sent_count += 1
        else:
            fail_count += 1
        await asyncio.sleep(0.04) # Rate limit protection

    await status_msg.edit_text(
        f"🎉 <b>Broadcast Finished!</b>\n\n"
        f"✅ Delivered: <b>{sent_count} users</b>\n"
        f"❌ Failed/Blocked: <b>{fail_count} users</b>",
        parse_mode=ParseMode.HTML
    )

# --- Real-Time Push Notification Engine ---
async def send_admin_alert(text: str, reply_markup: Optional[InlineKeyboardMarkup] = None):
    """Dispatches real-time push alert directly to Admin via @foxzenadmin_bot"""
    global admin_bot
    if not admin_bot:
        return
    for admin_id in ALLOWED_ADMIN_IDS:
        try:
            await admin_bot.send_message(
                chat_id=admin_id,
                text=text,
                reply_markup=reply_markup,
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            logger.error(f"Failed to send admin push alert to {admin_id}: {e}")

# --- Admin Bot Lifecycle ---
def init_admin_bot(token: str):
    global admin_bot, admin_dp
    if not token or not token.strip():
        logger.warning("No ADMIN_BOT_TOKEN provided. Admin Bot is disabled.")
        return None, None
        
    admin_bot = Bot(
        token=token.strip(),
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    admin_dp = Dispatcher(storage=MemoryStorage())
    admin_dp.message.middleware(AdminWhitelistMiddleware())
    admin_dp.callback_query.middleware(AdminWhitelistMiddleware())
    admin_dp.include_router(admin_router)
    return admin_bot, admin_dp

def get_admin_bot() -> Optional[Bot]:
    return admin_bot
