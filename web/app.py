import asyncio
from pathlib import Path
from fastapi import FastAPI, Request, Form, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from config import BASE_DIR, ADMIN_USERNAME
from database import (
    get_db,
    verify_password,
    hash_password,
    get_dashboard_stats,
    get_all_orders,
    get_order,
    get_products,
    get_product,
    add_product,
    update_product,
    delete_product,
    get_categories,
    add_category,
    delete_category,
    get_stock_items,
    add_stock_items,
    pop_available_stock,
    fulfill_order_and_get_stock,
    delete_stock_item,
    complete_order,
    cancel_order,
    get_setting,
    get_all_settings,
    update_settings,
    get_all_user_ids,
    get_all_users,
    update_user_balance,
    set_user_balance,
    get_user_profile,
    save_or_update_user,
    get_providers,
    get_provider,
    add_provider,
    update_provider,
    delete_provider,
    update_provider_balance
)
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from binance import test_binance_api_credentials, verify_binance_pay_transaction
from reseller_api import (
    test_provider_connection,
    check_provider_balance,
    fetch_provider_products,
    get_sample_provider_products
)
from web.auth import create_session_token, get_current_admin, COOKIE_NAME
from bot.bot_instance import get_bot, send_user_notification

web_app = FastAPI(title="Foxzen Bot Web Admin")

# Templates & Static Files
templates_dir = BASE_DIR / "web" / "templates"
templates = Jinja2Templates(directory=str(templates_dir))
static_dir = BASE_DIR / "web" / "static"
web_app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# --- Public Auth Routes ---
@web_app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, error: str = None):
    return templates.TemplateResponse(request=request, name="login.html", context={"error": error})

@web_app.post("/login")
async def login_action(username: str = Form(...), password: str = Form(...)):
    stored_username = await get_setting("admin_username", ADMIN_USERNAME)
    stored_password_hash = await get_setting("admin_password_hash")
    
    if username == stored_username and verify_password(password, stored_password_hash):
        response = RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)
        token = create_session_token(username)
        response.set_cookie(
            key=COOKIE_NAME,
            value=token,
            max_age=7 * 24 * 3600,
            httponly=True,
            samesite="lax"
        )
        return response
    else:
        return RedirectResponse(url="/login?error=Invalid+username+or+password", status_code=status.HTTP_303_SEE_OTHER)

@web_app.get("/logout")
async def logout():
    response = RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie(COOKIE_NAME)
    return response

# --- Protected Admin Routes ---
@web_app.get("/", response_class=HTMLResponse)
async def root(admin: str = Depends(get_current_admin)):
    return RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)

@web_app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request, alert: str = None, admin: str = Depends(get_current_admin)):
    stats = await get_dashboard_stats()
    recent_orders = await get_all_orders(limit=8)
    bot_token = await get_setting("telegram_bot_token")
    
    return templates.TemplateResponse(request=request, name="dashboard.html", context={
        "active_page": "dashboard",
        "stats": stats,
        "recent_orders": recent_orders,
        "bot_configured": bool(bot_token and bot_token.strip()),
        "alert_msg": alert,
        "alert_type": "success" if alert else None
    })

@web_app.get("/products", response_class=HTMLResponse)
async def products_page(request: Request, category_id: int = None, alert: str = None, admin: str = Depends(get_current_admin)):
    categories = await get_categories()
    products = await get_products(category_id=category_id)
    providers = await get_providers(active_only=True)
    
    return templates.TemplateResponse(request=request, name="products.html", context={
        "active_page": "products",
        "categories": categories,
        "products": products,
        "providers": providers,
        "selected_cat": category_id,
        "alert_msg": alert,
        "alert_type": "success" if alert else None
    })

