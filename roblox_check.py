# roblox_check.py
from __future__ import annotations
import requests
from requests import Session
from typing import Dict, Any, List

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
    s.timeout = timeout
    return s

def _get(s: Session, url: str, **kw):
    r = s.get(url, timeout=kw.pop("timeout", 15))
    if r.status_code in (401, 403):
        raise RobloxAPIError("unauthorized")
    r.raise_for_status()
    if "application/json" in r.headers.get("Content-Type", ""):
        return r.json()
    return r.text

def _calc_rap(s: Session, user_id: int) -> int:
    total = 0
    cursor = ""
    while True:
        url = f"https://inventory.roblox.com/v1/users/{user_id}/assets/collectibles?limit=100&sortOrder=Asc"
        if cursor: url += f"&cursor={cursor}"
        data = _get(s, url)
        for it in data.get("data", []):
            total += int(it.get("recentAveragePrice") or 0)
        cursor = data.get("nextPageCursor")
        if not cursor: break
    return total

def _total_spent(s: Session, user_id: int) -> float:
    spent = 0.0
    cursor = ""
    while True:
        url = f"https://economy.roblox.com/v2/users/{user_id}/transactions?transactionType=Purchase&limit=100"
        if cursor: url += f"&cursor={cursor}"
        data = _get(s, url)
        for t in data.get("data", []):
            amt = t.get("currency", {}).get("amount")
            if isinstance(amt, (int, float)) and amt < 0:
                spent += abs(float(amt))
        cursor = data.get("nextPageCursor")
        if not cursor: break
    return spent

def _pending_robux(s: Session, user_id: int) -> float:
    # best-effort: берём продажи и помеченные pending (если поле есть)
    pending = 0.0
    cursor = ""
    while True:
        url = f"https://economy.roblox.com/v2/users/{user_id}/transactions?transactionType=Sale&limit=100"
        if cursor: url += f"&cursor={cursor}"
        data = _get(s, url)
        for t in data.get("data", []):
            amt = t.get("currency", {}).get("amount")
            is_pending = t.get("isPending")
            if isinstance(amt, (int, float)) and amt > 0 and is_pending:
                pending += float(amt)
        cursor = data.get("nextPageCursor")
        if not cursor: break
    return pending

def _group_funds_if_owner(s: Session, user_id: int) -> int:
    total = 0
    try:
        groups = _get(s, f"https://groups.roblox.com/v2/users/{user_id}/groups/roles").get("data", [])
    except Exception:
        return 0
    for g in groups:
        group = g.get("group", {})
        role = g.get("role", {})
        if int(role.get("rank") or 0) == 255:  # владелец
            gid = group.get("id")
            try:
                val = _get(s, f"https://economy.roblox.com/v1/groups/{gid}/currency")
                total += int(val.get("robux") or 0)
            except Exception:
                pass
    return total

def check_cookie(cookie: str, timeout: int = 25) -> Dict[str, Any]:
    s = _sess(cookie, timeout=timeout)

    # базовый профиль + created
    me = _get(s, "https://users.roblox.com/v1/users/authenticated")
    user_id = int(me["id"])
    username = me.get("name")
    display_name = me.get("displayName")

    created_iso = None
    try:
        u = _get(s, f"https://users.roblox.com/v1/users/{user_id}")
        created_iso = u.get("created")
    except Exception:
        pass

    # mail
    mail_verified = False
    try:
        mail = _get(s, "https://accountsettings.roblox.com/v1/email")
        mail_verified = bool(mail.get("verified"))
    except Exception:
        pass

    # phone
    phone_verified = False
    try:
        phone = _get(s, "https://accountinformation.roblox.com/v1/phone")
        phone_verified = bool(phone.get("isVerified"))
    except Exception:
        pass

    # 2FA
    tfa_enabled = False
    try:
        tfa = _get(s, f"https://twostepverification.roblox.com/v1/users/{user_id}/configuration")
        tfa_enabled = bool(tfa.get("isEnabled") or tfa.get("isEnabledForLogin"))
    except Exception:
        pass

    # Premium
    premium = False
    try:
        premium = bool(_get(s, f"https://premiumfeatures.roblox.com/v1/users/{user_id}/validate-membership"))
    except Exception:
        pass

    # Robux balance
    robux = 0
    try:
        cur = _get(s, "https://economy.roblox.com/v1/user/currency")
        robux = int(cur.get("robux") or 0)
    except Exception:
        pass

    # Friends count
    friends_count = None
    try:
        friends_count = int(_get(s, f"https://friends.roblox.com/v1/users/{user_id}/friends/count").get("count") or 0)
    except Exception:
        pass

    # Inventory visibility
    inventory_public = None
    try:
        inv = _get(s, f"https://inventory.roblox.com/v1/users/{user_id}/can-view-inventory")
        inventory_public = bool(inv.get("canViewInventory"))
    except Exception:
        pass

    # Voice chat
    voice_enabled = None
    try:
        voice_enabled = bool(_get(s, "https://voice.roblox.com/v1/settings").get("isEnabled"))
    except Exception:
        pass

    # RAP
    rap = 0
    try:
        rap = _calc_rap(s, user_id)
    except Exception:
        pass

    # Pending Robux (best-effort)
    pending = 0.0
    try:
        pending = _pending_robux(s, user_id)
    except Exception:
        pass

    # Total spent
    total_spent = 0.0
    try:
        total_spent = _total_spent(s, user_id)
    except Exception:
        pass

    # Group funds if owner
    group_funds = 0
    try:
        group_funds = _group_funds_if_owner(s, user_id)
    except Exception:
        pass

    return {
        "status": "ok",
        "user": {
            "id": user_id,
            "username": username,
            "display_name": display_name,
            "created": created_iso,
            "premium": premium,
            "friends_count": friends_count,
            "inventory_public": inventory_public,
            "voice_enabled": voice_enabled
        },
        "checks": {
            "mail_verified": mail_verified,
            "phone_verified": phone_verified,
            "two_factor_enabled": tfa_enabled,
            "robux": robux,
            "pending_robux": pending,
            "rap": rap,
            "total_spent_robux": total_spent,
            "group_funds_robux": group_funds,
            "billing_sources": []  # попробуем получить ниже
        }
    }
