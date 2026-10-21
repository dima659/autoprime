"""Графическое меню запуска AutoPrime. Открывается двойным кликом."""

import os
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, scrolledtext

ROOT = Path(__file__).resolve().parent
ENV_FILE = ROOT / ".env"
process = None


def read_env():
    result = {}
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text("utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                key, value = line.split("=", 1)
                result[key.strip()] = value.strip()
    return result


def save_settings():
    token = token_var.get().strip()
    if ":" not in token or len(token) < 20:
        messagebox.showerror("AutoPrime", "Вставьте корректный токен из BotFather.")
        return False
    ENV_FILE.write_text(
        "\n".join(
            [
                f"BOT_TOKEN={token}",
                f"ADMIN_ID={admin_var.get().strip() or '5486146974'}",
                f"MANAGER_USERNAME={manager_var.get().strip().lstrip('@') or 'savrrage'}",
                "",
            ]
        ),
        "utf-8",
    )
    return True


def log(text):
    window.after(0, lambda: _log(text))


def _log(text):
    output.configure(state="normal")
    output.insert("end", text)
    output.see("end")
    output.configure(state="disabled")


def set_running(running):
    window.after(
        0,
        lambda: (
            start_button.configure(state="disabled" if running else "normal"),
            stop_button.configure(state="normal" if running else "disabled"),
            status_var.set("● Бот работает" if running else "○ Бот остановлен"),
        ),
    )


def worker():
    global process
    try:
        log("\nПроверяю библиотеки...\n")
        install = subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "--upgrade",
                "--only-binary=:all:",
                "--disable-pip-version-check",
                "-q",
                "-r",
                str(ROOT / "requirements.txt"),
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        if install.returncode:
            log(install.stdout + install.stderr)
            raise RuntimeError(
                "Не удалось установить готовые библиотеки для этой версии Python."
            )

        log("Запускаю AutoPrime и создаю защищённый адрес...\n\n")
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        process = subprocess.Popen(
            [sys.executable, "-u", str(ROOT / "main.py")],
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=flags,
        )
        set_running(True)
        for line in process.stdout:
            log(line)
        code = process.wait()
        log(f"\nПроцесс завершён, код {code}.\n")
    except Exception as error:
        log(f"\nОШИБКА: {error}\n")
    finally:
        process = None
        set_running(False)


def start():
    if process is not None:
        return
    if not save_settings():
        return
    output.configure(state="normal")
    output.delete("1.0", "end")
    output.configure(state="disabled")
    threading.Thread(target=worker, daemon=True).start()


def stop():
    global process
    if process is not None and process.poll() is None:
        log("\nОстанавливаю бота...\n")
        process.terminate()


def close():
    stop()
    window.destroy()


saved = read_env()
window = tk.Tk()
window.title("AutoPrime — запуск")
window.geometry("660x590")
window.minsize(560, 500)
window.configure(bg="#10120f")
window.protocol("WM_DELETE_WINDOW", close)

header = tk.Frame(window, bg="#10120f")
header.pack(fill="x", padx=24, pady=(22, 10))
tk.Label(
    header, text="AUTO", bg="#10120f", fg="#f4f6ef", font=("Arial", 22, "bold")
).pack(side="left")
tk.Label(
    header, text="PRIME", bg="#10120f", fg="#c8ff32", font=("Arial", 22, "bold")
).pack(side="left")
status_var = tk.StringVar(value="○ Бот остановлен")
tk.Label(header, textvariable=status_var, bg="#10120f", fg="#9ca392", font=("Arial", 11)).pack(
    side="right"
)

form = tk.Frame(window, bg="#181b16", highlightbackground="#30342d", highlightthickness=1)
form.pack(fill="x", padx=24, pady=10)


def field(label, variable, show=None):
    tk.Label(form, text=label, bg="#181b16", fg="#9ca392", anchor="w", font=("Arial", 10)).pack(
        fill="x", padx=16, pady=(12, 4)
    )
    entry = tk.Entry(
        form,
        textvariable=variable,
        show=show,
        bg="#0d0f0c",
        fg="#f4f6ef",
        insertbackground="#c8ff32",
        relief="flat",
        font=("Arial", 11),
    )
    entry.pack(fill="x", padx=16, ipady=9)
    return entry


token_var = tk.StringVar(value=saved.get("BOT_TOKEN", ""))
admin_var = tk.StringVar(value=saved.get("ADMIN_ID", "5486146974"))
manager_var = tk.StringVar(value=saved.get("MANAGER_USERNAME", "savrrage"))
field("Токен из BotFather", token_var, "●")
field("Telegram ID администратора", admin_var)
field("Username менеджера", manager_var)
tk.Frame(form, height=12, bg="#181b16").pack()

actions = tk.Frame(window, bg="#10120f")
actions.pack(fill="x", padx=24, pady=4)
start_button = tk.Button(
    actions,
    text="ЗАПУСТИТЬ БОТА",
    command=start,
    bg="#c8ff32",
    fg="#0a0b09",
    activebackground="#b5e82d",
    relief="flat",
    font=("Arial", 11, "bold"),
    cursor="hand2",
)
start_button.pack(side="left", fill="x", expand=True, ipady=10)
stop_button = tk.Button(
    actions,
    text="ОСТАНОВИТЬ",
    command=stop,
    state="disabled",
    bg="#2b3027",
    fg="#f4f6ef",
    disabledforeground="#73786d",
    relief="flat",
    font=("Arial", 10, "bold"),
)
stop_button.pack(side="left", padx=(10, 0), ipadx=12, ipady=10)

output = scrolledtext.ScrolledText(
    window,
    state="disabled",
    bg="#090a09",
    fg="#dce3d4",
    insertbackground="#c8ff32",
    relief="flat",
    font=("Consolas", 10),
    wrap="word",
)
output.pack(fill="both", expand=True, padx=24, pady=(12, 24))
_log("Введите токен и нажмите «Запустить бота».\nПосле надписи «ГОТОВО» отправьте боту /start.\n")

window.mainloop()