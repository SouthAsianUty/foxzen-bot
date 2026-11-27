import logging
import asyncio
from typing import Dict, Any, Optional
import aiohttp

logger = logging.getLogger(__name__)

async def test_provider_connection(api_url: str, api_key: str, api_secret: str = "") -> Dict[str, Any]:
    """
    Tests connection to a reseller/supplier API using standard digital store API format.
    Checks connectivity and attempts to retrieve account balance or status.
    """
    base_url = api_url.strip().rstrip("/")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "X-API-Key": api_key,
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "FoxzenStore/2.0"
    }

    # Try common balance/status endpoints
    test_endpoints = [
        f"{base_url}/balance",
        f"{base_url}/wallet",
        f"{base_url}/ping",
        f"{base_url}/user/balance",
        f"{base_url}/account",
        f"{base_url}/status",
        base_url
    ]

    timeout = aiohttp.ClientTimeout(total=12)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        for endpoint in test_endpoints:
            try:
                # First try GET
                async with session.get(endpoint, headers=headers) as resp:
                    if resp.status in (200, 201):
                        try:
                            data = await resp.json()
                            balance = _extract_balance(data)
                            return {
                                "success": True,
                                "status_code": resp.status,
                                "balance": balance,
                                "message": f"Connection successful! {f'Balance: ${balance:.2f} USDT' if balance is not None else 'API is reachable.'}",
                                "data": data
                            }
                        except Exception:
                            text = await resp.text()
                            return {
                                "success": True,
                                "status_code": resp.status,
                                "balance": None,
                                "message": "Connection successful (Server responded with HTTP 200).",
                                "raw": text[:200]
                            }
                    elif resp.status == 401 or resp.status == 403:
                        return {
                            "success": False,
                            "status_code": resp.status,
                            "message": "Authentication failed! Invalid API Key or Unauthorized."
                        }
            except aiohttp.ClientConnectorError as e:
                return {
                    "success": False,
                    "status_code": 0,
                    "message": f"Cannot connect to host: {e}"
                }
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.debug(f"Error testing endpoint {endpoint}: {e}")
                continue

            # Try POST with payload if GET returned 404/405
            try:
                payload = {"api_key": api_key, "action": "balance"}
                async with session.post(endpoint, json=payload, headers=headers) as resp:
                    if resp.status in (200, 201):
                        data = await resp.json()
                        balance = _extract_balance(data)
                        return {
                            "success": True,
                            "status_code": resp.status,
                            "balance": balance,
                            "message": f"Connection successful! {f'Balance: ${balance:.2f} USDT' if balance is not None else 'API responded.'}",
                            "data": data
                        }
            except Exception:
                pass

    return {
        "success": False,
        "status_code": 0,
        "message": "Could not establish connection to the provider API. Please check the API URL and Key."
    }

async def check_provider_balance(provider: dict) -> Optional[float]:
    """Queries provider to fetch remaining balance"""
    api_url = provider.get("api_url", "").strip().rstrip("/")
    api_key = provider.get("api_key", "").strip()
    if not api_url or not api_key:
        return None

    res = await test_provider_connection(api_url, api_key, provider.get("api_secret", ""))
    if res.get("success") and res.get("balance") is not None:
        return res["balance"]
    return None

