import aiosqlite
import hashlib
import os
import json
from datetime import datetime
from contextlib import asynccontextmanager
from config import (
    DB_PATH,
    ADMIN_USERNAME,
    ADMIN_PASSWORD,
    BINANCE_PAY_ID,
    BINANCE_API_KEY,
    BINANCE_API_SECRET,
    BOT_TOKEN,
    ADMIN_TELEGRAM_ID
)

def hash_password(password: str, salt: str = None) -> str:
    """Hashes password with SHA256 and salt (format: salt$hash)"""
    if not salt:
        salt = os.urandom(16).hex()
    hashed = hashlib.sha256((salt + password).encode('utf-8')).hexdigest()
    return f"{salt}${hashed}"

def verify_password(password: str, stored_hash: str) -> bool:
    """Verifies a plain password against stored salt$hash"""
    if not stored_hash or "$" not in stored_hash:
        return False
    salt, actual_hash = stored_hash.split("$", 1)
    return hashlib.sha256((salt + password).encode('utf-8')).hexdigest() == actual_hash

@asynccontextmanager
async def get_db():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        yield db

async def init_db():
    """Initializes tables and default settings"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA foreign_keys = ON;")
        
        # Users Table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                telegram_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                balance REAL DEFAULT 0.0,
                referral_earnings REAL DEFAULT 0.0,
                referred_by INTEGER,
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        # Ensure columns exist if table was previously created
        cursor = await db.execute("PRAGMA table_info(users)")
        columns = [row[1] for row in await cursor.fetchall()]
        if "balance" not in columns:
            await db.execute("ALTER TABLE users ADD COLUMN balance REAL DEFAULT 0.0")
        if "referral_earnings" not in columns:
            await db.execute("ALTER TABLE users ADD COLUMN referral_earnings REAL DEFAULT 0.0")
        if "referred_by" not in columns:
            await db.execute("ALTER TABLE users ADD COLUMN referred_by INTEGER")
        
        # Categories Table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                icon TEXT DEFAULT '📁',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        
        # Products Table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category_id INTEGER,
                name TEXT NOT NULL,
                description TEXT,
                price REAL NOT NULL,
                image_url TEXT,
                delivery_instructions TEXT,
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE SET NULL
            );
        """)
        
        # Stock Items Table (Accounts / Credentials / Keys)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS stock_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER NOT NULL,
                data TEXT NOT NULL,
                is_sold INTEGER DEFAULT 0,
                sold_to_order_id TEXT,
                sold_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
            );
        """)
        
        # Orders Table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                order_id TEXT PRIMARY KEY,
                telegram_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                product_name TEXT NOT NULL,
                amount REAL NOT NULL,
                quantity INTEGER DEFAULT 1,
                status TEXT DEFAULT 'PENDING_PAYMENT',
                binance_tx_id TEXT,
                delivered_data TEXT,
                admin_notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE SET NULL
            );
        """)
        
        # Ensure quantity and provider columns exist for orders
        cursor = await db.execute("PRAGMA table_info(orders)")
        cols = [r[1] for r in await cursor.fetchall()]
        if "quantity" not in cols:
            await db.execute("ALTER TABLE orders ADD COLUMN quantity INTEGER DEFAULT 1")
        if "provider_order_id" not in cols:
            await db.execute("ALTER TABLE orders ADD COLUMN provider_order_id TEXT DEFAULT NULL")
        if "provider_response" not in cols:
            await db.execute("ALTER TABLE orders ADD COLUMN provider_response TEXT DEFAULT NULL")

        # Providers Table (Reseller / Supplier APIs)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS providers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                api_url TEXT NOT NULL,
                api_key TEXT NOT NULL,
                api_secret TEXT DEFAULT '',
                balance REAL DEFAULT 0.0,
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # Ensure provider and fulfillment columns exist for products
        cursor = await db.execute("PRAGMA table_info(products)")
        p_cols = [r[1] for r in await cursor.fetchall()]
        if "fulfillment_type" not in p_cols:
            await db.execute("ALTER TABLE products ADD COLUMN fulfillment_type TEXT DEFAULT 'LOCAL'")
        if "provider_id" not in p_cols:
            await db.execute("ALTER TABLE products ADD COLUMN provider_id INTEGER DEFAULT NULL")
        if "provider_product_id" not in p_cols:
            await db.execute("ALTER TABLE products ADD COLUMN provider_product_id TEXT DEFAULT NULL")
        if "provider_price" not in p_cols:
            await db.execute("ALTER TABLE products ADD COLUMN provider_price REAL DEFAULT 0.0")
        
        # Settings Table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            );
        """)
        
        await db.commit()

        # Insert initial settings if missing
        default_settings = {
            "admin_username": ADMIN_USERNAME,
            "admin_password_hash": hash_password(ADMIN_PASSWORD),
            "binance_pay_id": BINANCE_PAY_ID,
            "binance_api_key": BINANCE_API_KEY,
            "binance_api_secret": BINANCE_API_SECRET,
            "telegram_bot_token": BOT_TOKEN,
            "admin_telegram_id": ADMIN_TELEGRAM_ID,
            "welcome_message": "👋 Welcome to Foxzen Digital Store!\n\nChoose a product below to purchase. All payments are verified instantly via Binance Pay.",
            "support_link": "@admin",
            "qr_code_url": ""
        }
        
        for k, v in default_settings.items():
            await db.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, str(v or "")))
        
        # Insert sample category & product if database is empty
        cursor = await db.execute("SELECT COUNT(*) FROM categories")
        count = (await cursor.fetchone())[0]
        if count == 0:
            await db.execute("INSERT INTO categories (name, description, icon) VALUES ('Streaming & VPN', 'Premium streaming accounts and VPN services', '🎬')")
            await db.execute("INSERT INTO categories (name, description, icon) VALUES ('Mail & Webmail', 'Private outlook, hotmail & webmail accounts', '📧')")
            await db.execute("INSERT INTO categories (name, description, icon) VALUES ('Gaming & Gift Cards', 'Game keys, Steam & digital gift cards', '🎮')")
            await db.execute("INSERT INTO categories (name, description, icon) VALUES ('Software & Tools', 'Software licenses, utilities and subscriptions', '⚡')")
            cat_id = 1
            await db.execute("""
                INSERT INTO products (category_id, name, description, price, delivery_instructions) 
                VALUES (?, ?, ?, ?, ?)
            """, (
                cat_id,
                "NordVPN 1 Month Premium",
                "High speed ultra secure VPN account with 1 month warranty.",
                2.50,
                "Warranty: 30 days. Do not change the email or password."
            ))
            # Insert sample stock
            await db.execute("""
                INSERT INTO stock_items (product_id, data) VALUES (1, 'demo_user@vpnmail.com:SecurePass2026')
            """)
        
        await db.commit()

# --- User Functions ---
async def save_or_update_user(telegram_id: int, username: str, first_name: str, referred_by: int = None):
    async with get_db() as db:
        # Check if user already exists
        cursor = await db.execute("SELECT telegram_id, referred_by FROM users WHERE telegram_id = ?", (telegram_id,))
        existing = await cursor.fetchone()
        
        if existing:
            await db.execute("""
                UPDATE users SET
                    username = ?,
                    first_name = ?
                WHERE telegram_id = ?
            """, (username or "", first_name or "", telegram_id))
        else:
            # Valid referral if not referring themselves
            valid_ref = referred_by if (referred_by and referred_by != telegram_id) else None
            await db.execute("""
                INSERT INTO users (telegram_id, username, first_name, referred_by)
                VALUES (?, ?, ?, ?)
            """, (telegram_id, username or "", first_name or "", valid_ref))
        await db.commit()

async def get_user_profile(telegram_id: int):
    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))
        user = await cursor.fetchone()
        
        # Calculate total completed spent
        cursor = await db.execute("SELECT COALESCE(SUM(amount), 0) FROM orders WHERE telegram_id = ? AND status = 'COMPLETED'", (telegram_id,))
        total_spent = float((await cursor.fetchone())[0])
        
        # Count referrals
        cursor = await db.execute("SELECT COUNT(*) FROM users WHERE referred_by = ?", (telegram_id,))
        referrals_count = int((await cursor.fetchone())[0])
        
        # Determine membership tier
        if total_spent >= 100:
            membership = "🥇 Gold"
        elif total_spent >= 25:
            membership = "🥈 Silver"
        else:
            membership = "🥉 Bronze"
            
        balance = float(user["balance"]) if user and "balance" in user.keys() and user["balance"] is not None else 0.0
        ref_earnings = float(user["referral_earnings"]) if user and "referral_earnings" in user.keys() and user["referral_earnings"] is not None else 0.0
        
        return {
            "telegram_id": telegram_id,
            "username": user["username"] if user else "",
            "first_name": user["first_name"] if user else "User",
            "balance": balance,
            "total_spent": total_spent,
            "membership": membership,
            "referrals_count": referrals_count,
            "referral_earnings": ref_earnings,
            "joined_at": user["joined_at"] if user else ""
        }

async def get_all_user_ids():
    async with get_db() as db:
        cursor = await db.execute("SELECT telegram_id FROM users")
        rows = await cursor.fetchall()
        return [row[0] for row in rows]

async def get_all_users():
    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM users ORDER BY joined_at DESC")
        return [dict(row) for row in await cursor.fetchall()]

async def get_user_balance(telegram_id: int) -> float:
    async with get_db() as db:
        cursor = await db.execute("SELECT balance FROM users WHERE telegram_id = ?", (telegram_id,))
        row = await cursor.fetchone()
        return float(row[0]) if row and row[0] is not None else 0.0

async def update_user_balance(telegram_id: int, delta: float) -> float:
    async with get_db() as db:
        await db.execute("UPDATE users SET balance = balance + ? WHERE telegram_id = ?", (delta, telegram_id))
        await db.commit()
        cursor = await db.execute("SELECT balance FROM users WHERE telegram_id = ?", (telegram_id,))
        row = await cursor.fetchone()
        return float(row[0]) if row and row[0] is not None else 0.0

async def set_user_balance(telegram_id: int, new_balance: float) -> float:
    async with get_db() as db:
        await db.execute("UPDATE users SET balance = ? WHERE telegram_id = ?", (max(0.0, new_balance), telegram_id))
        await db.commit()
        return new_balance

# --- Category Functions ---
async def get_categories():
    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM categories ORDER BY id ASC")
        return [dict(row) for row in await cursor.fetchall()]

async def get_category(category_id: int):
    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM categories WHERE id = ?", (category_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None

async def add_category(name: str, description: str = "", icon: str = "📁"):
    async with get_db() as db:
        cursor = await db.execute("INSERT INTO categories (name, description, icon) VALUES (?, ?, ?)", (name, description, icon))
        await db.commit()
        return cursor.lastrowid

async def delete_category(category_id: int):
    async with get_db() as db:
        await db.execute("DELETE FROM categories WHERE id = ?", (category_id,))
        await db.commit()

# --- Reseller / Provider API Functions ---
async def get_providers(active_only: bool = False):
    async with get_db() as db:
        query = "SELECT * FROM providers"
        if active_only:
            query += " WHERE is_active = 1"
        query += " ORDER BY id DESC"
        cursor = await db.execute(query)
        return [dict(row) for row in await cursor.fetchall()]

async def get_provider(provider_id: int):
    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM providers WHERE id = ?", (provider_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None

async def add_provider(name: str, api_url: str, api_key: str, api_secret: str = "") -> int:
    async with get_db() as db:
        cursor = await db.execute("""
            INSERT INTO providers (name, api_url, api_key, api_secret, balance, is_active)
            VALUES (?, ?, ?, ?, 0.0, 1)
        """, (name.strip(), api_url.strip(), api_key.strip(), api_secret.strip()))
        await db.commit()
        return cursor.lastrowid

async def update_provider(provider_id: int, name: str, api_url: str, api_key: str, api_secret: str = "", is_active: int = 1):
    async with get_db() as db:
        now = datetime.now().isoformat()
        await db.execute("""
            UPDATE providers SET
                name = ?,
                api_url = ?,
                api_key = ?,
                api_secret = ?,
                is_active = ?,
                updated_at = ?
            WHERE id = ?
        """, (name.strip(), api_url.strip(), api_key.strip(), api_secret.strip(), is_active, now, provider_id))
        await db.commit()

async def delete_provider(provider_id: int):
    async with get_db() as db:
        await db.execute("DELETE FROM providers WHERE id = ?", (provider_id,))
        await db.execute("UPDATE products SET fulfillment_type = 'LOCAL', provider_id = NULL WHERE provider_id = ?", (provider_id,))
        await db.commit()

async def update_provider_balance(provider_id: int, balance: float):
    async with get_db() as db:
        await db.execute("UPDATE providers SET balance = ?, updated_at = ? WHERE id = ?", (balance, datetime.now().isoformat(), provider_id))
        await db.commit()

# --- Product Functions ---
async def get_products(category_id: int = None, active_only: bool = False):
    async with get_db() as db:
        query = """
            SELECT p.*, c.name as category_name, prv.name as provider_name,
                   CASE 
                       WHEN p.fulfillment_type = 'API' THEN 999
                       ELSE (SELECT COUNT(*) FROM stock_items s WHERE s.product_id = p.id AND s.is_sold = 0)
                   END as in_stock
            FROM products p
            LEFT JOIN categories c ON p.category_id = c.id
            LEFT JOIN providers prv ON p.provider_id = prv.id
        """
        conditions = []
        params = []
        if category_id == 0:
            conditions.append("p.category_id IS NULL")
        elif category_id is not None:
            conditions.append("p.category_id = ?")
            params.append(category_id)
        if active_only:
            conditions.append("p.is_active = 1")
            
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY p.id DESC"
        
        cursor = await db.execute(query, params)
        return [dict(row) for row in await cursor.fetchall()]

async def get_product(product_id: int):
    async with get_db() as db:
        cursor = await db.execute("""
            SELECT p.*, c.name as category_name, prv.name as provider_name,
                   CASE 
                       WHEN p.fulfillment_type = 'API' THEN 999
                       ELSE (SELECT COUNT(*) FROM stock_items s WHERE s.product_id = p.id AND s.is_sold = 0)
                   END as in_stock
            FROM products p
            LEFT JOIN categories c ON p.category_id = c.id
            LEFT JOIN providers prv ON p.provider_id = prv.id
            WHERE p.id = ?
        """, (product_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None

async def add_product(
    category_id: int, 
    name: str, 
    description: str, 
    price: float, 
    delivery_instructions: str, 
    image_url: str = "",
    fulfillment_type: str = "LOCAL",
    provider_id: int = None,
    provider_product_id: str = None,
    provider_price: float = 0.0
):
    async with get_db() as db:
        cursor = await db.execute("""
            INSERT INTO products (
                category_id, name, description, price, delivery_instructions, image_url,
                fulfillment_type, provider_id, provider_product_id, provider_price
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            category_id, name, description, price, delivery_instructions, image_url,
            fulfillment_type, provider_id, provider_product_id, provider_price
        ))
        await db.commit()
        return cursor.lastrowid

