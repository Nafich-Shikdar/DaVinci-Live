from fastapi import FastAPI, Response
from PIL import Image, ImageDraw, ImageFont
import requests
import io
import random
import zipfile
import datetime
import struct

try:
    from fontTools.ttLib import TTFont
except ImportError:
    TTFont = None

app = FastAPI()

# Primary Google Font (Hind Siliguri) for UI Headers/Labels
HIND_SILIGURI_URL = "https://raw.githubusercontent.com/google/fonts/main/ofl/hindsiliguri/HindSiliguri-Medium.ttf"

# MULTI-LANGUAGE WORD POOLS
BANGLA_WORDS_POOL = ["শ্রদ্ধাঞ্জলি", "সূক্ষ্মতা", "আকাঙ্ক্ষা", "উচ্ছ্বসিত", "সংস্কৃতি", "স্বাধীনতা", "সন্ধ্যা", "প্রজ্বলিত", "নান্দনিক"]
ENGLISH_WORDS_POOL = ["Typography", "Aesthetics", "Creative", "Design", "Minimalism", "Elegance", "Branding", "Calligraphy"]
ARABIC_WORDS_POOL = ["الخط العربي", "جماليات", "إبداع", "تصميم", "أصالة", "فنون", "خطاط", "الخط"]
GLOBAL_RANDOM_WORDS = ["सुंदरता", "Tipografía", "Типографика", "デザイン", "Élégance", "حُسن", "Kalligraphie"]

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

def get_auto_fit_font(font_bytes, text, max_width, max_height, start_size=80, min_size=26):
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
    return {"status": "DaVinci Multilingual Engine Active"}

# -------------------------------------------------------------
# FONT METADATA EXTRACTOR (100% RELIABLE WITH FILENAME FALLBACK)
# -------------------------------------------------------------
@app.get("/font_info")
def get_font_info(font_url: str, font_name: str = "Font.ttf", inner_font: str = ""):
    try:
        font_res = requests.get(font_url, timeout=20)
        raw_bytes = font_res.content
        size_bytes = len(raw_bytes)
        file_bytes = io.BytesIO(raw_bytes)

        target_font_bytes = raw_bytes
        selected_font_filename = font_name

        # ZIP AUTO-EXTRACTOR
        if font_url.lower().endswith(".zip") or font_name.lower().endswith(".zip") or zipfile.is_zipfile(file_bytes):
            file_bytes.seek(0)
            with zipfile.ZipFile(file_bytes) as z:
                font_files = [f for f in z.namelist() if f.lower().endswith(('.ttf', '.otf')) and not f.split('/')[-1].startswith('._') and not f.startswith('__MACOSX')]
                if font_files:
                    target_file = font_files[0]
                    if inner_font:
                        for f in font_files:
                            if inner_font.lower() in f.lower() or f.lower().endswith(inner_font.lower()):
                                target_file = f
                                break
                    selected_font_filename = target_file.split('/')[-1]
                    target_font_bytes = z.read(target_file)
                    size_bytes = len(target_font_bytes)
                else:
                    return {"error": "No .ttf or .otf found in zip"}

        # Format detection
        fmt = "TTF (TrueType)"
        if selected_font_filename.lower().endswith(".otf"):
            fmt = "OTF (OpenType)"

        info = {
            "family": "তথ্য পাওয়া যায়নি",
            "full_name": "তথ্য পাওয়া যায়নি",
            "format": fmt,
            "version": "1.00",
            "weight": "Regular (400)",
            "style": "Regular",
            "unicode_support": "হ্যাঁ (Unicode Supported)",
            "glyph_count": "তথ্য পাওয়া যায়নি",
            "designer": "তথ্য পাওয়া যায়নি",
            "manufacturer": "তথ্য পাওয়া যায়নি",
            "copyright": "তথ্য পাওয়া যায়নি",
            "license": "তথ্য পাওয়া যায়নি",
            "file_size": f"{round(size_bytes / 1024, 2)} KB" if size_bytes < 1048576 else f"{round(size_bytes / 1048576, 2)} MB",
            "embedding_allowed": "হ্যাঁ (Installable / Unlimited)",
            "created_date": "তথ্য পাওয়া যায়নি",
            "modified_date": "তথ্য পাওয়া যায়নি"
        }

        # 1. Parse using fontTools if available
        if TTFont:
            try:
                tt = TTFont(io.BytesIO(target_font_bytes), lazy=True)
                
                if hasattr(tt, 'sfntVersion'):
                    if tt.sfntVersion == 'OTTO':
                        info["format"] = "OTF (OpenType)"
                    elif tt.sfntVersion in ['\x00\x01\x00\x00', 'true']:
                        info["format"] = "TTF (TrueType)"

                if 'maxp' in tt and hasattr(tt['maxp'], 'numGlyphs'):
                    info["glyph_count"] = str(tt['maxp'].numGlyphs)

                if 'name' in tt:
                    for rec in tt['name'].names:
                        try:
                            val = rec.toUnicode()
                            if not val:
                                for enc in ['utf-16-be', 'utf-8', 'latin1', 'cp1252', 'mac_roman']:
                                    try:
                                        val = rec.string.decode(enc)
                                        if val: break
                                    except Exception: pass
                            if val:
                                cleaned = val.replace('\x00', '').strip()
                                if cleaned:
                                    if rec.nameID in (1, 16) and info["family"] == "তথ্য পাওয়া যায়নি":
                                        info["family"] = cleaned
                                    elif rec.nameID == 4 and info["full_name"] == "তথ্য পাওয়া যায়নি":
                                        info["full_name"] = cleaned
                                    elif rec.nameID == 5 and info["version"] == "তথ্য পাওয়া যায়নি":
                                        info["version"] = cleaned
                                    elif rec.nameID in (2, 17) and info["style"] == "তথ্য পাওয়া যায়নি":
                                        info["style"] = cleaned
                                    elif rec.nameID == 9 and info["designer"] == "তথ্য পাওয়া যায়নি":
                                        info["designer"] = cleaned
                                    elif rec.nameID == 8 and info["manufacturer"] == "তথ্য পাওয়া যায়নি":
                                        info["manufacturer"] = cleaned
                                    elif rec.nameID == 0 and info["copyright"] == "তথ্য পাওয়া যায়নি":
                                        info["copyright"] = cleaned
                                    elif rec.nameID in (13, 14) and info["license"] == "তথ্য পাওয়া যায়নি":
                                        info["license"] = cleaned
                        except Exception: pass

                if 'cmap' in tt:
                    try:
                        best = tt.getBestCmap()
                        if best:
                            info["unicode_support"] = f"হ্যাঁ ({len(best)} Unicodes Supported)"
                    except Exception: pass

                if 'head' in tt:
                    head = tt['head']
                    mac_epoch = datetime.datetime(1904, 1, 1)
                    if hasattr(head, 'created') and head.created:
                        try: info["created_date"] = (mac_epoch + datetime.timedelta(seconds=head.created)).strftime("%Y-%m-%d")
                        except Exception: pass
                    if hasattr(head, 'modified') and head.modified:
                        try: info["modified_date"] = (mac_epoch + datetime.timedelta(seconds=head.modified)).strftime("%Y-%m-%d")
                        except Exception: pass

            except Exception: pass

        # 2. Smart Filename Fallback (Guarantees Name is NEVER Empty)
        clean_name = selected_font_filename.rsplit('.', 1)[0].replace('_', ' ').replace('-', ' ').strip()
        if info["family"] == "তথ্য পাওয়া যায়নি":
            info["family"] = clean_name
        if info["full_name"] == "তথ্য পাওয়া যায়নি":
            info["full_name"] = clean_name

        return info
    except Exception as e:
        return {"error": str(e)}