@web_app.post("/products/create")
async def create_product_action(
    name: str = Form(...),
    price: float = Form(...),
    category_id: str = Form(None),
    description: str = Form(""),
    delivery_instructions: str = Form(""),
    fulfillment_type: str = Form("LOCAL"),
    provider_id: str = Form(None),
    provider_product_id: str = Form(""),
    provider_price: float = Form(0.0),
    admin: str = Depends(get_current_admin)
):
    cat_id = int(category_id) if category_id and category_id.isdigit() else None
    prov_id = int(provider_id) if provider_id and provider_id.isdigit() else None
    await add_product(
        category_id=cat_id,
        name=name.strip(),
        description=description.strip(),
        price=price,
        delivery_instructions=delivery_instructions.strip(),
        fulfillment_type=fulfillment_type,
        provider_id=prov_id,
        provider_product_id=provider_product_id.strip() if provider_product_id else None,
        provider_price=provider_price
    )
    return RedirectResponse(url="/products?alert=Product+added+successfully", status_code=status.HTTP_303_SEE_OTHER)

@web_app.post("/products/{product_id}/edit")
async def edit_product_action(
    product_id: int,
    name: str = Form(...),
    price: float = Form(...),
    category_id: str = Form(None),
    description: str = Form(""),
    delivery_instructions: str = Form(""),
    is_active: str = Form("0"),
    fulfillment_type: str = Form("LOCAL"),
    provider_id: str = Form(None),
    provider_product_id: str = Form(""),
    provider_price: float = Form(0.0),
    admin: str = Depends(get_current_admin)
):
    cat_id = int(category_id) if category_id and category_id.isdigit() else None
    prov_id = int(provider_id) if provider_id and provider_id.isdigit() else None
    active_val = 1 if is_active == "1" else 0
    await update_product(
        product_id=product_id,
        category_id=cat_id,
        name=name.strip(),
        description=description.strip(),
        price=price,
        delivery_instructions=delivery_instructions.strip(),
        is_active=active_val,
        fulfillment_type=fulfillment_type,
        provider_id=prov_id,
        provider_product_id=provider_product_id.strip() if provider_product_id else None,
        provider_price=provider_price
    )
    return RedirectResponse(url="/products?alert=Product+updated+successfully", status_code=status.HTTP_303_SEE_OTHER)

@web_app.post("/products/{product_id}/delete")
async def delete_product_action(product_id: int, admin: str = Depends(get_current_admin)):
    await delete_product(product_id)
    return RedirectResponse(url="/products?alert=Product+deleted", status_code=status.HTTP_303_SEE_OTHER)

@web_app.post("/categories/create")
async def create_category_action(
    name: str = Form(...),
    icon: str = Form("📁"),
    description: str = Form(""),
    admin: str = Depends(get_current_admin)
):
    await add_category(name.strip(), description.strip(), icon.strip() or "📁")
    return RedirectResponse(url="/products?alert=Category+created", status_code=status.HTTP_303_SEE_OTHER)

@web_app.post("/categories/{category_id}/delete")
async def delete_category_action(category_id: int, admin: str = Depends(get_current_admin)):
    await delete_category(category_id)
    return RedirectResponse(url="/products?alert=Category+deleted", status_code=status.HTTP_303_SEE_OTHER)

@web_app.get("/stock", response_class=HTMLResponse)
async def stock_page(request: Request, product_id: int = None, alert: str = None, error: str = None, admin: str = Depends(get_current_admin)):
    products = await get_products()
    selected_p_id = product_id or (products[0]["id"] if products else None)
    
    current_product = None
    stock_items = []
    if selected_p_id:
        current_product = await get_product(selected_p_id)
        stock_items = await get_stock_items(selected_p_id)
        
    return templates.TemplateResponse(request=request, name="stock.html", context={
        "active_page": "stock",
        "products": products,
        "selected_product_id": selected_p_id,
        "current_product": current_product,
        "stock_items": stock_items,
        "alert_msg": alert or error,
        "alert_type": "error" if error else ("success" if alert else None)
    })

@web_app.post("/stock/add")
async def add_stock_action(
    product_id: int = Form(...),
    bulk_items: str = Form(...),
    admin: str = Depends(get_current_admin)
):
    lines = [line.strip() for line in bulk_items.splitlines() if line.strip()]
    count = await add_stock_items(product_id, lines)
    return RedirectResponse(url=f"/stock?product_id={product_id}&alert=Successfully+added+{count}+items+to+stock", status_code=status.HTTP_303_SEE_OTHER)

