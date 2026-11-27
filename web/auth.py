import hmac
import hashlib
import time
from typing import Optional
from fastapi import Request, HTTPException, status
from fastapi.responses import RedirectResponse
from config import SECRET_KEY
from database import get_setting, verify_password

COOKIE_NAME = "foxzen_admin_session"

def create_session_token(username: str) -> str:
    """Creates a signed session token: username:timestamp:signature"""
    ts = str(int(time.time()))
    data = f"{username}:{ts}"
    signature = hmac.new(SECRET_KEY.encode(), data.encode(), hashlib.sha256).hexdigest()
    return f"{data}:{signature}"

def verify_session_token(token: str) -> Optional[str]:
    """Verifies session token and returns username if valid"""
    if not token or ":" not in token:
        return None
    parts = token.split(":")
    if len(parts) != 3:
        return None
    username, ts, signature = parts
    data = f"{username}:{ts}"
    expected_sig = hmac.new(SECRET_KEY.encode(), data.encode(), hashlib.sha256).hexdigest()
    
    if not hmac.compare_digest(signature, expected_sig):
        return None
        
    # Check session expiration (e.g. 7 days)
    try:
        token_time = int(ts)
        if time.time() - token_time > 7 * 24 * 3600:
            return None
    except ValueError:
        return None
        
    return username

async def get_current_admin(request: Request) -> str:
    """Dependency for securing admin routes"""
    token = request.cookies.get(COOKIE_NAME)
    username = verify_session_token(token)
    if not username:
        raise HTTPException(
            status_code=status.HTTP_307_TEMPORARY_REDIRECT,
            headers={"Location": "/login"}
        )
    return username
