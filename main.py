from fastapi import FastAPI, Response
from PIL import Image, ImageDraw, ImageFont
import requests
import io
import random
import re

app = FastAPI()

# Standard Bengali/English Fallback Font for Sub-labels & Headers
FALLBACK_FONT_URL = "https://raw.githubusercontent.com/google/fonts/main/ofl/hindsiliguri/HindSiliguri-Medium.ttf"

# Random Bangla Words Sets with Complex Conjuncts (যুক্তবর্ণ)
BANGLA_WORD_SETS = [
    ["আকাঙ্ক্ষা", "শ্রাবণ", "সন্ধ্যা", "সূক্ষ্ম"],
    ["স্বাধীনতা", "প্রকৃতি", "সংস্কৃতি", "উচ্ছ্বসিত"],
    ["শ্রদ্ধাঞ্জলি", "নৈর্ব্যক্তিক", "অভিজ্ঞতা", "আকাঙ্ক্ষিত"],
    ["প্রজ্বলিত", "সূক্ষ্মতা", "মনোমুগ্ধকর", "বিতৃষ্ণা"],
    ["অপরিহার্য", "পরাকাষ্ঠা", "শ্রদ্ধাস্পদ", "আত্মীয়তা"]
]

# Random English Words Sets
ENGLISH_WORD_SETS = [
    ["Typography", "Aesthetics", "Creative", "Design"],
    ["Minimalism", "Elegance", "Branding", "Futuristic"],
    ["Masterpiece", "Caligraphy", "Symphony", "Modern"]
]

# Download fallback font into memory
try:
    fb_res = requests.get(FALLBACK_FONT_URL, timeout=10)
    FALLBACK_FONT_BYTES = io.BytesIO(fb_res.content)
except Exception as e:
    FALLBACK_FONT_BYTES = None

@app.get("/")
def home():
    return {"status": "DaVinci Professional Font Preview Engine V2 Active"}

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

        # Detect if font name or text contains English or Bangla
        is_english = bool(re.search(r'[a-zA-Z]', text)) if text else bool(re.search(r'^[a-zA-Z0-9_\-\.\s]+$', font_name))

        # Canvas Setup (1080x1080 Square Post Template)
        width, height = 1080, 1080
        img = Image.new('RGB', (width, height), color='#0b1320') # Dark slate navy background
        draw = ImageDraw.Draw(img)

        # Load Standard Fallback Font for Headers/Credits/Sub-labels
        def get_fallback_font(size):
            if FALLBACK_FONT_BYTES:
                FALLBACK_FONT_BYTES.seek(0)
                return ImageFont.truetype(FALLBACK_FONT_BYTES, size=size)
            return ImageFont.load_default()

        header_fallback = get_fallback_font(28)
        sublabel_font = get_fallback_font(22)
        credit_main_font = get_fallback_font(38)
        credit_sub_font = get_fallback_font(24)

        # -------------------------------------------------------------
        # 1. HEADER SECTION
        # -------------------------------------------------------------
        # Load Custom Font for Title Header
        try:
            custom_font_bytes.seek(0)
            title_font = ImageFont.truetype(custom_font_bytes, size=52)
        except:
            title_font = get_fallback_font(52)

        title_text = font_name
        title_bbox = draw.textbbox((0, 0), title_text, font=title_font)
        title_w = title_bbox[2] - title_bbox[0]
        draw.text(((width - title_w) / 2, 60), title_text, fill="#ffffff", font=title_font)

        # Header Subtitle
        sub_title = "fontsfinder.netlify.app"
        sub_bbox = draw.textbbox((0, 0), sub_title, font=header_fallback)
        sub_w = sub_bbox[2] - sub_bbox[0]
        draw.text(((width - sub_w) / 2, 135), sub_title, fill="#64748b", font=header_fallback)

        # Header Divider Line
        draw.line([(80, 190), (width - 80, 190)], fill="#1e293b", width=2)

        # -------------------------------------------------------------
        # 2. 2x2 GRID CARDS SECTION
        # -------------------------------------------------------------
        # Determine words to display
        if text.strip():
            words = text.strip().split()
            if len(words) < 4:
                words = (words * 4)[:4]
            else:
                words = words[:4]
        else:
            word_pool = ENGLISH_WORD_SETS if is_english else BANGLA_WORD_SETS
            words = random.choice(word_pool)

        card_positions = [
            (60, 230, 510, 500),   # Top Left
            (570, 230, 1020, 500),  # Top Right
            (60, 530, 510, 800),   # Bottom Left
            (570, 530, 1020, 800)  # Bottom Right
        ]

        for idx, (x1, y1, x2, y2) in enumerate(card_positions):
            card_w = x2 - x1
            card_h = y2 - y1

            # Card Dark Box
            draw.rounded_rectangle([x1, y1, x2, y2], radius=16, fill="#131e30", outline="#1e293b", width=2)

            # Card Bottom Accent Line (Cyan)
            draw.rectangle([x1 + 30, y2 - 6, x2 - 30, y2 - 2], fill="#06b6d4")

            word = words[idx]

            # Render Main Custom Font Word
            try:
                custom_font_bytes.seek(0)
                card_font = ImageFont.truetype(custom_font_bytes, size=48)
            except:
                card_font = get_fallback_font(48)

            w_bbox = draw.textbbox((0, 0), word, font=card_font)
            w_width = w_bbox[2] - w_bbox[0]
            w_height = w_bbox[3] - w_bbox[1]

            # Center align main text inside card
            word_x = x1 + (card_w - w_width) / 2
            word_y = y1 + (card_h - w_height) / 2 - 25
            draw.text((word_x, word_y), word, fill="#ffffff", font=card_font)

            # Render Sub-label (Meaning/Spelling in Fallback Font)
            sub_bbox = draw.textbbox((0, 0), word, font=sublabel_font)
            sub_w = sub_bbox[2] - sub_bbox[0]
            sub_x = x1 + (card_w - sub_w) / 2
            sub_y = y2 - 45
            draw.text((sub_x, sub_y), word, fill="#64748b", font=sublabel_font)

        # -------------------------------------------------------------
        # 3. FOOTER BRANDING SECTION
        # -------------------------------------------------------------
        # Footer Divider Line
        draw.line([(80, 840), (width - 80, 840)], fill="#1e293b", width=2)

        # Primary Telegram Credit
        credit_1 = "Telegram/@davinci_live_bot"
        c1_bbox = draw.textbbox((0, 0), credit_1, font=credit_main_font)
        c1_w = c1_bbox[2] - c1_bbox[0]
        draw.text(((width - c1_w) / 2, 880), credit_1, fill="#38bdf8", font=credit_main_font)

        # Secondary URL Credit
        credit_2 = "fontsfinder.netlify.app"
        c2_bbox = draw.textbbox((0, 0), credit_2, font=credit_sub_font)
        c2_w = c2_bbox[2] - c2_bbox[0]
        draw.text(((width - c2_w) / 2, 945), credit_2, fill="#64748b", font=credit_sub_font)

        # Output PNG Buffer
        img_byte_arr = io.BytesIO()
        img.save(img_byte_arr, format='PNG')
        return Response(content=img_byte_arr.getvalue(), media_type="image/png")

    except Exception as e:
        return {"error": str(e)}