async def update_product(
    product_id: int, 
    category_id: int, 
    name: str, 
    description: str, 
    price: float, 
    delivery_instructions: str, 
    is_active: int,
    fulfillment_type: str = "LOCAL",
    provider_id: int = None,
    provider_product_id: str = None,
    provider_price: float = 0.0
):
    async with get_db() as db:
        await db.execute("""
            UPDATE products SET
                category_id = ?,
                name = ?,
                description = ?,
                price = ?,
                delivery_instructions = ?,
                is_active = ?,
                fulfillment_type = ?,
                provider_id = ?,
                provider_product_id = ?,
                provider_price = ?
            WHERE id = ?
        """, (
            category_id, name, description, price, delivery_instructions, is_active,
            fulfillment_type, provider_id, provider_product_id, provider_price, product_id
        ))
        await db.commit()
        await db.commit()

async def delete_product(product_id: int):
    async with get_db() as db:
        await db.execute("DELETE FROM products WHERE id = ?", (product_id,))
        await db.commit()

# --- Stock Functions ---
async def add_stock_items(product_id: int, items_list: list[str]):
    async with get_db() as db:
        cleaned = [item.strip() for item in items_list if item.strip()]
        for item in cleaned:
            await db.execute("INSERT INTO stock_items (product_id, data) VALUES (?, ?)", (product_id, item))
        await db.commit()
        return len(cleaned)

