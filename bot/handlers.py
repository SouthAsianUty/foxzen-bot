import random
import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from database import (
    save_or_update_user,
    get_user_profile,
    get_user_balance,
    get_categories,
    get_category,
    get_products,
    get_product,
    create_order,
    get_order,
    get_active_order_for_user,
    get_user_orders,
    submit_order_tx_id,
    is_txid_used,
    complete_order,
    cancel_order,
    cancel_unpaid_orders_for_user,
    pop_available_stock,
    fulfill_order_and_get_stock,
    execute_wallet_purchase,
    create_and_pay_wallet_order,
    get_setting
)
from binance import verify_binance_pay_transaction
from bot.keyboards import (
    main_reply_keyboard,
    main_inline_menu,
    wallet_keyboard,
    profile_keyboard,
    referral_keyboard,
    back_to_home_keyboard,
    support_keyboard,
    reseller_keyboard,
    shop_menu_keyboard,
    categories_keyboard,
    products_keyboard,
    product_detail_keyboard,
    order_actions_keyboard,
    wallet_deposit_keyboard,
    empty_orders_keyboard,
    my_orders_keyboard,
    single_order_view_keyboard,
    confirm_wallet_buy_keyboard,
    confirm_wallet_payorder_keyboard,
    insufficient_wallet_keyboard,
    delivery_success_keyboard,
    quantity_selection_keyboard,
    payment_selection_keyboard,
    custom_quantity_keyboard
)
from bot.bot_instance import notify_admin

logger = logging.getLogger(__name__)
router = Router()

class OrderState(StatesGroup):
    waiting_for_txid = State()
    waiting_for_quantity = State()

BOT_USERNAME = "foxzen_bot"

async def build_welcome_text(user_id: int, bot_username: str = BOT_USERNAME) -> str:
    """Builds the exact welcome card matching the design in user screenshot"""
    profile = await get_user_profile(user_id)
    username_display = f"@{profile['username']}" if profile['username'] else "None"
    
    text = (
        "🅵 🅾 🆇 🆉 🅴 🅽\n\n"
        f"👋 Welcome back, <b>{profile['first_name']}</b>!\n"
        "<i>Quality products at cheapest rates</i>\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🏷️ Username: {username_display}\n"
        f"🆔 UserID: <code>{profile['telegram_id']}</code>\n"
        f"👑 Membership: {profile['membership']}\n"
        f"💰 Balance: ${profile['balance']:.2f}\n"
        f"💎 Total Spent: ${profile['total_spent']:.2f}\n"
        f"🤝 Referrals: {profile['referrals_count']}\n"
        f"💸 Referral Earning: ${profile['referral_earnings']:.2f}\n"
        f"🔗 Referral Link: https://t.me/{bot_username}?start=ref_{profile['telegram_id']}\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "<i>Choose an option below to get started.</i>"
    )
    return text

# --- Helper function for delivery ---
async def deliver_order_to_user(message_or_query, order: dict, stock_data: str, bot):
    qty = int(order.get("quantity") or 1)
    qty_str = f"🔢 <b>Quantity:</b> <code>{qty}x</code>\n" if qty > 1 else ""
    delivery_text = (
        f"🎉 <b>Payment Verified Successfully!</b>\n\n"
        f"Order ID: <b>#{order['order_id']}</b>\n"
        f"Product: <b>{order['product_name']}</b>\n"
        f"{qty_str}\n"
        f"🔑 <b>Your Login Details / Product Key:</b>\n"
        f"<code>{stock_data}</code>\n\n"
        f"📋 <b>Instructions & Warranty:</b>\n"
        f"<i>Please keep your credentials safe. If you need any assistance, contact our support team.</i>\n\n"
        f"Thank you for your purchase!"
    )
    user_id = order["telegram_id"]
    try:
        await bot.send_message(
            chat_id=user_id,
            text=delivery_text,
            reply_markup=single_order_view_keyboard(order["order_id"], "COMPLETED")
        )
    except Exception as e:
        logger.error(f"Error sending delivery to user {user_id}: {e}")

# --- /start Command (with Referral support) ---
@router.message(CommandStart())
async def handle_start(message: Message, state: FSMContext):
    await state.clear()
    user = message.from_user
    
    # Check referral code in /start ref_123456
    referred_by = None
    args = message.text.split()
    if len(args) > 1 and args[1].startswith("ref_"):
        try:
            referred_by = int(args[1].replace("ref_", ""))
        except ValueError:
            referred_by = None

    await save_or_update_user(user.id, user.username, user.first_name, referred_by=referred_by)
    
    # Get bot username if available
    bot_info = await message.bot.get_me()
    bot_username = bot_info.username or BOT_USERNAME
    
    welcome_text = await build_welcome_text(user.id, bot_username)
    channel_link = await get_setting("channel_link", "https://t.me/Foxzenreseller") or "https://t.me/Foxzenreseller"

    await message.answer(
        text=welcome_text,
        reply_markup=main_inline_menu(channel_url=channel_link)
    )

# --- Reply Keyboard Text & Command Triggers ---
@router.message(Command("shop"))
@router.message(F.text == "🛍️ SHOP")
async def text_shop(message: Message):
    text = (
        "🛍️ <b>Foxzen Digital Store</b>\n\n"
        "Select an option below to browse our shop:\n\n"
        "• <b>🛒 View All Products:</b> View all items in 1-tap\n"
        "• <b>📂 Categories Wise:</b> Browse items organized by category"
    )
    await message.answer(text, reply_markup=shop_menu_keyboard())

@router.message(Command("wallet"))
@router.message(F.text.in_(["💱 Wallet", "👛 Wallet"]))
async def text_wallet(message: Message):
    profile = await get_user_profile(message.from_user.id)
    text = (
        "💱 <b>My Wallet & Balance</b>\n\n"
        f"💰 Available Balance: <b>${profile['balance']:.2f} USDT</b>\n"
        f"💎 Total Spent: <b>${profile['total_spent']:.2f} USDT</b>\n"
        f"👑 Membership Tier: <b>{profile['membership']}</b>\n\n"
        "You can purchase products directly with Binance Pay, or top up your account balance below:"
    )
    await message.answer(text, reply_markup=wallet_keyboard())

@router.message(Command("orders"))
@router.message(F.text.in_(["📦 My Orders", "📦 Orders", "📦 Purchase History"]))
async def cmd_orders(message: Message):
    orders = await get_user_orders(message.from_user.id, status="COMPLETED")
    if not orders:
        await message.answer(
            "📦 <b>Purchase History</b>\n\n"
            "You haven't made any completed purchases yet.\n"
            "Browse our shop to purchase products with instant delivery!",
            reply_markup=empty_orders_keyboard()
        )
        return
    await message.answer(
        "📦 <b>Your Purchase History:</b>\nTap any completed order below to view product details and credentials:",
        reply_markup=my_orders_keyboard(orders)
    )

