import mss
import pytesseract
from PIL import Image
from normalize import normalize



def capture_screen() -> str:
    with mss.mss() as sct:
        monitor = sct.monitors[1]
        shot = sct.grab(monitor)
        img = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")

    raw_text = pytesseract.image_to_string(img, lang='eng+ukr')
    return normalize(raw_text)