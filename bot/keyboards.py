from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, CopyTextButton

def main_reply_keyboard():
    """Persistent bottom keyboard for easy navigation"""
    keyboard = [
        [KeyboardButton(text="🛍️ SHOP"), KeyboardButton(text="👛 Wallet")],
        [KeyboardButton(text="😃 Profile"), KeyboardButton(text="📦 Purchase History")],
        [KeyboardButton(text="🎧 Support"), KeyboardButton(text="❓ Help")]
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

def main_inline_menu(trials_url: str = "https://t.me/Foxzenreseller", channel_url: str = None):
    """Colourful menu matching user UI with native primary, success, and danger styles"""
    target_channel = channel_url or trials_url or "https://t.me/Foxzenreseller"
    keyboard = [
        # Row 1: Full width SHOP button (Blue / Primary)
        [
            InlineKeyboardButton(text="🛍️ SHOP", callback_data="nav_products", style="primary")
        ],
        # Row 2: 3 buttons (Wallet=Green, Freebies=Blue, Profile=Green)
        [
            InlineKeyboardButton(text="👛 Wallet", callback_data="nav_wallet", style="success"),
            InlineKeyboardButton(text="🎁 Freebies", callback_data="nav_freebies", style="primary"),
            InlineKeyboardButton(text="😃 Profile", callback_data="nav_profile", style="success")
        ],
        # Row 3: Purchase History (Blue / Primary)
        [
            InlineKeyboardButton(text="📦 Purchase History", callback_data="nav_my_orders", style="primary")
        ],
        # Row 4: Support=Green, Help=Blue, Channel=Green
        [
            InlineKeyboardButton(text="🎧 Support", callback_data="nav_support", style="success"),
            InlineKeyboardButton(text="❓ Help", callback_data="nav_help", style="primary"),
            InlineKeyboardButton(text="📢 Channel ↗️", url=target_channel, style="success")
        ],
        # Row 5: Clear Chat=Red
        [
            InlineKeyboardButton(text="🧹 Clear Chat", callback_data="nav_clearchat", style="danger")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def wallet_keyboard():
    """Wallet options with colourful buttons"""
    keyboard = [
        [
            InlineKeyboardButton(text="💳 Deposit Balance (Binance Pay)", callback_data="wallet_deposit", style="success")
        ],
        [
            InlineKeyboardButton(text="📦 My Orders", callback_data="nav_my_orders", style="primary"),
            InlineKeyboardButton(text="🛍️ Go to Shop", callback_data="nav_products", style="primary")
        ],
        [
            InlineKeyboardButton(text="⬅️ Back", callback_data="nav_home"),
            InlineKeyboardButton(text="🏠 Main Menu", callback_data="nav_home")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def profile_keyboard():
    """Profile options"""
    keyboard = [
        [
            InlineKeyboardButton(text="📦 My Order History", callback_data="nav_my_orders", style="primary"),
            InlineKeyboardButton(text="👛 My Wallet", callback_data="nav_wallet", style="success")
        ],
        [
            InlineKeyboardButton(text="⬅️ Back", callback_data="nav_home"),
            InlineKeyboardButton(text="🏠 Main Menu", callback_data="nav_home")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def referral_keyboard(telegram_id: int, bot_username: str = "foxzen_bot", support_link: str = "@admin"):
    """Referral store buttons with copy link, claim reward, and share"""
    ref_link = f"https://t.me/{bot_username}?start=ref_{telegram_id}"
    share_text = f"https://t.me/share/url?url={ref_link}&text=🔥%20Get%20premium%20accounts%20at%20cheapest%20rates%20on%20Foxzen%20Store!"
    support_url = f"https://t.me/{support_link.replace('@', '')}" if support_link.startswith('@') else support_link
    
    keyboard = [
        [
            InlineKeyboardButton(text="📋 Copy Referral Link", copy_text=CopyTextButton(text=ref_link))
        ],
        [
            InlineKeyboardButton(text="🎁 Claim Free Surfshark VPN", callback_data="claim_surfshark", style="success")
        ],
        [
            InlineKeyboardButton(text="📤 Share with Friends", url=share_text, style="primary"),
            InlineKeyboardButton(text="🎧 Support", url=support_url, style="primary")
        ],
        [
            InlineKeyboardButton(text="⬅️ Back", callback_data="nav_home"),
            InlineKeyboardButton(text="🏠 Main Menu", callback_data="nav_home")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def back_to_home_keyboard():
    keyboard = [
        [
            InlineKeyboardButton(text="⬅️ Back", callback_data="nav_home"),
            InlineKeyboardButton(text="🏠 Main Menu", callback_data="nav_home")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def support_keyboard(support_link: str = "@foxzen_Digital"):
    """Keyboard with 1-click button to open support chat"""
    username = support_link.replace("@", "").strip()
    url = f"https://t.me/{username}" if not support_link.startswith("http") else support_link
    keyboard = [
        [
            InlineKeyboardButton(
                text=f"💬 Chat with Support ({support_link})",
                url=url,
                style="success"
            )
        ],
        [
            InlineKeyboardButton(text="⬅️ Back", callback_data="nav_home"),
            InlineKeyboardButton(text="🏠 Main Menu", callback_data="nav_home")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def reseller_keyboard():
    """Keyboard for reseller & channel join option"""
    keyboard = [
        [
            InlineKeyboardButton(
                text="📢 Join @Foxzenreseller Channel",
                url="https://t.me/Foxzenreseller",
                style="success"
            )
        ],
        [
            InlineKeyboardButton(text="⬅️ Back", callback_data="nav_home"),
            InlineKeyboardButton(text="🏠 Main Menu", callback_data="nav_home")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def shop_menu_keyboard():
    """Main shop screen keyboard: 1. View All Products (top), 2. Categories Wise, 3. Main Menu"""
    buttons = [
        [
            InlineKeyboardButton(
                text="🛒 View All Products",
                callback_data="cat_all",
                style="success"
            )
        ],
        [
            InlineKeyboardButton(
                text="📂 Categories Wise",
                callback_data="nav_categories",
                style="primary"
            )
        ],
        [
            InlineKeyboardButton(text="⬅️ Back", callback_data="nav_home"),
            InlineKeyboardButton(text="🏠 Main Menu", callback_data="nav_home")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def categories_keyboard(categories: list, has_uncategorized: bool = False):
    """List of product categories when user clicks Categories Wise"""
    buttons = []
    row = []
    for cat in categories:
        row.append(InlineKeyboardButton(
            text=f"{cat.get('icon', '📁')} {cat.get('name')}",
            callback_data=f"cat_{cat['id']}",
            style="primary"
        ))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    
    if has_uncategorized:
        buttons.append([
            InlineKeyboardButton(
                text="📦 Direct Products (No Category)",
                callback_data="cat_0",
                style="primary"
            )
        ])
    
    # Bottom controls
    buttons.append([
        InlineKeyboardButton(text="🛒 View All Products", callback_data="cat_all", style="success")
    ])
    buttons.append([
        InlineKeyboardButton(text="⬅️ Back", callback_data="nav_products"),
        InlineKeyboardButton(text="🏠 Main Menu", callback_data="nav_home")
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def products_keyboard(products: list, category_name: str = None):
    """List of products in a category or all"""
    buttons = []
    for p in products:
        stock_text = f"✅ Stock: {p['in_stock']}" if p['in_stock'] > 0 else "❌ Out of Stock"
        btn_style = "success" if p['in_stock'] > 0 else "danger"
        buttons.append([
            InlineKeyboardButton(
                text=f"{p['name']} | ${p['price']} ({stock_text})",
                callback_data=f"prod_{p['id']}",
                style=btn_style
            )
        ])
    
    back_target = "nav_categories" if category_name else "nav_products"
    buttons.append([
        InlineKeyboardButton(text="⬅️ Back", callback_data=back_target),
        InlineKeyboardButton(text="🏠 Main Menu", callback_data="nav_home")
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def product_detail_keyboard(product: dict):
    """Detailed product view keyboard with Buy Now leading to quantity selection"""
    buttons = []
    p_id = product["id"]
    in_stock = product.get("in_stock", 0) > 0
    cat_id = product.get("category_id")
    back_target = f"cat_{cat_id}" if cat_id else "nav_categories"
    
    if in_stock:
        buttons.append([
            InlineKeyboardButton(
                text=f"🟡 🛍️ Buy Now (${product['price']} USDT)",
                callback_data=f"selectqty_{p_id}_1",
                style="primary"
            )
        ])
        buttons.append([
            InlineKeyboardButton(
                text="🔵 👛 Pay with Wallet",
                callback_data=f"selectqty_{p_id}_1",
                style="primary"
            ),
            InlineKeyboardButton(
                text="🟡 💳 Binance Pay",
                callback_data=f"selectqty_{p_id}_1",
                style="primary"
            )
        ])
    else:
        buttons.append([
            InlineKeyboardButton(
                text="❌ ⚠️ Out of Stock (Check back later)",
                callback_data=f"out_of_stock_{p_id}",
                style="danger"
            )
        ])
        
    buttons.append([
        InlineKeyboardButton(text="🟡 📂 Categories Wise", callback_data="nav_categories", style="primary")
    ])
    buttons.append([
        InlineKeyboardButton(text="🔴 ⬅️ Back", callback_data=back_target, style="danger"),
        InlineKeyboardButton(text="🏠 Main Menu", callback_data="nav_home")
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def quantity_selection_keyboard(product: dict):
    """Quantity selection keyboard with Red, Blue, and Yellow styling:
    [ 🟡 Buy Quantity: ]
    [ 🔵 1 ] [ 🟡 All ({in_stock}) ]
    [ 🔵 Custom Quantity ] (blue primary)
    (No Set Price Alert as requested)
    [ 🔴 « Back to Shop ] (red danger)
    [ 🟡 ❓ Help ]
    """
    p_id = product["id"]
    in_stock = max(1, int(product.get("in_stock", 1)))
    
    buttons = [
        # Row 1: Header / Label button (Yellow)
        [
            InlineKeyboardButton(text="🟡 Buy Quantity:", callback_data="noop_qty", style="primary")
        ],
        # Row 2: 1 (Blue) | All (Yellow)
        [
            InlineKeyboardButton(text="🔵 1", callback_data=f"pickqty_{p_id}_1", style="primary"),
            InlineKeyboardButton(text=f"🟡 All ({in_stock})", callback_data=f"pickqty_{p_id}_{in_stock}", style="primary")
        ],
        # Row 3: Custom Quantity (Blue button)
        [
            InlineKeyboardButton(text="🔵 Custom Quantity", callback_data=f"customqty_{p_id}", style="primary")
        ],
        # Row 4: « Back to Shop (Red button)
        [
            InlineKeyboardButton(text="🔴 « Back to Shop", callback_data=f"prod_{p_id}", style="danger")
        ],
        # Row 5: ❓ Help (Yellow)
        [
            InlineKeyboardButton(text="🟡 ❓ Help", callback_data="nav_support")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def payment_selection_keyboard(product: dict, quantity: int = 1):
    """Payment methods keyboard shown after selecting quantity with Red, Blue, and Yellow styling"""
    p_id = product["id"]
    price = float(product["price"])
    total_amount = round(price * quantity, 2)
    
    buttons = [
        [
            InlineKeyboardButton(
                text=f"🔵 👛 Pay with Wallet (${total_amount:.2f} USDT)",
                callback_data=f"buywallet_{p_id}_{quantity}",
                style="primary"
            )
        ],
        [
            InlineKeyboardButton(
                text=f"🟡 💳 Pay with Binance Pay (${total_amount:.2f} USDT)",
                callback_data=f"buy_{p_id}_{quantity}",
                style="primary"
            )
        ],
        [
            InlineKeyboardButton(
                text="🔄 Change Quantity",
                callback_data=f"selectqty_{p_id}_1"
            )
        ],
        [
            InlineKeyboardButton(
                text="🔴 « Back to Shop",
                callback_data=f"prod_{p_id}",
                style="danger"
            ),
            InlineKeyboardButton(
                text="🏠 Main Menu",
                callback_data="nav_home"
            )
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def custom_quantity_keyboard(product_id: int):
    """Back button when typing custom quantity"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔴 « Back", callback_data=f"selectqty_{product_id}_1", style="danger")]
    ])

def order_actions_keyboard(order_id: str, pay_id: str = "717053382"):
    """Keyboard matching user screenshot with 1-tap Copy Binance ID button and Wallet Pay option"""
    buttons = [
        [
            InlineKeyboardButton(
                text="👛 Pay via Wallet Balance",
                callback_data=f"paywallet_{order_id}",
                style="primary"
            )
        ],
        [
            InlineKeyboardButton(
                text="📋 Copy Binance ID",
                copy_text=CopyTextButton(text=str(pay_id))
            )
        ],
        [
            InlineKeyboardButton(
                text="✅ Submit Binance TxID / Order ID",
                callback_data=f"submittx_{order_id}",
                style="success"
            )
        ],
        [
            InlineKeyboardButton(
                text="❌ Cancel Order",
                callback_data=f"cancelorder_{order_id}",
                style="danger"
            )
        ],
        [
            InlineKeyboardButton(text="⬅️ Back", callback_data="nav_products"),
            InlineKeyboardButton(text="🏠 Main Menu", callback_data="nav_home")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def confirm_wallet_buy_keyboard(product_id: int, total_price: float, quantity: int = 1):
    """Confirmation buttons for direct wallet purchase with quantity"""
    buttons = [
        [
            InlineKeyboardButton(
                text=f"✅ Confirm Purchase (${total_price:.2f} USDT)",
                callback_data=f"dobuywallet_{product_id}_{quantity}",
                style="success"
            )
        ],
        [
            InlineKeyboardButton(
                text="🔄 Change Quantity",
                callback_data=f"selectqty_{product_id}_1"
            ),
            InlineKeyboardButton(
                text="🔴 « Back to Shop",
                callback_data=f"prod_{product_id}",
                style="danger"
            )
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def confirm_wallet_payorder_keyboard(order_id: str, amount: float):
    """Confirmation buttons for paying an existing order via wallet"""
    buttons = [
        [
            InlineKeyboardButton(
                text=f"✅ Confirm & Pay (${amount} USDT)",
                callback_data=f"confirm_payorder_{order_id}",
                style="success"
            )
        ],
        [
            InlineKeyboardButton(
                text="⬅️ Back to Invoice",
                callback_data=f"backtoinvoice_{order_id}",
                style="danger"
            )
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def insufficient_wallet_keyboard(product_id: int = None, order_id: str = None, quantity: int = 1):
    """Keyboard when user does not have enough wallet balance"""
    buttons = [
        [
            InlineKeyboardButton(
                text="💳 Deposit Balance (Binance Pay)",
                callback_data="wallet_deposit",
                style="success"
            )
        ]
    ]
    if product_id:
        buttons.append([
            InlineKeyboardButton(
                text="💳 Pay with Binance Pay",
                callback_data=f"buy_{product_id}_{quantity}",
                style="success"
            )
        ])
        back_dest = f"selectqty_{product_id}_1"
    elif order_id:
        buttons.append([
            InlineKeyboardButton(
                text="⬅️ Back to Invoice",
                callback_data=f"backtoinvoice_{order_id}",
                style="primary"
            )
        ])
        back_dest = f"backtoinvoice_{order_id}"
    else:
        back_dest = "nav_wallet"
    
    buttons.append([
        InlineKeyboardButton(text="⬅️ Back", callback_data=back_dest),
        InlineKeyboardButton(text="🏠 Main Menu", callback_data="nav_home")
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def delivery_success_keyboard(order_id: str, credentials: str = None):
    """Buttons shown after instant delivery"""
    buttons = []
    if credentials:
        clean_copy = str(credentials).strip()
        # Telegram CopyTextButton only accepts 1-256 characters without carriage returns
        if 0 < len(clean_copy) <= 256 and "\n" not in clean_copy:
            try:
                buttons.append([
                    InlineKeyboardButton(text="📋 Copy Credentials", copy_text=CopyTextButton(text=clean_copy))
                ])
            except Exception:
                pass
    buttons.append([
        InlineKeyboardButton(
            text="📦 View in Purchase History",
            callback_data="nav_my_orders",
            style="primary"
        )
    ])
    buttons.append([
        InlineKeyboardButton(
            text="🛍️ Shop More",
            callback_data="nav_products",
            style="success"
        ),
        InlineKeyboardButton(
            text="🏠 Home",
            callback_data="nav_home",
            style="primary"
        )
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def wallet_deposit_keyboard(pay_id: str = "717053382"):
    """Keyboard for wallet deposit screen with Copy Binance ID button"""
    buttons = [
        [
            InlineKeyboardButton(
                text="📋 Copy Binance ID",
                copy_text=CopyTextButton(text=str(pay_id))
            )
        ],
        [
            InlineKeyboardButton(text="⬅️ Back", callback_data="nav_wallet"),
            InlineKeyboardButton(text="🏠 Main Menu", callback_data="nav_home")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def empty_orders_keyboard():
    """Keyboard shown when user has no completed orders"""
    buttons = [
        [InlineKeyboardButton(text="🛍️ Go to Shop", callback_data="nav_products", style="success")],
        [
            InlineKeyboardButton(text="⬅️ Back", callback_data="nav_home"),
            InlineKeyboardButton(text="🏠 Main Menu", callback_data="nav_home")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def my_orders_keyboard(orders: list):
    """List of user's past successful purchases"""
    buttons = []
    for o in orders:
        buttons.append([
            InlineKeyboardButton(
                text=f"✅ #{o['order_id']} - {o['product_name']} (${o['amount']})",
                callback_data=f"vieworder_{o['order_id']}",
                style="success"
            )
        ])
    buttons.append([
        InlineKeyboardButton(text="🛍️ Shop More", callback_data="nav_products", style="success")
    ])
    buttons.append([
        InlineKeyboardButton(text="⬅️ Back", callback_data="nav_home"),
        InlineKeyboardButton(text="🏠 Main Menu", callback_data="nav_home")
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def single_order_view_keyboard(order_id: str, status: str, pay_id: str = "717053382", credentials: str = None):
    """Action for a specific order view"""
    buttons = []
    if status == "COMPLETED" and credentials:
        buttons.append([
            InlineKeyboardButton(text="📋 Copy Credentials", copy_text=CopyTextButton(text=str(credentials)))
        ])
    elif status == "PENDING_PAYMENT":
        buttons.append([
            InlineKeyboardButton(text="📋 Copy Binance ID", copy_text=CopyTextButton(text=str(pay_id)))
        ])
        buttons.append([
            InlineKeyboardButton(text="✅ Submit Binance TxID", callback_data=f"submittx_{order_id}", style="success"),
            InlineKeyboardButton(text="❌ Cancel", callback_data=f"cancelorder_{order_id}", style="danger")
        ])
    elif status == "PENDING_VERIFICATION":
        buttons.append([
            InlineKeyboardButton(text="🔄 Check Status", callback_data=f"vieworder_{order_id}", style="primary")
        ])
    buttons.append([
        InlineKeyboardButton(text="⬅️ Back", callback_data="nav_my_orders"),
        InlineKeyboardButton(text="🏠 Main Menu", callback_data="nav_home")
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)