@web_app.post("/stock/{stock_id}/delete")
async def delete_stock_action(
    stock_id: int,
    product_id: str = Form(None),
    admin: str = Depends(get_current_admin)
):
    await delete_stock_item(stock_id)
    redirect_url = f"/stock?product_id={product_id}&alert=Stock+item+deleted" if product_id else "/stock?alert=Stock+item+deleted"
    return RedirectResponse(url=redirect_url, status_code=status.HTTP_303_SEE_OTHER)

@web_app.get("/orders", response_class=HTMLResponse)
async def orders_page(request: Request, status: str = None, alert: str = None, error: str = None, admin: str = Depends(get_current_admin)):
    orders = await get_all_orders(status=status)
    return templates.TemplateResponse(request=request, name="orders.html", context={
        "active_page": "orders",
        "orders": orders,
        "current_status": status,
        "alert_msg": alert or error,
        "alert_type": "error" if error else ("success" if alert else None)
    })

@web_app.post("/orders/{order_id}/approve")
async def approve_order_action(order_id: str, admin: str = Depends(get_current_admin)):
    order = await get_order(order_id)
    if not order:
        return RedirectResponse(url="/orders?error=Order+not+found", status_code=status.HTTP_303_SEE_OTHER)
        
    if order["status"] == "COMPLETED":
        return RedirectResponse(url="/orders?alert=Order+is+already+completed", status_code=status.HTTP_303_SEE_OTHER)

    # Deliver via Stock or Reseller Provider API
    fulfil_res = await fulfill_order_and_get_stock(order_id)
    if not fulfil_res.get("success"):
        err = fulfil_res.get("error", "Failed to retrieve stock/credentials")
        return RedirectResponse(
            url=f"/orders?error=Cannot+approve:+{err}",
            status_code=status.HTTP_303_SEE_OTHER
        )

    stock_item = fulfil_res["delivered_data"]

    # Mark completed in DB
    await complete_order(order_id, delivered_data=stock_item)

    # Dispatch to Telegram Bot
    delivery_text = (
        f"🎉 <b>Payment Approved by Admin!</b>\n\n"
        f"Order ID: <b>#{order['order_id']}</b>\n"
        f"Product: <b>{order['product_name']}</b>\n\n"
        f"🔑 <b>Your Login Details / Credentials:</b>\n"
        f"<code>{stock_item}</code>\n\n"
        f"Thank you for shopping with Foxzen Store!"
    )
    await send_user_notification(order["telegram_id"], delivery_text)

    msg = f"Order #{order_id} approved"
    if fulfil_res.get("is_api"):
        msg += f" (Auto-purchased via {fulfil_res.get('provider_name')})"
    return RedirectResponse(url=f"/orders?alert={msg}", status_code=status.HTTP_303_SEE_OTHER)

@web_app.post("/orders/{order_id}/reject")
async def reject_order_action(order_id: str, admin: str = Depends(get_current_admin)):
    order = await get_order(order_id)
    if order:
        await cancel_order(order_id, reason="Rejected by Admin")
        # Notify user
        reject_text = f"❌ Your payment for Order <b>#{order_id}</b> ({order['product_name']}) could not be verified and has been cancelled. If you believe this is a mistake, please contact support."
        await send_user_notification(order["telegram_id"], reject_text)
        
    return RedirectResponse(url=f"/orders?alert=Order+%23{order_id}+marked+as+rejected", status_code=status.HTTP_303_SEE_OTHER)