async def fetch_provider_products(provider: dict) -> Dict[str, Any]:
    """
    Fetches the catalog of products / services offered by the provider.
    Tries common digital goods / SMM provider endpoints:
      1. POST {base_url} with {"action": "services", "key": api_key} (Standard SMM / Account Panel)
      2. POST {base_url} with {"action": "products", "api_key": api_key}
      3. GET {base_url}/products
      4. GET {base_url}/services
      5. GET {base_url}/catalog
      6. GET {base_url}/items
      7. GET {base_url}?action=services&key={api_key}
    Returns standardized list of products.
    """
    api_url = provider.get("api_url", "").strip().rstrip("/")
    api_key = provider.get("api_key", "").strip()

    if not api_url or not api_key:
        return {
            "success": False,
            "error": "Provider API URL or API Key is missing.",
            "products": []
        }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "X-API-Key": api_key,
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "FoxzenStore/2.0"
    }

    timeout = aiohttp.ClientTimeout(total=15)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        # Strategy 1: Standard POST actions (services, products)
        post_variants = [
            {"action": "services", "key": api_key},
            {"action": "services", "api_key": api_key},
            {"action": "products", "key": api_key},
            {"action": "products", "api_key": api_key},
            {"action": "catalog", "key": api_key}
        ]

        # Targets to try POST
        post_endpoints = [api_url]
        if not api_url.endswith("/services") and not api_url.endswith("/products"):
            post_endpoints.append(f"{api_url}/services")
            post_endpoints.append(f"{api_url}/products")

        for endpoint in post_endpoints:
            for payload in post_variants:
                try:
                    async with session.post(endpoint, json=payload, headers=headers) as resp:
                        if resp.status in (200, 201):
                            data = await resp.json()
                            products = _parse_product_list(data)
                            if products:
                                return {
                                    "success": True,
                                    "products": products,
                                    "count": len(products),
                                    "endpoint": endpoint,
                                    "message": f"Successfully retrieved {len(products)} products from supplier!"
                                }
                except Exception as e:
                    logger.debug(f"POST {endpoint} attempt failed: {e}")
                    continue

        # Strategy 2: GET endpoints
        get_endpoints = [
            f"{api_url}/products?inStock=true&all=true",
            f"{api_url}/products?inStock=true",
            f"{api_url}/products",
            f"{api_url}/services",
            f"{api_url}/catalog",
            f"{api_url}/items",
            f"{api_url}/api/v1/products",
            f"{api_url}?action=services&key={api_key}",
            f"{api_url}?action=services&api_key={api_key}",
            f"{api_url}?action=products&key={api_key}",
            api_url
        ]

        for endpoint in get_endpoints:
            try:
                async with session.get(endpoint, headers=headers) as resp:
                    if resp.status in (200, 201):
                        data = await resp.json()
                        products = _parse_product_list(data)
                        if products:
                            return {
                                "success": True,
                                "products": products,
                                "count": len(products),
                                "endpoint": endpoint,
                                "message": f"Successfully retrieved {len(products)} products from supplier!"
                            }
            except Exception as e:
                logger.debug(f"GET {endpoint} attempt failed: {e}")
                continue

    return {
        "success": False,
        "error": "Could not automatically fetch products catalog from this supplier URL. The supplier may not support a public services endpoint, or requires a custom route.",
        "products": []
    }

def _parse_product_list(data: Any) -> list:
    """Extracts and normalizes product items from different JSON structures"""
    raw_list = []
    if isinstance(data, list):
        raw_list = data
    elif isinstance(data, dict):
        for key in ["products", "services", "data", "items", "result", "payload", "catalog"]:
            if key in data and isinstance(data[key], list):
                raw_list = data[key]
                break
        if not raw_list and "data" in data and isinstance(data["data"], dict):
            for key in ["products", "services", "items"]:
                if key in data["data"] and isinstance(data["data"][key], list):
                    raw_list = data["data"][key]
                    break

    normalized = []
    for item in raw_list:
        if not isinstance(item, dict):
            continue

        item_id = str(item.get("service") or item.get("id") or item.get("product_id") or item.get("sku") or item.get("package_id") or "")
        item_name = str(item.get("name") or item.get("title") or item.get("product_name") or item.get("service_name") or item.get("name_en") or "")
        category = str(item.get("category") or item.get("category_name") or item.get("group") or item.get("type") or "Digital Goods")

        # If item has variants (e.g. Crazy Store / GetItSasta API format)
        variants = item.get("variants")
        if variants and isinstance(variants, list) and len(variants) > 0:
            for v in variants:
                if not isinstance(v, dict):
                    continue
                v_id = str(v.get("id") or item_id)
                v_name = str(v.get("name") or "Standard")
                display_title = f"{item_name} ({v_name})" if v_name.lower() != "standard" else item_name
                
                # Extract variant price
                v_price = 0.0
                for p_key in ["priceUsdt", "costPriceUsdt", "price", "rate", "cost", "wholesale_price"]:
                    if p_key in v and v[p_key] is not None:
                        try:
                            v_price = float(v[p_key])
                            break
                        except (ValueError, TypeError):
                            pass
                if v_price <= 0.0:
                    for p_key in ["costFromPriceUsdt", "fromPriceUsdt", "fromPrice", "price"]:
                        if p_key in item and item[p_key] is not None:
                            try:
                                v_price = float(item[p_key])
                                break
                            except (ValueError, TypeError):
                                pass

                normalized.append({
                    "id": v_id,
                    "name": display_title,
                    "price": v_price,
                    "category": category,
                    "min": 1,
                    "max": v.get("stock") or 100
                })
            continue

        if not item_id or not item_name:
            continue

        # Extract wholesale price / rate
        price_val = 0.0
        for p_key in ["rate", "price", "cost", "wholesale_price", "unit_price", "amount", "costFromPriceUsdt", "fromPriceUsdt", "fromPrice"]:
            if p_key in item and item[p_key] is not None:
                try:
                    price_val = float(item[p_key])
                    break
                except (ValueError, TypeError):
                    pass

        normalized.append({
            "id": item_id,
            "name": item_name,
            "price": price_val,
            "category": category,
            "min": item.get("min", 1),
            "max": item.get("max", 100)
        })

    return normalized