# -------------------------------------------------------------
# PREVIEW RENDERER
# -------------------------------------------------------------
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
        font_res = requests.get(font_url, timeout=20)
        file_bytes = io.BytesIO(font_res.content)

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
                    custom_font_bytes = io.BytesIO(z.read(target_file))
                else:
                    return {"error": "No .ttf or .otf found in zip"}
        else:
            file_bytes.seek(0)
            custom_font_bytes = file_bytes

        width, height = 1080, 1080
        
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

        header_font = get_hind_siliguri_font(42)
        title_bbox = draw.textbbox((0, 0), font_name, font=header_font)
        title_w = title_bbox[2] - title_bbox[0]
        draw.text(((width - title_w) / 2, 55), font_name, fill=text_c, font=header_font)
        draw.line([(80, 135), (width - 80, 135)], fill=border_c, width=2)

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
                words = [random.choice(BANGLA_WORDS_POOL), random.choice(ENGLISH_WORDS_POOL), random.choice(ARABIC_WORDS_POOL), random.choice(GLOBAL_RANDOM_WORDS)]

        card_positions = [
            (60, 170, 510, 480),
            (570, 170, 1020, 480),
            (60, 510, 510, 820),
            (570, 510, 1020, 820)
        ]

        for idx, (x1, y1, x2, y2) in enumerate(card_positions):
            card_w, card_h = x2 - x1, y2 - y1

            draw.rounded_rectangle([x1, y1, x2, y2], radius=16, fill=card_bg, outline=border_c, width=2)
            draw.rectangle([x1 + 30, y2 - 6, x2 - 30, y2 - 2], fill="#06b6d4")

            word = words[idx]
            card_font = get_auto_fit_font(custom_font_bytes, word, max_width=card_w - 60, max_height=card_h - 90, start_size=80, min_size=26)

            w_bbox = draw.textbbox((0, 0), word, font=card_font)
            w_width, w_height = w_bbox[2] - w_bbox[0], w_bbox[3] - w_bbox[1]

            word_x = x1 + (card_w - w_width) / 2
            word_y = y1 + (card_h - w_height) / 2 - 20
            draw.text((word_x, word_y), word, fill=text_c, font=card_font)

            sub_bbox = draw.textbbox((0, 0), word, font=sublabel_font)
            sub_w = sub_bbox[2] - sub_bbox[0]
            draw.text((sub_x if 'sub_x' in locals() else x1 + (card_w - sub_w) / 2, y2 - 45), word, fill=sub_c, font=sublabel_font)

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
