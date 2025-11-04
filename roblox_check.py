from __future__ import annotations
import os, time
import requests
from requests import Session
from typing import Dict, Any

class RobloxAPIError(Exception):
    pass

def _sess(cookie: str) -> Session:
    """
    Бережная сессия:
    - только нужные заголовки (без Origin/Referer)
    - поддержка стабильного RBX-DeviceId (ENV RBX_DEVICE_ID)
    - уважает прокси из ENV (HTTP_PROXY/HTTPS_PROXY), если заданы
    - ВСЕГДА только GET (никаких POST)
    """
    s = requests.Session()
    s.trust_env = True
    s.cookies.set(".ROBLOSECURITY", cookie, domain=".roblox.com")
    headers = {
        "User-Agent": os.environ.get("RBX_USER_AGENT", "NeonChecker/1.4 (+render)"),
        "Accept": "application/json",
    }
    dev_id = os.environ.get("RBX_DEVICE_ID")
    if dev_id:
        headers["RBX-DeviceId"] = dev_id
    s.headers.update(headers)
    return s

def _get(s: Session, url: str, timeout: float = 15.0, retries: int = 2):
    backoff = 0.7
    for attempt in range(retries + 1):
        try:
            r = s.get(url, timeout=timeout)
        except requests.RequestException as e:
            if attempt == retries:
                raise RobloxAPIError(f"network_error:{type(e).__name__}")
            time.sleep(backoff); backoff *= 1.7
            continue

        if r.status_code in (401, 403):
            raise RobloxAPIError("unauthorized")
        if r.status_code == 429:
            if attempt == retries:
                raise RobloxAPIError("rate_limited")
            time.sleep(backoff); backoff *= 1.7
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

def _env_flag(name: str) -> bool:
    v = os.environ.get(name, "").strip().lower()
    return v in ("1", "true", "yes", "on")

def check_cookie(cookie: str, timeout: int = 20) -> Dict[str, Any]:
    """
    SAFE по умолчанию. Глубокие проверки включаются флагами:
      RBX_DEEP_TRANSACTIONS=1  -> total_spent / pending по всем страницам
      RBX_DEEP_INVENTORY=1     -> RAP (collectibles pagination)
      RBX_ENABLE_BILLING=1     -> card_present / billing_sources
    Рекомендуется также задать RBX_DEVICE_ID (стабильный UUID) и при необходимости прокси своего региона.
    """
    s = _sess(cookie)
    deep_transactions = _env_flag("RBX_DEEP_TRANSACTIONS")
    deep_inventory    = _env_flag("RBX_DEEP_INVENTORY")
    enable_billing    = _env_flag("RBX_ENABLE_BILLING")

    # 0) Аутентификация
    try:
        me = _get(s, "https://users.roblox.com/v1/users/authenticated", timeout=timeout)
    except RobloxAPIError as e:
        return {"status": "error", "error": str(e),
                "hint": "Проверь .ROBLOSECURITY и совпадение IP/региона. Лучше использовать отдельную сессию для чекера."}

    user_id   = int(me.get("id"))
    username  = me.get("name")
    display   = me.get("displayName")

    # 1) Лёгкие запросы (минимальный риск)
    created_iso = _safe(lambda: _get(s, f"https://users.roblox.com/v1/users/{user_id}", timeout=timeout).get("created"))
    premium     = bool(_safe(lambda: _get(s, f"https://premiumfeatures.roblox.com/v1/users/{user_id}/validate-membership", timeout=timeout), False))
    mail_ver    = bool(_safe(lambda: _get(s, "https://accountsettings.roblox.com/v1/email", timeout=timeout).get("verified"), False))
    phone_ver   = bool(_safe(lambda: _get(s, "https://accountinformation.roblox.com/v1/phone", timeout=timeout).get("isVerified"), False))
    tfa_en      = bool(_safe(lambda: (_get(s, f"https://twostepverification.roblox.com/v1/users/{user_id}/configuration", timeout=timeout).get("isEnabled")
                                      or _get(s, f"https://twostepverification.roblox.com/v1/users/{user_id}/configuration", timeout=timeout).get("isEnabledForLogin")), False))
    friends_cnt = int(_safe(lambda: _get(s, f"https://friends.roblox.com/v1/users/{user_id}/friends/count", timeout=timeout).get("count"), 0))
    # Баланс — корректный эндпоинт «для текущего пользователя», а не по userId
    robux       = int(_safe(lambda: _get(s, "https://economy.roblox.com/v1/user/currency", timeout=timeout).get("robux"), 0))

    # 2) По умолчанию пропускаем «тяжёлые» вещи. Включаются флагами.

    # RAP (deep inventory)
    rap = 0
    if deep_inventory:
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

    pending = None
    total_spent = None
    if deep_transactions:
        def _pending():
            # считаем по Sales, где isPending == True
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
            # суммируем модуль отрицательных Purchase
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

        pending     = float(_safe(_pending, 0.0))
        total_spent = float(_safe(_spent, 0.0))

    group_funds = None
    if deep_transactions:
        def _group_funds():
            total = 0
            groups = _get(s, f"https://groups.roblox.com/v2/users/{user_id}/groups/roles", timeout=timeout).get("data", [])
            for g in groups:
                if int(g.get("role", {}).get("rank") or 0) == 255:
                    gid = g.get("group", {}).get("id")
                    try:
                        val = _get(s, f"https://economy.roblox.com/v1/groups/{gid}/currency", timeout=timeout)
                        total += int(val.get("robux") or 0)
                    except RobloxAPIError:
                        pass
            return total
        group_funds = int(_safe(_group_funds, 0))

    # billing/card (опционально)
    billing_sources = None
    card_present = None
    if enable_billing:
        def _billing():
            nonlocal card_present, billing_sources
            pm = _get(s, "https://billing.roblox.com/v1/payment-methods", timeout=timeout)
            items = pm if isinstance(pm, list) else (pm or [])
            billing_sources = []
            card_present = False
            for p in items:
                typ = p.get("paymentMethodType") or p.get("paymentProvider") or p.get("type")
                if typ:
                    st = str(typ).lower()
                    billing_sources.append(str(typ))
                    if "card" in st or "credit" in st or "adyen" in st or "visa" in st or "master" in st:
                        card_present = True
        _safe(_billing, None)

    return {
        "status": "ok",
        "notes": {
            "deep_transactions": deep_transactions,
            "deep_inventory": deep_inventory,
            "enable_billing": enable_billing
        },
        "user": {
            "id": user_id,
            "username": username,
            "display_name": display,
            "created": created_iso,
            "premium": premium,
            "friends_count": friends_cnt
        },
        "checks": {
            "mail_verified": mail_ver,
            "phone_verified": phone_ver,
            "two_factor_enabled": tfa_en,
            "robux": robux,
            "rap": rap if deep_inventory else None,
            "pending_robux": pending if deep_transactions else None,
            "total_spent_robux": total_spent if deep_transactions else None,
            "group_funds_robux": group_funds if deep_transactions else None,
            "billing_sources": billing_sources if enable_billing else None,
            "card_present": card_present if enable_billing else None
        }
    }
