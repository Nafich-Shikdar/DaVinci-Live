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
# HIGH-PRECISION NATIVE TTF/OTF BINARY METADATA PARSER
# -------------------------------------------------------------
def parse_ttf_binary_metadata(data: bytes):
    meta = {}
    if len(data) < 12:
        return meta
    
    sfnt_version = data[:4]
    if sfnt_version == b'OTTO':
        meta['format'] = 'OTF (OpenType)'
    elif sfnt_version in [b'\x00\x01\x00\x00', b'true']:
        meta['format'] = 'TTF (TrueType)'

    try:
        num_tables = struct.unpack('>H', data[4:6])[0]
        tables = {}
        offset = 12
        for _ in range(num_tables):
            if offset + 16 > len(data):
                break
            tag, check_sum, t_offset, length = struct.unpack('>4sIII', data[offset:offset+16])
            tag_str = tag.decode('latin1', errors='ignore')
            tables[tag_str] = (t_offset, length)
            offset += 16

        # Glyph count from maxp table
        if 'maxp' in tables:
            t_off, t_len = tables['maxp']
            if t_len >= 6 and t_off + 6 <= len(data):
                meta['glyph_count'] = str(struct.unpack('>H', data[t_off+4:t_off+6])[0])

        # Name table records
        if 'name' in tables:
            t_off, t_len = tables['name']
            if t_off + 6 <= len(data):
                fmt, count, string_offset = struct.unpack('>HHH', data[t_off:t_off+6])
                records_start = t_off + 6
                storage_start = t_off + string_offset

                names = {}
                for i in range(count):
                    rec_off = records_start + i * 12
                    if rec_off + 12 > len(data):
                        break
                    p_id, e_id, l_id, n_id, length, s_off = struct.unpack('>HHHHHH', data[rec_off:rec_off+12])
                    str_start = storage_start + s_off
                    if str_start + length <= len(data):
                        raw_str = data[str_start:str_start+length]
                        val = None
                        for enc in ['utf-16-be', 'utf-8', 'latin1', 'cp1252', 'mac-roman']:
                            try:
                                decoded = raw_str.decode(enc)
                                cleaned = decoded.replace('\x00', '').strip()
                                if cleaned and any(c.isalnum() for c in cleaned):
                                    val = cleaned
                                    break
                            except Exception:
                                pass
                        
                        if val and (n_id not in names or p_id == 3):
                            names[n_id] = val

                if 1 in names: meta['family'] = names[1]
                if 16 in names and ('family' not in meta or not meta['family']): meta['family'] = names[16]
                if 4 in names: meta['full_name'] = names[4]
                if 5 in names: meta['version'] = names[5]
                if 2 in names: meta['style'] = names[2]
                if 17 in names and ('style' not in meta or not meta['style']): meta['style'] = names[17]
                if 8 in names: meta['manufacturer'] = names[8]
                if 9 in names: meta['designer'] = names[9]
                if 0 in names: meta['copyright'] = names[0]
                if 13 in names: meta['license'] = names[13]

        # OS/2 table for weight and embedding
        if 'OS/2' in tables:
            t_off, t_len = tables['OS/2']
            if t_len >= 10 and t_off + 10 <= len(data):
                us_weight_class = struct.unpack('>H', data[t_off+4:t_off+6])[0]
                weights = {
                    100: "Thin (100)", 200: "Extra Light (200)", 300: "Light (300)", 
                    400: "Regular (400)", 500: "Medium (500)", 600: "Semi Bold (600)", 
                    700: "Bold (700)", 800: "Extra Bold (800)", 900: "Black (900)"
                }
                meta['weight'] = weights.get(us_weight_class, f"Weight {us_weight_class}")

                fs_type = struct.unpack('>H', data[t_off+8:t_off+10])[0]
                if fs_type == 0 or not (fs_type & 0x000E):
                    meta['embedding_allowed'] = "হ্যাঁ (Installable / Unlimited)"
                elif fs_type & 0x0002:
                    meta['embedding_allowed'] = "সীমিত (Restricted License)"
                elif fs_type & 0x0004:
                    meta['embedding_allowed'] = "হ্যাঁ (Preview & Print)"
                elif fs_type & 0x0008:
                    meta['embedding_allowed'] = "হ্যাঁ (Editable Embedding)"
    except Exception:
        pass

    return meta

# -------------------------------------------------------------
# FONT METADATA API
# -------------------------------------------------------------
@app.get("/font_info")
def get_font_info(font_url: str, font_name: str = "Font.ttf", inner_font: str = ""):
    try:
        font_res = requests.get(font_url, timeout=20)
        raw_bytes = font_res.content
        size_bytes = len(raw_bytes)
        file_bytes = io.BytesIO(raw_bytes)

        target_font_bytes = raw_bytes

        # ZIP AUTO-EXTRACTOR LOGIC
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
                    target_font_bytes = z.read(target_file)
                    size_bytes = len(target_font_bytes)
                else:
                    return {"error": "No .ttf or .otf found in zip"}

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

        # 1. fontTools Extraction
        if TTFont:
            try:
                tt = TTFont(io.BytesIO(target_font_bytes))
                if 'name' in tt:
                    for record in tt['name'].names:
                        try:
                            val = None
                            try: val = record.toUnicode()
                            except Exception:
                                for enc in ['utf-16-be', 'utf-8', 'mac-roman', 'latin1']:
                                    try: val = record.string.decode(enc); break
                                    except Exception: pass
                            if val:
                                cleaned = val.replace('\x00', '').strip()
                                if cleaned:
                                    if record.nameID in [1, 16] and info["family"] == "তথ্য পাওয়া যায়নি": info["family"] = cleaned
                                    elif record.nameID == 4 and info["full_name"] == "তথ্য পাওয়া যায়নি": info["full_name"] = cleaned
                                    elif record.nameID == 5 and info["version"] == "তথ্য পাওয়া যায়নি": info["version"] = cleaned
                                    elif record.nameID in [2, 17] and info["style"] == "তথ্য পাওয়া যায়নি": info["style"] = cleaned
                                    elif record.nameID == 9 and info["designer"] == "তথ্য পাওয়া যায়নি": info["designer"] = cleaned
                                    elif record.nameID == 8 and info["manufacturer"] == "তথ্য পাওয়া যায়নি": info["manufacturer"] = cleaned
                                    elif record.nameID == 0 and info["copyright"] == "তথ্য পাওয়া যায়নি": info["copyright"] = cleaned
                                    elif record.nameID in [13, 14] and info["license"] == "তথ্য পাওয়া যায়নি": info["license"] = cleaned
                        except Exception: pass

                if 'cmap' in tt:
                    try:
                        best = tt.getBestCmap()
                        if best: info["unicode_support"] = f"হ্যাঁ ({len(best)} Unicodes Supported)"
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

        # 2. Native Binary Parser Fallback
        binary_meta = parse_ttf_binary_metadata(target_font_bytes)
        for k, v in binary_meta.items():
            if v and (k not in info or info[k] == "তথ্য পাওয়া যায়নি"):
                info[k] = v

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
