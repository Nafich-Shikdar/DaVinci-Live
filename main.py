from fastapi import FastAPI, Response
from PIL import Image, ImageDraw, ImageFont
import requests
import io
import random

app = FastAPI()

# Fallback Font URL
FALLBACK_FONT_URL = "https://raw.githubusercontent.com/google/fonts/main/ofl/hindsiliguri/HindSiliguri-Medium.ttf"

BANGLA_WORDS_POOL = [
    "আকাঙ্ক্ষা", "শ্রাবণ", "সন্ধ্যা", "সূক্ষ্ম", 
    "স্বাধীনতা", "সংস্কৃতি", "উচ্ছ্বসিত", "প্রজ্বলিত", "সূক্ষ্মতা", "শ্রদ্ধাঞ্জলি"
]

ENGLISH_WORDS_POOL = [
    "Typography", "Aesthetics", "Creative", "Design", 
    "Minimalism", "Elegance", "Branding", "Calligraphy"
]

# Load Fallback Font Bytes
try:
    fb_res = requests.get(FALLBACK_FONT_URL, timeout=10)
    FALLBACK_FONT_BYTES = io.BytesIO(fb_res.content)
except Exception:
    FALLBACK_FONT_BYTES = None

def get_fallback_font(size):
    if FALLBACK_FONT_BYTES:
        FALLBACK_FONT_BYTES.seek(0)
        return ImageFont.truetype(FALLBACK_FONT_BYTES, size=size)
    return ImageFont.load_default()

# AUTO-RESPONSIVE FONT CALCULATOR (ডায়নামিক ফন্ট সাইজ ক্যালকুলেটর)
def get_auto_fit_font(font_bytes, text, max_width, max_height, start_size=80, min_size=28):
    for size in range(start_size, min_size - 1, -3):
        try:
            font_bytes.seek(0)
            font = ImageFont.truetype(font_bytes, size=size)
        except Exception:
            return get_fallback_font(size)

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
        return get_fallback_font(min_size)

@app.get("/")
def home():
    return {"status": "DaVinci Responsive Engine Active"}

@app.get("/preview")
def generate_preview(
    font_url: str,
    font_name: str = "Davinci_Font.ttf",
    text: str = ""
):
    try:
        # Download Font File
        font_res = requests.get(font_url, timeout=15)
        custom_font_bytes = io.BytesIO(font_res.content)

        # Canvas Setup (1080x1080 Square Post)
        width, height = 1080, 1080
        img = Image.new('RGB', (width, height), color='#0b1320')
        draw = ImageDraw.Draw(img)

        header_fallback = get_fallback_font(28)
        sublabel_font = get_fallback_font(22)
        credit_main_font = get_fallback_font(38)
        credit_sub_font = get_fallback_font(26)

        # -------------------------------------------------------------
        # 1. HEADER SECTION (Auto-fit Title)
        # -------------------------------------------------------------
        title_font = get_auto_fit_font(custom_font_bytes, font_name, max_width=920, max_height=70, start_size=55, min_size=30)
        
        title_bbox = draw.textbbox((0, 0), font_name, font=title_font)
        title_w = title_bbox[2] - title_bbox[0]
        draw.text(((width - title_w) / 2, 55), font_name, fill="#ffffff", font=title_font)

        # Header Subtitle
        sub_title = "t.me/PremiumBanglaFonts"
        sub_bbox = draw.textbbox((0, 0), sub_title, font=header_fallback)
        sub_w = sub_bbox[2] - sub_bbox[0]
        draw.text(((width - sub_w) / 2, 135), sub_title, fill="#38bdf8", font=header_fallback)

        draw.line([(80, 190), (width - 80, 190)], fill="#1e293b", width=2)

        # -------------------------------------------------------------
        # 2. 2x2 GRID CARDS SECTION (Dynamic Responsive Text Size)
        # -------------------------------------------------------------
        if text.strip():
            words = text.strip().split()
            if len(words) < 4:
                words = (words * 4)[:4]
            else:
                words = words[:4]
        else:
            selected_bn = random.sample(BANGLA_WORDS_POOL, 2)
            selected_en = random.sample(ENGLISH_WORDS_POOL, 2)
            words = [selected_bn[0], selected_bn[1], selected_en[0], selected_en[1]]

        card_positions = [
            (60, 230, 510, 500),   # Top Left
            (570, 230, 1020, 500),  # Top Right
            (60, 530, 510, 800),   # Bottom Left
            (570, 530, 1020, 800)  # Bottom Right
        ]

        for idx, (x1, y1, x2, y2) in enumerate(card_positions):
            card_w = x2 - x1
            card_h = y2 - y1

            # Card Background
            draw.rounded_rectangle([x1, y1, x2, y2], radius=16, fill="#131e30", outline="#1e293b", width=2)
            draw.rectangle([x1 + 30, y2 - 6, x2 - 30, y2 - 2], fill="#06b6d4")

            word = words[idx]

            # Dynamically calculate font size to fit card perfectly!
            max_t_w = card_w - 60  # Padding inside card
            max_t_h = card_h - 90
            card_font = get_auto_fit_font(custom_font_bytes, word, max_width=max_t_w, max_height=max_t_h, start_size=82, min_size=28)

            w_bbox = draw.textbbox((0, 0), word, font=card_font)
            w_width = w_bbox[2] - w_bbox[0]
            w_height = w_bbox[3] - w_bbox[1]

            # Center align main text vertically and horizontally
            word_x = x1 + (card_w - w_width) / 2
            word_y = y1 + (card_h - w_height) / 2 - 20
            draw.text((word_x, word_y), word, fill="#ffffff", font=card_font)

            # Sub-label (Meaning/Spelling)
            sub_bbox = draw.textbbox((0, 0), word, font=sublabel_font)
            sub_w = sub_bbox[2] - sub_bbox[0]
            sub_x = x1 + (card_w - sub_w) / 2
            sub_y = y2 - 45
            draw.text((sub_x, sub_y), word, fill="#64748b", font=sublabel_font)

        # -------------------------------------------------------------
        # 3. FOOTER BRANDING SECTION
        # -------------------------------------------------------------
        draw.line([(80, 840), (width - 80, 840)], fill="#1e293b", width=2)

        credit_1 = "Telegram/@davinci_live_bot"
        c1_bbox = draw.textbbox((0, 0), credit_1, font=credit_main_font)
        c1_w = c1_bbox[2] - c1_bbox[0]
        draw.text(((width - c1_w) / 2, 875), credit_1, fill="#38bdf8", font=credit_main_font)

        credit_2 = "t.me/PremiumBanglaFonts"
        c2_bbox = draw.textbbox((0, 0), credit_2, font=credit_sub_font)
        c2_w = c2_bbox[2] - c2_bbox[0]
        draw.text(((width - c2_w) / 2, 940), credit_2, fill="#94a3b8", font=credit_sub_font)

        # Output PNG
        img_byte_arr = io.BytesIO()
        img.save(img_byte_arr, format='PNG')
        return Response(content=img_byte_arr.getvalue(), media_type="image/png")

    except Exception as e:
        return {"error": str(e)}
