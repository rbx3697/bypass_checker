import os
import json
import subprocess
import shlex
import tempfile
import sys
import traceback
from typing import Dict

def run_check_safe(encrypted_cookie: str, fernet, max_seconds: int = 30) -> Dict:
    """
    Безопасный адаптер для запуска MeowTool-проверки.
    - расшифровывает куки с помощью fernet
    - если в проекте есть MeowTool.py — пытается импортировать ограниченно
    - иначе запускает MeowTool.py как subprocess с таймаутом и парсит stdout/выходный json
    Возвращает словарь с результатами проверки (или ошибку).
    """
    try:
        cookie = fernet.decrypt(encrypted_cookie.encode()).decode()
    except Exception as e:
        return {"status": "error", "error": "invalid_encryption"}

    # 1) Попробуем импортировать MeowTool (безопасно: проверяем наличие)
    if os.path.exists("MeowTool.py"):
        try:
            # импортируем модуль динамически в sandbox-namespace
            import importlib.util
            spec = importlib.util.spec_from_file_location("meowtool_local", os.path.abspath("MeowTool.py"))
            meow = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(meow)
            # ожидаем, что есть функция check_cookie или похожая; делаем best-effort
            if hasattr(meow, "check_cookie"):
                # предполагаем синхронный вызов: check_cookie(cookie) -> dict
                res = meow.check_cookie(cookie)
                return {"status": "ok", "source": "import", "result": res}
            # иначе — попытаемся вызвать main-like CLI
        except Exception:
            # не прерываем: делаем fallback на subprocess
            pass

    # 2) Fallback: запустим MeowTool.py как внешний процесс, чтобы не подцеплять его в наш процесс
    if os.path.exists("MeowTool.py"):
        try:
            # создаём временный файл с куки (чтобы не передавать в argv)
            with tempfile.NamedTemporaryFile(mode="w+", delete=False, encoding="utf-8") as tf:
                tf.write(cookie)
                tf.flush()
                temp_path = tf.name

            # формируем команду — предполагаем, что MeowTool умеет читать куки из файла через аргумент.
            cmd = f"{sys.executable} MeowTool.py --input-file {shlex.quote(temp_path)} --json-output"
            proc = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=max_seconds)
            stdout = proc.stdout.strip()
            stderr = proc.stderr.strip()
            # Попытка распарсить JSON из stdout
            try:
                parsed = json.loads(stdout)
                return {"status": "ok", "source": "subprocess", "result": parsed, "stderr": stderr}
            except Exception:
                # Если нет JSON, вернём сырой вывод
                return {"status": "ok", "source": "subprocess", "result": {"raw_stdout": stdout, "raw_stderr": stderr}}
        except subprocess.TimeoutExpired:
            return {"status": "error", "error": "timeout"}
        except Exception as e:
            return {"status": "error", "error": "subprocess_error", "trace": traceback.format_exc()}
        finally:
            try:
                os.unlink(temp_path)
            except Exception:
                pass

    return {"status": "error", "error": "meowtool_not_found"}
