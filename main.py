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

# Primary Google Font (Hind Siliguri) for UI Headers/Labels
HIND_SILIGURI_URL = "https://raw.githubusercontent.com/google/fonts/main/ofl/hindsiliguri/HindSiliguri-Medium.ttf"

# নির্দিষ্ট ৩টি ভাষার শব্দভাণ্ডার
BANGLA_WORDS_POOL = ["শ্রদ্ধাঞ্জলি", "সূক্ষ্মতা", "আকাঙ্ক্ষা", "উচ্ছ্বসিত", "সংস্কৃতি", "স্বাধীনতা", "সন্ধ্যা", "প্রজ্বলিত", "নান্দনিক"]
ENGLISH_WORDS_POOL = ["Typography", "Aesthetics", "Creative", "Design", "Minimalism", "Elegance", "Branding", "Calligraphy"]
ARABIC_WORDS_POOL = ["الخط العربي", "جماليات", "إبداع", "تصميم", "أصالة", "فنون", "خطاط", "الخط"]

# RAM MEMORY CACHE FOR FAST FONT LOADING
FONT_BYTES_CACHE = {}
MAX_CACHE_SIZE = 30

def fetch_font_bytes_cached(font_url: str) -> bytes:
    if font_url in FONT_BYTES_CACHE:
        return FONT_BYTES_CACHE[font_url]
    
    res = requests.get(font_url, timeout=20)
    raw_bytes = res.content
    
    if len(FONT_BYTES_CACHE) >= MAX_CACHE_SIZE:
        first_key = next(iter(FONT_BYTES_CACHE))
        FONT_BYTES_CACHE.pop(first_key)
        
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
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]

        if w <= max_width and h <= max_height:
            return font

    font_bytes.seek(0)
    try:
        return ImageFont.truetype(font_bytes, size=min_size)
    except Exception:
        return get_hind_siliguri_font(min_size)

@app.get("/")
def home():
    return {"status": "DaVinci 3-Language Preview Engine Active"}

# -------------------------------------------------------------
# ZIP MANAGER (অন্যান্য ফাংশনগুলো আগের মতোই থাকবে)
# -------------------------------------------------------------
# [পূর্বের জিপ ম্যানেজার ফাংশনগুলো এখানে থাকবে...]
# (কোডটি ছোট রাখতে এখানে শুধু পরিবর্তিত অংশটি দেওয়া হলো)

# -------------------------------------------------------------
# 🔥 UPDATED PREVIEW RENDERER – সাপোর্ট (bn, en, mixed)
# -------------------------------------------------------------
@app.get("/preview")
def generate_preview(
    font_url: str,
    font_name: str = "Davinci_Font.ttf",
    requested_by: str = "User",
    bg_theme: str = "dark",
    inner_font: str = "",
    lang_mode: str = "mixed"  # নতুন প্যারামিটার (bn, en, mixed)
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

        # ফন্টের আসল নাম বের করা
        detected_header_name = font_name
        try:
            # (parse_ttf_binary_metadata ফাংশনটি আগে থেকেই আপনার কোডে আছে)
            binary_meta = parse_ttf_binary_metadata(raw_bytes)
            real_name = binary_meta.get('full_name') or binary_meta.get('family')
            if real_name and len(real_name.strip()) > 0:
                detected_header_name = real_name.strip()
        except Exception:
            pass

        width, height = 1080, 1080

        # থিম সেট
        if bg_theme == "light":
            canvas_bg, card_bg, border_c, text_c, sub_c = "#f8fafc", "#ffffff", "#e2e8f0", "#0f172a", "#64748b"
        elif bg_theme == "transparent":
            canvas_bg, card_bg, border_c, text_c, sub_c = (0,0,0,0), "#131e30", "#1e293b", "#ffffff", "#64748b"
        else:
            canvas_bg, card_bg, border_c, text_c, sub_c = "#0b1320", "#131e30", "#1e293b", "#ffffff", "#64748b"

        img = Image.new('RGBA' if bg_theme == "transparent" else 'RGB', (width, height), color=canvas_bg)
        draw = ImageDraw.Draw(img)

        sublabel_font = get_hind_siliguri_font(22)
        credit_user_font = get_hind_siliguri_font(30)

        # হেডার
        header_font = get_hind_siliguri_font(42)
        title_bbox = draw.textbbox((0, 0), detected_header_name, font=header_font)
        title_w = title_bbox[2] - title_bbox[0]
        draw.text(((width - title_w) / 2, 55), detected_header_name, fill=text_c, font=header_font)
        draw.line([(80, 135), (width - 80, 135)], fill=border_c, width=2)

        # ভাষা সিলেকশন লজিক
        if lang_mode == "bn":
            words = [random.choice(BANGLA_WORDS_POOL) for _ in range(3)]
        elif lang_mode == "en":
            words = [random.choice(ENGLISH_WORDS_POOL) for _ in range(3)]
        else:
            words = [random.choice(BANGLA_WORDS_POOL), random.choice(ENGLISH_WORDS_POOL), random.choice(ARABIC_WORDS_POOL)]

        # নতুন কার্ড লেআউট
        card1 = (60, 170, 1020, 480)    # উপরে পূর্ণ প্রস্থ
        card2 = (60, 510, 540, 820)     # নিচে বামে
        card3 = (540, 510, 1020, 820)   # নিচে ডানে

        cards = [card1, card2, card3]

        for idx, (x1, y1, x2, y2) in enumerate(cards):
            card_w = x2 - x1
            card_h = y2 - y1

            draw.rounded_rectangle([x1, y1, x2, y2], radius=16, fill=card_bg, outline=border_c, width=2)
            draw.rectangle([x1 + 30, y2 - 6, x2 - 30, y2 - 2], fill="#06b6d4")

            word = words[idx]
            card_font = get_auto_fit_font(custom_font_bytes, word, max_width=card_w - 60, max_height=card_h - 90, start_size=80, min_size=26)

            w_bbox = draw.textbbox((0, 0), word, font=card_font)
            w_width, w_height = w_bbox[2] - w_bbox[0], w_bbox[3] - w_bbox[1]

            word_x = x1 + (card_w - w_width) / 2
            word_y = y1 + (card_h - w_height) / 2 - 20
            draw.text((word_x, word_y), word, fill=text_c, font=card_font)

            # নিচে শব্দের নাম ছোট করে
            sub_bbox = draw.textbbox((0, 0), word, font=sublabel_font)
            sub_w = sub_bbox[2] - sub_bbox[0]
            draw.text((x1 + (card_w - sub_w) / 2, y2 - 45), word, fill=sub_c, font=sublabel_font)

        # ফুটার
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
