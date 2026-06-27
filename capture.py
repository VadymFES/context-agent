import mss
import win32gui
import pytesseract
from PIL import Image
from normalize import normalize


def capture_screen(hwnd: int) -> tuple[str, str]:
    """Returns (normalized_text, raw_text). Use raw_text for URL extraction."""
    left, top, right, bottom = win32gui.GetWindowRect(hwnd)

    monitor = {"left": left, "top": top, "width": right - left, "height": bottom - top}

    with mss.mss() as sct:
        shot = sct.grab(monitor)
        img = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")

    raw_text = pytesseract.image_to_string(img, lang='eng+ukr')
    return normalize(raw_text), raw_text