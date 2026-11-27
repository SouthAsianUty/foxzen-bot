import time
import hmac
import hashlib
import urllib.parse
import httpx
from typing import Optional, Dict, Any, Tuple

BINANCE_API_URL = "https://api.binance.com"

def generate_signature(query_string: str, secret_key: str) -> str:
    """Generates HMAC-SHA256 signature for Binance API"""
    return hmac.new(
        secret_key.encode("utf-8"),
        query_string.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()

async def test_binance_api_credentials(api_key: str, api_secret: str) -> Tuple[bool, str]:
    """Tests if the provided Binance API credentials are valid"""
    if not api_key or not api_secret:
        return False, "API Key or Secret is empty."

    timestamp = int(time.time() * 1000)
    params = {"timestamp": timestamp}
    query_string = urllib.parse.urlencode(params)
    signature = generate_signature(query_string, api_secret)
    params["signature"] = signature

    headers = {"X-MBX-APIKEY": api_key}
    endpoint = f"{BINANCE_API_URL}/sapi/v1/pay/transactions"

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.get(endpoint, params=params, headers=headers)
            data = res.json()
            
            # Binance returns code 000000 or status 200 for success
            if res.status_code == 200 and (data.get("code") == "000000" or data.get("success") is True or "data" in data):
                return True, "Binance API connected successfully!"
            else:
                msg = data.get("errorMessage") or data.get("msg") or f"HTTP {res.status_code}"
                return False, f"Binance error: {msg}"
    except Exception as e:
        return False, f"Connection failed: {str(e)}"

async def verify_binance_pay_transaction(
    api_key: str,
    api_secret: str,
    submitted_tx_id: str,
    expected_amount: float,
    expected_currency: str = "USDT"
) -> Dict[str, Any]:
    """
    Queries Binance Pay API (and capital deposit fallback) to check if submitted_tx_id 
    corresponds to a valid incoming transaction matching expected amount.
    """
    if not api_key or not api_secret:
        return {
            "verified": False,
            "status": "CONFIG_MISSING",
            "error": "Binance API Key and Secret must both be configured."
        }

    clean_tx = submitted_tx_id.strip()
    if not clean_tx:
        return {
            "verified": False,
            "status": "INVALID_INPUT",
            "error": "Empty transaction ID provided."
        }

    clean_tx_lower = clean_tx.lower()
    # If user submitted full string or stripped prefix, keep variations
    clean_digits = "".join(filter(str.isdigit, clean_tx))

    timestamp = int(time.time() * 1000)
    # Check transactions in the last 7 days (well within 90 days max)
    start_time = timestamp - (7 * 24 * 60 * 60 * 1000)
    
    params = {
        "timestamp": timestamp,
        "startTime": start_time,
        "limit": 100
    }
    query_string = urllib.parse.urlencode(params)
    signature = generate_signature(query_string, api_secret)
    params["signature"] = signature

    headers = {"X-MBX-APIKEY": api_key}
    endpoint = f"{BINANCE_API_URL}/sapi/v1/pay/transactions"

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            # 1. Query Binance Pay Transactions
            res = await client.get(endpoint, params=params, headers=headers)
            if res.status_code == 200:
                payload = res.json()
                transactions = payload.get("data", [])
                
                for tx in transactions:
                    tx_id = str(tx.get("transactionId", "")).strip().lower()
                    order_id = str(tx.get("orderId", "")).strip().lower()
                    
                    # Smart match: exact, substring, or stripped numeric digits
                    matched = False
                    if clean_tx_lower in (tx_id, order_id):
                        matched = True
                    elif clean_digits and len(clean_digits) >= 8:
                        if clean_digits in tx_id or clean_digits in order_id:
                            matched = True
                    elif len(clean_tx_lower) >= 6 and (clean_tx_lower in tx_id or tx_id.endswith(clean_tx_lower)):
                        matched = True

                    if matched:
                        # Extract currency & amount
                        curr = tx.get("currency", "").upper()
                        amount_val = 0.0
                        try:
                            amount_val = float(tx.get("amount", "0"))
                        except ValueError:
                            amount_val = 0.0

                        # Check fundsDetail fallback if primary currency differs
                        if curr != expected_currency.upper() and tx.get("fundsDetail"):
                            for f in tx.get("fundsDetail", []):
                                if f.get("currency", "").upper() == expected_currency.upper():
                                    curr = expected_currency.upper()
                                    try:
                                        amount_val = float(f.get("amount", amount_val))
                                    except ValueError:
                                        pass
                                    break

                        if curr != expected_currency.upper():
                            return {
                                "verified": False,
                                "status": "CURRENCY_MISMATCH",
                                "error": f"Currency mismatch: expected {expected_currency}, got {curr}",
                                "raw_tx": tx
                            }

                        # Check amount with small float tolerance (0.005)
                        if amount_val < (expected_amount - 0.005):
                            return {
                                "verified": False,
                                "status": "AMOUNT_LOW",
                                "error": f"Amount insufficient: expected ${expected_amount}, received ${amount_val}",
                                "raw_tx": tx
                            }

                        return {
                            "verified": True,
                            "status": "SUCCESS",
                            "transaction_id": tx.get("transactionId", clean_tx),
                            "amount": amount_val,
                            "currency": curr,
                            "payer": tx.get("payerInfo", {}),
                            "transaction_time": tx.get("transactionTime"),
                            "raw_tx": tx
                        }

            # 2. Fallback: Query on-chain crypto deposit history (/sapi/v1/capital/deposit/hisrec)
            dep_params = {
                "coin": expected_currency.upper(),
                "status": 1, # 1 = success
                "startTime": start_time,
                "timestamp": int(time.time() * 1000),
                "limit": 100
            }
            dep_qs = urllib.parse.urlencode(dep_params)
            dep_sig = generate_signature(dep_qs, api_secret)
            dep_params["signature"] = dep_sig
            
            dep_res = await client.get(f"{BINANCE_API_URL}/sapi/v1/capital/deposit/hisrec", params=dep_params, headers=headers)
            if dep_res.status_code == 200:
                deposits = dep_res.json()
                if isinstance(deposits, list):
                    for dep in deposits:
                        dep_txid = str(dep.get("txId", "")).strip().lower()
                        dep_id = str(dep.get("id", "")).strip().lower()
                        
                        if clean_tx_lower in (dep_txid, dep_id) or (len(clean_tx_lower) >= 10 and clean_tx_lower in dep_txid):
                            dep_amount = float(dep.get("amount", 0.0))
                            if dep_amount >= (expected_amount - 0.005):
                                return {
                                    "verified": True,
                                    "status": "SUCCESS",
                                    "transaction_id": dep.get("txId", clean_tx),
                                    "amount": dep_amount,
                                    "currency": expected_currency.upper(),
                                    "network": dep.get("network", "CRYPTO"),
                                    "raw_tx": dep
                                }

            return {
                "verified": False,
                "status": "NOT_FOUND",
                "error": "Transaction ID not found in recent Binance records. Note that incoming transfers may take 1-3 minutes to appear."
            }

    except Exception as e:
        return {
            "verified": False,
            "status": "EXCEPTION",
            "error": f"Network exception: {str(e)}"
        }
