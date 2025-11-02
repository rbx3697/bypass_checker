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

# Временное хранилище в памяти
users_sessions = {}
active_checks = 0
total_checks = 0
online_users = set()

class BypassSystem:
    def bypass_13_minus(self, credentials):
        """Bypass для аккаунтов 13-"""
        try:
            username = credentials.get('username', '')
            password = credentials.get('password', '')
            
            # Имитация байпаса
            result = {
                "status": "success",
                "message": f"Bypass 13- completed for {username}",
                "restrictions_removed": ["chat_limits", "content_filters", "purchase_blocks"],
                "new_privileges": ["full_messaging", "adult_content", "unlimited_purchases"]
            }
            return result
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    def bypass_13_17(self, credentials):
        """Bypass для аккаунтов 13-17"""
        try:
            username = credentials.get('username', '')
            password = credentials.get('password', '')
            
            result = {
                "status": "success", 
                "message": f"Bypass 13-17 completed for {username}",
                "restrictions_removed": ["time_restrictions", "spending_limits"],
                "new_privileges": ["extended_usage", "higher_spending_limits"]
            }
            return result
        except Exception as e:
            return {"status": "error", "message": str(e)}

class MeowChecker:
    def check_single(self, account_data):
        """Проверка одного аккаунта"""
        try:
            if ':' not in account_data:
                return {
                    "account": account_data,
                    "status": "invalid", 
                    "details": "Invalid format. Use username:password",
                    "robux": 0,
                    "premium": False
                }
            
            username, password = account_data.split(':', 1)
            
            # Имитация проверки
            time.sleep(0.3)
            
            status_options = ["valid", "valid", "valid", "limited", "banned"]
            status = random.choice(status_options)
            
            result = {
                "account": account_data,
                "status": status,
                "robux": random.randint(0, 50000),
                "premium": random.choice([True, False]),
                "details": self.get_status_details(status),
                "items_count": random.randint(0, 1000)
            }
            
            return result
            
        except Exception as e:
            return {
                "account": account_data,
                "status": "error",
                "details": f"Check error: {str(e)}",
                "robux": 0,
                "premium": False
            }

    def get_status_details(self, status):
        details = {
            "valid": "✅ Аккаунт валиден и активен",
            "limited": "⚠️ Аккаунт ограничен", 
            "banned": "❌ Аккаунт забанен",
            "invalid": "❌ Неверные данные для входа"
        }
        return details.get(status, "Unknown status")

    def mass_check(self, accounts_list):
        """Массовая проверка аккаунтов"""
        results = []
        
        for account in accounts_list:
            if account.strip():
                result = self.check_single(account.strip())
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
    credentials = request.json.get('credentials', {})
    result = bypass_system.bypass_13_minus(credentials)
    
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
    accounts_list = [acc for acc in accounts_text.split('\n') if acc.strip()]
    
    active_checks += len(accounts_list)
    results = checker_system.mass_check(accounts_list)
    active_checks -= len(accounts_list)
    total_checks += len(accounts_list)
    
    user_id = get_user_id(request)
    if user_id in users_sessions:
        users_sessions[user_id]['check_count'] += len(accounts_list)
        users_sessions[user_id]['last_check'] = datetime.now().isoformat()
    
    return jsonify({'results': results})

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

@app.route('/test')
def test():
    return "✅ Сервер работает! MeowTool активен."

if __name__ == '__main__':
    # Запускаем фоновую задачу
    thread = threading.Thread(target=update_online_users, daemon=True)
    thread.start()
    
    port = int(os.environ.get('PORT', 5000))
    print(f"🚀 MeowTool Web запущен на порту {port}")
    app.run(host='0.0.0.0', port=port, debug=False)