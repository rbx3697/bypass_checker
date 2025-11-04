from __future__ import annotations
import os, time
import requests
from requests import Session
from typing import Dict, Any, Optional

class RobloxAPIError(Exception):
    pass

def _sess(cookie: str) -> Session:
    """
    Аккуратная сессия:
    - ТОЛЬКО нужные заголовки (без Origin/Referer)
    - стабильный RBX-DeviceId (если указан в ENV)
    - можно задать прокси (ENV HTTP_PROXY / HTTPS_PROXY)
    - никаких POST, только GET (чтобы не трогать CSRF и не трогать сессию)
    """
    s = requests.Session()
    s.trust_env = True  # разрешим прокси из окружения, если заданы
    s.cookies.set(".ROBLOSECURITY", cookie, domain=".roblox.com")
    headers = {
        "User-Agent": os.environ.get("RBX_USER_AGENT", "NeonChecker/1.3 (+render)"),
        "Accept": "application/json",
    }
    device_id = os.environ.get("RBX_DEVICE_ID")
    if device_id:
        headers["RBX-DeviceId"] = device_id
    s.headers.update(headers)

    # мягкие таймауты на уровне запросов
    s.request = _wrap_request_with_timeout(s.request, default_timeout=float(os.environ.get("RBX_HTTP_TIMEOUT", "15")))
    return s

def _wrap_request_with_timeout(orig_request, default_timeout: float):
    def _request(method, url, **kw):
        if "timeout" not in kw:
            kw["timeout"] = default_timeout
        return orig_request(method, url, **kw)
    return _request

def _get(s: Session, url: str, retries: int = 2):
    delay = 0.6
    for attempt in range(retries + 1):
        try:
            r = s.get(url)
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

# ---------- сборщик ----------

def check_cookie(cookie: str, timeout: int = 20) -> Dict[str, Any]:
    s = _sess(cookie)

    # 0) кто мы (если тут шлёпается — отдаём понятную ошибку, не ломаем сайт)
    try:
        me = _get(s, "https://users.roblox.com/v1/users/authenticated")
    except RobloxAPIError as e:
        return {
            "status": "error",
            "error": str(e),
            "hint": "Проверь .ROBLOSECURITY и попробуй ещё раз (лучше с тем же IP/регионом, что и браузер)."
        }

    user_id   = int(me.get("id"))
    username  = me.get("name")
    display   = me.get("displayName")

    # 1) базовые данные (только чтение + GET)
    created_iso = _safe(lambda: _get(s, f"https://users.roblox.com/v1/users/{user_id}").get("created"))
    premium     = bool(_safe(lambda: _get(s, f"https://premiumfeatures.roblox.com/v1/users/{user_id}/validate-membership"), False))
    friends_cnt = int(_safe(lambda: _get(s, f"https://friends.roblox.com/v1/users/{user_id}/friends/count").get("count"), 0))

    # 2) верификации
    mail_verified  = bool(_safe(lambda: _get(s, "https://accountsettings.roblox.com/v1/email").get("verified"), False))
    phone_verified = bool(_safe(lambda: _get(s, "https://accountinformation.roblox.com/v1/phone").get("isVerified"), False))
    tfa_enabled    = bool(_safe(lambda: (_get(s, f"https://twostepverification.roblox.com/v1/users/{user_id}/configuration").get("isEnabled")
                                        or _get(s, f"https://twostepverification.roblox.com/v1/users/{user_id}/configuration").get("isEnabledForLogin")), False))

    # 3) баланс Robux: берём userId-вариант (он надёжнее)
    robux = int(_safe(lambda: _get(s, f"https://economy.roblox.com/v1/users/{user_id}/currency").get("robux"), 0))

    # 4) RAP — только collectibles; если инвентарь закрыт, вернётся 0 (и это ок)
    def _rap():
        total, cursor = 0, ""
        while True:
            url = f"https://inventory.roblox.com/v1/users/{user_id}/assets/collectibles?limit=100&sortOrder=Asc"
            if cursor: url += f"&cursor={cursor}"
            data = _get(s, url)
            for it in data.get("data", []):
                total += int(it.get("recentAveragePrice") or 0)
            cursor = data.get("nextPageCursor")
            if not cursor: break
        return total
    rap = int(_safe(_rap, 0))

    # 5) Pending — из Sales с isPending
    def _pending():
        total, cursor = 0.0, ""
        while True:
            url = f"https://economy.roblox.com/v2/users/{user_id}/transactions?transactionType=Sale&limit=100"
            if cursor: url += f"&cursor={cursor}"
            data = _get(s, url)
            for t in data.get("data", []):
                amt = t.get("currency", {}).get("amount")
                if isinstance(amt, (int, float)) and amt > 0 and t.get("isPending"):
                    total += float(amt)
            cursor = data.get("nextPageCursor")
            if not cursor: break
        return total
    pending = float(_safe(_pending, 0.0))

    # 6) Всего потрачено — все страницы Purchase (отрицательные суммы берём по модулю)
    def _spent():
        total, cursor = 0.0, ""
        while True:
            url = f"https://economy.roblox.com/v2/users/{user_id}/transactions?transactionType=Purchase&limit=100"
            if cursor: url += f"&cursor={cursor}"
            data = _get(s, url)
            for t in data.get("data", []):
                amt = t.get("currency", {}).get("amount")
                if isinstance(amt, (int, float)) and amt < 0:
                    total += abs(float(amt))
            cursor = data.get("nextPageCursor")
            if not cursor: break
        return total
    total_spent = float(_safe(_spent, 0.0))

    # 7) Group funds (если владелец)
    def _group_funds():
        total = 0
        groups = _get(s, f"https://groups.roblox.com/v2/users/{user_id}/groups/roles").get("data", [])
        for g in groups:
            if int(g.get("role", {}).get("rank") or 0) == 255:
                gid = g.get("group", {}).get("id")
                try:
                    val = _get(s, f"https://economy.roblox.com/v1/groups/{gid}/currency")
                    total += int(val.get("robux") or 0)
                except RobloxAPIError:
                    pass
        return total
    group_funds = int(_safe(_group_funds, 0))

    # 8) Платёжные методы → есть ли карта
    card_present = False
    billing_sources = []
    def _billing():
        nonlocal card_present, billing_sources
        pm = _get(s, "https://billing.roblox.com/v1/payment-methods")
        # формат может отличаться; пытаемся угадать тип
        if isinstance(pm, list):
            items = pm
        else:
            items = pm or []
        for p in items:
            typ = p.get("paymentMethodType") or p.get("paymentProvider") or p.get("type")
            if typ:
                billing_sources.append(str(typ))
                if "card" in str(typ).lower() or "adyen" in str(typ).lower() or "credit" in str(typ).lower():
                    card_present = True
    _safe(_billing, None)

    return {
        "status": "ok",
        "user": {
            "id": user_id,
            "username": username,
            "display_name": display,
            "created": created_iso,
            "premium": premium,
            "friends_count": friends_cnt
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
            "billing_sources": billing_sources,
            "card_present": card_present
        }
    }
