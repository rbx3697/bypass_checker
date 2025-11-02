// Обновление статистики сайта каждые 10 секунд
function updateStats() {
    fetch('/api/stats')
        .then(response => response.json())
        .then(data => {
            document.getElementById('active-checks').textContent = data.active_checks;
            document.getElementById('total-checks').textContent = data.total_checks;
            document.getElementById('online-users').textContent = data.online_users;
            document.getElementById('online-counter').textContent = `Online: ${data.online_users}`;
            
            // Обновление статистики на главной
            const statsOnline = document.getElementById('stats-online');
            const statsActive = document.getElementById('stats-active');
            const statsTotal = document.getElementById('stats-total');
            
            if (statsOnline) statsOnline.textContent = data.online_users;
            if (statsActive) statsActive.textContent = data.active_checks;
            if (statsTotal) statsTotal.textContent = data.total_checks;
        })
        .catch(error => console.error('Error updating stats:', error));
}

// Обновление статистики пользователя
function updateUserStats() {
    fetch('/api/user_stats')
        .then(response => response.json())
        .then(data => {
            const userCheckCount = document.getElementById('user-check-count');
            const userBypassCount = document.getElementById('user-bypass-count');
            const lastCheck = document.getElementById('last-check');
            const lastBypass = document.getElementById('last-bypass');
            
            if (userCheckCount) userCheckCount.textContent = data.check_count;
            if (userBypassCount) userBypassCount.textContent = data.bypass_count;
            if (lastCheck) lastCheck.textContent = data.last_check;
            if (lastBypass) lastBypass.textContent = data.last_bypass;
        })
        .catch(error => console.error('Error updating user stats:', error));
}

// Запуск обновлений
setInterval(updateStats, 10000); // Каждые 10 секунд
setInterval(updateUserStats, 15000); // Каждые 15 секунд

// Инициализация при загрузке
document.addEventListener('DOMContentLoaded', function() {
    updateStats();
    updateUserStats();
    
    // Добавляем анимации при загрузке
    const cards = document.querySelectorAll('.card');
    cards.forEach((card, index) => {
        card.style.opacity = '0';
        card.style.transform = 'translateY(20px)';
        setTimeout(() => {
            card.style.transition = 'all 0.5s ease';
            card.style.opacity = '1';
            card.style.transform = 'translateY(0)';
        }, index * 100);
    });
});

// Функция для показа уведомлений
function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.innerHTML = `
        <div class="notification-content">
            <span class="notification-message">${message}</span>
            <button class="notification-close" onclick="this.parentElement.parentElement.remove()">×</button>
        </div>
    `;
    
    // Стили для уведомления
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        background: ${type === 'success' ? 'rgba(0, 255, 136, 0.9)' : 
                     type === 'error' ? 'rgba(255, 68, 68, 0.9)' : 
                     'rgba(5, 217, 232, 0.9)'};
        color: white;
        padding: 1rem;
        border-radius: 8px;
        box-shadow: 0 0 20px rgba(0,0,0,0.3);
        z-index: 10000;
        max-width: 300px;
        backdrop-filter: blur(10px);
    `;
    
    document.body.appendChild(notification);
    
    // Автоматическое удаление через 5 секунд
    setTimeout(() => {
        if (notification.parentElement) {
            notification.remove();
        }
    }, 5000);
}

// Добавляем стили для уведомлений
const notificationStyles = document.createElement('style');
notificationStyles.textContent = `
    .notification-content {
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    
    .notification-close {
        background: none;
        border: none;
        color: white;
        font-size: 1.2rem;
        cursor: pointer;
        margin-left: 1rem;
    }
    
    .notification-close:hover {
        opacity: 0.8;
    }
`;
document.head.appendChild(notificationStyles);