// Обновление статистики каждые 10 секунд
function updateStats() {
    fetch('/api/stats')
        .then(response => response.json())
        .then(data => {
            document.getElementById('active-checks').textContent = data.active_checks;
            document.getElementById('total-checks').textContent = data.total_checks;
            document.getElementById('online-users').textContent = data.online_users;
            document.getElementById('online-counter').textContent = `Online: ${data.online_users}`;
        })
        .catch(error => console.error('Error updating stats:', error));
}

// Обновление статистики пользователя
function updateUserStats() {
    fetch('/api/user_stats')
        .then(response => response.json())
        .then(data => {
            const userStatsElement = document.getElementById('user-stats');
            if (userStatsElement) {
                userStatsElement.innerHTML = `
                    <p>ID: ${data.user_id}</p>
                    <p>Проверок: ${data.check_count}</p>
                    <p>Последняя проверка: ${data.last_check}</p>
                `;
            }
        });
}

// Запуск обновлений
setInterval(updateStats, 10000); // Каждые 10 секунд
setInterval(updateUserStats, 15000); // Каждые 15 секунд

// Инициализация при загрузке
document.addEventListener('DOMContentLoaded', function() {
    updateStats();
    updateUserStats();
});

// Функция для проверки аккаунтов
function checkAccounts() {
    const accountsText = document.getElementById('accounts-input').value;
    const resultsDiv = document.getElementById('checker-results');
    
    if (!accountsText.trim()) {
        alert('Введите аккаунты для проверки!');
        return;
    }
    
    resultsDiv.innerHTML = '<p>Проверка запущена...</p>';
    
    fetch('/api/check_accounts', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            accounts: accountsText
        })
    })
    .then(response => response.json())
    .then(data => {
        displayResults(data.results);
        updateStats(); // Обновляем статистику после проверки
        updateUserStats();
    })
    .catch(error => {
        console.error('Error:', error);
        resultsDiv.innerHTML = '<p>Ошибка при проверке аккаунтов</p>';
    });
}

// Отображение результатов проверки
function displayResults(results) {
    const resultsDiv = document.getElementById('checker-results');
    let html = '<h3>Результаты проверки:</h3>';
    
    results.forEach(result => {
        const statusClass = `result-${result.status}`;
        html += `
            <div class="result-item ${statusClass}">
                <strong>${result.account}</strong> - ${result.status} 
                <br><small>${result.details}</small>
            </div>
        `;
    });
    
    resultsDiv.innerHTML = html;
}