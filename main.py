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

# MULTI-LANGUAGE WORD POOLS
BANGLA_WORDS_POOL = ["শ্রদ্ধাঞ্জলি", "সূক্ষ্মতা", "আকাঙ্ক্ষা", "উচ্ছ্বসিত", "সংস্কৃতি", "স্বাধীনতা", "সন্ধ্যা", "প্রজ্বলিত", "নান্দনিক"]
ENGLISH_WORDS_POOL = ["Typography", "Aesthetics", "Creative", "Design", "Minimalism", "Elegance", "Branding", "Calligraphy"]
ARABIC_WORDS_POOL = ["الخط العربي", "جماليات", "إبداع", "تصميم", "أصالة", "فنون", "خطاط", "الخط"]
GLOBAL_RANDOM_WORDS = ["सुंदरता", "Tipografía", "Типографика", "デザイン", "Élégance", "حُسن", "Kalligraphie"]

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
    return {"status": "DaVinci Multilingual & ZIP Manager Engine Active"}

# -------------------------------------------------------------
# ZIP MANAGER: INSPECT, EXTRACT & CREATE (PASSWORD & CUSTOM NAME SUPPORTED)
# -------------------------------------------------------------
class ZipInspectRequest(BaseModel):
    zip_url: str
    password: Optional[str] = None

class ZipFileItem(BaseModel):
    url: str
    name: str

class ZipCreateRequest(BaseModel):
    files: List[ZipFileItem]
    password: Optional[str] = None
    zip_name: Optional[str] = "Archive.zip"

def check_zip_is_encrypted(zip_bytes: bytes) -> bool:
    try:
        zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
        for zinfo in zf.infolist():
            if zinfo.flag_bits & 0x1:
                return True
    except Exception:
        pass
    return False

