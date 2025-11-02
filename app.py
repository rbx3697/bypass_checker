from flask import Flask, render_template, request, jsonify, session
import hashlib
import time
import threading
from datetime import datetime
import json
import requests
import random

app = Flask(__name__)
app.secret_key = 'meow-secret-key-' + str(random.randint(1000, 9999))  # Автогенерация

# Временное хранилище в памяти
users_sessions = {}
active_checks = 0
total_checks = 0
online_users = set()

class BypassSystem:
    def bypass_13_minus(self, credentials):
        """Bypass для аккаунтов 13-"""
        try:
            # Пример логики байпаса для младших аккаунтов
            username = credentials.get('username', '')
            password = credentials.get('password', '')
            
            # Имитация запросов байпаса
            result = {
                "status": "success",
                "message": f"Bypass 13- completed for {username}",
                "restrictions_removed": ["chat_limits", "content_filters"],
                "new_privileges": ["full_messaging", "adult_content"]
            }
            return result
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    def bypass_13_17(self, credentials):
        """Bypass для аккаунтов 13-17"""
        try:
            username = credentials.get('username', '')
            password = credentials.get('password', '')
            
            # Имитация байпаса для подростковых аккаунтов
            result = {
                "status": "success", 
                "message": f"Bypass 13-17 completed for {username}",
                "restrictions_removed": ["purchase_limits", "time_restrictions"],
                "new_privileges": ["unlimited_purchases", "extended_usage"]
            }
            return result
        except Exception as e:
            return {"status": "error", "message": str(e)}

class MeowChecker:
    def __init__(self):
        self.session = requests.Session()
        # Заголовки как в реальном браузере
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Content-Type': 'application/json'
        }

    def check_roblox_account(self, username, password):
        """Проверка Roblox аккаунта (аналог MeowTool)"""
        try:
            # Имитация проверки через Roblox API
            login_check = self._check_login(username, password)
            if not login_check["valid"]:
                return {"status": "invalid", "details": "Invalid credentials"}
            
            # Проверка ограничений
            restrictions = self._check_restrictions(username)
            
            # Проверка баланса и предметов
            inventory_info = self._check_inventory(username)
            
            result = {
                "account": username,
                "status": "valid",
                "premium": login_check.get("premium", False),
                "balance": inventory_info.get("robux", 0),
                "restrictions": restrictions,
                "created_date": login_check.get("created", "Unknown"),
                "last_online": login_check.get("last_online", "Unknown")
            }
            
            # Определяем финальный статус
            if restrictions.get("banned", False):
                result["status"] = "banned"
            elif restrictions.get("limited", False):
                result["status"] = "limited"
                
            return result
            
        except Exception as e:
            return {"status": "error", "details": str(e)}

    def _check_login(self, username, password):
        """Проверка валидности логина"""
        # Имитация проверки логина (в реальности - запросы к API)
        time.sleep(0.2)  # Имитация задержки
        
        # Случайная генерация результатов для демо
        return {
            "valid": random.choice([True, True, True, False]),  # 75% валидных
            "premium": random.choice([True, False]),
            "created": f"202{random.randint(0,3)}-{random.randint(1,12):02d}-{random.randint(1,28):02d}",
            "last_online": f"2024-{random.randint(1,12):02d}-{random.randint(1,28):02d}"
        }

    def _check_restrictions(self, username):
        """Проверка ограничений аккаунта"""
        return {
            "banned": random.choice([True, False, False, False]),  # 25% бан
            "limited": random.choice([True, False, False, False, False]),  # 20% лимит
            "chat_restricted": random.choice([True, False]),
            "trade_restricted": random.choice([True, False])
        }

    def _check_inventory(self, username):
        """Проверка инвентаря и баланса"""
        return {
            "robux": random.randint(0, 50000),
            "items_count": random.randint(0, 1000),
            "limiteds_count": random.randint(0, 50),
            "rap_value": random.randint(0, 100000)
        }

    def check_single(self, account_data):
        """Проверка одного аккаунта в формате username:password"""
        try:
            if ':' not in account_data:
                return {
                    "account": account_data,
                    "status": "invalid", 
                    "details": "Invalid format. Use username:password"
                }
            
            username, password = account_data.split(':', 1)
            result = self.check_roblox_account(username.strip(), password.strip())
            result["account"] = account_data
            
            return result
            
        except Exception as e:
            return {
                "account": account_data,
                "status": "error",
                "details": f"Check error: {str(e)}"
            }

    def mass_check(self, accounts_list):
        """Массовая проверка аккаунтов"""
        results = []
        
        for account in accounts_list:
            if account.strip():
                result = self.check_single(account.strip())
                results.append(result)
        
        return results

    def check_with_proxy(self, account_data, proxy=None):
        """Проверка с использованием прокси"""
        if proxy:
            self.session.proxies = {
                'http': proxy,
                'https': proxy
            }
        return self.check_single(account_data)

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

