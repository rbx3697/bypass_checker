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

def get_user_id(request):
    """Создаем ID пользователя на основе браузера и IP"""
    user_agent = request.headers.get('User-Agent', '')
    ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    user_string = f"{ip}_{user_agent}"
    user_hash = hashlib.md5(user_string.encode()).hexdigest()
    return user_hash

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

# БАЗОВЫЕ МАРШРУТЫ
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
@app.route('/api/stats')
def api_stats():
    """Статистика сайта"""
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

# Тестовый маршрут для проверки
@app.route('/test')
def test():
    return "✅ Сервер работает! MeowTool активен."

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)