@app.post("/zip_inspect")
def inspect_zip_archive(req: ZipInspectRequest):
    try:
        raw_bytes = fetch_font_bytes_cached(req.zip_url)
        is_encrypted = check_zip_is_encrypted(raw_bytes)
        
        pwd_bytes = req.password.encode('utf-8') if req.password else None
        
        zf = None
        if pyzipper and is_encrypted:
            try:
                zf = pyzipper.AESZipFile(io.BytesIO(raw_bytes))
                if pwd_bytes: zf.setpassword(pwd_bytes)
            except Exception:
                zf = zipfile.ZipFile(io.BytesIO(raw_bytes))
                if pwd_bytes: zf.setpassword(pwd_bytes)
        else:
            zf = zipfile.ZipFile(io.BytesIO(raw_bytes))
            if pwd_bytes: zf.setpassword(pwd_bytes)

        password_valid = not is_encrypted
        files_info = []
        folders_set = set()
        total_size = 0

        if is_encrypted and req.password:
            try:
                for info in zf.infolist():
                    if not info.is_dir():
                        with zf.open(info, 'r') as f:
                            f.read(16)
                        password_valid = True
                        break
            except Exception:
                password_valid = False

        if not is_encrypted or password_valid:
            for info in zf.infolist():
                parts = info.filename.rstrip('/').split('/')
                if len(parts) > 1:
                    folder_path = "/".join(parts[:-1])
                    folders_set.add(folder_path)

                if not info.is_dir() and not info.filename.startswith('__MACOSX') and not info.filename.split('/')[-1].startswith('._'):
                    file_name = info.filename.split('/')[-1]
                    files_info.append({
                        "name": file_name if file_name else info.filename,
                        "path": info.filename,
                        "size": info.file_size
                    })
                    total_size += info.file_size

        return {
            "success": True,
            "is_encrypted": is_encrypted,
            "password_valid": password_valid,
            "file_count": len(files_info),
            "folder_count": len(folders_set),
            "total_size": total_size,
            "files": files_info,
            "error": None
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.get("/zip_extract_file")
def extract_single_file_from_zip(zip_url: str, file_path: str, password: str = ""):
    try:
        raw_bytes = fetch_font_bytes_cached(zip_url)
        pwd_bytes = password.encode('utf-8') if password else None
        data = None

        if pyzipper:
            try:
                zf = pyzipper.AESZipFile(io.BytesIO(raw_bytes))
                if pwd_bytes: zf.setpassword(pwd_bytes)
                data = zf.read(file_path)
            except Exception:
                zf = zipfile.ZipFile(io.BytesIO(raw_bytes))
                if pwd_bytes: zf.setpassword(pwd_bytes)
                data = zf.read(file_path)
        else:
            zf = zipfile.ZipFile(io.BytesIO(raw_bytes))
            if pwd_bytes: zf.setpassword(pwd_bytes)
            data = zf.read(file_path)

        filename = file_path.split('/')[-1] or "extracted_file"
        return Response(content=data, media_type="application/octet-stream", headers={"Content-Disposition": f"attachment; filename={filename}"})
    except Exception as e:
        return Response(content=f"Error: {str(e)}".encode('utf-8'), status_code=500)

@app.post("/zip_create")
def create_zip_archive_endpoint(req: ZipCreateRequest):
    try:
        buf = io.BytesIO()
        pwd_bytes = req.password.encode('utf-8') if (req.password and req.password.strip()) else None

        total_uncompressed_size = 0
        added_files_count = 0

        if pwd_bytes:
            if pyzipper is not None:
                with pyzipper.AESZipFile(buf, 'w', compression=pyzipper.ZIP_DEFLATED, encryption=pyzipper.WZ_AES_256) as zf:
                    zf.setpassword(pwd_bytes)
                    for item in req.files:
                        try:
                            f_res = requests.get(item.url, timeout=25)
                            if f_res.status_code == 200:
                                content = f_res.content
                                total_uncompressed_size += len(content)
                                zf.writestr(item.name, content)
                                added_files_count += 1
                        except Exception:
                            pass
            else:
                return Response(content=b"Error: pyzipper module not installed on server for password protection", status_code=500)
        else:
            with zipfile.ZipFile(buf, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
                for item in req.files:
                    try:
                        f_res = requests.get(item.url, timeout=25)
                        if f_res.status_code == 200:
                            content = f_res.content
                            total_uncompressed_size += len(content)
                            zf.writestr(item.name, content)
                            added_files_count += 1
                    except Exception:
                        pass

        buf.seek(0)
        zip_data = buf.getvalue()

        final_zip_name = req.zip_name if req.zip_name else "Archive.zip"
        if not final_zip_name.lower().endswith(".zip"):
            final_zip_name += ".zip"

        return Response(
            content=zip_data, 
            media_type="application/zip", 
            headers={
                "Content-Disposition": f"attachment; filename={final_zip_name}",
                "X-Total-Files": str(added_files_count),
                "X-Uncompressed-Size": str(total_uncompressed_size),
                "X-Compressed-Size": str(len(zip_data))
            }
        )
    except Exception as e:
        return Response(content=f"Error creating zip: {str(e)}".encode('utf-8'), status_code=500)

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

        if 'maxp' in tables:
            t_off, t_len = tables['maxp']
            if t_len >= 6 and t_off + 6 <= len(data):
                meta['glyph_count'] = str(struct.unpack('>H', data[t_off+4:t_off+6])[0])

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
                if 6 in names: meta['postscript_name'] = names[6]
                if 3 in names: meta['unique_id'] = names[3]
                if 2 in names: meta['style'] = names[2]
                if 17 in names and ('style' not in meta or not meta['style']): meta['style'] = names[17]
                if 8 in names: meta['manufacturer'] = names[8]
                if 9 in names: meta['designer'] = names[9]
                if 0 in names: meta['copyright'] = names[0]
                if 13 in names: meta['license'] = names[13]
                if 5 in names: meta['version'] = names[5]

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
        raw_bytes = fetch_font_bytes_cached(font_url)
        size_bytes = len(raw_bytes)
        file_bytes = io.BytesIO(raw_bytes)

        target_font_bytes = raw_bytes

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
            "postscript_name": "তথ্য পাওয়া যায়নি",
            "unique_id": "তথ্য পাওয়া যায়নি",
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
                                    elif record.nameID == 6 and info["postscript_name"] == "তথ্য পাওয়া যায়নি": info["postscript_name"] = cleaned
                                    elif record.nameID == 3 and info["unique_id"] == "তথ্য পাওয়া যায়নি": info["unique_id"] = cleaned
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

        binary_meta = parse_ttf_binary_metadata(target_font_bytes)
        for k, v in binary_meta.items():
            if v and (k not in info or info[k] == "তথ্য পাওয়া যায়নি"):
                info[k] = v

        return info
    except Exception as e:
        return {"error": str(e)}

# -------------------------------------------------------------
# GLYPH INSPECTOR & PREVIEW GENERATOR
# -------------------------------------------------------------
@app.get("/glyph_info")
def get_glyph_info(font_url: str, font_name: str = "Font.ttf", inner_font: str = "", char: str = ""):
    try:
        raw_bytes = fetch_font_bytes_cached(font_url)
        file_bytes = io.BytesIO(raw_bytes)
        target_font_bytes = raw_bytes

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
                    target_font_bytes = z.read(target_file)

        total_glyphs = "তথ্য পাওয়া যায়নি"
        unicode_glyphs = "তথ্য পাওয়া যায়নি"
        missing_glyphs = 0
        supported_set = "Bangla, English, Numbers & Symbols"
        font_encoding = "Unicode (CMAP)"

        if TTFont:
            try:
                tt = TTFont(io.BytesIO(target_font_bytes))
                if 'maxp' in tt:
                    total_glyphs = str(tt['maxp'].numGlyphs)
                if 'cmap' in tt:
                    cmap = tt.getBestCmap()
                    if cmap:
                        unicode_glyphs = str(len(cmap))
            except Exception:
                pass

        if total_glyphs == "তথ্য পাওয়া যায়নি":
            meta = parse_ttf_binary_metadata(target_font_bytes)
            if meta.get('glyph_count'):
                total_glyphs = meta['glyph_count']

        return {
            "font_name": font_name,
            "total_glyphs": total_glyphs,
            "unicode_glyphs": unicode_glyphs,
            "missing_glyphs": missing_glyphs,
            "supported_set": supported_set,
            "font_encoding": font_encoding,
            "query_char": char.strip() if char else ""
        }
    except Exception as e:
        return {"error": str(e)}

@app.get("/glyph_preview")
def generate_glyph_preview(
    font_url: str,
    font_name: str = "Font.ttf",
    inner_font: str = "",
    char: str = "",
    requested_by: str = "User"
):
    try:
        raw_bytes = fetch_font_bytes_cached(font_url)
        file_bytes = io.BytesIO(raw_bytes)
        target_font_bytes = raw_bytes

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
                    target_font_bytes = z.read(target_file)

        font_io = io.BytesIO(target_font_bytes)
        width, height = 1080, 1080
        img = Image.new('RGB', (width, height), color="#0b1320")
        draw = ImageDraw.Draw(img)

        header_font = get_hind_siliguri_font(38)
        sub_font = get_hind_siliguri_font(22)
        credit_font = get_hind_siliguri_font(28)

        if char and len(char.strip()) > 0:
            target_char = char.strip()[0]
            title_text = f"Single Glyph View: '{target_char}'"
            draw.text((60, 45), title_text, fill="#ffffff", font=header_font)
            draw.line([(60, 105), (width - 60, 105)], fill="#1e293b", width=2)

            draw.rounded_rectangle([240, 180, 840, 780], radius=24, fill="#131e30", outline="#06b6d4", width=3)
            
            big_custom_font = get_auto_fit_font(font_io, target_char, max_width=500, max_height=500, start_size=320, min_size=60)
            c_bbox = draw.textbbox((0, 0), target_char, font=big_custom_font)
            cw, ch = c_bbox[2] - c_bbox[0], c_bbox[3] - c_bbox[1]
            draw.text((240 + (600 - cw) / 2, 180 + (600 - ch) / 2 - 20), target_char, fill="#38bdf8", font=big_custom_font)

            hex_code = f"U+{ord(target_char):04X}"
            code_text = f"Char: {target_char}   |   Unicode: {hex_code}"
            draw.text((340, 810), code_text, fill="#94a3b8", font=header_font)

        else:
            title_text = f"Glyph Collection Sheet: {font_name}"
            draw.text((60, 45), title_text, fill="#ffffff", font=header_font)
            draw.line([(60, 105), (width - 60, 105)], fill="#1e293b", width=2)

            grid_chars = [
                "অ", "আ", "ই", "ঈ", "উ", "ঊ", "ঋ", "এ", "ঐ", "ও", "ঔ",
                "ক", "খ", "গ", "ঘ", "ঙ", "চ", "ছ", "জ", "ঝ", "ঞ", "ট",
                "ঠ", "ড", "ঢ", "ণ", "ত", "থ", "দ", "ধ", "ন", "প", "ফ",
                "ব", "ভ", "ম", "য", "র", "ল", "শ", "ষ", "স", "হ", "ড়",
                "A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K",
                "L", "M", "N", "O", "P", "Q", "R", "S", "T", "U", "V",
                "0", "1", "2", "3", "4", "5", "6", "7", "8", "9",
                "০", "১", "২", "৩", "৪", "৫", "৬", "৭", "৮", "৯",
                "!", "@", "#", "$", "%", "&", "*", "(", ")", "+", "?"
            ]

            cols, rows = 11, 8
            start_x, start_y = 60, 130
            cell_w, cell_h = 86, 86

            grid_custom_font = get_auto_fit_font(font_io, "ক", max_width=50, max_height=50, start_size=42, min_size=20)

            for idx, ch in enumerate(grid_chars):
                r = idx // cols
                c = idx % cols
                x1 = start_x + c * (cell_w + 2)
                y1 = start_y + r * (cell_h + 2)

                draw.rounded_rectangle([x1, y1, x1 + cell_w, y1 + cell_h], radius=8, fill="#131e30", outline="#1e293b", width=1)
                
                try:
                    cb = draw.textbbox((0, 0), ch, font=grid_custom_font)
                    cw, ch_h = cb[2] - cb[0], cb[3] - cb[1]
                    draw.text((x1 + (cell_w - cw) / 2, y1 + (cell_h - ch_h) / 2 - 4), ch, fill="#f8fafc", font=grid_custom_font)
                except Exception:
                    draw.text((x1 + 35, y1 + 25), "?", fill="#ef4444", font=sub_font)

        draw.line([(60, 880), (width - 60, 880)], fill="#1e293b", width=2)
        u_text = f"Glyph Preview Requested by: {requested_by}"
        draw.text((60, 910), u_text, fill="#38bdf8", font=credit_font)

        img_byte_arr = io.BytesIO()
        img.save(img_byte_arr, format='PNG')
        return Response(content=img_byte_arr.getvalue(), media_type="image/png")

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
        try:
            binary_meta = parse_ttf_binary_metadata(raw_bytes)
            real_name = binary_meta.get('full_name') or binary_meta.get('family')
            if real_name and len(real_name.strip()) > 0:
                detected_header_name = real_name.strip()
        except Exception:
            pass

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
        title_bbox = draw.textbbox((0, 0), detected_header_name, font=header_font)
        title_w = title_bbox[2] - title_bbox[0]
        draw.text(((width - title_w) / 2, 55), detected_header_name, fill=text_c, font=header_font)
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