async def get_stock_items(product_id: int):
    async with get_db() as db:
        cursor = await db.execute("""
            SELECT * FROM stock_items WHERE product_id = ? ORDER BY is_sold ASC, id DESC
        """, (product_id,))
        return [dict(row) for row in await cursor.fetchall()]

async def pop_available_stock(product_id: int, order_id: str, count: int = 1):
    """Picks `count` unsold items, marks them sold, and returns their formatted data"""
    async with get_db() as db:
        cursor = await db.execute("""
            SELECT id, data FROM stock_items 
            WHERE product_id = ? AND is_sold = 0 
            ORDER BY id ASC LIMIT ?
        """, (product_id, count))
        rows = await cursor.fetchall()
        if len(rows) < count:
            return None
        
        stock_ids = [r[0] for r in rows]
        datas = [r[1] for r in rows]
        now = datetime.now().isoformat()
        
        placeholders = ",".join("?" * len(stock_ids))
        await db.execute(f"""
            UPDATE stock_items 
            SET is_sold = 1, sold_to_order_id = ?, sold_at = ?
            WHERE id IN ({placeholders})
        """, (order_id, now, *stock_ids))
        await db.commit()
        
        if count > 1:
            formatted = [f"📦 [Item #{i}]:\n{d}" for i, d in enumerate(datas, 1)]
            return "\n\n".join(formatted)
        return datas[0]

