# roblox_check.py
# Честный серверный чекер под веб. Никаких «сборов» лишнего — только чтение статуса.
# Используются публичные роблокс-эндпоинты. Требуется .ROBLOSECURITY в cookie.
# ВНИМАНИЕ: держи таймауты короткими и включай rate-limit на роут.

from __future__ import annotations
import requests
from requests import Session
from typing import Dict, Any

RAP_LIMITS_PAGE_SIZE = 100

class RobloxAPIError(Exception):
    pass

def _sess(cookie: str, timeout: int = 15) -> Session:
    s = requests.Session()
    # важное: кука только в серверной памяти, не логировать
    s.cookies.set(".ROBLOSECURITY", cookie, domain=".roblox.com")
    s.headers.update({
        "User-Agent": "NeonChecker/1.0 (+web)",
        "Accept": "application/json",
        "Origin": "https://www.roblox.com",
        "Referer": "https://www.roblox.com/"
    })
    s.timeout = timeout
    return s

def _get(s: Session, url: str, **kw) -> Any:
    r = s.get(url, timeout=kw.pop("timeout", 15))
    if r.status_code == 401 or r.status_code == 403:
        raise RobloxAPIError("unauthorized")
    r.raise_for_status()
    if "application/json" in r.headers.get("Content-Type", ""):
        return r.json()
    return r.text

def _calc_rap(s: Session, user_id: int) -> int:
    # Limited & LimitedU collectibles — пагинация
    total = 0
    cursor = ""
    while True:
        url = f"https://inventory.roblox.com/v1/users/{user_id}/assets/collectibles?limit=100&sortOrder=Asc"
        if cursor:
            url += f"&cursor={cursor}"
        data = _get(s, url)
        for item in data.get("data", []):
            # recentAveragePrice может отсутствовать, тогда 0
            total += int(item.get("recentAveragePrice") or 0)
        cursor = data.get("nextPageCursor")
        if not cursor:
            break
    return total

def _total_spent(s: Session, user_id: int) -> float:
    # быстрый приблизительный подсчёт: из истории покупок пользователя за Robux
    # (официальные приватные методы недоступны — берём доступное API economy)
    spent = 0.0
    cursor = ""
    while True:
        url = f"https://economy.roblox.com/v2/users/{user_id}/transactions?transactionType=Purchase&limit=100"
        if cursor:
            url += f"&cursor={cursor}"
        data = _get(s, url)
        for t in data.get("data", []):
            # суммируем только отрицательные Robux (трата)
            amt = t.get("currency", {}).get("amount")
            if isinstance(amt, (int, float)) and amt < 0:
                spent += abs(float(amt))
        cursor = data.get("nextPageCursor")
        if not cursor:
            break
    return spent

def check_cookie(cookie: str, timeout: int = 20) -> Dict[str, Any]:
    s = _sess(cookie, timeout=timeout)

    # 1) базовый профиль
    me = _get(s, "https://users.roblox.com/v1/users/authenticated")
    user_id = int(me["id"])
    username = me.get("name")
    display_name = me.get("displayName")

    # 2) верификации
    # e-mail
    mail = _get(s, "https://accountsettings.roblox.com/v1/email")
    mail_verified = bool(mail.get("verified"))

    # телефон
    try:
        phone = _get(s, "https://accountinformation.roblox.com/v1/phone")
        phone_verified = bool(phone.get("isVerified"))
    except Exception:
        phone_verified = False  # у региона/аккаунта может не быть эндпоинта

    # 2FA
    try:
        tfa = _get(s, f"https://twostepverification.roblox.com/v1/users/{user_id}/configuration")
        tfa_enabled = bool(tfa.get("isEnabled") or tfa.get("isEnabledForLogin"))
    except Exception:
        tfa_enabled = False

    # 3) billing (методы оплаты, если видны API)
    billing_sources = []
    try:
        pm = _get(s, "https://billing.roblox.com/v1/payment-methods")
        for p in pm or []:
            typ = p.get("paymentProvider") or p.get("paymentMethodType")
            if typ:
                billing_sources.append(str(typ))
    except Exception:
        pass

    # 4) RAP
    rap = 0
    try:
        rap = _calc_rap(s, user_id)
    except Exception:
        pass

    # 5) total spent (Robux)
    total_spent = 0.0
    try:
        total_spent = _total_spent(s, user_id)
    except Exception:
        pass

    return {
        "status": "ok",
        "user": {
            "id": user_id,
            "username": username,
            "display_name": display_name
        },
        "checks": {
            "mail_verified": mail_verified,
            "phone_verified": phone_verified,
            "two_factor_enabled": tfa_enabled,
            "billing_sources": billing_sources,
            "rap": rap,
            "total_spent_robux": total_spent
        }
    }