@router.message(Command("profile"))
@router.message(F.text == "😃 Profile")
async def text_profile(message: Message):
    profile = await get_user_profile(message.from_user.id)
    text = (
        "😃 <b>Customer Profile</b>\n\n"
        f"👤 Name: <b>{profile['first_name']}</b>\n"
        f"🏷️ Username: @{profile['username'] or 'None'}\n"
        f"🆔 User ID: <code>{profile['telegram_id']}</code>\n"
        f"👑 Membership: <b>{profile['membership']}</b>\n"
        f"💰 Balance: <b>${profile['balance']:.2f} USDT</b>\n"
        f"💎 Total Spent: <b>${profile['total_spent']:.2f} USDT</b>\n"
        f"🤝 Referrals: <b>{profile['referrals_count']} users</b>\n"
        f"💸 Referral Earnings: <b>${profile['referral_earnings']:.2f} USDT</b>\n"
        f"📅 Registered: <b>{profile['joined_at'][:10] if profile['joined_at'] else 'Recent'}</b>"
    )
    await message.answer(text, reply_markup=profile_keyboard())

async def render_referral_store_text(user_id: int, bot_username: str = BOT_USERNAME) -> str:
    profile = await get_user_profile(user_id)
    ref_link = f"https://t.me/{bot_username}?start=ref_{profile['telegram_id']}"
    code = str(profile['telegram_id'])
    referrals = profile['referrals_count']
    credits_count = referrals

    text = (
        "━━━━━━━━━━━━━━━━━━\n"
        "🎯  <b>REFERRAL STORE</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "<b>How it works</b>\n"
        "──────────────\n"
        "• Invite a brand-new member with your link — each one earns you 1 credit.\n"
        "• The credit lands once your friend opens the shop and views a product.\n"
        "• Up to 10 invites per day are counted — extra invites that day are skipped.\n"
        "• Spend credits on the rewards below, or redeem them to your wallet.\n\n"
        "🔗  <b>Your Referral Link</b>\n"
        f"<code>{ref_link}</code>\n\n"
        "🎟  <b>Your Code</b>\n"
        f"<code>{code}</code>\n\n"
        f"👥  <b>Referrals:</b>  {referrals}\n"
        f"🎯  <b>Your Credits:</b>  {credits_count}\n\n"
        "🎁 <b>Special Offer:</b>\n"
        "if i get 6 invite from your link you get 1 months surfshark vpn free\n"
        "<i>you get vpn throug support</i>"
    )
    return text

@router.message(Command("referral"))
@router.message(F.text == "🎯 Referral Store")
async def cmd_referral(message: Message):
    bot_info = await message.bot.get_me()
    bot_username = bot_info.username or BOT_USERNAME
    support_link = await get_setting("support_link", "@admin")
    text = await render_referral_store_text(message.from_user.id, bot_username)
    await message.answer(
        text=text,
        reply_markup=referral_keyboard(message.from_user.id, bot_username, support_link)
    )

@router.message(Command("support"))
@router.message(F.text == "🎧 Support")
async def text_support(message: Message):
    support_link = await get_setting("support_link", "@foxzen_Digital")
    text = (
        "🎧 <b>Customer Support 24/7</b>\n\n"
        "Need assistance with an order, replacement warranty, or custom request?\n"
        f"Our support team is ready to help: <b>{support_link}</b>\n\n"
        "👉 Tap the button below to message our support directly:"
    )
    await message.answer(text, reply_markup=support_keyboard(support_link))

@router.message(Command("help"))
@router.message(F.text == "❓ Help")
async def text_help(message: Message):
    pay_id = await get_setting("binance_pay_id", "Not configured")
    text = (
        "❓ <b>Foxzen Bot Help & FAQ</b>\n\n"
        "<b>1️⃣ How to Buy:</b>\n"
        "Click 🛍️ <b>SHOP</b>, choose your category and product, then tap <b>Buy Now</b>.\n\n"
        "<b>2️⃣ How to Pay via Binance:</b>\n"
        f"Transfer USDT via Binance Pay to Pay ID: <code>{pay_id}</code> (Name: <b>User-c034c</b>). Put your Order ID in remarks, then submit your Binance TxID in the bot.\n\n"
        "<b>3️⃣ Instant Delivery:</b>\n"
        "The bot automatically delivers login accounts / keys right into your chat!\n\n"
        "<b>4️⃣ Warranty & Replacement:</b>\n"
        "All accounts include warranty coverage. If you ever have questions, contact 🎧 <b>Support</b>."
    )
    await message.answer(text, reply_markup=back_to_home_keyboard())