@web_app.post("/orders/{order_id}/verify-binance")
async def verify_binance_action(order_id: str, admin: str = Depends(get_current_admin)):
    order = await get_order(order_id)
    if not order:
        return RedirectResponse(url="/orders?error=Order+not+found", status_code=status.HTTP_303_SEE_OTHER)

    if not order.get("binance_tx_id"):
        return RedirectResponse(url="/orders?error=Customer+has+not+submitted+a+Binance+TxID+yet", status_code=status.HTTP_303_SEE_OTHER)

    api_key = await get_setting("binance_api_key")
    api_secret = await get_setting("binance_api_secret")

    if not api_key or not api_secret:
        return RedirectResponse(url="/orders?error=Binance+API+credentials+not+configured+in+Settings", status_code=status.HTTP_303_SEE_OTHER)

    result = await verify_binance_pay_transaction(
        api_key=api_key,
        api_secret=api_secret,
        submitted_tx_id=order["binance_tx_id"],
        expected_amount=order["amount"]
    )

    if result.get("verified") is True:
        # Deliver item via Stock or Reseller API
        fulfil_res = await fulfill_order_and_get_stock(order_id)
        if not fulfil_res.get("success"):
            err = fulfil_res.get("error", "Failed to retrieve stock/credentials")
            return RedirectResponse(url=f"/orders?error=Verified+on+Binance+but+{err}", status_code=status.HTTP_303_SEE_OTHER)
            
        stock_item = fulfil_res["delivered_data"]
        await complete_order(order_id, delivered_data=stock_item)
        delivery_text = (
            f"🎉 <b>Binance Payment Verified!</b>\n\n"
            f"Order ID: <b>#{order['order_id']}</b>\n"
            f"Product: <b>{order['product_name']}</b>\n\n"
            f"🔑 <b>Your Credentials:</b>\n"
            f"<code>{stock_item}</code>\n"
        )
        await send_user_notification(order["telegram_id"], delivery_text)
        return RedirectResponse(url=f"/orders?alert=Verified+on+Binance!+Order+%23{order_id}+delivered", status_code=status.HTTP_303_SEE_OTHER)
    else:
        err = result.get("error", "Transaction could not be verified on Binance.")
        return RedirectResponse(url=f"/orders?error=Binance+API:+{err}", status_code=status.HTTP_303_SEE_OTHER)

@web_app.get("/users", response_class=HTMLResponse)
async def users_page(
    request: Request,
    alert: str = None,
    error: str = None,
    user_id: int = None,
    admin: str = Depends(get_current_admin)
):
    users = await get_all_users()
    total_balance = sum((u.get("balance") or 0.0) for u in users)
    active_wallets = sum(1 for u in users if (u.get("balance") or 0.0) > 0)
    
    return templates.TemplateResponse(request=request, name="users.html", context={
        "active_page": "users",
        "users": users,
        "total_balance": round(total_balance, 2),
        "active_wallets": active_wallets,
        "preselected_user_id": user_id,
        "alert_msg": alert or error,
        "alert_type": "error" if error else ("success" if alert else None)
    })

@web_app.post("/users/add-fund")
async def add_fund_to_user_action(
    telegram_id: int = Form(...),
    amount: float = Form(...),
    action: str = Form("add"),
    note: str = Form(""),
    notify_user: str = Form(""),
    admin: str = Depends(get_current_admin)
):
    # Ensure user exists in database
    user_prof = await get_user_profile(telegram_id)
    if not user_prof or not user_prof.get("telegram_id"):
        await save_or_update_user(telegram_id, username="", first_name=f"User {telegram_id}")

    if action == "set":
        if amount < 0:
            return RedirectResponse(url="/users?error=Balance+cannot+be+negative", status_code=status.HTTP_303_SEE_OTHER)
        new_bal = await set_user_balance(telegram_id, amount)
    elif action == "deduct":
        if amount <= 0:
            return RedirectResponse(url="/users?error=Amount+to+deduct+must+be+greater+than+0", status_code=status.HTTP_303_SEE_OTHER)
        new_bal = await update_user_balance(telegram_id, -amount)
    else:  # add
        if amount <= 0:
            return RedirectResponse(url="/users?error=Amount+must+be+greater+than+0", status_code=status.HTTP_303_SEE_OTHER)
        new_bal = await update_user_balance(telegram_id, amount)

    # Send receipt/notification to user on Telegram
    if notify_user:
        note_str = f"\n📝 <b>Remark:</b> {note.strip()}" if note and note.strip() else ""
        
        if action == "add":
            msg = (
                f"🎉 <b>Wallet Balance Credited!</b>\n\n"
                f"💵 <b>Amount Added:</b> <code>+{amount:.2f} USDT</code>\n"
                f"💰 <b>Updated Available Balance:</b> <code>${new_bal:.2f} USDT</code>"
                f"{note_str}\n\n"
                f"🛍️ <i>Your funds are ready! Tap below to shop with 1-click instant delivery:</i>"
            )
        elif action == "deduct":
            msg = (
                f"ℹ️ <b>Wallet Balance Updated</b>\n\n"
                f"💵 <b>Amount Deducted:</b> <code>-{amount:.2f} USDT</code>\n"
                f"💰 <b>Updated Available Balance:</b> <code>${new_bal:.2f} USDT</code>"
                f"{note_str}"
            )
        else:  # set
            msg = (
                f"ℹ️ <b>Wallet Balance Adjusted</b>\n\n"
                f"💰 <b>Updated Available Balance:</b> <code>${new_bal:.2f} USDT</code>"
                f"{note_str}"
            )

        buttons = [
            [
                InlineKeyboardButton(text="🛍️ Go to Shop", callback_data="nav_products", style="success"),
                InlineKeyboardButton(text="👛 View Wallet", callback_data="nav_wallet", style="primary")
            ]
        ]
        markup = InlineKeyboardMarkup(inline_keyboard=buttons)
        try:
            await send_user_notification(telegram_id, msg, reply_markup=markup)
        except Exception as e:
            print(f"Error sending balance notification: {e}")

    if action == "set":
        verb = f"set to ${new_bal:.2f} USDT for"
    elif action == "deduct":
        verb = "deducted from"
    else:
        verb = "credited to"

    return RedirectResponse(
        url=f"/users?alert=Successfully+{verb}+user+{telegram_id}!+New+Balance:+${new_bal:.2f}+USDT",
        status_code=status.HTTP_303_SEE_OTHER
    )

