from fastapi import FastAPI, Response, Request
from PIL import Image, ImageDraw, ImageFont
from pydantic import BaseModel
from typing import List, Optional
import requests
import io
import random
import zipfile
import datetime
import struct

try:
    import pyzipper
except ImportError:
    pyzipper = None

try:
    from fontTools.ttLib import TTFont
except ImportError:
    TTFont = None

app = FastAPI()

HIND_SILIGURI_URL = "https://raw.githubusercontent.com/google/fonts/main/ofl/hindsiliguri/HindSiliguri-Medium.ttf"

BANGLA_WORDS_POOL = ["শ্রদ্ধাঞ্জলি", "সূক্ষ্মতা", "আকাঙ্ক্ষা", "উচ্ছ্বসিত", "সংস্কৃতি", "স্বাধীনতা", "সন্ধ্যা", "প্রজ্বলিত", "নান্দনিক"]
ENGLISH_WORDS_POOL = ["Typography", "Aesthetics", "Creative", "Design", "Minimalism", "Elegance", "Branding", "Calligraphy"]
ARABIC_WORDS_POOL = ["الخط العربي", "جماليات", "إبداع", "تصميم", "أصالة", "فنون", "خطاط", "الخط"]

FONT_BYTES_CACHE = {}
MAX_CACHE_SIZE = 30

def fetch_font_bytes_cached(font_url: str) -> bytes:
    if font_url in FONT_BYTES_CACHE:
        return FONT_BYTES_CACHE[font_url]
    res = requests.get(font_url, timeout=20)
    raw_bytes = res.content
    if len(FONT_BYTES_CACHE) >= MAX_CACHE_SIZE:
        FONT_BYTES_CACHE.pop(next(iter(FONT_BYTES_CACHE)))
    FONT_BYTES_CACHE[font_url] = raw_bytes
    return raw_bytes

try:
    hs_res = requests.get(HIND_SILIGURI_URL, timeout=10)
    HIND_SILIGURI_BYTES = io.BytesIO(hs_res.content)
except Exception:
    HIND_SILIGURI_BYTES = None

def get_hind_siliguri_font(size):
    if HIND_SILIGURI_BYTES:
        HIND_SILIGURI_BYTES.seek(0)
        return ImageFont.truetype(HIND_SILIGURI_BYTES, size=size)
    return ImageFont.load_default()

def get_auto_fit_font(font_bytes, text, max_width, max_height, start_size=80, min_size=20):
    for size in range(start_size, min_size - 1, -2):
        try:
            font_bytes.seek(0)
            font = ImageFont.truetype(font_bytes, size=size)
        except Exception:
            return get_hind_siliguri_font(size)

        dummy_img = Image.new('RGB', (1, 1))
        d = ImageDraw.Draw(dummy_img)
        bbox = d.textbbox((0, 0), text, font=font)
        w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]

        if w <= max_width and h <= max_height:
            return font

    font_bytes.seek(0)
    try:
        return ImageFont.truetype(font_bytes, size=min_size)
    except Exception:
        return get_hind_siliguri_font(min_size)

# SMART GLYPH & LANGUAGE DETECTOR TO PREVENT TOFU (BOXES)
def detect_font_supported_languages(font_bytes: bytes):
    has_bangla = False
    has_latin = False
    has_arabic = False

    if TTFont:
        try:
            tt = TTFont(io.BytesIO(font_bytes))
            cmap = tt.getBestCmap()
            if cmap:
                for code in cmap.keys():
                    if 0x0980 <= code <= 0x09FF:
                        has_bangla = True
                    elif (0x0041 <= code <= 0x005A) or (0x0061 <= code <= 0x007A):
                        has_latin = True
                    elif 0x0600 <= code <= 0x06FF:
                        has_arabic = True
        except Exception:
            pass

    if not has_bangla and not has_latin and not has_arabic:
        has_bangla = True
        has_latin = True

    return has_bangla, has_latin, has_arabic