# --- Navigation Callbacks ---
@router.callback_query(F.data == "nav_home")
async def cb_home(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    bot_info = await callback.bot.get_me()
    bot_username = bot_info.username or BOT_USERNAME
    welcome_text = await build_welcome_text(callback.from_user.id, bot_username)
    channel_link = await get_setting("channel_link", "https://t.me/Foxzenreseller") or "https://t.me/Foxzenreseller"
    
    try:
        await callback.message.edit_text(
            text=welcome_text,
            reply_markup=main_inline_menu(channel_url=channel_link)
        )
    except Exception:
        await callback.message.answer(
            text=welcome_text,
            reply_markup=main_inline_menu(channel_url=channel_link)
        )
    await callback.answer()

@router.callback_query(F.data == "nav_products")
async def cb_products(callback: CallbackQuery):
    text = (
        "🛍️ <b>Foxzen Digital Store</b>\n\n"
        "Select an option below to browse our shop:\n\n"
        "• <b>🛒 View All Products:</b> View all items in 1-tap\n"
        "• <b>📂 Categories Wise:</b> Browse items organized by category"
    )
    await callback.message.edit_text(text, reply_markup=shop_menu_keyboard())
    await callback.answer()

@router.callback_query(F.data == "nav_categories")
async def cb_categories(callback: CallbackQuery):
    cats = await get_categories()
    uncat_products = await get_products(category_id=0, active_only=True)
    if not cats and not uncat_products:
        products = await get_products(active_only=True)
        await callback.message.edit_text("🛒 <b>Available Products:</b>", reply_markup=products_keyboard(products))
        await callback.answer()
        return

    text = (
        "📂 <b>Product Categories</b>\n\n"
        "Select a category below to view products with instant delivery:"
    )
    await callback.message.edit_text(text, reply_markup=categories_keyboard(cats, has_uncategorized=bool(uncat_products)))
    await callback.answer()

@router.callback_query(F.data == "nav_wallet")
async def cb_wallet(callback: CallbackQuery):
    profile = await get_user_profile(callback.from_user.id)
    text = (
        "💱 <b>My Wallet & Balance</b>\n\n"
        f"💰 Available Balance: <b>${profile['balance']:.2f} USDT</b>\n"
        f"💎 Total Spent: <b>${profile['total_spent']:.2f} USDT</b>\n"
        f"👑 Membership Tier: <b>{profile['membership']}</b>\n\n"
        "Pay per order directly via Binance Pay, or top up your wallet balance below:"
    )
    await callback.message.edit_text(text, reply_markup=wallet_keyboard())
    await callback.answer()

@router.callback_query(F.data == "wallet_deposit")
async def cb_wallet_deposit(callback: CallbackQuery):
    pay_id = await get_setting("binance_pay_id", "717053382")
    text = (
        "💳 <b>Deposit Funds via Binance Pay</b>\n\n"
        "1. Choose <b>Binance Pay</b>, not an on-chain withdrawal.\n"
        "2. Send any USDT amount to our Binance Pay ID / UID:\n"
        f"   👉 <code>{pay_id}</code> (Name: <b>User-c034c</b>)\n"
        "3. Copy the full Pay Transaction / Order ID from your receipt.\n"
        "4. Paste your TxID in this chat or send to 🎧 Support to credit balance!\n\n"
        "👇 <i>Tap the button below to copy Binance ID in 1-tap:</i>"
    )
    await callback.message.edit_text(text, reply_markup=wallet_deposit_keyboard(pay_id))
    await callback.answer()

@router.message(Command("freebies"))
@router.message(F.text == "🎁 Freebies")
async def cmd_freebies(message: Message):
    bot_info = await message.bot.get_me()
    bot_username = bot_info.username or BOT_USERNAME
    support_link = await get_setting("support_link", "@foxzen_Digital")
    text = await render_referral_store_text(message.from_user.id, bot_username)
    await message.answer(
        text=text,
        reply_markup=referral_keyboard(message.from_user.id, bot_username, support_link)
    )

@router.callback_query(F.data == "nav_freebies")
async def cb_freebies(callback: CallbackQuery):
    bot_info = await callback.bot.get_me()
    bot_username = bot_info.username or BOT_USERNAME
    support_link = await get_setting("support_link", "@foxzen_Digital")
    text = await render_referral_store_text(callback.from_user.id, bot_username)
    await callback.message.edit_text(
        text=text,
        reply_markup=referral_keyboard(callback.from_user.id, bot_username, support_link)
    )
    await callback.answer()

@router.callback_query(F.data == "nav_profile")
async def cb_profile(callback: CallbackQuery):
    profile = await get_user_profile(callback.from_user.id)
    text = (
        "😃 <b>Customer Profile</b>\n\n"
        f"👤 Name: <b>{profile['first_name']}</b>\n"
        f"🏷️ Username: @{profile['username'] or 'None'}\n"
        f"🆔 User ID: <code>{profile['telegram_id']}</code>\n"
        f"👑 Membership: <b>{profile['membership']}</b>\n"
        f"💰 Balance: <b>${profile['balance']:.2f} USDT</b>\n"
        f"💎 Total Spent: <b>${profile['total_spent']:.2f} USDT</b>\n"
        f"🤝 Referrals: <b>{profile['referrals_count']} users</b>\n"
        f"💸 Referral Earnings: <b>${profile['referral_earnings']:.2f} USDT</b>\n"
        f"📅 Registered: <b>{profile['joined_at'][:10] if profile['joined_at'] else 'Recent'}</b>"
    )
    await callback.message.edit_text(text, reply_markup=profile_keyboard())
    await callback.answer()

@router.callback_query(F.data == "nav_referral")
async def cb_referral(callback: CallbackQuery):
    bot_info = await callback.bot.get_me()
    bot_username = bot_info.username or BOT_USERNAME
    support_link = await get_setting("support_link", "@admin")
    text = await render_referral_store_text(callback.from_user.id, bot_username)
    await callback.message.edit_text(
        text=text,
        reply_markup=referral_keyboard(callback.from_user.id, bot_username, support_link)
    )
    await callback.answer()

@router.callback_query(F.data == "claim_surfshark")
async def cb_claim_surfshark(callback: CallbackQuery):
    profile = await get_user_profile(callback.from_user.id)
    support_link = await get_setting("support_link", "@foxzen_Digital")
    referrals = profile['referrals_count']
    
    if referrals >= 6:
        msg = (
            f"🎉 <b>6 Invites Completed!</b>\n\n"
            f"You have <b>{referrals} referrals</b> and have unlocked <b>1 Month Surfshark VPN Free</b>!\n\n"
            f"Please message support with your User Code <code>{profile['telegram_id']}</code> to claim your account:\n"
            f"👉 <b>Support:</b> {support_link}"
        )
        await callback.message.edit_text(msg, reply_markup=support_keyboard(support_link))
        await callback.answer("🎉 Reward Unlocked!", show_alert=True)
        
        await notify_admin(
            f"🎁 <b>Surfshark VPN Reward Eligible!</b>\n"
            f"User: @{callback.from_user.username or 'N/A'} (ID: <code>{callback.from_user.id}</code>)\n"
            f"Referrals: {referrals}/6 invites! Ready to receive Surfshark VPN."
        )
    else:
        needed = 6 - referrals
        await callback.answer(
            f"⚠️ You currently have {referrals}/6 invites.\nInvite {needed} more friend(s) to unlock 1 Month Surfshark VPN free!",
            show_alert=True
        )

@router.callback_query(F.data == "nav_support")
async def cb_support(callback: CallbackQuery):
    support_link = await get_setting("support_link", "@foxzen_Digital")
    text = (
        "🎧 <b>Customer Support 24/7</b>\n\n"
        "Need assistance with an order, replacement warranty, or custom request?\n"
        f"Our support team is ready to help: <b>{support_link}</b>\n\n"
        "👉 Tap the button below to message our support directly:"
    )
    await callback.message.edit_text(text, reply_markup=support_keyboard(support_link))
    await callback.answer()

@router.callback_query(F.data == "nav_help")
async def cb_help(callback: CallbackQuery):
    pay_id = await get_setting("binance_pay_id", "Not configured")
    text = (
        "❓ <b>Foxzen Bot Help & FAQ</b>\n\n"
        "<b>1️⃣ How to Buy:</b>\n"
        "Click 🛍️ <b>SHOP</b>, choose your category and product, then tap <b>Buy Now</b>.\n\n"
        "<b>2️⃣ How to Pay via Binance:</b>\n"
        f"Transfer USDT via Binance Pay to Pay ID: <code>{pay_id}</code> (Name: <b>User-c034c</b>). Put your Order ID in remarks, then submit your Binance TxID in the bot.\n\n"
        "<b>3️⃣ Instant Delivery:</b>\n"
        "The bot automatically delivers login accounts / keys right into your chat!\n\n"
        "<b>4️⃣ Warranty & Replacement:</b>\n"
        "All accounts include warranty coverage. If you ever have questions, contact 🎧 <b>Support</b>."
    )
    await callback.message.edit_text(text, reply_markup=back_to_home_keyboard())
    await callback.answer()

@router.message(Command("channel"))
async def cmd_channel(message: Message):
    text = (
        "📢 <b>Foxzen Official Reseller Channel</b>\n\n"
        "Join our exclusive Telegram channel: <b>@Foxzenreseller</b>\n\n"
        "✨ Exclusive wholesale discounts\n"
        "📦 Daily restock & new digital products\n"
        "⚡ Flash sales & gift vouchers\n"
        "💼 Reseller API & bulk account supply\n\n"
        "👉 Tap below to join our channel directly:"
    )
    await message.answer(text, reply_markup=reseller_keyboard())

@router.callback_query(F.data == "nav_reseller")
async def cb_reseller(callback: CallbackQuery):
    support_link = await get_setting("support_link", "@admin")
    text = (
        "👥 <b>Foxzen Reseller & Wholesale Program</b>\n\n"
        "Are you a bulk reseller or looking to integrate accounts into your own store?\n\n"
        "We offer:\n"
        "✅ Special wholesale tier pricing\n"
        "✅ Priority stock reserves & bulk accounts\n"
        "✅ Automated REST API delivery\n"
        "✅ 24/7 dedicated reseller support\n\n"
        "📢 <b>Official Channel:</b> @Foxzenreseller\n"
        f"💼 <b>Management Contact:</b> {support_link}\n\n"
        "👉 Tap below to join our official reseller channel:"
    )
    await callback.message.edit_text(text, reply_markup=reseller_keyboard())
    await callback.answer()

@router.callback_query(F.data == "nav_clearchat")
async def cb_clearchat(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    try:
        await callback.message.delete()
    except Exception:
        pass
    
    bot_info = await callback.bot.get_me()
    bot_username = bot_info.username or BOT_USERNAME
    welcome_text = await build_welcome_text(callback.from_user.id, bot_username)
    channel_link = await get_setting("channel_link", "https://t.me/Foxzenreseller") or "https://t.me/Foxzenreseller"
    
    await callback.message.answer(
        text=welcome_text,
        reply_markup=main_inline_menu(channel_url=channel_link)
    )
    await callback.answer("Chat refreshed!")

# --- Product Browsing ---
@router.callback_query(F.data == "cat_all")
async def cb_cat_all(callback: CallbackQuery):
    products = await get_products(active_only=True)
    if not products:
        await callback.message.edit_text("⚠️ No products available right now.", reply_markup=back_to_home_keyboard())
        return
    text = (
        "🛒 <b>All Available Products:</b>\n\n"
        "Select any product below to view details and purchase with Instant Delivery:"
    )
    await callback.message.edit_text(text, reply_markup=products_keyboard(products))
    await callback.answer()

@router.callback_query(F.data.startswith("cat_"))
async def cb_category_filter(callback: CallbackQuery):
    cat_id_raw = callback.data.replace("cat_", "")
    if cat_id_raw == "all":
        return
    try:
        cat_id = int(cat_id_raw)
    except ValueError:
        return

    if cat_id == 0:
        cat_name = "Direct / Other Products"
        cat_icon = "📦"
    else:
        cat = await get_category(cat_id)
        cat_name = cat.get("name", "Category") if cat else "Category"
        cat_icon = cat.get("icon", "📁") if cat else "📁"

    products = await get_products(category_id=cat_id, active_only=True)
    if not products:
        text = (
            f"{cat_icon} <b>{cat_name}</b>\n\n"
            "⚠️ No products are currently available in this category.\n"
            "Please check other categories or tap View All Products!"
        )
        buttons = [
            [InlineKeyboardButton(text="🛒 View All Products", callback_data="cat_all", style="success")],
            [InlineKeyboardButton(text="📂 Categories Wise", callback_data="nav_categories", style="primary")],
            [
                InlineKeyboardButton(text="⬅️ Back", callback_data="nav_categories"),
                InlineKeyboardButton(text="🏠 Main Menu", callback_data="nav_home")
            ]
        ]
        await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
        await callback.answer()
        return

    text = (
        f"{cat_icon} <b>{cat_name}</b>\n\n"
        "Select a product below to view details and purchase with Instant Delivery:"
    )
    await callback.message.edit_text(text, reply_markup=products_keyboard(products, category_name=cat_name))
    await callback.answer()

@router.callback_query(F.data.startswith("prod_"))
async def cb_product_detail(callback: CallbackQuery):
    p_id = int(callback.data.replace("prod_", ""))
    p = await get_product(p_id)
    if not p:
        await callback.answer("Product not found!", show_alert=True)
        return
    
    stock_status = f"✅ In Stock: <b>{p['in_stock']} available</b>" if p['in_stock'] > 0 else "❌ <b>Currently Out of Stock</b>"
    desc = p.get('description', '')
    instructions = p.get('delivery_instructions', '')
    
    text = (
        f"🏷️ <b>{p['name']}</b>\n"
        f"📁 Category: {p.get('category_name') or 'General'}\n"
        f"💵 Price: <b>${p['price']} USDT</b>\n"
        f"{stock_status}\n\n"
        f"📝 <b>Description:</b>\n{desc}\n\n"
    )
    if instructions:
        text += f"ℹ️ <b>Note / Warranty:</b>\n{instructions}\n"
        
    await callback.message.edit_text(text, reply_markup=product_detail_keyboard(p))
    await callback.answer()

@router.callback_query(F.data.startswith("out_of_stock_"))
async def cb_out_of_stock(callback: CallbackQuery):
    await callback.answer("This product is currently out of stock. Please check back later or contact support!", show_alert=True)

# --- Quantity Selection Flow (Matches Reference UI) ---
def render_quantity_prompt_text(product: dict) -> str:
    unit_price = float(product["price"])
    in_stock = int(product.get("in_stock", 0))
    desc = product.get("description", "").strip()
    desc_part = f"📝 <i>{desc}</i>\n\n" if desc else ""
    return (
        f"🛍️ <b>{product['name']}</b>\n\n"
        f"{desc_part}"
        f"💵 <b>Price per item:</b> <code>${unit_price:.2f} USDT</code>\n"
        f"📦 <b>In Stock:</b> <code>{in_stock} available</code>\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🟡 <b>Select Quantity:</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👉 <i>Choose <b>🔵 1</b>, <b>🟡 All</b>, or tap <b>🔵 Custom Quantity</b> below:</i>"
    )

def render_payment_prompt_text(product: dict, quantity: int) -> str:
    unit_price = float(product["price"])
    total_amount = round(unit_price * quantity, 2)
    in_stock = int(product.get("in_stock", 0))
    return (
        f"🛍️ <b>Order Checkout: {product['name']}</b>\n\n"
        f"🔢 <b>Selected Quantity:</b> <code>{quantity}x</code>\n"
        f"💵 <b>Unit Price:</b> <code>${unit_price:.2f} USDT</code>\n"
        f"📦 <b>Stock Remaining:</b> <code>{in_stock}</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💰 <b>Total Payable:</b> <code>${total_amount:.2f} USDT</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🟡 <b>Select Payment Method:</b>\n"
        f"🔵 <b>Wallet Balance:</b> Instant delivery\n"
        f"🟡 <b>Binance Pay:</b> Pay via Binance Pay ID\n\n"
        f"💳 <i>Choose your payment method below to complete your order:</i>"
    )

@router.callback_query(F.data.startswith("selectqty_") | (F.data == "noop_qty"))
async def cb_select_quantity_menu(callback: CallbackQuery, state: FSMContext):
    if callback.data == "noop_qty":
        await callback.answer("Please select 1, All, or Custom Quantity below 👇", show_alert=False)
        return
        
    await state.clear()
    parts = callback.data.split("_")
    try:
        p_id = int(parts[1])
    except (IndexError, ValueError):
        await callback.answer("Invalid product.", show_alert=True)
        return
        
    p = await get_product(p_id)
    if not p:
        await callback.answer("Product not found!", show_alert=True)
        return
        
    in_stock = int(p.get("in_stock", 0))
    if in_stock <= 0:
        await callback.answer("Sorry, this item is out of stock!", show_alert=True)
        return
        
    text = render_quantity_prompt_text(p)
    kb = quantity_selection_keyboard(p)
    
    try:
        await callback.message.edit_text(text, reply_markup=kb)
    except Exception:
        pass
    await callback.answer()

@router.callback_query(F.data.startswith("pickqty_"))
async def cb_pick_quantity(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    parts = callback.data.replace("pickqty_", "").split("_")
    try:
        p_id = int(parts[0])
        qty = int(parts[1])
    except (IndexError, ValueError):
        await callback.answer("Invalid quantity.", show_alert=True)
        return
        
    p = await get_product(p_id)
    if not p:
        await callback.answer("Product not found!", show_alert=True)
        return
        
    in_stock = int(p.get("in_stock", 0))
    if in_stock <= 0:
        await callback.answer("Sorry, this item is out of stock!", show_alert=True)
        return
        
    qty = max(1, min(in_stock, qty))
    text = render_payment_prompt_text(p, qty)
    kb = payment_selection_keyboard(p, qty)
    
    try:
        await callback.message.edit_text(text, reply_markup=kb)
    except Exception:
        pass
    await callback.answer()

@router.callback_query(F.data.startswith("customqty_"))
async def cb_custom_quantity(callback: CallbackQuery, state: FSMContext):
    p_id_str = callback.data.replace("customqty_", "")
    try:
        p_id = int(p_id_str)
    except ValueError:
        await callback.answer("Invalid product ID.", show_alert=True)
        return
        
    p = await get_product(p_id)
    if not p:
        await callback.answer("Product not found!", show_alert=True)
        return
        
    in_stock = int(p.get("in_stock", 0))
    if in_stock <= 0:
        await callback.answer("Sorry, this item is out of stock!", show_alert=True)
        return
        
    await state.set_state(OrderState.waiting_for_quantity)
    await state.update_data(product_id=p_id)
    
    prompt_text = (
        f"✏️ <b>Enter Custom Quantity</b>\n\n"
        f"📦 <b>Item:</b> {p['name']}\n"
        f"💵 <b>Price per item:</b> <code>${p['price']} USDT</code>\n"
        f"📊 <b>Stock Available:</b> <code>{in_stock}</code>\n\n"
        f"✍️ <i>Please send the quantity number you want to purchase (1 to {in_stock}):</i>"
    )
    await callback.message.edit_text(prompt_text, reply_markup=custom_quantity_keyboard(p_id))
    await callback.answer()

@router.message(OrderState.waiting_for_quantity)
async def handle_custom_quantity_input(message: Message, state: FSMContext):
    data = await state.get_data()
    p_id = data.get("product_id")
    if not p_id:
        await state.clear()
        await message.answer("Session expired. Please select the product again from Shop.", reply_markup=back_to_home_keyboard())
        return
        
    p = await get_product(p_id)
    if not p:
        await state.clear()
        await message.answer("Product not found.", reply_markup=back_to_home_keyboard())
        return
        
    in_stock = int(p.get("in_stock", 0))
    raw_text = (message.text or "").strip()
    
    if not raw_text.isdigit():
        await message.answer(
            f"⚠️ <b>Invalid number!</b>\n\nPlease enter a valid whole number between <b>1</b> and <b>{in_stock}</b>:",
            reply_markup=custom_quantity_keyboard(p_id)
        )
        return
        
    qty = int(raw_text)
    if qty < 1 or qty > in_stock:
        await message.answer(
            f"⚠️ <b>Quantity out of range!</b>\n\nYou entered <code>{qty}</code>. Available stock is <b>{in_stock}</b>.\nPlease enter a number between <b>1</b> and <b>{in_stock}</b>:",
            reply_markup=custom_quantity_keyboard(p_id)
        )
        return
        
    await state.clear()
    text = render_payment_prompt_text(p, qty)
    kb = payment_selection_keyboard(p, qty)
    await message.answer(text, reply_markup=kb)

# --- Wallet Purchase Flow ---
@router.callback_query(F.data.startswith("buywallet_"))
async def cb_buywallet_product(callback: CallbackQuery):
    raw = callback.data.replace("buywallet_", "")
    parts = raw.split("_")
    p_id = int(parts[0])
    qty = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 1
    
    p = await get_product(p_id)
    if not p:
        await callback.answer("Product not found!", show_alert=True)
        return
    
    in_stock = int(p.get("in_stock", 0))
    if in_stock < qty:
        await callback.answer(f"Sorry, only {in_stock} available in stock!", show_alert=True)
        return
    
    unit_price = float(p["price"])
    total_price = round(unit_price * qty, 2)
    balance = await get_user_balance(callback.from_user.id)
    
    if balance < total_price:
        text = (
            "⚠️ <b>Insufficient Wallet Balance!</b>\n\n"
            f"📦 <b>Item:</b> {p['name']}\n"
            f"🔢 <b>Quantity:</b> <code>{qty}x</code>\n"
            f"💵 <b>Total Price:</b> <code>${total_price:.2f}</code> USDT\n"
            f"💰 <b>Your Balance:</b> <code>${balance:.2f}</code> USDT\n"
            f"📉 <b>Shortfall:</b> <code>${total_price - balance:.2f}</code> USDT\n\n"
            "💡 <i>You can top up your wallet via Binance Pay, or pay directly via Binance Pay below:</i>"
        )
        await callback.message.edit_text(text, reply_markup=insufficient_wallet_keyboard(product_id=p_id, quantity=qty))
        await callback.answer()
        return

    text = (
        "👛 <b>Confirm Wallet Purchase</b>\n\n"
        f"📦 <b>Item:</b> {p['name']}\n"
        f"🔢 <b>Quantity:</b> <code>{qty}x</code>\n"
        f"💵 <b>Unit Price:</b> <code>${unit_price:.2f}</code> USDT\n"
        f"💰 <b>Total Price:</b> <code>${total_price:.2f}</code> USDT\n"
        f"🪙 <b>Your Current Balance:</b> <code>${balance:.2f}</code> USDT\n"
        f"💳 <b>Balance After Purchase:</b> <code>${balance - total_price:.2f}</code> USDT\n\n"
        "⚡ <i>Tap confirm below to purchase and receive your credentials instantly:</i>"
    )
    await callback.message.edit_text(text, reply_markup=confirm_wallet_buy_keyboard(p_id, total_price, quantity=qty))
    await callback.answer()

@router.callback_query(F.data.startswith("confirm_buywallet_") | F.data.startswith("dobuywallet_"))
async def cb_confirm_buywallet(callback: CallbackQuery):
    if callback.data.startswith("confirm_buywallet_"):
        raw = callback.data.replace("confirm_buywallet_", "")
    else:
        raw = callback.data.replace("dobuywallet_", "")
    parts = raw.split("_")
    p_id = int(parts[0])
    qty = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 1
    user_id = callback.from_user.id
    username = callback.from_user.username or "N/A"
    
    res = await create_and_pay_wallet_order(user_id, p_id, quantity=qty)
    if not res["success"]:
        if res.get("error") == "insufficient_balance":
            await callback.answer("Insufficient balance!", show_alert=True)
            await callback.message.edit_text(
                "⚠️ <b>Insufficient Wallet Balance!</b>\nPlease deposit funds or choose Binance Pay.",
                reply_markup=insufficient_wallet_keyboard(product_id=p_id, quantity=qty)
            )
        elif res.get("error") == "out_of_stock":
            await callback.answer("Sorry, item just went out of stock!", show_alert=True)
            await callback.message.edit_text(
                "⚠️ <b>Out of Stock!</b>\nThis product was just sold out. Please check back later or contact support.",
                reply_markup=back_to_home_keyboard()
            )
        else:
            await callback.answer(f"Error: {res.get('error')}", show_alert=True)
        return
    
    order_id = res["order_id"]
    delivery_text = (
        f"🎉 <b>Purchase Successful via Wallet!</b>\n\n"
        f"📦 <b>Order ID:</b> <code>#{order_id}</code>\n"
        f"🛍️ <b>Product:</b> {res['product_name']}\n"
        f"🔢 <b>Quantity:</b> <code>{qty}x</code>\n"
        f"💵 <b>Amount Paid:</b> <code>${res['amount']} USDT</code>\n"
        f"💰 <b>Remaining Wallet Balance:</b> <code>${res['remaining_balance']:.2f} USDT</code>\n\n"
        f"🔑 <b>Your Login Details / Credentials:</b>\n"
        f"<code>{res['delivered_data']}</code>\n\n"
        f"📋 <b>Instructions:</b>\n"
        f"<i>Please keep your credentials safe. You can also view this anytime under <b>📦 Purchase History</b>.</i>"
    )
    try:
        await callback.message.edit_text(delivery_text, reply_markup=delivery_success_keyboard(order_id, credentials=res['delivered_data']))
    except Exception as e:
        logger.warning(f"Error editing message with delivery keyboard: {e}, falling back to safe keyboard")
        await callback.message.edit_text(delivery_text, reply_markup=delivery_success_keyboard(order_id, credentials=None))
    await callback.answer("Purchase successful!")
    
    # Notify Admin
    try:
        await notify_admin(
            f"⚡ <b>Automated Wallet Order Delivered!</b>\n\n"
            f"Order: #{order_id}\n"
            f"User: @{username} (ID: <code>{user_id}</code>)\n"
            f"Product: {res['product_name']}\n"
            f"Quantity: {qty}x\n"
            f"Amount: ${res['amount']} USDT (Wallet Balance)\n"
            f"Remaining User Balance: ${res['remaining_balance']:.2f} USDT"
        )
    except Exception as e:
        logger.warning(f"Failed to notify admin: {e}")

@router.callback_query(F.data.startswith("paywallet_"))
async def cb_paywallet_order(callback: CallbackQuery):
    order_id = callback.data.replace("paywallet_", "")
    order = await get_order(order_id)
    if not order:
        await callback.answer("Order not found.", show_alert=True)
        return
        
    if order["status"] == "COMPLETED":
        await callback.answer("This order is already completed!", show_alert=True)
        return

    balance = await get_user_balance(callback.from_user.id)
    if balance < order["amount"]:
        text = (
            "⚠️ <b>Insufficient Wallet Balance!</b>\n\n"
            f"Order: <b>#{order_id}</b> ({order['product_name']})\n"
            f"💵 <b>Required:</b> <code>{order['amount']}</code> USDT\n"
            f"💰 <b>Your Balance:</b> <code>${balance:.2f}</code> USDT\n"
            f"📉 <b>Shortfall:</b> <code>${order['amount'] - balance:.2f}</code> USDT\n\n"
            "💡 <i>You can top up your wallet via Binance Pay, or continue with direct Binance Pay transfer.</i>"
        )
        await callback.message.edit_text(text, reply_markup=insufficient_wallet_keyboard(order_id=order_id))
        await callback.answer()
        return

    text = (
        f"👛 <b>Pay Order #{order_id} via Wallet</b>\n\n"
        f"📦 <b>Item:</b> {order['product_name']}\n"
        f"💵 <b>Amount:</b> <code>{order['amount']}</code> USDT\n"
        f"💰 <b>Your Current Balance:</b> <code>${balance:.2f}</code> USDT\n"
        f"🪙 <b>Balance After Payment:</b> <code>${balance - order['amount']:.2f}</code> USDT\n\n"
        "⚡ <i>Tap confirm to pay and receive credentials instantly:</i>"
    )
    await callback.message.edit_text(text, reply_markup=confirm_wallet_payorder_keyboard(order_id, order["amount"]))
    await callback.answer()

@router.callback_query(F.data.startswith("confirm_payorder_"))
async def cb_confirm_payorder(callback: CallbackQuery):
    order_id = callback.data.replace("confirm_payorder_", "")
    user_id = callback.from_user.id
    username = callback.from_user.username or "N/A"
    
    res = await execute_wallet_purchase(order_id, user_id)
    if not res["success"]:
        if res.get("error") == "insufficient_balance":
            await callback.answer("Insufficient balance!", show_alert=True)
            await callback.message.edit_text(
                "⚠️ <b>Insufficient Wallet Balance!</b>\nPlease deposit funds or choose Binance Pay.",
                reply_markup=insufficient_wallet_keyboard(order_id=order_id)
            )
        elif res.get("error") == "out_of_stock":
            await callback.answer("Sorry, item is currently out of stock!", show_alert=True)
            await callback.message.edit_text(
                "⚠️ <b>Out of Stock!</b>\nAdmin has been notified to restock. Your balance was not deducted.",
                reply_markup=back_to_home_keyboard()
            )
            await notify_admin(
                f"🚨 <b>Stock Empty for Wallet Order Attempt #{order_id}!</b>\n"
                f"User: @{username} (ID: {user_id})"
            )
        else:
            await callback.answer(f"Error: {res.get('error')}", show_alert=True)
        return
        
    delivery_text = (
        f"🎉 <b>Payment Successful via Wallet!</b>\n\n"
        f"📦 <b>Order ID:</b> <code>#{order_id}</code>\n"
        f"🛍️ <b>Product:</b> {res['order']['product_name']}\n"
        f"💵 <b>Amount Paid:</b> <code>${res['amount']} USDT</code>\n"
        f"💰 <b>Remaining Wallet Balance:</b> <code>${res['remaining_balance']:.2f} USDT</code>\n\n"
        f"🔑 <b>Your Login Details / Credentials:</b>\n"
        f"<code>{res['delivered_data']}</code>\n\n"
        f"📋 <b>Instructions:</b>\n"
        f"<i>Please keep your credentials safe. You can also view this anytime under <b>📦 Purchase History</b>.</i>"
    )
    try:
        await callback.message.edit_text(delivery_text, reply_markup=delivery_success_keyboard(order_id, credentials=res['delivered_data']))
    except Exception as e:
        logger.warning(f"Error editing message with delivery keyboard: {e}, falling back to safe keyboard")
        await callback.message.edit_text(delivery_text, reply_markup=delivery_success_keyboard(order_id, credentials=None))
    await callback.answer("Payment completed!")
    
    try:
        await notify_admin(
            f"⚡ <b>Order #{order_id} Paid via Wallet!</b>\n\n"
            f"User: @{username} (ID: <code>{user_id}</code>)\n"
            f"Product: {res['order']['product_name']}\n"
            f"Amount: ${res['amount']} USDT\n"
            f"Remaining User Balance: ${res['remaining_balance']:.2f} USDT"
        )
    except Exception as e:
        logger.warning(f"Failed to notify admin: {e}")

@router.callback_query(F.data.startswith("backtoinvoice_"))
async def cb_backtoinvoice(callback: CallbackQuery):
    order_id = callback.data.replace("backtoinvoice_", "")
    order = await get_order(order_id)
    if not order:
        await callback.answer("Order not found.", show_alert=True)
        return
    pay_id = await get_setting("binance_pay_id", "717053382")
    qty = int(order.get("quantity") or 1)
    qty_line = f"🔢 <b>Quantity:</b> <code>{qty}x</code>\n" if qty > 1 else ""
    invoice_text = (
        f"🛍️ <b>Order Created: #{order_id}</b>\n\n"
        f"📦 <b>Item:</b> {order['product_name']}\n"
        f"{qty_line}"
        f"💵 <b>Total Amount:</b> <code>{order['amount']}</code> USDT\n"
        f"🆔 <b>Binance Pay ID:</b> <code>{pay_id}</code>\n"
        f"👤 <b>Payee Name:</b> <b>User-c034c</b>\n\n"
        "1. Choose <b>Binance Pay</b>, not an on-chain withdrawal.\n"
        f"2. Use the recipient shown on the invoice or tap <b>Copy Binance ID</b> to send <b>{order['amount']} USDT</b>.\n"
        f"3. In Payment Remark / Note, write: <code>{order_id}</code>\n"
        "4. Open your payment receipt and copy the <b>full Pay Transaction/Order ID</b> (not recipient ID/UID).\n"
        "5. Paste that full ID in <b>this chat</b> within <b>30 minutes</b> of paying.\n\n"
        "⏱️ Only a payment made in the <b>30 minutes before</b> you paste its Order ID is accepted.\n"
        "⏳ <i>Invoice expires in 30 minutes — paste your Order ID before then.</i>"
    )
    await callback.message.edit_text(invoice_text, reply_markup=order_actions_keyboard(order_id, pay_id))
    await callback.answer()

# --- Buy Flow (Binance Pay) ---
@router.callback_query(F.data.startswith("buy_"))
async def cb_buy_product(callback: CallbackQuery, state: FSMContext):
    raw = callback.data.replace("buy_", "")
    parts = raw.split("_")
    p_id = int(parts[0])
    qty = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 1
    
    p = await get_product(p_id)
    if not p:
        await callback.answer("Product not found!", show_alert=True)
        return
    
    in_stock = int(p.get("in_stock", 0))
    if in_stock < qty:
        await callback.answer(f"Sorry, only {in_stock} available in stock!", show_alert=True)
        return
    
    unit_price = float(p["price"])
    total_amount = round(unit_price * qty, 2)
    pay_id = await get_setting("binance_pay_id", "717053382")
    
    # Silently clear any uncompleted checkout attempt so customer is never blocked
    await cancel_unpaid_orders_for_user(callback.from_user.id)

    # Generate unique Order ID
    order_id = f"ORD-{random.randint(10000, 99999)}"
    await create_order(
        order_id=order_id,
        telegram_id=callback.from_user.id,
        product_id=p["id"],
        product_name=p["name"],
        amount=total_amount,
        quantity=qty
    )
    
    invoice_text = (
        f"🛍️ <b>Order Created: #{order_id}</b>\n\n"
        f"📦 <b>Item:</b> {p['name']}\n"
        f"🔢 <b>Quantity:</b> <code>{qty}x</code>\n"
        f"💵 <b>Total Amount:</b> <code>{total_amount:.2f}</code> USDT\n"
        f"🆔 <b>Binance Pay ID:</b> <code>{pay_id}</code>\n"
        f"👤 <b>Payee Name:</b> <b>User-c034c</b>\n\n"
        "1. Choose <b>Binance Pay</b>, not an on-chain withdrawal.\n"
        f"2. Use the recipient shown on the invoice or tap <b>Copy Binance ID</b> to send <b>{total_amount:.2f} USDT</b>.\n"
        f"3. In Payment Remark / Note, write: <code>{order_id}</code>\n"
        "4. Open your payment receipt and copy the <b>full Pay Transaction/Order ID</b> (not recipient ID/UID).\n"
        "5. Paste that full ID in <b>this chat</b> within <b>30 minutes</b> of paying.\n\n"
        "⏱️ Only a payment made in the <b>30 minutes before</b> you paste its Order ID is accepted.\n"
        "⏳ <i>Invoice expires in 30 minutes — paste your Order ID before then.</i>"
    )

    await callback.message.edit_text(invoice_text, reply_markup=order_actions_keyboard(order_id, pay_id))
    await callback.answer()

# --- Cancel Order ---
@router.callback_query(F.data.startswith("cancelorder_"))
async def cb_cancel_order(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    order_id = callback.data.replace("cancelorder_", "")
    order = await get_order(order_id)
    if not order:
        await callback.answer("Order not found.", show_alert=True)
        return
    
    if order["status"] == "COMPLETED":
        await callback.answer("Completed orders cannot be cancelled.", show_alert=True)
        return
    
    await cancel_order(order_id, reason="Cancelled by user")
    await callback.message.edit_text(
        f"❌ Order <b>#{order_id}</b> has been cancelled.\n\nFeel free to explore our other products!",
        reply_markup=back_to_home_keyboard()
    )
    await callback.answer("Order cancelled.")

# --- Submit Binance TxID ---
@router.callback_query(F.data.startswith("submittx_"))
async def cb_submit_tx(callback: CallbackQuery, state: FSMContext):
    order_id = callback.data.replace("submittx_", "")
    order = await get_order(order_id)
    if not order:
        await callback.answer("Order not found.", show_alert=True)
        return
    
    if order["status"] == "COMPLETED":
        await callback.answer("This order is already completed!", show_alert=True)
        return

    await state.update_data(order_id=order_id)
    await state.set_state(OrderState.waiting_for_txid)
    
    prompt = (
        f"📝 <b>Submit Binance Pay Transaction ID</b>\n\n"
        f"Order: <b>#{order_id}</b>\n"
        f"Amount: <b>${order['amount']} USDT</b>\n\n"
        f"Please send your <b>Binance Order ID / Transaction ID</b> (e.g. <code>2389102938</code>) below in reply to this message:\n\n"
        f"<i>To cancel, send /cancel or click below.</i>"
    )
    await callback.message.edit_text(prompt)
    await callback.answer()

@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Action cancelled.", reply_markup=main_reply_keyboard())

# --- Handle TxID text message ---
@router.message(OrderState.waiting_for_txid)
@router.message(F.text & ~F.text.startswith("/"))
async def handle_txid_input(message: Message, state: FSMContext):
    # Ignore persistent menu button clicks
    menu_buttons = [
        "🛍️ SHOP", "💱 Wallet", "👛 Wallet", "😃 Profile",
        "🎯 Referral Store", "🎧 Support", "❓ Help", "📦 My Orders", "📦 Orders"
    ]
    if message.text in menu_buttons:
        return

    current_state = await state.get_state()
    if current_state and current_state != OrderState.waiting_for_txid.state:
        return

    data = await state.get_data()
    order_id = data.get("order_id")
    await state.clear()

    if not order_id:
        active = await get_active_order_for_user(message.from_user.id)
        if active and active.get("status") == "PENDING_PAYMENT" and len(message.text.strip()) >= 5:
            order_id = active["order_id"]
        else:
            return  # Not an active order payment, ignore quietly

    submitted_tx = message.text.strip()
    if len(submitted_tx) < 4:
        await message.answer("⚠️ Invalid Transaction ID. Please make sure you copied the full Binance Order ID.")
        return

    already_used = await is_txid_used(submitted_tx, current_order_id=order_id)
    if already_used:
        await message.answer(
            f"❌ <b>Transaction ID already redeemed!</b>\n\n"
            f"TxID <code>{submitted_tx}</code> has already been used for a previous order. "
            f"Double spending is not allowed. If you think this is an error, please contact support.",
            reply_markup=main_reply_keyboard()
        )
        return

    await submit_order_tx_id(order_id, submitted_tx)
    order = await get_order(order_id)

    status_msg = await message.answer("⏳ <i>Verifying payment with Binance API... Please wait a moment.</i>")

    api_key = await get_setting("binance_api_key")
    api_secret = await get_setting("binance_api_secret")

    verification_result = None
    if api_key and api_secret:
        verification_result = await verify_binance_pay_transaction(
            api_key=api_key,
            api_secret=api_secret,
            submitted_tx_id=submitted_tx,
            expected_amount=order["amount"],
            expected_currency="USDT"
        )
    else:
        logger.warning("Binance payment auto-verification skipped: binance_api_secret is not configured.")

    if verification_result and verification_result.get("verified") is True:
        fulfil_res = await fulfill_order_and_get_stock(order_id)
        if fulfil_res.get("success"):
            delivered_data = fulfil_res["delivered_data"]
            await complete_order(order_id, delivered_data=delivered_data)
            await status_msg.delete()
            await deliver_order_to_user(message, order, delivered_data, message.bot)
            
            provider_tag = f" (via Provider: {fulfil_res.get('provider_name')})" if fulfil_res.get("is_api") else ""
            await notify_admin(
                f"✅ <b>Automated Order Completed!</b>{provider_tag}\n\n"
                f"Order: #{order_id}\n"
                f"User: @{message.from_user.username or 'N/A'} (ID: <code>{message.from_user.id}</code>)\n"
                f"Product: {order['product_name']}\n"
                f"Amount: ${order['amount']} USDT\n"
                f"TxID: <code>{submitted_tx}</code>"
            )
            return
        else:
            err_msg = fulfil_res.get("error", "Stock unavailable")
            await status_msg.edit_text(
                f"⚠️ Payment verified! Preparing your credentials... "
                f"Our admin has been notified and will verify dispatch immediately."
            )
            await notify_admin(
                f"🚨 <b>URGENT: Delivery Issue for Paid Order #{order_id}!</b>\n"
                f"User: @{message.from_user.username} (ID: {message.from_user.id})\n"
                f"Product: {order['product_name']}\n"
                f"Reason: {err_msg}\n"
                f"Payment verified: ${order['amount']} USDT. Please check supplier/stock & deliver via Dashboard!"
            )
            return

    reason_str = ""
    if verification_result and verification_result.get("error"):
        reason_str = f"API Check Note: <i>{verification_result['error']}</i>\n"
    elif not api_secret:
        reason_str = "API Check Note: <i>Binance API Secret is not set in settings.</i>\n"

    msg_text = (
        f"✅ <b>Payment Details Submitted!</b>\n\n"
        f"Order ID: <b>#{order_id}</b>\n"
        f"Binance TxID: <code>{submitted_tx}</code>\n"
        f"Amount: <b>${order['amount']} USDT</b>\n\n"
        f"⏳ <b>Status: Pending Verification</b>\n"
        f"Your payment has been logged. Automated Binance Pay records can take 1-3 minutes to update. "
        f"Our admin will also review and dispatch your credentials as soon as verified!\n\n"
        f"Check <b>📦 My Orders</b> anytime to track status."
    )
    await status_msg.edit_text(msg_text, reply_markup=single_order_view_keyboard(order_id, "PENDING_VERIFICATION"))

    await notify_admin(
        f"🔔 <b>New Payment Verification Pending!</b>\n\n"
        f"Order: <b>#{order_id}</b>\n"
        f"User: @{message.from_user.username or 'N/A'} (ID: <code>{message.from_user.id}</code>)\n"
        f"Product: <b>{order['product_name']}</b> (${order['amount']} USDT)\n"
        f"TxID: <code>{submitted_tx}</code>\n"
        f"{reason_str}\n"
        f"👉 Open @foxzenadmin_bot or Web Dashboard to inspect & approve."
    )

# --- My Orders View ---
@router.callback_query(F.data == "nav_my_orders")
async def cb_my_orders(callback: CallbackQuery):
    orders = await get_user_orders(callback.from_user.id, status="COMPLETED")
    if not orders:
        await callback.message.edit_text(
            "📦 <b>Purchase History</b>\n\n"
            "You haven't made any completed purchases yet.\n"
            "Browse our shop to purchase products with instant delivery!",
            reply_markup=empty_orders_keyboard()
        )
        await callback.answer()
        return

    await callback.message.edit_text(
        "📦 <b>Your Purchase History:</b>\nTap any completed order below to view product details and credentials:",
        reply_markup=my_orders_keyboard(orders)
    )
    await callback.answer()

@router.callback_query(F.data.startswith("vieworder_"))
async def cb_view_single_order(callback: CallbackQuery):
    order_id = callback.data.replace("vieworder_", "")
    order = await get_order(order_id)
    if not order:
        await callback.answer("Purchase record not found.", show_alert=True)
        return

    pay_method = "👛 Wallet Balance" if (order.get("binance_tx_id") in ["WALLET_BALANCE", "WALLET"]) else "💳 Binance Pay"
    created_at = order.get("created_at", "")[:19]
    qty = int(order.get("quantity") or 1)
    qty_str = f"🔢 <b>Quantity:</b> <code>{qty}x</code>\n" if qty > 1 else ""

    text = (
        f"📦 <b>Purchase Details: #{order['order_id']}</b>\n\n"
        f"🛍️ <b>Product:</b> <b>{order['product_name']}</b>\n"
        f"{qty_str}"
        f"💵 <b>Amount Paid:</b> <code>${order['amount']} USDT</code>\n"
        f"💳 <b>Payment Method:</b> {pay_method}\n"
        f"📅 <b>Date:</b> {created_at}\n"
        f"✅ <b>Status:</b> Completed & Delivered\n\n"
    )

    if order.get("delivered_data"):
        text += (
            f"🔑 <b>Login Credentials / Account Key:</b>\n"
            f"<code>{order['delivered_data']}</code>\n\n"
            f"📋 <b>Instructions:</b>\n"
            f"<i>Please store your credentials safely. If you encounter any issue, contact support.</i>"
        )

    pay_id = await get_setting("binance_pay_id", "717053382")
    await callback.message.edit_text(
        text,
        reply_markup=single_order_view_keyboard(
            order_id,
            order["status"],
            pay_id,
            credentials=order.get("delivered_data")
        )
    )
    await callback.answer()