@web_app.post("/users/{telegram_id}/balance")
async def update_user_balance_route(
    telegram_id: int,
    amount: float = Form(...),
    action: str = Form("add"),
    note: str = Form(""),
    notify_user: str = Form("on"),
    admin: str = Depends(get_current_admin)
):
    if action == "set":
        if amount < 0:
            return RedirectResponse(url="/users?error=Balance+cannot+be+negative", status_code=status.HTTP_303_SEE_OTHER)
        new_bal = await set_user_balance(telegram_id, amount)
    elif action == "deduct":
        if amount <= 0:
            return RedirectResponse(url="/users?error=Amount+to+deduct+must+be+greater+than+0", status_code=status.HTTP_303_SEE_OTHER)
        new_bal = await update_user_balance(telegram_id, -amount)
    else:
        if amount <= 0:
            return RedirectResponse(url="/users?error=Amount+must+be+greater+than+0", status_code=status.HTTP_303_SEE_OTHER)
        new_bal = await update_user_balance(telegram_id, amount)
    
    if notify_user:
        note_str = f"\n📝 <b>Remark:</b> {note.strip()}" if note and note.strip() else ""
        
        if action == "add":
            msg = (
                f"🎉 <b>Wallet Balance Credited!</b>\n\n"
                f"💵 <b>Amount Added:</b> <code>+{amount:.2f} USDT</code>\n"
                f"💰 <b>Updated Available Balance:</b> <code>${new_bal:.2f} USDT</code>"
                f"{note_str}\n\n"
                f"🛍️ <i>You can now purchase products in the shop with instant 1-click delivery!</i>"
            )
        elif action == "deduct":
            msg = (
                f"ℹ️ <b>Wallet Balance Updated</b>\n\n"
                f"💵 <b>Amount Deducted:</b> <code>-{amount:.2f} USDT</code>\n"
                f"💰 <b>Updated Available Balance:</b> <code>${new_bal:.2f} USDT</code>"
                f"{note_str}"
            )
        else:
            msg = (
                f"ℹ️ <b>Wallet Balance Adjusted</b>\n\n"
                f"💰 <b>Updated Available Balance:</b> <code>${new_bal:.2f} USDT</code>"
                f"{note_str}"
            )

        buttons = [
            [
                InlineKeyboardButton(text="🛍️ Go to Shop", callback_data="nav_products", style="success"),
                InlineKeyboardButton(text="👛 View Wallet", callback_data="nav_wallet", style="primary")
            ]
        ]
        markup = InlineKeyboardMarkup(inline_keyboard=buttons)
        try:
            await send_user_notification(telegram_id, msg, reply_markup=markup)
        except Exception:
            pass

    return RedirectResponse(
        url=f"/users?alert=Balance+updated+for+user+{telegram_id}!+New+balance:+${new_bal:.2f}+USDT",
        status_code=status.HTTP_303_SEE_OTHER
    )

