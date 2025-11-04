import os
import uuid
from flask import Flask, render_template, request, redirect, url_for, flash, send_file
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from cryptography.fernet import Fernet
from meow_wrapper import run_check_safe
import json

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-me")
limiter = Limiter(key_func=get_remote_address, default_limits=["10 per minute", "100 per day"])

# Fernet key - обязательно задавать в окружении в prod
FERNET_KEY = os.environ.get("FERNET_KEY")
if not FERNET_KEY:
    FERNET_KEY = Fernet.generate_key().decode()
fernet = Fernet(FERNET_KEY.encode() if isinstance(FERNET_KEY, str) else FERNET_KEY)

TMP_DIR = os.environ.get("TMP_DIR", "/tmp/checker_results")
os.makedirs(TMP_DIR, exist_ok=True)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/check", methods=["POST"])
@limiter.limit("5 per minute")
def check():
    owner_confirm = request.form.get("owner_confirm")
    cookie_text = request.form.get("cookie")

    if owner_confirm != "on":
        flash("Вы должны подтвердить, что аккаунт принадлежит вам или у вас есть разрешение владельца.", "danger")
        return redirect(url_for("index"))

    if not cookie_text or len(cookie_text) < 10:
        flash("Пожалуйста, вставьте действительный куки или токен.", "danger")
        return redirect(url_for("index"))

    try:
        token = fernet.encrypt(cookie_text.encode()).decode()
    except Exception:
        flash("Ошибка шифрования данных.", "danger")
        return redirect(url_for("index"))

    task_id = str(uuid.uuid4())
    out_file = os.path.join(TMP_DIR, f"{task_id}.json")

    try:
        result = run_check_safe(encrypted_cookie=token, fernet=fernet, max_seconds=40)
    except Exception:
        app.logger.exception("Check failed")
        flash("Ошибка выполнения проверки. Проверь логи сервера.", "danger")
        return redirect(url_for("index"))

    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    return render_template("results.html", result=result, task_id=task_id)

@app.route("/download/<task_id>")
def download(task_id):
    out_file = os.path.join(TMP_DIR, f"{task_id}.json")
    if not os.path.exists(out_file):
        flash("Отчёта не найдено или он удалён.", "warning")
        return redirect(url_for("index"))
    return send_file(out_file, as_attachment=True, download_name=f"report_{task_id}.json", mimetype="application/json")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=os.environ.get("FLASK_DEBUG", "0") == "1")
