from fastapi import FastAPI, Response
from PIL import Image, ImageDraw, ImageFont
import requests
import io
import random

app = FastAPI()

# Fallback Font URL for rendering sub-labels & fallback text
FALLBACK_FONT_URL = "https://raw.githubusercontent.com/google/fonts/main/ofl/hindsiliguri/HindSiliguri-Medium.ttf"

# Random Bangla Words Sets with Complex Conjuncts (যুক্তবর্ণ)
BANGLA_WORDS_POOL = [
    "আকাঙ্ক্ষা", "শ্রাবণ", "সন্ধ্যা", "সূক্ষ্ম", " hisসব", 
    "স্বাধীনতা", "সংস্কৃতি", "উচ্ছ্বসিত", "প্রজ্বলিত", "সূক্ষ্মতা", "শ্রদ্ধাঞ্জলি"
]

# Random English Words Sets
ENGLISH_WORDS_POOL = [
    "Typography", "Aesthetics", "Creative", "Design", 
    "Minimalism", "Elegance", "Branding", "Calligraphy"
]

# Download fallback font into memory
try:
    fb_res = requests.get(FALLBACK_FONT_URL, timeout=10)
    FALLBACK_FONT_BYTES = io.BytesIO(fb_res.content)
except Exception as e:
    FALLBACK_FONT_BYTES = None

@app.get("/")
def home():
    return {"status": "DaVinci Font Preview Engine V3 Active"}

@app.get("/preview")
def generate_preview(
    font_url: str,
    font_name: str = "Davinci_Font.ttf",
    text: str = ""
):
    try:
        # Download Target Font File
        font_res = requests.get(font_url, timeout=15)
        custom_font_bytes = io.BytesIO(font_res.content)

        # Canvas Setup (1080x1080 Square Post Template)
        width, height = 1080, 1080
        img = Image.new('RGB', (width, height), color='#0b1320') # Dark slate navy background
        draw = ImageDraw.Draw(img)

        # Helper function for fallback font
        def get_fallback_font(size):
            if FALLBACK_FONT_BYTES:
                FALLBACK_FONT_BYTES.seek(0)
                return ImageFont.truetype(FALLBACK_FONT_BYTES, size=size)
            return ImageFont.load_default()

        header_fallback = get_fallback_font(28)
        sublabel_font = get_fallback_font(22)
        credit_main_font = get_fallback_font(38)
        credit_sub_font = get_fallback_font(26)

        # -------------------------------------------------------------
        # 1. HEADER SECTION
        # -------------------------------------------------------------
        try:
            custom_font_bytes.seek(0)
            title_font = ImageFont.truetype(custom_font_bytes, size=52)
        except:
            title_font = get_fallback_font(52)

        title_text = font_name
        title_bbox = draw.textbbox((0, 0), title_text, font=title_font)
        title_w = title_bbox[2] - title_bbox[0]
        draw.text(((width - title_w) / 2, 60), title_text, fill="#ffffff", font=title_font)

        # Header Subtitle (Telegram Group Link)
        sub_title = "t.me/PremiumBanglaFonts"
        sub_bbox = draw.textbbox((0, 0), sub_title, font=header_fallback)
        sub_w = sub_bbox[2] - sub_bbox[0]
        draw.text(((width - sub_w) / 2, 135), sub_title, fill="#38bdf8", font=header_fallback)

        # Header Divider Line
        draw.line([(80, 190), (width - 80, 190)], fill="#1e293b", width=2)

        # -------------------------------------------------------------
        # 2. 2x2 GRID CARDS SECTION (2 Bangla + 2 English)
        # -------------------------------------------------------------
        if text.strip():
            # If user provides custom text
            words = text.strip().split()
            if len(words) < 4:
                words = (words * 4)[:4]
            else:
                words = words[:4]
        else:
            # 2 Random Bangla words + 2 Random English words
            selected_bn = random.sample(BANGLA_WORDS_POOL, 2)
            selected_en = random.sample(ENGLISH_WORDS_POOL, 2)
            words = [selected_bn[0], selected_bn[1], selected_en[0], selected_en[1]]

        card_positions = [
            (60, 230, 510, 500),   # Top Left (Bangla 1)
            (570, 230, 1020, 500),  # Top Right (Bangla 2)
            (60, 530, 510, 800),   # Bottom Left (English 1)
            (570, 530, 1020, 800)  # Bottom Right (English 2)
        ]

        for idx, (x1, y1, x2, y2) in enumerate(card_positions):
            card_w = x2 - x1
            card_h = y2 - y1

            # Card Background & Accent Line
            draw.rounded_rectangle([x1, y1, x2, y2], radius=16, fill="#131e30", outline="#1e293b", width=2)
            draw.rectangle([x1 + 30, y2 - 6, x2 - 30, y2 - 2], fill="#06b6d4")

            word = words[idx]

            # Main Font Text
            try:
                custom_font_bytes.seek(0)
                card_font = ImageFont.truetype(custom_font_bytes, size=48)
            except:
                card_font = get_fallback_font(48)

            w_bbox = draw.textbbox((0, 0), word, font=card_font)
            w_width = w_bbox[2] - w_bbox[0]
            w_height = w_bbox[3] - w_bbox[1]

            word_x = x1 + (card_w - w_width) / 2
            word_y = y1 + (card_h - w_height) / 2 - 25
            draw.text((word_x, word_y), word, fill="#ffffff", font=card_font)

            # Sub-label (Fallback font for pronunciation/spelling)
            sub_bbox = draw.textbbox((0, 0), word, font=sublabel_font)
            sub_w = sub_bbox[2] - sub_bbox[0]
            sub_x = x1 + (card_w - sub_w) / 2
            sub_y = y2 - 45
            draw.text((sub_x, sub_y), word, fill="#64748b", font=sublabel_font)

        # -------------------------------------------------------------
        # 3. FOOTER BRANDING SECTION
        # -------------------------------------------------------------
        draw.line([(80, 840), (width - 80, 840)], fill="#1e293b", width=2)

        # Primary Credit: Bot Username
        credit_1 = "Telegram/@davinci_live_bot"
        c1_bbox = draw.textbbox((0, 0), credit_1, font=credit_main_font)
        c1_w = c1_bbox[2] - c1_bbox[0]
        draw.text(((width - c1_w) / 2, 875), credit_1, fill="#38bdf8", font=credit_main_font)

        # Secondary Credit: Telegram Group Link
        credit_2 = "t.me/PremiumBanglaFonts"
        c2_bbox = draw.textbbox((0, 0), credit_2, font=credit_sub_font)
        c2_w = c2_bbox[2] - c2_bbox[0]
        draw.text(((width - c2_w) / 2, 940), credit_2, fill="#94a3b8", font=credit_sub_font)

        # Output PNG Buffer
        img_byte_arr = io.BytesIO()
        img.save(img_byte_arr, format='PNG')
        return Response(content=img_byte_arr.getvalue(), media_type="image/png")

    except Exception as e:
        return {"error": str(e)}
