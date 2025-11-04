from __future__ import annotations
import requests
from requests import Session
from typing import Dict, Any

class RobloxAPIError(Exception):
    pass

def _sess(cookie: str, timeout: int = 15) -> Session:
    s = requests.Session()
    s.cookies.set(".ROBLOSECURITY", cookie, domain=".roblox.com")
    s.headers.update({
        "User-Agent": "NeonChecker/1.1 (+web)",
        "Accept": "application/json",
        "Origin": "https://www.roblox.com",
        "Referer": "https://www.roblox.com/"
    })
    return s

def _get(s: Session, url: str, timeout: int = 15):
    try:
        r = s.get(url, timeout=timeout)
    except requests.RequestException as e:
        raise RobloxAPIError(f"network_error:{type(e).__name__}")
    if r.status_code in (401, 403):
        raise RobloxAPIError("unauthorized")
    try:
        r.raise_for_status()
    except requests.HTTPError:
        raise RobloxAPIError(f"http_{r.status_code}")
    if "application/json" in r.headers.get("Content-Type", ""):
        return r.json()
    return r.text

def _safe(call, default=None):
    try:
        return call()
    except Exception:
        return default

def check_cookie(cookie: str, timeout: int = 25) -> Dict[str, Any]:
    s = _sess(cookie, timeout=timeout)

    # базовый профиль (если тут ошибка — вернём понятный ответ, а не 500)
    try:
        me = _get(s, "https://users.roblox.com/v1/users/authenticated", timeout=timeout)
    except RobloxAPIError as e:
        return {
            "status": "error",
            "error": str(e),
            "hint": "Проверь .ROBLOSECURITY (полный и валидный), либо попробуй позже."
        }

    user_id   = int(me.get("id"))
    username  = me.get("name")
    display   = me.get("displayName")

    created_iso = _safe(lambda: _get(s, f"https://users.roblox.com/v1/users/{user_id}", timeout=timeout).get("created"))

    mail_verified  = bool(_safe(lambda: _get(s, "https://accountsettings.roblox.com/v1/email", timeout=timeout).get("verified"), False))
    phone_verified = bool(_safe(lambda: _get(s, "https://accountinformation.roblox.com/v1/phone", timeout=timeout).get("isVerified"), False))
    tfa_enabled    = bool(_safe(lambda: (_get(s, f"https://twostepverification.roblox.com/v1/users/{user_id}/configuration", timeout=timeout).get("isEnabled")
                                        or _get(s, f"https://twostepverification.roblox.com/v1/users/{user_id}/configuration", timeout=timeout).get("isEnabledForLogin")), False))
    premium = bool(_safe(lambda: _get(s, f"https://premiumfeatures.roblox.com/v1/users/{user_id}/validate-membership", timeout=timeout), False))
    robux = int(_safe(lambda: _get(s, "https://economy.roblox.com/v1/user/currency", timeout=timeout).get("robux"), 0))
    friends_count   = int(_safe(lambda: _get(s, f"https://friends.roblox.com/v1/users/{user_id}/friends/count", timeout=timeout).get("count"), 0))
    inventory_public= _safe(lambda: bool(_get(s, f"https://inventory.roblox.com/v1/users/{user_id}/can-view-inventory", timeout=timeout).get("canViewInventory")), None)
    voice_enabled   = bool(_safe(lambda: _get(s, "https://voice.roblox.com/v1/settings", timeout=timeout).get("isEnabled"), False))

    def _rap():
        total, cursor = 0, ""
        while True:
            url = f"https://inventory.roblox.com/v1/users/{user_id}/assets/collectibles?limit=100&sortOrder=Asc"
            if cursor: url += f"&cursor={cursor}"
            data = _get(s, url, timeout=timeout)
            for it in data.get("data", []):
                total += int(it.get("recentAveragePrice") or 0)
            cursor = data.get("nextPageCursor")
            if not cursor: break
        return total

    def _pending():
        total, cursor = 0.0, ""
        while True:
            url = f"https://economy.roblox.com/v2/users/{user_id}/transactions?transactionType=Sale&limit=100"
            if cursor: url += f"&cursor={cursor}"
            data = _get(s, url, timeout=timeout)
            for t in data.get("data", []):
                amt = t.get("currency", {}).get("amount")
                if isinstance(amt, (int, float)) and amt > 0 and t.get("isPending"):
                    total += float(amt)
            cursor = data.get("nextPageCursor")
            if not cursor: break
        return total

    def _spent():
        total, cursor = 0.0, ""
        while True:
            url = f"https://economy.roblox.com/v2/users/{user_id}/transactions?transactionType=Purchase&limit=100"
            if cursor: url += f"&cursor={cursor}"
            data = _get(s, url, timeout=timeout)
            for t in data.get("data", []):
                amt = t.get("currency", {}).get("amount")
                if isinstance(amt, (int, float)) and amt < 0:
                    total += abs(float(amt))
            cursor = data.get("nextPageCursor")
            if not cursor: break
        return total

    def _group_funds():
        total = 0
        groups = _get(s, f"https://groups.roblox.com/v2/users/{user_id}/groups/roles", timeout=timeout).get("data", [])
        for g in groups:
            role = g.get("role", {})
            if int(role.get("rank") or 0) == 255:
                gid = g.get("group", {}).get("id")
                try:
                    val = _get(s, f"https://economy.roblox.com/v1/groups/{gid}/currency", timeout=timeout)
                    total += int(val.get("robux") or 0)
                except RobloxAPIError:
                    pass
        return total

    rap         = int(_safe(_rap, 0))
    pending     = float(_safe(_pending, 0.0))
    total_spent = float(_safe(_spent, 0.0))
    group_funds = int(_safe(_group_funds, 0))

    return {
        "status": "ok",
        "user": {
            "id": user_id, "username": username, "display_name": display,
            "created": created_iso, "premium": premium, "friends_count": friends_count,
            "inventory_public": inventory_public, "voice_enabled": voice_enabled
        },
        "checks": {
            "mail_verified": mail_verified, "phone_verified": phone_verified,
            "two_factor_enabled": tfa_enabled, "robux": robux, "pending_robux": pending,
            "rap": rap, "total_spent_robux": total_spent, "group_funds_robux": group_funds,
            "billing_sources": []   # при необходимости сможем дополнить
        }
    }