def get_sample_provider_products() -> list:
    """Sample catalog for testing or previewing before live provider setup"""
    return [
        {"id": "101", "name": "Netflix Premium 4K UHD (1 Month)", "price": 2.50, "category": "Streaming", "min": 1, "max": 10},
        {"id": "102", "name": "Spotify Premium Individual (3 Months)", "price": 3.00, "category": "Music & Audio", "min": 1, "max": 10},
        {"id": "103", "name": "NordVPN Premium (1 Year)", "price": 3.50, "category": "VPN & Security", "min": 1, "max": 5},
        {"id": "104", "name": "YouTube Premium (1 Month)", "price": 1.80, "category": "Streaming", "min": 1, "max": 10},
        {"id": "105", "name": "Discord Nitro (1 Month Boost)", "price": 2.20, "category": "Gaming", "min": 1, "max": 10},
        {"id": "106", "name": "Prime Video (6 Months)", "price": 4.00, "category": "Streaming", "min": 1, "max": 5},
        {"id": "107", "name": "Canva Pro Lifetime Invite", "price": 1.50, "category": "Design & Tools", "min": 1, "max": 10},
    ]

async def order_from_provider(provider: dict, provider_product_id: str, quantity: int = 1, order_id: str = "") -> Dict[str, Any]:
    """
    Places an order on the provider / seller API and returns delivered account credentials.
    Standard Digital Goods API structure:
      POST {api_url}/order or {api_url}/buy or {api_url}
      Payload:
        {
          "api_key": "...",
          "product_id": "...",
          "quantity": N,
          "order_id": "..."
        }
    """
    api_url = provider.get("api_url", "").strip().rstrip("/")
    api_key = provider.get("api_key", "").strip()

    if not api_url or not api_key:
        return {"success": False, "error": "Provider API URL or API Key is missing."}

    # Determine order endpoint
    if api_url.endswith("/orders") or api_url.endswith("/order"):
        order_endpoints = [api_url]
    else:
        order_endpoints = [f"{api_url}/orders", f"{api_url}/order", api_url]

    import uuid
    idempotency_key = str(uuid.uuid4())

    headers = {
        "Authorization": f"Bearer {api_key}",
        "X-API-Key": api_key,
        "Idempotency-Key": idempotency_key,
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "FoxzenStore/2.0"
    }

    # Universal payload supporting SMM, Kinguin, GetItSasta / CrazyStore
    payload = {
        "variantId": provider_product_id,
        "productId": provider_product_id,
        "product_id": provider_product_id,
        "service": provider_product_id,
        "package_id": provider_product_id,
        "quantity": quantity,
        "order_id": order_id,
        "custom_id": order_id,
        "api_key": api_key,
        "key": api_key
    }

    logger.info(f"Dispatching Reseller API order for product {provider_product_id} (qty={quantity})")

    timeout = aiohttp.ClientTimeout(total=30)
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            for endpoint in order_endpoints:
                try:
                    async with session.post(endpoint, json=payload, headers=headers) as resp:
                        text_response = await resp.text()
                        try:
                            data = await resp.json()
                        except Exception:
                            data = {}

                        # If 404 on endpoint, try next endpoint variant
                        if resp.status == 404 and len(order_endpoints) > 1 and endpoint != order_endpoints[-1]:
                            continue

                        if resp.status not in (200, 201):
                            error_msg = data.get("error") or data.get("message") or f"HTTP {resp.status}: {text_response[:120]}"
                            logger.error(f"Provider API order failed: {error_msg}")
                            return {
                                "success": False,
                                "error": str(error_msg),
                                "status_code": resp.status,
                                "raw": text_response[:300]
                            }

                        # Check if API returned an internal error inside 200 response
                        if data.get("success") is False or data.get("status") in ["error", "failed", 0, "0"]:
                            error_msg = data.get("error") or data.get("message") or "Provider rejected the order."
                            return {
                                "success": False,
                                "error": str(error_msg),
                                "data": data
                            }

                        # Extract credentials from provider response
                        delivered_data = _extract_delivered_data(data, quantity)
                        provider_order_id = str(
                            data.get("orderNumber") or data.get("order_id") or data.get("id") or data.get("order", {}).get("id") or f"API-{order_id}"
                        )

                        if not delivered_data:
                            # If provider didn't return text credentials directly, check if it returned a code or key
                            delivered_data = f"Provider Order Reference: #{provider_order_id}\n(Order placed successfully on supplier system)"

                        return {
                            "success": True,
                            "delivered_data": delivered_data,
                            "provider_order_id": provider_order_id,
                            "raw_response": data
                        }
                except Exception as e:
                    logger.debug(f"Error trying endpoint {endpoint}: {e}")
                    if endpoint == order_endpoints[-1]:
                        raise e

    except aiohttp.ClientConnectorError as e:
        logger.error(f"Connection error to provider {api_url}: {e}")
        return {"success": False, "error": f"Cannot connect to provider API server: {e}"}
    except asyncio.TimeoutError:
        logger.error(f"Timeout connecting to provider {api_url}")
        return {"success": False, "error": "Provider API timed out (took longer than 30s)."}
    except Exception as e:
        logger.error(f"Unexpected error calling provider API: {e}", exc_info=True)
        return {"success": False, "error": f"API error: {str(e)}"}

