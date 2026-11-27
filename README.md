# 🦊 Foxzen Bot - Digital Products Store & Binance Pay Auto-Delivery

Ek complete automated Telegram Shop Bot jisme customer Binance Pay se payment karega, payment verify hone par bot turant product ke login credentials deliver karega, aur aap pure bot aur products ko Web Admin Dashboard se manage kar sakte hain.

---

## 🌟 Key Features

1. **🛍️ Telegram Bot Store**:
   - Categories aur Products ka clean interactive inline catalog.
   - Real-time stock status (e.g. *5 Accounts Available* ya *Out of Stock*).
   - Instant Order Generation with unique Order ID (e.g. `#ORD-82914`).
   - Customer previous orders aur login credentials kabhi bhi dekh sakte hain (`📦 My Orders`).

2. **⚡ Binance Pay Instant Verification & Delivery**:
   - Customer ko payment instructions ke sath aapka **Binance Pay ID / UID** milta hai.
   - Customer payment karne ke baad apna **Binance Order ID / TxID** submit karta hai.
   - **Double-spend protection**: Ek Transaction ID do baar use nahi ho sakti.
   - **Binance API Verification**: Agar aapne Binance API Keys configure ki hain, to bot Binance se verify karke customer ko turant single-use account/credential deliver kar deta hai.
   - **Manual Admin Review Fallback**: Agar Binance API configured nahi hai ya verification pending hai, to Admin Web Dashboard se single-click **"Approve & Deliver"** kar sakta hai, jisse bot turant customer ko login details bhej deta hai.

3. **💻 Web Admin Dashboard (`http://localhost:8000`)**:
   - **Overview & Analytics**: Total Sales (USDT), Orders Count, In-Stock Accounts, Total Users.
   - **Products & Categories**: Products add/edit/delete karein, price USDT me set karein.
   - **Stock & Credentials Manager**: 50 ya 100 accounts ek sath copy-paste (bulk add) karein (e.g. `email:password`). Unsold vs Sold inventory track karein.
   - **Orders Management**: All transactions list, pending approvals, TxID check, 1-click Approve/Deliver ya Reject.
   - **Bot Broadcast**: Sabhi Telegram bot users ko ek sath mass message bhejein.
   - **Settings**: Binance Pay ID, Binance API Keys, Telegram Bot Token, Admin Telegram Alert ID aur Dashboard Password change karein.

---

## 🚀 Quick Start (Kaise Run Karein)

Terminal me Foxzen_bot folder me jaakar yeh command run karein:

```bash
./start.sh
```

Ya manual command:

```bash
.venv/bin/python main.py
```

Console par aayega:
```
=======================================================
🚀 Foxzen Bot & Web Admin Dashboard Starting...
🌐 Web Admin URL: http://localhost:8000
👤 Default Login: admin / admin123
=======================================================
```

Browser me open karein: **[http://localhost:8000](http://localhost:8000)**

---

## ⚙️ Step-by-Step Setup Guide

### 1. Web Dashboard me Login Karein
- URL: `http://localhost:8000/login`
- **Username:** `admin`
- **Password:** `admin123`
*(Aap ise **Settings** page par jakar change kar sakte hain).*

---

### 2. Telegram Bot Token Setup
1. Telegram par **[@BotFather](https://t.me/BotFather)** open karein.
2. `/newbot` command bhej kar apna bot banayein aur API Token copy karein.
3. Web Dashboard me **Settings** par jayein.
4. **Telegram Bot Token** field me token paste karein.
5. (Optional) **Admin Telegram Chat ID** dalein (apna Telegram ID @userinfobot se lekar daal sakte hain taaki jab bhi koi order aaye, aapko phone par instant Telegram notification mile).
6. **Save All Settings** click karein. Bot turant live ho jayega!

---

### 3. Binance Pay Setup
Web Dashboard ke **Settings** page me:
- **Binance Pay ID / UID**: Apna Binance Pay ID enter karein (Binance App ➡️ Profile ➡️ Pay me jakar aapko aapka Pay ID mil jayega).
- **Binance API Key & Secret (Optional)**:
  - Agar aap automated API check chahte hain: Binance account me jakar **API Management** me ek Read-only API key banayein aur yahan paste karein.
  - Web Dashboard par **"Test API Connection"** button daba kar test kar sakte hain.
  - *Note:* Agar aap API Key nahi bhi dalte hain, tab bhi customers payment karke TxID bhej sakte hain aur aap apne Binance app me payment dekh kar Dashboard se **1-Click "Approve & Deliver"** kar sakte hain!

---

### 4. Products aur Accounts (Stock) Add Karna
1. **Products & Catalog** page par jayein:
   - "Add New Product" click karein.
   - Name dalein (e.g. `Netflix Premium 1 Month` ya `NordVPN`).
   - Price USDT me dalein (e.g. `2.50`).
2. **Stock & Credentials** page par jayein:
   - "Bulk Add Credentials" click karein.
   - Product select karein.
   - Textarea me accounts paste karein (har line ek account/login key hoti hai):
     ```text
     user1@gmail.com:Pass123
     user2@gmail.com:Pass456
     user3@gmail.com:Pass789
     ```
   - "Upload Stock" click karein.
   - Ab bot me customer ko dikhega ki 3 accounts stock me available hain!

---

## 🔄 Customer Purchase & Delivery Flow

1. Customer Telegram bot me `/start` karega aur **"🛍️ Products Catalog"** par click karega.
2. Product select karke **"💳 Buy Now"** par click karega.
3. Bot Order generate karega (e.g. `#ORD-48192`) aur payment instructions dikhayega:
   - Binance Pay ID: `XXXXXX`
   - Exact USDT Amount
   - Remark / Note: `#ORD-48192`
4. Customer Binance App me payment send karke apna **Binance Transaction ID / Order ID** bot me submit karega.
5. **Instant Delivery**:
   - System payment verify karega.
   - Database se ek unsold account nikaal kar use **Sold** mark karega.
   - Customer ko turant clean format me login details code block me send kar dega:
     ```
     🎉 Payment Verified Successfully!
     Order ID: #ORD-48192
     Product: Netflix Premium 1 Month

     🔑 Your Login Details:
     user1@gmail.com:Pass123
     ```
6. Customer apne past orders aur login details bot ke **"📦 My Orders"** section me kabhi bhi dekh sakta hai!

---

## 📁 Project Structure

```
Foxzen_bot/
├── config.py              # Environment & application config
├── database.py            # SQLite schema, async CRUD & stock manager
├── binance.py             # Binance Pay API client & HMAC verification
├── main.py                # Main server launcher (FastAPI + Telegram Bot)
├── start.sh               # 1-click startup script
├── requirements.txt       # Python dependencies
├── .env                   # Configuration variables
├── bot/
│   ├── bot_instance.py    # Bot client & push notifications
│   ├── keyboards.py       # Inline & reply keyboards
│   └── handlers.py        # Bot command & purchase handlers
└── web/
    ├── app.py             # FastAPI routes & admin endpoints
    ├── auth.py            # Secure admin session cookies & authentication
    └── templates/         # Modern Tailwind CSS Dark Theme UI
        ├── base.html      # Responsive layout & sidebar
        ├── login.html     # Admin sign-in
        ├── dashboard.html # Analytics & quick orders
        ├── products.html  # Product catalog manager
        ├── stock.html     # Inventory & bulk accounts manager
        ├── orders.html    # Orders list & Binance verification
        ├── broadcast.html # Mass message sender to bot users
        └── settings.html  # Binance & Telegram settings
```
