"""System tray launcher for claude-note.

Run cn.exe → tray icon appears, worker + web server auto-start.
Right-click → start/stop worker, open Web UI, quit.
"""

import atexit
import shutil
import subprocess
import sys
import threading
import webbrowser

import pystray
from PIL import Image, ImageDraw, ImageFont

from . import config

_WEB_HOST = "127.0.0.1"
_WEB_PORT = 8080

_procs: dict[str, subprocess.Popen] = {}
_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Icon
# ---------------------------------------------------------------------------

def _make_icon(color: str = "#757575") -> Image.Image:
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse([2, 2, size - 2, size - 2], fill=color)
    try:
        font = ImageFont.truetype("arial.ttf", 20)
    except OSError:
        font = ImageFont.load_default()
    d.text((size // 2, size // 2), "CN", fill="white", font=font, anchor="mm")
    return img


def _status_color() -> str:
    running = sum(1 for p in _procs.values() if p.poll() is None)
    total = len(_procs)
    if running == 0 or total == 0:
        return "#757575"   # grey  — все остановлены
    if running < total:
        return "#FF9800"   # orange — частично
    return "#4CAF50"       # green  — все запущены


# ---------------------------------------------------------------------------
# Process management
# ---------------------------------------------------------------------------

def _exe() -> str:
    """Return path to current executable (works both frozen and dev)."""
    if getattr(sys, "frozen", False):
        return sys.executable

    # Dev mode: resolve cn / claude-note script
    for name in ("cn", "claude-note"):
        found = shutil.which(name)
        if found:
            return found

    # Fallback: run as module
    return None


def _cmd(subcommand: str, extra: list[str] | None = None) -> list[str]:
    exe = _exe()
    if exe:
        cmd = [exe, subcommand]
    else:
        cmd = [sys.executable, "-m", "claude_note", subcommand]
    if extra:
        cmd.extend(extra)
    return cmd


def _is_running(service: str) -> bool:
    p = _procs.get(service)
    return p is not None and p.poll() is None


def _start(service: str):
    with _lock:
        if _is_running(service):
            return
        if service == "worker":
            cmd = _cmd("worker", ["--foreground"])
        elif service == "web":
            cmd = _cmd("web", ["--host", _WEB_HOST, "--port", str(_WEB_PORT)])
        else:
            return
        popen_kwargs: dict = {}
        if sys.platform == "win32":
            popen_kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
            popen_kwargs["stdout"] = subprocess.DEVNULL
            popen_kwargs["stderr"] = subprocess.DEVNULL
        _procs[service] = subprocess.Popen(cmd, **popen_kwargs)


def _stop(service: str):
    with _lock:
        p = _procs.pop(service, None)
        if p and p.poll() is None:
            p.terminate()
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                p.kill()


def _stop_all():
    for service in list(_procs):
        _stop(service)


# ---------------------------------------------------------------------------
# Menu
# ---------------------------------------------------------------------------

def _label(service: str, display_name: str):
    def fn(item):
        mark = "▶" if _is_running(service) else "■"
        return f"{mark}  {display_name}"
    return fn


def _toggle(service: str, icon: pystray.Icon):
    if _is_running(service):
        _stop(service)
    else:
        _start(service)
    _refresh(icon)


def _refresh(icon: pystray.Icon):
    icon.icon = _make_icon(_status_color())
    icon.title = _tooltip()
    icon.update_menu()


def _tooltip() -> str:
    lines = ["claude-note"]
    labels = {"worker": "Worker", "web": "Web UI"}
    for name, p in _procs.items():
        state = "запущен" if p.poll() is None else "остановлен"
        lines.append(f"{labels.get(name, name)}: {state}")
    return "\n".join(lines)


def _build_menu(icon: pystray.Icon) -> pystray.Menu:
    def toggle_worker(i, it):
        _toggle("worker", i)

    def toggle_web(i, it):
        _toggle("web", i)

    def start_all(i, it):
        _start("worker")
        _start("web")
        _refresh(i)

    def stop_all(i, it):
        _stop_all()
        _refresh(i)

    def open_ui(i, it):
        webbrowser.open(f"http://{_WEB_HOST}:{_WEB_PORT}")

    def quit_app(i, it):
        _stop_all()
        i.stop()

    return pystray.Menu(
        pystray.MenuItem("claude-note", None, enabled=False),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem(_label("worker", "Worker"),  toggle_worker),
        pystray.MenuItem(_label("web",    "Web UI"),  toggle_web),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Запустить все",  start_all),
        pystray.MenuItem("Остановить все", stop_all),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem(
            f"Открыть Web UI  ({_WEB_HOST}:{_WEB_PORT})",
            open_ui,
        ),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Выход", quit_app),
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run_tray():
    """Start tray app and auto-launch worker + web server."""
    atexit.register(_stop_all)

    icon = pystray.Icon(
        name="claude-note",
        icon=_make_icon(_status_color()),
        title="claude-note",
    )
    icon.menu = _build_menu(icon)

    # Auto-start
    _start("worker")
    _start("web")

    _refresh(icon)
    icon.run()
