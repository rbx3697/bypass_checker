import os
import uuid
import json
from flask import Flask, render_template, request, redirect, url_for, flash, send_file, Response
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from cryptography.fernet import Fernet
from meow_wrapper import run_check_safe

app = Flask(__name__)

# --- Secrets / Config ---
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-me")
limiter = Limiter(key_func=get_remote_address, default_limits=["10 per minute", "100 per day"])

FERNET_KEY = os.environ.get("FERNET_KEY")
if not FERNET_KEY:
    # dev-only fallback; в проде ОБЯЗАТЕЛЬНО задать FERNET_KEY в Environment
    FERNET_KEY = Fernet.generate_key().decode()

fernet = Fernet(FERNET_KEY.encode() if isinstance(FERNET_KEY, str) else FERNET_KEY)

TMP_DIR = os.environ.get("TMP_DIR", "/tmp/checker_results")
os.makedirs(TMP_DIR, exist_ok=True)

# --- Routes ---

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/check", methods=["POST"])
@limiter.limit("5 per minute")
def check():
    owner_confirm = request.form.get("owner_confirm")
    cookie_text = request.form.get("cookie")

    if owner_confirm != "on":
        flash("Подтверди, что аккаунт твой или есть разрешение владельца.", "danger")
        return redirect(url_for("index"))

    if not cookie_text or len(cookie_text) < 10:
        flash("Вставь валидный куки/токен.", "danger")
        return redirect(url_for("index"))

    # шифруем токен
    try:
        token = fernet.encrypt(cookie_text.encode()).decode()
    except Exception:
        flash("Ошибка шифрования.", "danger")
        return redirect(url_for("index"))

    task_id = str(uuid.uuid4())
    out_json = os.path.join(TMP_DIR, f"{task_id}.json")
    out_secret = os.path.join(TMP_DIR, f"{task_id}.secret")

    # храним ЗАШИФРОВАННЫЙ токен (нужен только для txt-экспорта по явному запросу)
    with open(out_secret, "w", encoding="utf-8") as f:
        f.write(token)

    # запускаем проверку
    try:
        result = run_check_safe(encrypted_cookie=token, fernet=fernet, max_seconds=40)
    except Exception:
        app.logger.exception("check failed")
        result = {"status": "error", "error": "internal_exception"}

    # сохраняем отчёт (даже если error)
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    payload = result.get("result") or {}
    return render_template("results.html", result=result, payload=payload, task_id=task_id)

@app.route("/download/<task_id>")
def download(task_id):
    out_file = os.path.join(TMP_DIR, f"{task_id}.json")
    if not os.path.exists(out_file):
        flash("Отчёт не найден.", "warning")
        return redirect(url_for("index"))
    return send_file(out_file, as_attachment=True, download_name=f"report_{task_id}.json", mimetype="application/json")

def _build_summary_line(payload: dict, secret_cookie: str | None) -> str:
    u = payload.get("user", {}) if isinstance(payload, dict) else {}
    c = payload.get("checks", {}) if isinstance(payload, dict) else {}

    username = u.get("username") or "-"
    uid = u.get("id") or "-"
    robux = c.get("robux", 0)
    total_spent = c.get("total_spent_robux", 0)
    premium = "Да" if u.get("premium") else "Нет"
    twofa = "Да" if c.get("two_factor_enabled") else "Нет"
    pending = c.get("pending_robux", 0)
    billing = ",".join(c.get("billing_sources", []) or []) if c.get("billing_sources") else "Нет"
    card = "Нет"  # если понадобится — можно распознать по billing_sources
    inventory = "Friends" if u.get("inventory_public") is False else ("Public" if u.get("inventory_public") else "Unknown")
    voice = "Да" if u.get("voice_enabled") else "Нет"
    created = (u.get("created") or "-")[:10]
    rap = c.get("rap", 0)
    groups = c.get("group_funds_robux", 0)

    line = (f"Username: {username} | ID: {uid} | Robux: {robux} | Total Spent: {total_spent} | "
            f"Premium: {premium} | 2FA: {twofa} | Pending: {pending} | Billing: {billing} | "
            f"Card: {card} | Inventory: {inventory} | Voice: {voice} | Created: {created} | "
            f"RAP: {rap} | GroupFunds: {groups}")

    if secret_cookie:
        warning = "_|WARNING:-DO-NOT-SHARE-THIS.--Sharing-this-will-allow-someone-to-log-in-as-you-and-to-steal-your-ROBUX-and-items.|_"
        line = f"{line} | {warning}{secret_cookie}"
    return line

@app.route("/export/<task_id>")
def export_txt(task_id):
    include_secret = request.args.get("include_secret") == "1"
    out_json = os.path.join(TMP_DIR, f"{task_id}.json")
    out_secret = os.path.join(TMP_DIR, f"{task_id}.secret")

    if not os.path.exists(out_json):
        flash("Отчёт не найден.", "warning")
        return redirect(url_for("index"))

    with open(out_json, "r", encoding="utf-8") as f:
        result = json.load(f)
    payload = result.get("result") or {}

    secret_cookie = None
    if include_secret and os.path.exists(out_secret):
        try:
            with open(out_secret, "r", encoding="utf-8") as f:
                enc = f.read().strip()
            secret_cookie = fernet.decrypt(enc.encode()).decode()
        except Exception:
            secret_cookie = None

    line = _build_summary_line(payload, secret_cookie)
    return Response(
        line, mimetype="text/plain",
        headers={"Content-Disposition": f"attachment; filename=summary_{task_id}.txt"}
    )

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=os.environ.get("FLASK_DEBUG", "0") == "1")