@web_app.get("/broadcast", response_class=HTMLResponse)
async def broadcast_page(request: Request, alert: str = None, error: str = None, admin: str = Depends(get_current_admin)):
    users = await get_all_user_ids()
    return templates.TemplateResponse(request=request, name="broadcast.html", context={
        "active_page": "broadcast",
        "total_users": len(users),
        "alert_msg": alert or error,
        "alert_type": "error" if error else ("success" if alert else None)
    })

@web_app.post("/broadcast")
async def broadcast_action(broadcast_text: str = Form(...), admin: str = Depends(get_current_admin)):
    users = await get_all_user_ids()
    sent_count = 0
    bot = get_bot()
    
    if not bot:
        return RedirectResponse(url="/broadcast?error=Telegram+Bot+is+not+running.+Configure+Bot+Token+first.", status_code=status.HTTP_303_SEE_OTHER)
        
    for user_id in users:
        success = await send_user_notification(user_id, broadcast_text)
        if success:
            sent_count += 1
        await asyncio.sleep(0.05) # Rate limiting
        
    return RedirectResponse(url=f"/broadcast?alert=Broadcast+successfully+sent+to+{sent_count}+users!", status_code=status.HTTP_303_SEE_OTHER)

@web_app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request, alert: str = None, error: str = None, admin: str = Depends(get_current_admin)):
    settings_dict = await get_all_settings()
    return templates.TemplateResponse(request=request, name="settings.html", context={
        "active_page": "settings",
        "settings": settings_dict,
        "alert_msg": alert or error,
        "alert_type": "error" if error else ("success" if alert else None)
    })

@web_app.post("/settings")
async def update_settings_action(
    binance_pay_id: str = Form(...),
    binance_api_key: str = Form(""),
    binance_api_secret: str = Form(""),
    telegram_bot_token: str = Form(""),
    admin_telegram_id: str = Form(""),
    support_link: str = Form(""),
    welcome_message: str = Form(""),
    admin_username: str = Form("admin"),
    new_password: str = Form(""),
    admin: str = Depends(get_current_admin)
):
    updates = {
        "binance_pay_id": binance_pay_id.strip(),
        "binance_api_key": binance_api_key.strip(),
        "binance_api_secret": binance_api_secret.strip(),
        "telegram_bot_token": telegram_bot_token.strip(),
        "admin_telegram_id": admin_telegram_id.strip(),
        "support_link": support_link.strip(),
        "welcome_message": welcome_message.strip(),
        "admin_username": admin_username.strip()
    }
    
    if new_password and new_password.strip():
        updates["admin_password_hash"] = hash_password(new_password.strip())
        
    await update_settings(updates)
    
    # Reload bot service in background if token was set
    try:
        from main import start_bot_service
        asyncio.create_task(start_bot_service())
    except Exception as e:
        print(f"Error triggering bot reload: {e}")
        
    return RedirectResponse(url="/settings?alert=Settings+updated+successfully!", status_code=status.HTTP_303_SEE_OTHER)

@web_app.post("/settings/test-binance")
async def test_binance_api_route(api_key: str = Form(""), api_secret: str = Form(""), admin: str = Depends(get_current_admin)):
    success, msg = await test_binance_api_credentials(api_key.strip(), api_secret.strip())
    return JSONResponse(content={"success": success, "message": msg})

# --- Reseller & Supplier APIs Routes ---
@web_app.get("/providers", response_class=HTMLResponse)
async def providers_page(request: Request, alert: str = None, error: str = None, admin: str = Depends(get_current_admin)):
    providers = await get_providers()
    categories = await get_categories()
    return templates.TemplateResponse(request=request, name="providers.html", context={
        "active_page": "providers",
        "providers": providers,
        "categories": categories,
        "alert_msg": alert or error,
        "alert_type": "error" if error else ("success" if alert else None)
    })

