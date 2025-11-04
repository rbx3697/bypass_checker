import os
import time
import uuid
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from cryptography.fernet import Fernet, InvalidToken
from meow_wrapper import run_check_safe

# Настройка
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-me")
limiter = Limiter(key_func=get_remote_address, default_limits=["10 per minute", "100 per day"])

# Ключ для шифрования куков (Fernet)
FERNET_KEY = os.environ.get("FERNET_KEY")  # обязательно задавай в Render или .env
if not FERNET_KEY:
    # генерация временного ключа в dev режиме (не для продакшена)
    FERNET_KEY = Fernet.generate_key().decode()
fernet = Fernet(FERNET_KEY.encode() if isinstance(FERNET_KEY, str) else FERNET_KEY)

# Папка для временных результатов (не долгоживущая)
TMP_DIR = os.environ.get("TMP_DIR", "/tmp/checker_results")
os.makedirs(TMP_DIR, exist_ok=True)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/check", methods=["POST"])
@limiter.limit("5 per minute")  # дополнительный rate limit на эндпоинт
def check():
    # ВАЖНО: требуем подтверждение владения
    owner_confirm = request.form.get("owner_confirm")
    cookie_text = request.form.get("cookie")
    friend_email = request.form.get("friend_email", "").strip()

    if owner_confirm != "on":
        flash("Вы должны подтвердить, что аккаунт принадлежит вам или у вас есть разрешение владельца.", "danger")
        return redirect(url_for("index"))

    if not cookie_text or len(cookie_text) < 10:
        flash("Пожалуйста, вставьте действительный куки (или токен) для проверки.", "danger")
        return redirect(url_for("index"))

    # Зашифруем куки перед временным хранением
    try:
        token = fernet.encrypt(cookie_text.encode()).decode()
    except Exception as e:
        flash("Ошибка шифрования данных.", "danger")
        return redirect(url_for("index"))

    # Генерируем id задачи
    task_id = str(uuid.uuid4())
    task_file = os.path.join(TMP_DIR, f"{task_id}.task")
    with open(task_file, "w", encoding="utf-8") as f:
        f.write(token)

    # Запускаем проверку безопасно (run_check_safe возвращает dict с результатами)
    try:
        result = run_check_safe(encrypted_cookie=token, fernet=fernet, max_seconds=40)
    except Exception as e:
        # не раскрываем внутренности пользователю — логируем и показываем дружелюбную ошибку
        app.logger.exception("Check failed")
        flash("Ошибка выполнения проверки. Проверь логи сервера.", "danger")
        return redirect(url_for("index"))

    # Сохраним краткий отчет как json (в tmp) — для последующего скачивания/удаления
    out_file = os.path.join(TMP_DIR, f"{task_id}.json")
    import json
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    # (опционально) можно отправить приглашение другу — но почтовый сервис не настроен здесь
    if friend_email:
        app.logger.info("Friend invite requested (not sent): %s", friend_email)
        # Рекомендуется настроить явный mail provider (SendGrid/Mailgun) если хочешь рассылать приглашения.

    return render_template("results.html", result=result, task_id=task_id)

@app.route("/download/<task_id>")
def download(task_id):
    # отдаёт json отчёт, если существует
    out_file = os.path.join(TMP_DIR, f"{task_id}.json")
    if not os.path.exists(out_file):
        flash("Отчёта не найдено или он удалён.", "warning")
        return redirect(url_for("index"))
    from flask import send_file
    return send_file(out_file, as_attachment=True, download_name=f"report_{task_id}.json", mimetype="application/json")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=os.environ.get("FLASK_DEBUG", "0") == "1")
