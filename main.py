from fastapi import FastAPI, Response
from PIL import Image, ImageDraw, ImageFont
import requests
import io
import random
import zipfile
import datetime

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
    return {"status": "DaVinci Advanced Multilingual Engine Active"}

# -------------------------------------------------------------
# FONT METADATA EXTRACTOR (WITH ENCODING FALLBACK & ZIP SUPPORT)
# -------------------------------------------------------------
@app.get("/font_info")
def get_font_info(font_url: str, font_name: str = "Font.ttf", inner_font: str = ""):
    try:
        font_res = requests.get(font_url, timeout=20)
        file_bytes = io.BytesIO(font_res.content)
        size_bytes = len(file_bytes.getvalue())

        # ZIP AUTO-UNZIP LOGIC
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
                    font_name = target_file.split('/')[-1]
                    raw_data = z.read(target_file)
                    file_bytes = io.BytesIO(raw_data)
                    size_bytes = len(raw_data)
                else:
                    return {"error": "No .ttf or .otf found in zip"}
        else:
            file_bytes.seek(0)

        info = {
            "family": "তথ্য পাওয়া যায়নি",
            "full_name": "তথ্য পাওয়া যায়নি",
            "format": "TTF (TrueType)" if font_name.lower().endswith(".ttf") else ("OTF (OpenType)" if font_name.lower().endswith(".otf") else "তথ্য পাওয়া যায়নি"),
            "version": "তথ্য পাওয়া যায়নি",
            "weight": "তথ্য পাওয়া যায়নি",
            "style": "তথ্য পাওয়া যায়নি",
            "unicode_support": "তথ্য পাওয়া যায়নি",
            "glyph_count": "তথ্য পাওয়া যায়নি",
            "designer": "তথ্য পাওয়া যায়নি",
            "manufacturer": "তথ্য পাওয়া যায়নি",
            "copyright": "তথ্য পাওয়া যায়নি",
            "license": "তথ্য পাওয়া যায়নি",
            "file_size": f"{round(size_bytes / 1024, 2)} KB" if size_bytes < 1048576 else f"{round(size_bytes / 1048576, 2)} MB",
            "embedding_allowed": "তথ্য পাওয়া যায়নি",
            "created_date": "তথ্য পাওয়া যায়নি",
            "modified_date": "তথ্য পাওয়া যায়নি"
        }

        if TTFont:
            try:
                file_bytes.seek(0)
                font = TTFont(file_bytes)

                if hasattr(font, 'sfntVersion'):
                    if font.sfntVersion == 'OTTO':
                        info["format"] = "OTF (OpenType)"
                    elif font.sfntVersion in ['\x00\x01\x00\x00', 'true']:
                        info["format"] = "TTF (TrueType)"

                # Robust multi-encoding name parser
                def get_name_record(name_ids):
                    if 'name' not in font:
                        return None
                    if isinstance(name_ids, int):
                        name_ids = [name_ids]
                    
                    for nid in name_ids:
                        records = [r for r in font['name'].names if r.nameID == nid]
                        records.sort(key=lambda r: 0 if r.platformID == 3 else (1 if r.platformID == 0 else 2))
                        for r in records:
                            val = None
                            try:
                                val = r.toUnicode()
                            except Exception:
                                try:
                                    val = r.string.decode('utf-16-be', errors='ignore')
                                except Exception:
                                    try:
                                        val = r.string.decode('utf-8', errors='ignore')
                                    except Exception:
                                        try:
                                            val = r.string.decode('latin1', errors='ignore')
                                        except Exception:
                                            pass
                            if val:
                                cleaned = val.replace('\x00', '').strip()
                                if cleaned:
                                    return cleaned
                    return None

                family = get_name_record([1, 16])
                if family: info["family"] = family

                full_name = get_name_record([4])
                if full_name: info["full_name"] = full_name

                version = get_name_record([5])
                if version: info["version"] = version

                style = get_name_record([2, 17])
                if style: info["style"] = style

                designer = get_name_record([9])
                if designer: info["designer"] = designer

                manufacturer = get_name_record([8])
                if manufacturer: info["manufacturer"] = manufacturer

                copyright_info = get_name_record([0])
                if copyright_info: info["copyright"] = copyright_info

                license_info = get_name_record([13, 14])
                if license_info: info["license"] = license_info

                if 'maxp' in font and hasattr(font['maxp'], 'numGlyphs'):
                    info["glyph_count"] = str(font['maxp'].numGlyphs)
                elif hasattr(font, 'getGlyphOrder'):
                    info["glyph_count"] = str(len(font.getGlyphOrder()))

                if 'OS/2' in font:
                    os2 = font['OS/2']
                    w_class = getattr(os2, 'usWeightClass', None)
                    if w_class:
                        weights = {
                            100: "Thin (100)", 200: "Extra Light (200)", 300: "Light (300)", 
                            400: "Regular (400)", 500: "Medium (500)", 600: "Semi Bold (600)", 
                            700: "Bold (700)", 800: "Extra Bold (800)", 900: "Black (900)"
                        }
                        info["weight"] = weights.get(w_class, f"Weight {w_class}")
                    elif info["style"] != "তথ্য পাওয়া যায়নি":
                        s_lower = info["style"].lower()
                        if "bold" in s_lower: info["weight"] = "Bold (700)"
                        elif "light" in s_lower: info["weight"] = "Light (300)"
                        elif "medium" in s_lower: info["weight"] = "Medium (500)"
                        elif "regular" in s_lower: info["weight"] = "Regular (400)"

                    fsType = getattr(os2, 'fsType', None)
                    if fsType is not None:
                        if fsType == 0 or not (fsType & 0x000E):
                            info["embedding_allowed"] = "হ্যাঁ (Installable / Unlimited)"
                        elif fsType & 0x0002:
                            info["embedding_allowed"] = "সীমিত (Restricted License)"
                        elif fsType & 0x0004:
                            info["embedding_allowed"] = "হ্যাঁ (Preview & Print)"
                        elif fsType & 0x0008:
                            info["embedding_allowed"] = "হ্যাঁ (Editable Embedding)"

                if 'cmap' in font:
                    try:
                        best_cmap = font.getBestCmap()
                        if best_cmap and len(best_cmap) > 0:
                            info["unicode_support"] = f"হ্যাঁ ({len(best_cmap)} Unicodes Supported)"
                        else:
                            unicode_tables = [t for t in font['cmap'].tables if t.isUnicode()]
                            if unicode_tables:
                                info["unicode_support"] = "হ্যাঁ (Unicode Supported)"
                    except Exception:
                        pass

                if 'head' in font:
                    head = font['head']
                    mac_epoch = datetime.datetime(1904, 1, 1)
                    if hasattr(head, 'created') and head.created:
                        try:
                            c_date = mac_epoch + datetime.timedelta(seconds=head.created)
                            info["created_date"] = c_date.strftime("%Y-%m-%d")
                        except Exception:
                            pass
                    if hasattr(head, 'modified') and head.modified:
                        try:
                            m_date = mac_epoch + datetime.timedelta(seconds=head.modified)
                            info["modified_date"] = m_date.strftime("%Y-%m-%d")
                        except Exception:
                            pass

            except Exception:
                pass

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