@app.route('/')
def index():
    """Главная страница с автоматическим входом"""
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
    credentials = request.json.get('credentials', {})
    result = bypass_system.bypass_13_minus(credentials)
    
    # Обновляем статистику пользователя
    user_id = get_user_id(request)
    if user_id in users_sessions:
        users_sessions[user_id]['bypass_count'] += 1
        users_sessions[user_id]['last_bypass'] = datetime.now().isoformat()
    
    return jsonify(result)

@app.route('/api/bypass_13_17', methods=['POST'])
def api_bypass_13_17():
    """Bypass для аккаунтов 13-17"""
    credentials = request.json.get('credentials', {})
    result = bypass_system.bypass_13_17(credentials)
    
    user_id = get_user_id(request)
    if user_id in users_sessions:
        users_sessions[user_id]['bypass_count'] += 1
        users_sessions[user_id]['last_bypass'] = datetime.now().isoformat()
    
    return jsonify(result)

@app.route('/api/check_accounts', methods=['POST'])
def api_check_accounts():
    """Проверка аккаунтов"""
    global active_checks, total_checks
    
    accounts_text = request.json.get('accounts', '')
    use_proxy = request.json.get('use_proxy', False)
    proxy_list = request.json.get('proxies', [])
    
    accounts_list = [acc for acc in accounts_text.split('\n') if acc.strip()]
    
    active_checks += len(accounts_list)
    
    # Выполняем проверку
    results = checker_system.mass_check(accounts_list)
    
    # Обновляем статистику
    active_checks -= len(accounts_list)
    total_checks += len(accounts_list)
    
    # Обновляем статистику пользователя
    user_id = get_user_id(request)
    if user_id in users_sessions:
        users_sessions[user_id]['check_count'] += len(accounts_list)
        users_sessions[user_id]['last_check'] = datetime.now().isoformat()
    
    return jsonify({'results': results})

@app.route('/api/check_single', methods=['POST'])
def api_check_single():
    """Проверка одного аккаунта"""
    global active_checks, total_checks
    
    account_data = request.json.get('account', '')
    
    if not account_data.strip():
        return jsonify({'error': 'No account provided'})
    
    active_checks += 1
    result = checker_system.check_single(account_data.strip())
    active_checks -= 1
    total_checks += 1
    
    user_id = get_user_id(request)
    if user_id in users_sessions:
        users_sessions[user_id]['check_count'] += 1
        users_sessions[user_id]['last_check'] = datetime.now().isoformat()
    
    return jsonify({'result': result})

@app.route('/api/stats')
def api_stats():
    """Статистика сайта"""
    global active_checks, total_checks
    
    return jsonify({
        'active_checks': active_checks,
        'total_checks': total_checks,
        'online_users': len(online_users),
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

if __name__ == '__main__':
    # Запускаем фоновую задачу для очистки неактивных пользователей
    thread = threading.Thread(target=update_online_users, daemon=True)
    thread.start()
    
    print("🐱 MeowTool Web запущен!")
    print("Secret Key:", app.secret_key)
    app.run(debug=True, host='0.0.0.0', port=5000)