@web_app.post("/providers/create")
async def create_provider_action(
    name: str = Form(...),
    api_url: str = Form(...),
    api_key: str = Form(...),
    api_secret: str = Form(""),
    admin: str = Depends(get_current_admin)
):
    await add_provider(
        name=name.strip(),
        api_url=api_url.strip(),
        api_key=api_key.strip(),
        api_secret=api_secret.strip()
    )
    return RedirectResponse(url="/providers?alert=Supplier+API+connected+successfully!", status_code=status.HTTP_303_SEE_OTHER)

@web_app.post("/providers/{provider_id}/edit")
async def edit_provider_action(
    provider_id: int,
    name: str = Form(...),
    api_url: str = Form(...),
    api_key: str = Form(...),
    api_secret: str = Form(""),
    is_active: str = Form("0"),
    admin: str = Depends(get_current_admin)
):
    active_val = 1 if is_active == "1" else 0
    await update_provider(
        provider_id=provider_id,
        name=name.strip(),
        api_url=api_url.strip(),
        api_key=api_key.strip(),
        api_secret=api_secret.strip(),
        is_active=active_val
    )
    return RedirectResponse(url="/providers?alert=Supplier+API+updated+successfully!", status_code=status.HTTP_303_SEE_OTHER)

@web_app.post("/providers/{provider_id}/delete")
async def delete_provider_action(provider_id: int, admin: str = Depends(get_current_admin)):
    await delete_provider(provider_id)
    return RedirectResponse(url="/providers?alert=Supplier+removed+successfully", status_code=status.HTTP_303_SEE_OTHER)

@web_app.post("/providers/{provider_id}/test")
async def test_provider_action(provider_id: int, admin: str = Depends(get_current_admin)):
    provider = await get_provider(provider_id)
    if not provider:
        return JSONResponse(status_code=404, content={"success": False, "message": "Provider not found"})

    res = await test_provider_connection(
        api_url=provider["api_url"],
        api_key=provider["api_key"],
        api_secret=provider.get("api_secret", "")
    )

    if res.get("success") and res.get("balance") is not None:
        await update_provider_balance(provider_id, res["balance"])

    return JSONResponse(content={
        "success": res.get("success", False),
        "message": res.get("message", "Test completed"),
        "balance": res.get("balance")
    })

@web_app.get("/api/providers/{provider_id}/products")
async def api_get_provider_products(provider_id: int, sample: bool = False, admin: str = Depends(get_current_admin)):
    provider = await get_provider(provider_id)
    if not provider:
        return JSONResponse(status_code=404, content={"success": False, "error": "Provider not found", "products": []})

    if sample:
        products = get_sample_provider_products()
        return JSONResponse(content={
            "success": True,
            "provider_name": provider["name"],
            "products": products,
            "count": len(products),
            "is_sample": True,
            "message": f"Loaded {len(products)} sample products for preview/testing."
        })

    res = await fetch_provider_products(provider)
    res["provider_name"] = provider["name"]
    return JSONResponse(content=res)

@web_app.post("/api/products/quick-import")
async def api_quick_import_product(
    provider_id: int = Form(...),
    provider_product_id: str = Form(...),
    name: str = Form(...),
    price: float = Form(...),
    category_id: str = Form(""),
    provider_price: float = Form(0.0),
    description: str = Form(""),
    delivery_instructions: str = Form(""),
    admin: str = Depends(get_current_admin)
):
    cat_id = int(category_id) if category_id and category_id.isdigit() else None
    
    new_prod_id = await add_product(
        name=name.strip(),
        price=price,
        category_id=cat_id,
        description=description.strip() if description else f"Automated digital product delivered instantly via provider.",
        delivery_instructions=delivery_instructions.strip() if delivery_instructions else "Delivery format: Account Credentials / License Key. Do not change login details.",
        fulfillment_type="API",
        provider_id=provider_id,
        provider_product_id=provider_product_id.strip(),
        provider_price=provider_price
    )
    
    return JSONResponse(content={
        "success": True,
        "message": f"Successfully imported '{name}' to your bot store!",
        "product_id": new_prod_id
    })
