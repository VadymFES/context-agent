import time
import win32gui
import win32process
import psutil


def get_active_window() -> tuple[str, str, int]:
    hwnd = win32gui.GetForegroundWindow()
    title = win32gui.GetWindowText(hwnd)

    try:
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        app = psutil.Process(pid).name()
    except Exception:
        app = "unknown"

    return title, app, hwnd


def watch(on_change, interval: float = 0.5):
    last_title = ""

    while True:
        title, app, hwnd = get_active_window()

        if title and title != last_title:
            last_title = title
            on_change(title, app, hwnd)

        time.sleep(interval)