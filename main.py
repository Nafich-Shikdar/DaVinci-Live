from fastapi import FastAPI, Response
from PIL import Image, ImageDraw, ImageFont
import requests
import io
import random

app = FastAPI()

# Primary Google Font (Hind Siliguri) for UI Headers/Labels
HIND_SILIGURI_URL = "https://raw.githubusercontent.com/google/fonts/main/ofl/hindsiliguri/HindSiliguri-Medium.ttf"

# MULTI-LANGUAGE WORD POOLS
BANGLA_WORDS_POOL = [
    "শ্রদ্ধাঞ্জলি", "সূক্ষ্মতা", "আকাঙ্ক্ষা", "উচ্ছ্বসিত", 
    "সংস্কৃতি", " স্বাধীনতা", "সন্ধ্যা", "প্রজ্বলিত", "নান্দনিক"
]

ENGLISH_WORDS_POOL = [
    "Typography", "Aesthetics", "Creative", "Design", 
    "Minimalism", "Elegance", "Branding", "Calligraphy"
]

ARABIC_WORDS_POOL = [
    "الخط العربي", "جماليات", "إبداع", "تصميم", 
    "أصالة", "فنون", "خطاط", "الخط"
]

GLOBAL_RANDOM_WORDS = [
    "सुंदरता", "Tipografía", "Типографика", "デザイン", 
    "Élégance", "حُسن", "Kalligraphie"
]

# Load Hind Siliguri Font Bytes
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

# AUTO-RESPONSIVE FONT CALCULATOR
def get_auto_fit_font(font_bytes, text, max_width, max_height, start_size=80, min_size=28):
    for size in range(start_size, min_size - 1, -3):
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
    return {"status": "DaVinci Clean Engine Active"}

@app.get("/preview")
def generate_preview(
    font_url: str,
    font_name: str = "Davinci_Font.ttf",
    text: str = "",
    lang: str = "all",
    requested_by: str = "User"
):
    try:
        # Download Font File
        font_res = requests.get(font_url, timeout=15)
        custom_font_bytes = io.BytesIO(font_res.content)

        # Canvas Setup (1080x1080 Square Canvas)
        width, height = 1080, 1080
        img = Image.new('RGB', (width, height), color='#0b1320')
        draw = ImageDraw.Draw(img)

        # Standard Hind Siliguri UI Fonts
        sublabel_font = get_hind_siliguri_font(22)
        credit_user_font = get_hind_siliguri_font(30)

        # -------------------------------------------------------------
        # 1. HEADER SECTION (Hind Siliguri Font Name, No Branding Link)
        # -------------------------------------------------------------
        header_font = get_hind_siliguri_font(42)
        title_bbox = draw.textbbox((0, 0), font_name, font=header_font)
        title_w = title_bbox[2] - title_bbox[0]
        draw.text(((width - title_w) / 2, 55), font_name, fill="#ffffff", font=header_font)

        # Clean Header Divider
        draw.line([(80, 135), (width - 80, 135)], fill="#1e293b", width=2)

        # -------------------------------------------------------------
        # 2. SELECT WORDS BASED ON LANGUAGE SHORTCODE
        # -------------------------------------------------------------
        if text.strip():
            words = text.strip().split()
            if len(words) < 4:
                words = (words * 4)[:4]
            else:
                words = words[:4]
        else:
            if lang == 'b':
                words = random.sample(BANGLA_WORDS_POOL, 4)
            elif lang == 'e':
                words = random.sample(ENGLISH_WORDS_POOL, 4)
            elif lang == 'a':
                words = random.sample(ARABIC_WORDS_POOL, 4)
            else:
                # Default /live Mode: 1 Bangla, 1 English, 1 Arabic, 1 Global
                bn_w = random.choice(BANGLA_WORDS_POOL)
                en_w = random.choice(ENGLISH_WORDS_POOL)
                ar_w = random.choice(ARABIC_WORDS_POOL)
                gl_w = random.choice(GLOBAL_RANDOM_WORDS)
                words = [bn_w, en_w, ar_w, gl_w]

        # -------------------------------------------------------------
        # 3. 2x2 GRID CARDS SECTION
        # -------------------------------------------------------------
        card_positions = [
            (60, 170, 510, 480),   # Top Left
            (570, 170, 1020, 480),  # Top Right
            (60, 510, 510, 820),   # Bottom Left
            (570, 510, 1020, 820)  # Bottom Right
        ]

        for idx, (x1, y1, x2, y2) in enumerate(card_positions):
            card_w = x2 - x1
            card_h = y2 - y1

            # Card Background
            draw.rounded_rectangle([x1, y1, x2, y2], radius=16, fill="#131e30", outline="#1e293b", width=2)
            draw.rectangle([x1 + 30, y2 - 6, x2 - 30, y2 - 2], fill="#06b6d4")

            word = words[idx]

            # Dynamic Auto-fit for Custom Font
            max_t_w = card_w - 60
            max_t_h = card_h - 90
            card_font = get_auto_fit_font(custom_font_bytes, word, max_width=max_t_w, max_height=max_t_h, start_size=80, min_size=26)

            w_bbox = draw.textbbox((0, 0), word, font=card_font)
            w_width = w_bbox[2] - w_bbox[0]
            w_height = w_bbox[3] - w_bbox[1]

            word_x = x1 + (card_w - w_width) / 2
            word_y = y1 + (card_h - w_height) / 2 - 20
            draw.text((word_x, word_y), word, fill="#ffffff", font=card_font)

            # Sub-label
            sub_bbox = draw.textbbox((0, 0), word, font=sublabel_font)
            sub_w = sub_bbox[2] - sub_bbox[0]
            sub_x = x1 + (card_w - sub_w) / 2
            sub_y = y2 - 45
            draw.text((sub_x, sub_y), word, fill="#64748b", font=sublabel_font)

        # -------------------------------------------------------------
        # 4. CLEAN FOOTER SECTION (Only User Credit)
        # -------------------------------------------------------------
        draw.line([(80, 860), (width - 80, 860)], fill="#1e293b", width=2)

        user_credit_text = f"Preview Generated by: {requested_by}"
        uc_bbox = draw.textbbox((0, 0), user_credit_text, font=credit_user_font)
        uc_w = uc_bbox[2] - uc_bbox[0]
        draw.text(((width - uc_w) / 2, 910), user_credit_text, fill="#38bdf8", font=credit_user_font)

        # Output PNG
        img_byte_arr = io.BytesIO()
        img.save(img_byte_arr, format='PNG')
        return Response(content=img_byte_arr.getvalue(), media_type="image/png")

    except Exception as e:
        return {"error": str(e)}