async def delete_stock_item(stock_id: int):
    async with get_db() as db:
        await db.execute("DELETE FROM stock_items WHERE id = ? AND is_sold = 0", (stock_id,))
        await db.commit()

# --- Order Functions ---
async def create_order(order_id: str, telegram_id: int, product_id: int, product_name: str, amount: float, quantity: int = 1):
    async with get_db() as db:
        await db.execute("""
            INSERT INTO orders (order_id, telegram_id, product_id, product_name, amount, quantity, status)
            VALUES (?, ?, ?, ?, ?, ?, 'PENDING_PAYMENT')
        """, (order_id, telegram_id, product_id, product_name, amount, quantity))
        await db.commit()

async def get_order(order_id: str):
    async with get_db() as db:
        cursor = await db.execute("""
            SELECT o.*, u.username, u.first_name 
            FROM orders o
            LEFT JOIN users u ON o.telegram_id = u.telegram_id
            WHERE o.order_id = ?
        """, (order_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None

async def get_active_order_for_user(telegram_id: int):
    async with get_db() as db:
        cursor = await db.execute("""
            SELECT * FROM orders 
            WHERE telegram_id = ? AND status IN ('PENDING_PAYMENT', 'PENDING_VERIFICATION')
            ORDER BY created_at DESC LIMIT 1
        """, (telegram_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None

async def cancel_unpaid_orders_for_user(telegram_id: int):
    """Silently cancels any uncompleted PENDING_PAYMENT order so user is never blocked"""
    async with get_db() as db:
        await db.execute("""
            UPDATE orders SET status = 'CANCELLED', admin_notes = 'Superseded by new checkout attempt'
            WHERE telegram_id = ? AND status = 'PENDING_PAYMENT'
        """, (telegram_id,))
        await db.commit()

async def get_user_orders(telegram_id: int, limit: int = 20, status: str = "COMPLETED"):
    """Returns user orders, defaulting to ONLY completed successful purchases"""
    async with get_db() as db:
        if status:
            cursor = await db.execute("""
                SELECT * FROM orders 
                WHERE telegram_id = ? AND status = ? 
                ORDER BY created_at DESC LIMIT ?
            """, (telegram_id, status, limit))
        else:
            cursor = await db.execute("""
                SELECT * FROM orders 
                WHERE telegram_id = ? 
                ORDER BY created_at DESC LIMIT ?
            """, (telegram_id, limit))
        return [dict(row) for row in await cursor.fetchall()]

async def get_all_orders(status: str = None, limit: int = 100):
    async with get_db() as db:
        query = """
            SELECT o.*, u.username, u.first_name 
            FROM orders o
            LEFT JOIN users u ON o.telegram_id = u.telegram_id
        """
        params = []
        if status:
            query += " WHERE o.status = ?"
            params.append(status)
        query += " ORDER BY o.created_at DESC LIMIT ?"
        params.append(limit)
        cursor = await db.execute(query, params)
        return [dict(row) for row in await cursor.fetchall()]

async def submit_order_tx_id(order_id: str, binance_tx_id: str):
    async with get_db() as db:
        now = datetime.now().isoformat()
        await db.execute("""
            UPDATE orders SET 
                binance_tx_id = ?, 
                status = 'PENDING_VERIFICATION',
                updated_at = ?
            WHERE order_id = ?
        """, (binance_tx_id.strip(), now, order_id))
        await db.commit()

async def is_txid_used(tx_id: str, current_order_id: str = None) -> bool:
    """Checks if a Binance TxID is already used in a completed order"""
    async with get_db() as db:
        query = "SELECT COUNT(*) FROM orders WHERE binance_tx_id = ? AND status = 'COMPLETED'"
        params = [tx_id.strip()]
        if current_order_id:
            query += " AND order_id != ?"
            params.append(current_order_id)
        cursor = await db.execute(query, params)
        count = (await cursor.fetchone())[0]
        return count > 0

async def complete_order(order_id: str, delivered_data: str):
    async with get_db() as db:
        now = datetime.now().isoformat()
        await db.execute("""
            UPDATE orders SET 
                status = 'COMPLETED',
                delivered_data = ?,
                updated_at = ?
            WHERE order_id = ?
        """, (delivered_data, now, order_id))
        await db.commit()

async def cancel_order(order_id: str, reason: str = ""):
    async with get_db() as db:
        now = datetime.now().isoformat()
        await db.execute("""
            UPDATE orders SET 
                status = 'CANCELLED',
                admin_notes = ?,
                updated_at = ?
            WHERE order_id = ?
        """, (reason, now, order_id))
        await db.commit()

async def fulfill_order_and_get_stock(order_id: str) -> dict:
    """
    Retrieves credentials for an order:
    - If product is 'API': automatically purchases from reseller provider API.
    - If product is 'LOCAL': pops from local stock_items.
    """
    order = await get_order(order_id)
    if not order:
        return {"success": False, "error": "Order not found"}
        
    p = await get_product(order["product_id"])
    if not p:
        return {"success": False, "error": "Product not found"}
        
    qty = int(order.get("quantity") or 1)
    
    if p.get("fulfillment_type") == "API":
        provider_id = p.get("provider_id")
        provider = await get_provider(provider_id)
        if not provider:
            return {"success": False, "error": "Configured Reseller Provider not found"}
            
        from reseller_api import order_from_provider
        api_res = await order_from_provider(
            provider=provider,
            provider_product_id=p.get("provider_product_id") or str(p["id"]),
            quantity=qty,
            order_id=order_id
        )
        if not api_res.get("success"):
            return {"success": False, "error": api_res.get("error", "Supplier purchase failed")}
            
        delivered_data = api_res["delivered_data"]
        prov_order_id = api_res.get("provider_order_id", "")
        
        async with get_db() as db:
            now = datetime.now().isoformat()
            await db.execute("""
                UPDATE orders SET 
                    delivered_data = ?, 
                    provider_order_id = ?,
                    admin_notes = 'Auto-fulfilled via Reseller API',
                    updated_at = ?
                WHERE order_id = ?
            """, (delivered_data, prov_order_id, now, order_id))
            await db.commit()
            
        return {
            "success": True, 
            "delivered_data": delivered_data, 
            "provider_order_id": prov_order_id, 
            "is_api": True,
            "provider_name": provider.get("name")
        }
    else:
        stock_data = await pop_available_stock(order["product_id"], order_id, count=qty)
        if not stock_data:
            return {"success": False, "error": "out_of_stock"}
        return {"success": True, "delivered_data": stock_data, "is_api": False}

async def execute_wallet_purchase(order_id: str, telegram_id: int) -> dict:
    """Executes instant wallet payment: checks balance, pops stock or buys from API, deducts balance, marks completed"""
    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM orders WHERE order_id = ?", (order_id,))
        order_row = await cursor.fetchone()
        if not order_row:
            return {"success": False, "error": "Order not found."}
        order = dict(order_row)
        if order["status"] == "COMPLETED":
            return {"success": False, "error": "Order is already completed!"}
        if order["status"] == "CANCELLED":
            return {"success": False, "error": "This order was cancelled."}

        cursor = await db.execute("SELECT balance FROM users WHERE telegram_id = ?", (telegram_id,))
        user_row = await cursor.fetchone()
        balance = float(user_row[0]) if user_row and user_row[0] is not None else 0.0

        if balance < order["amount"]:
            return {
                "success": False, 
                "error": "insufficient_balance", 
                "balance": balance, 
                "required": order["amount"],
                "order": order
            }

        qty = int(order.get("quantity") or 1)
        now = datetime.now().isoformat()

        cursor = await db.execute("SELECT * FROM products WHERE id = ?", (order["product_id"],))
        p_row = await cursor.fetchone()
        product = dict(p_row) if p_row else None

        if product and product.get("fulfillment_type") == "API":
            provider_id = product.get("provider_id")
            cursor = await db.execute("SELECT * FROM providers WHERE id = ?", (provider_id,))
            prov_row = await cursor.fetchone()
            if not prov_row:
                return {"success": False, "error": "Supplier provider not found."}
            provider = dict(prov_row)

            from reseller_api import order_from_provider
            api_res = await order_from_provider(
                provider=provider,
                provider_product_id=product.get("provider_product_id") or str(product["id"]),
                quantity=qty,
                order_id=order_id
            )
            if not api_res.get("success"):
                return {"success": False, "error": f"Supplier Error: {api_res.get('error', 'Purchase failed')}"}

            delivered_data = api_res["delivered_data"]
            prov_order_id = api_res.get("provider_order_id", "")

            # Deduct balance
            await db.execute("""
                UPDATE users 
                SET balance = MAX(0.0, balance - ?) 
                WHERE telegram_id = ?
            """, (order["amount"], telegram_id))

            # Mark completed
            await db.execute("""
                UPDATE orders SET 
                    status = 'COMPLETED',
                    binance_tx_id = 'WALLET_BALANCE',
                    delivered_data = ?,
                    provider_order_id = ?,
                    admin_notes = 'Auto-fulfilled via Reseller API',
                    updated_at = ?
                WHERE order_id = ?
            """, (delivered_data, prov_order_id, now, order_id))

            await db.commit()

            new_balance = round(balance - order["amount"], 2)
            return {
                "success": True,
                "order": order,
                "delivered_data": delivered_data,
                "amount": order["amount"],
                "remaining_balance": new_balance,
                "provider_name": provider.get("name")
            }

        # Local stock branch
        cursor = await db.execute("""
            SELECT id, data FROM stock_items 
            WHERE product_id = ? AND is_sold = 0 
            ORDER BY id ASC LIMIT ?
        """, (order["product_id"], qty))
        stock_rows = await cursor.fetchall()
        if len(stock_rows) < qty:
            return {"success": False, "error": "out_of_stock", "order": order}

        stock_ids = [r[0] for r in stock_rows]
        datas = [r[1] for r in stock_rows]
        delivered_data = "\n\n".join([f"📦 [Item #{i}]:\n{d}" for i, d in enumerate(datas, 1)]) if qty > 1 else datas[0]

        # Mark stock sold
        placeholders = ",".join("?" * len(stock_ids))
        await db.execute(f"""
            UPDATE stock_items 
            SET is_sold = 1, sold_to_order_id = ?, sold_at = ?
            WHERE id IN ({placeholders})
        """, (order_id, now, *stock_ids))

        # Deduct balance
        await db.execute("""
            UPDATE users 
            SET balance = MAX(0.0, balance - ?) 
            WHERE telegram_id = ?
        """, (order["amount"], telegram_id))

        # Mark completed
        await db.execute("""
            UPDATE orders SET 
                status = 'COMPLETED',
                binance_tx_id = 'WALLET_BALANCE',
                delivered_data = ?,
                admin_notes = 'Paid via Wallet Balance',
                updated_at = ?
            WHERE order_id = ?
        """, (delivered_data, now, order_id))

        await db.commit()

        new_balance = round(balance - order["amount"], 2)
        return {
            "success": True,
            "order": order,
            "delivered_data": delivered_data,
            "amount": order["amount"],
            "remaining_balance": new_balance
        }

async def create_and_pay_wallet_order(telegram_id: int, product_id: int, quantity: int = 1) -> dict:
    """Creates a new order and completes it using wallet balance (handles both Reseller API and local stock)"""
    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM products WHERE id = ?", (product_id,))
        p_row = await cursor.fetchone()
        if not p_row:
            return {"success": False, "error": "Product not found."}
        product = dict(p_row)
        
        total_amount = round(float(product["price"]) * quantity, 2)
        
        cursor = await db.execute("SELECT balance FROM users WHERE telegram_id = ?", (telegram_id,))
        user_row = await cursor.fetchone()
        balance = float(user_row[0]) if user_row and user_row[0] is not None else 0.0

        if balance < total_amount:
            return {
                "success": False,
                "error": "insufficient_balance",
                "balance": balance,
                "required": total_amount,
                "product": product,
                "quantity": quantity
            }

        now = datetime.now().isoformat()
        import random
        order_id = f"ORD-{random.randint(10000, 99999)}"
        prod_display_name = f"{product['name']} (x{quantity})" if quantity > 1 else product['name']

        # Branch 1: Fulfilled via Reseller Provider API
        if product.get("fulfillment_type") == "API":
            provider_id = product.get("provider_id")
            if not provider_id:
                return {"success": False, "error": "Supplier API provider is not configured for this product."}

            cursor = await db.execute("SELECT * FROM providers WHERE id = ?", (provider_id,))
            prov_row = await cursor.fetchone()
            if not prov_row:
                return {"success": False, "error": "Configured supplier was not found."}
            provider = dict(prov_row)

            from reseller_api import order_from_provider
            api_res = await order_from_provider(
                provider=provider,
                provider_product_id=product.get("provider_product_id") or str(product["id"]),
                quantity=quantity,
                order_id=order_id
            )

            if not api_res.get("success"):
                error_msg = api_res.get("error", "Supplier purchase failed.")
                logger.error(f"Supplier API purchase failed for order {order_id}: {error_msg}")
                return {"success": False, "error": f"Supplier Error: {error_msg}"}

            delivered_data = api_res["delivered_data"]
            prov_order_id = api_res.get("provider_order_id", "")

            # Deduct wallet balance
            await db.execute("""
                UPDATE users 
                SET balance = MAX(0.0, balance - ?) 
                WHERE telegram_id = ?
            """, (total_amount, telegram_id))

            # Insert completed order
            await db.execute("""
                INSERT INTO orders (order_id, telegram_id, product_id, product_name, amount, quantity, status, binance_tx_id, delivered_data, provider_order_id, admin_notes, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, 'COMPLETED', 'WALLET_BALANCE', ?, ?, 'Auto-fulfilled via Reseller API', ?)
            """, (order_id, telegram_id, product["id"], prod_display_name, total_amount, quantity, delivered_data, prov_order_id, now))

            await db.commit()

            new_balance = round(balance - total_amount, 2)
            return {
                "success": True,
                "order_id": order_id,
                "product_name": prod_display_name,
                "amount": total_amount,
                "remaining_balance": new_balance,
                "delivered_data": delivered_data,
                "quantity": quantity,
                "provider_name": provider.get("name"),
                "is_reseller_api": True
            }

        # Branch 2: Local Stock Fulfillment
        cursor = await db.execute("""
            SELECT id, data FROM stock_items 
            WHERE product_id = ? AND is_sold = 0 
            ORDER BY id ASC LIMIT ?
        """, (product_id, quantity))
        stock_rows = await cursor.fetchall()
        if len(stock_rows) < quantity:
            return {"success": False, "error": "out_of_stock", "product": product, "available": len(stock_rows)}

        stock_ids = [r[0] for r in stock_rows]
        datas = [r[1] for r in stock_rows]
        delivered_data = "\n\n".join([f"📦 [Item #{i}]:\n{d}" for i, d in enumerate(datas, 1)]) if quantity > 1 else datas[0]

        # Mark stock sold
        placeholders = ",".join("?" * len(stock_ids))
        await db.execute(f"""
            UPDATE stock_items 
            SET is_sold = 1, sold_to_order_id = ?, sold_at = ?
            WHERE id IN ({placeholders})
        """, (order_id, now, *stock_ids))

        # Deduct balance
        await db.execute("""
            UPDATE users 
            SET balance = MAX(0.0, balance - ?) 
            WHERE telegram_id = ?
        """, (total_amount, telegram_id))

        # Insert completed order
        await db.execute("""
            INSERT INTO orders (order_id, telegram_id, product_id, product_name, amount, quantity, status, binance_tx_id, delivered_data, admin_notes, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, 'COMPLETED', 'WALLET_BALANCE', ?, 'Paid via Wallet Balance', ?)
        """, (order_id, telegram_id, product["id"], prod_display_name, total_amount, quantity, delivered_data, now))

        await db.commit()

        new_balance = round(balance - total_amount, 2)
        return {
            "success": True,
            "order_id": order_id,
            "product_name": prod_display_name,
            "amount": total_amount,
            "remaining_balance": new_balance,
            "delivered_data": delivered_data,
            "quantity": quantity,
            "is_reseller_api": False
        }

# --- Settings Functions ---
async def get_setting(key: str, default: str = "") -> str:
    async with get_db() as db:
        cursor = await db.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = await cursor.fetchone()
        return row[0] if row else default

async def get_all_settings() -> dict:
    async with get_db() as db:
        cursor = await db.execute("SELECT key, value FROM settings")
        rows = await cursor.fetchall()
        return {row[0]: row[1] for row in rows}

async def update_settings(settings_dict: dict):
    async with get_db() as db:
        for k, v in settings_dict.items():
            await db.execute("""
                INSERT INTO settings (key, value) VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """, (k, str(v or "")))
        await db.commit()

async def update_setting(key: str, value: str):
    await update_settings({key: value})

# --- Dashboard Stats ---
async def get_dashboard_stats():
    async with get_db() as db:
        # Total revenue
        c1 = await db.execute("SELECT COALESCE(SUM(amount), 0) FROM orders WHERE status = 'COMPLETED'")
        total_revenue = (await c1.fetchone())[0]
        
        # Order counts
        c2 = await db.execute("SELECT COUNT(*) FROM orders")
        total_orders = (await c2.fetchone())[0]
        
        c3 = await db.execute("SELECT COUNT(*) FROM orders WHERE status = 'PENDING_VERIFICATION'")
        pending_orders = (await c3.fetchone())[0]
        
        c4 = await db.execute("SELECT COUNT(*) FROM orders WHERE status = 'COMPLETED'")
        completed_orders = (await c4.fetchone())[0]
        
        # Total users
        c5 = await db.execute("SELECT COUNT(*) FROM users")
        total_users = (await c5.fetchone())[0]
        
        # In-stock items
        c6 = await db.execute("SELECT COUNT(*) FROM stock_items WHERE is_sold = 0")
        total_in_stock = (await c6.fetchone())[0]
        
        # Total products
        c7 = await db.execute("SELECT COUNT(*) FROM products")
        total_products = (await c7.fetchone())[0]

        # Total user wallet balances
        c8 = await db.execute("SELECT COALESCE(SUM(balance), 0) FROM users")
        total_user_balance = (await c8.fetchone())[0]

        # Unpaid / Checkout attempts (visited and clicked buy without paying)
        c9 = await db.execute("SELECT COUNT(*) FROM orders WHERE status = 'PENDING_PAYMENT'")
        unpaid_attempts = (await c9.fetchone())[0]
        
        return {
            "total_revenue": round(float(total_revenue), 2),
            "total_orders": total_orders,
            "pending_orders": pending_orders,
            "completed_orders": completed_orders,
            "total_users": total_users,
            "total_in_stock": total_in_stock,
            "total_products": total_products,
            "total_user_balance": round(float(total_user_balance), 2),
            "unpaid_attempts": unpaid_attempts
        }
