# meow_wrapper.py
import traceback
from typing import Dict
from roblox_check import check_cookie as _check

def run_check_safe(encrypted_cookie: str, fernet, max_seconds: int = 40) -> Dict:
    try:
        cookie = fernet.decrypt(encrypted_cookie.encode()).decode()
    except Exception:
        return {"status": "error", "error": "invalid_encryption"}
    try:
        result = _check(cookie, timeout=min(max_seconds, 25))
        return {"status": "ok", "source": "roblox_api", "result": result}
    except Exception:
        return {"status": "error", "error": "checker_exception", "trace": traceback.format_exc()}