@app.get("/preview")
def generate_preview(
    font_url: str,
    font_name: str = "Davinci_Font.ttf",
    text: str = "",
    lang: str = "all",
    requested_by: str = "User",
    bg_theme: str = "dark",
    inner_font: str = ""
):
    try:
        raw_bytes = fetch_font_bytes_cached(font_url)
        file_bytes = io.BytesIO(raw_bytes)

        if font_url.lower().endswith(".zip") or font_name.lower().endswith(".zip") or zipfile.is_zipfile(file_bytes):
            file_bytes.seek(0)
            with zipfile.ZipFile(file_bytes) as z:
                font_files = [f for f in z.namelist() if f.lower().endswith(('.ttf', '.otf')) and not f.split('/')[-1].startswith('._') and not f.startswith('__MACOSX')]
                if font_files:
                    target_file = font_files[0]
                    if inner_font:
                        for f in font_files:
                            if inner_font.lower() in f.lower():
                                target_file = f
                                break
                    font_name = target_file.split('/')[-1]
                    raw_bytes = z.read(target_file)
                    custom_font_bytes = io.BytesIO(raw_bytes)
                else:
                    return {"error": "No .ttf or .otf found in zip"}
        else:
            file_bytes.seek(0)
            custom_font_bytes = file_bytes

        detected_header_name = font_name

        # Detect supported languages
        has_bn, has_en, has_ar = detect_font_supported_languages(raw_bytes)

        width, height = 1080, 1080
        canvas_bg, card_bg, border_c, text_c, sub_c = "#0b1320", "#131e30", "#1e293b", "#ffffff", "#64748b"

        img = Image.new('RGB', (width, height), color=canvas_bg)
        draw = ImageDraw.Draw(img)

        sublabel_font = get_hind_siliguri_font(22)
        credit_user_font = get_hind_siliguri_font(30)
        header_font = get_hind_siliguri_font(42)

        title_bbox = draw.textbbox((0, 0), detected_header_name, font=header_font)
        title_w = title_bbox[2] - title_bbox[0]
        draw.text(((width - title_w) / 2, 55), detected_header_name, fill=text_c, font=header_font)
        draw.line([(80, 135), (width - 80, 135)], fill=border_c, width=2)

        # SMART SAMPLE TEXT SELECTION LOGIC
        if text.strip():
            words = text.strip().split()
            words = (words * 4)[:4] if len(words) < 4 else words[:4]
        else:
            if lang == 'b' or (has_bn and not has_en and not has_ar):
                words = random.sample(BANGLA_WORDS_POOL, 4)
            elif lang == 'e' or (has_en and not has_bn and not has_ar):
                words = random.sample(ENGLISH_WORDS_POOL, 4)
            elif lang == 'a' or (has_ar and not has_bn and not has_en):
                words = random.sample(ARABIC_WORDS_POOL, 4)
            else:
                words = []
                if has_bn: words.append(random.choice(BANGLA_WORDS_POOL))
                if has_en: words.append(random.choice(ENGLISH_WORDS_POOL))
                if has_ar: words.append(random.choice(ARABIC_WORDS_POOL))
                
                while len(words) < 4:
                    if has_bn: words.append(random.choice(BANGLA_WORDS_POOL))
                    elif has_en: words.append(random.choice(ENGLISH_WORDS_POOL))
                    else: words.append("Typeface")

        card_positions = [(60, 170, 510, 480), (570, 170, 1020, 480), (60, 510, 510, 820), (570, 510, 1020, 820)]

        for idx, (x1, y1, x2, y2) in enumerate(card_positions):
            card_w, card_h = x2 - x1, y2 - y1
            draw.rounded_rectangle([x1, y1, x2, y2], radius=16, fill=card_bg, outline=border_c, width=2)
            draw.rectangle([x1 + 30, y2 - 6, x2 - 30, y2 - 2], fill="#06b6d4")

            word = words[idx]
            card_font = get_auto_fit_font(custom_font_bytes, word, max_width=card_w - 60, max_height=card_h - 90, start_size=80, min_size=26)

            w_bbox = draw.textbbox((0, 0), word, font=card_font)
            w_width, w_height = w_bbox[2] - w_bbox[0], w_bbox[3] - w_bbox[1]

            draw.text((x1 + (card_w - w_width) / 2, y1 + (card_h - w_height) / 2 - 20), word, fill=text_c, font=card_font)

            sub_bbox = draw.textbbox((0, 0), word, font=sublabel_font)
            sub_w = sub_bbox[2] - sub_bbox[0]
            draw.text((x1 + (card_w - sub_w) / 2, y2 - 45), word, fill=sub_c, font=sublabel_font)

        draw.line([(80, 860), (width - 80, 860)], fill=border_c, width=2)
        user_credit_text = f"Preview Generated by: {requested_by}"
        uc_bbox = draw.textbbox((0, 0), user_credit_text, font=credit_user_font)
        uc_w = uc_bbox[2] - uc_bbox[0]
        draw.text(((width - uc_w) / 2, 910), user_credit_text, fill="#38bdf8", font=credit_user_font)

        img_byte_arr = io.BytesIO()
        img.save(img_byte_arr, format='PNG')
        return Response(content=img_byte_arr.getvalue(), media_type="image/png")

    except Exception as e:
        return {"error": str(e)}