def _extract_balance(data: Any) -> Optional[float]:
    """Helper to extract balance from various JSON responses"""
    if not isinstance(data, dict):
        return None
    for key in ["balanceUsdt", "balance", "funds", "wallet", "current_balance", "credit", "account_balance"]:
        if key in data and data[key] is not None:
            try:
                return float(data[key])
            except (ValueError, TypeError):
                pass
    if "data" in data and isinstance(data["data"], dict):
        return _extract_balance(data["data"])
    if "user" in data and isinstance(data["user"], dict):
        return _extract_balance(data["user"])
    return None

def _extract_delivered_data(data: Any, quantity: int = 1) -> Optional[str]:
    """Helper to extract account logins/keys from various supplier JSON response shapes"""
    if not isinstance(data, dict):
        return str(data) if data else None

    # Priority 1: Direct clean delivery text or note if provided by supplier
    if data.get("deliveryText"):
        return str(data["deliveryText"]).strip()

    # Priority 2: Extract from items list (GetItSasta / CrazyStore / standard digital APIs)
    items = data.get("items")
    if items and isinstance(items, list):
        extracted_items = []
        for it in items:
            if isinstance(it, dict):
                # Check for direct value / secret key / code
                if it.get("value"):
                    extracted_items.append(str(it["value"]))
                elif it.get("secret") and isinstance(it["secret"], dict):
                    sec = it["secret"]
                    if sec.get("key"):
                        extracted_items.append(str(sec["key"]))
                    elif sec.get("email") and sec.get("password"):
                        extracted_items.append(f"Email: {sec['email']}\nPassword: {sec['password']}")
                    elif sec.get("username") and sec.get("password"):
                        extracted_items.append(f"Username: {sec['username']}\nPassword: {sec['password']}")
                    else:
                        extracted_items.append("\n".join([f"{k}: {v}" for k, v in sec.items()]))
                elif it.get("key"):
                    extracted_items.append(str(it["key"]))
                elif it.get("code"):
                    extracted_items.append(str(it["code"]))
                elif it.get("license"):
                    extracted_items.append(str(it["license"]))
                elif it.get("account"):
                    extracted_items.append(str(it["account"]))
                elif it.get("credentials"):
                    extracted_items.append(str(it["credentials"]))
                elif it.get("values") and isinstance(it["values"], list):
                    extracted_items.extend([str(v) for v in it["values"]])
                else:
                    # fallback to string of it
                    extracted_items.append(str(it))
            else:
                extracted_items.append(str(it))

        if extracted_items:
            if len(extracted_items) == 1:
                return extracted_items[0]
            return "\n\n".join([f"📦 [Item #{i}]:\n{item}" for i, item in enumerate(extracted_items, 1)])

    # Priority 3: Common single-key credentials
    for key in [
        "credentials", "account", "accounts", "code", "keys", "license", 
        "license_key", "serial", "delivered_data", "details", "key", "token"
    ]:
        val = data.get(key)
        if val:
            if isinstance(val, list):
                if len(val) > 1:
                    return "\n\n".join([f"📦 [Item #{i}]:\n{item}" for i, item in enumerate(val, 1)])
                elif len(val) == 1:
                    return str(val[0])
            elif isinstance(val, dict):
                if "email" in val and "password" in val:
                    return f"Email: {val['email']}\nPassword: {val['password']}"
                elif "username" in val and "password" in val:
                    return f"Username: {val['username']}\nPassword: {val['password']}"
                elif "key" in val:
                    return str(val["key"])
                return "\n".join([f"{k}: {v}" for k, v in val.items()])
            else:
                return str(val).strip()

    # Nested structures (e.g. data.data or data.order)
    for sub in ["data", "order", "result", "payload"]:
        if sub in data and isinstance(data[sub], dict):
            extracted = _extract_delivered_data(data[sub], quantity)
            if extracted:
                return extracted

    return None
