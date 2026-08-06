from fastapi import FastAPI, Query
import requests
import io
from fontTools.ttLib import TTFont
from zipfile import ZipFile, is_zipfile

app = FastAPI()  # আপনার ইতিমধ্যেই আছে

# Helper: font bytes fetch (আপনার পূর্বের কোড অনুযায়ী)
def fetch_font_bytes_cached(url):
    # আপনার ক্যাশিং লজিক এখানে
    res = requests.get(url, timeout=20)
    return res.content

def detect_font_script(font_bytes: bytes) -> str:
    """ফন্টের ইউনিকোড cmap থেকে বাংলা, আরবি, ল্যাটিন স্ক্রিপ্ট সনাক্ত"""
    try:
        font = TTFont(io.BytesIO(font_bytes))
        cmap = font.getBestCmap()
        if not cmap:
            return "all"

        # নির্দিষ্ট ইউনিকোড রেঞ্জ চেক
        has_bengali = any(0x0980 <= cp <= 0x09FF for cp in cmap.keys())
        has_arabic  = any(0x0600 <= cp <= 0x06FF for cp in cmap.keys())
        has_latin   = any(0x0041 <= cp <= 0x007A for cp in cmap.keys())  # A-Z, a-z

        # যদি শুধুমাত্র নির্দিষ্ট স্ক্রিপ্ট পায়
        if has_bengali and not has_arabic and not has_latin:
            return "b"
        if has_arabic and not has_bengali and not has_latin:
            return "a"
        if has_latin and not has_bengali and not has_arabic:
            return "e"

        # মিশ্র হলে মাল্টি
        return "all"
    except:
        return "all"

@app.get("/detect_language")
def detect_language(font_url: str, font_name: str = "font.ttf", inner_font: str = ""):
    try:
        raw_bytes = fetch_font_bytes_cached(font_url)
        target_bytes = raw_bytes

        # ZIP ফাইল হলে ভেতরের ফন্ট বের করা
        if font_name.lower().endswith(".zip") or is_zipfile(io.BytesIO(raw_bytes)):
            with ZipFile(io.BytesIO(raw_bytes)) as zf:
                fonts = [f for f in zf.namelist() if f.lower().endswith(('.ttf', '.otf'))]
                if not fonts:
                    return {"language": "all", "error": "No font in zip"}
                target_file = fonts[0]
                if inner_font:
                    target_file = next((f for f in fonts if f.endswith(inner_font)), fonts[0])
                target_bytes = zf.read(target_file)

        lang = detect_font_script(target_bytes)
        return {"language": lang}
    except Exception as e:
        return {"language": "all", "error": str(e)}
