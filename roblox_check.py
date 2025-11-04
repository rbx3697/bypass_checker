from __future__ import annotations
import os
import time
import requests
from requests import Session
from typing import Dict, Any, Optional

class RobloxAPIError(Exception):
    pass

def _sess(cookie: str, timeout: int = 15) -> Session:
    """
    Аккуратная сессия:
    - ТОЛЬКО нужные заголовки
    - без Origin/Referer (чтобы не провоцировать CSRF/смену сессии)
    - стабильный RBX-DeviceId (если задан в окружении), чтобы Roblox видел постоянное устройство
    """
    s = requests.Session()
    s.trust_env = False  # не тащим прокси из окружения
    s.cookies.set(".ROBLOSECURITY", cookie, domain=".roblox.com")
    headers = {
        "User-Agent": os.environ.get("RBX_USER_AGENT", "NeonChecker/1.2 (+render)"),
        "Accept": "application/json",
    }
    device_id = os.environ.get("RBX_DEVICE_ID")
    if device_id:
        headers["RBX-DeviceId"] = device_id
    s.headers.update(headers)
    return s

def _get(s: Session, url: str, timeout: int = 15, retries: int = 2):
    """
    GET с лёгким бэкоффом: если 429 — ждём и пробуем ещё раз.
    """
    delay = 0.7
    for attempt in range(retries + 1):
        try:
            r = s.get(url, timeout=timeout)
        except requests.RequestException as e:
            if attempt == retries:
                raise RobloxAPIError(f"network_error:{type(e).__name__}")
            time.sleep(delay); delay *= 1.6
            continue

        if r.status_code in (401, 403):
            raise RobloxAPIError("unauthorized")
        if r.status_code == 429:
            if attempt == retries:
                raise RobloxAPIError("rate_limited")
            time.sleep(delay); delay *= 1.6
            continue
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

    # 0) БАЗОВОЕ: кто мы
    try:
        me = _get(s, "https://users.roblox.com/v1/users/authenticated", timeout=timeout)
    except RobloxAPIError as e:
        return {
            "status": "error",
            "error": str(e),
            "hint": "Проверь .ROBLOSECURITY (полностью скопирован), или повтори позже."
        }

    user_id   = int(me.get("id"))
    username  = me.get("name")
    display   = me.get("displayName")

    # 1) Данные пользователя
    created_iso = _safe(lambda: _get(s, f"https://users.roblox.com/v1/users/{user_id}", timeout=timeout).get("created"))
    premium = bool(_safe(lambda: _get(s, f"https://premiumfeatures.roblox.com/v1/users/{user_id}/validate-membership", timeout=timeout), False))
    friends_count   = int(_safe(lambda: _get(s, f"https://friends.roblox.com/v1/users/{user_id}/friends/count", timeout=timeout).get("count"), 0))
    inventory_public= _safe(lambda: bool(_get(s, f"https://inventory.roblox.com/v1/users/{user_id}/can-view-inventory", timeout=timeout).get("canViewInventory")), None)
    voice_enabled   = bool(_safe(lambda: _get(s, "https://voice.roblox.com/v1/settings", timeout=timeout).get("isEnabled"), False))

    # 2) Верификации
    mail_verified  = bool(_safe(lambda: _get(s, "https://accountsettings.roblox.com/v1/email", timeout=timeout).get("verified"), False))
    phone_verified = bool(_safe(lambda: _get(s, "https://accountinformation.roblox.com/v1/phone", timeout=timeout).get("isVerified"), False))
    tfa_enabled    = bool(_safe(lambda: (_get(s, f"https://twostepverification.roblox.com/v1/users/{user_id}/configuration", timeout=timeout).get("isEnabled")
                                        or _get(s, f"https://twostepverification.roblox.com/v1/users/{user_id}/configuration", timeout=timeout).get("isEnabledForLogin")), False))

    # 3) Баланс Robux (более надёжный эндпоинт)
    robux = int(_safe(lambda: _get(s, f"https://economy.roblox.com/v1/users/{user_id}/currency", timeout=timeout).get("robux"), 0))

    # 4) RAP
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
    rap = int(_safe(_rap, 0))

    # 5) Pending Robux (по продажам с флагом isPending)
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
    pending = float(_safe(_pending, 0.0))

    # 6) Всего потрачено (по типу Purchase)
    def _spent():
        total, cursor = 0.0, ""
        while True:
            url = f"https://economy.roblox.com/v2/users/{user_id}/transactions?transactionType=Purchase&limit=100"
            if cursor: url += f"&cursor={cursor}"
            data = _get(s, url, timeout=timeout)
            for t in data.get("data", []):
                amt = t.get("currency", {}).get("amount")
                # Покупки отображаются отрицательными — считаем модуль
                if isinstance(amt, (int, float)) and amt < 0:
                    total += abs(float(amt))
            cursor = data.get("nextPageCursor")
            if not cursor: break
        return total
    total_spent = float(_safe(_spent, 0.0))

    # 7) Group funds (сумма по группам, где юзер владелец)
    def _group_funds():
        total = 0
        groups = _get(s, f"https://groups.roblox.com/v2/users/{user_id}/groups/roles", timeout=timeout).get("data", [])
        for g in groups:
            role = g.get("role", {})
            if int(role.get("rank") or 0) == 255:  # владелец
                gid = g.get("group", {}).get("id")
                try:
                    val = _get(s, f"https://economy.roblox.com/v1/groups/{gid}/currency", timeout=timeout)
                    total += int(val.get("robux") or 0)
                except RobloxAPIError:
                    pass
        return total
    group_funds = int(_safe(_group_funds, 0))

    return {
        "status": "ok",
        "user": {
            "id": user_id,
            "username": username,
            "display_name": display,
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
            "billing_sources": []  # (Roblox не даёт стабильный публичный список — оставляем пустым)
        }
    }
