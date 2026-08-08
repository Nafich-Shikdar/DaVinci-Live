from fastapi import FastAPI, Response, Request
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask
from PIL import Image, ImageDraw, ImageFont
from pydantic import BaseModel
from typing import List, Optional
import requests
import io
import random
import zipfile
import datetime
import struct
import os
import tempfile
import uuid
import re
import subprocess

try:
    import pyzipper
except ImportError:
    pyzipper = None

try:
    from fontTools.ttLib import TTFont
except ImportError:
    TTFont = None

try:
    import yt_dlp
except ImportError:
    yt_dlp = None

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

# ভিডিও ডাউনলোড সংক্রান্ত কনফিগারেশন
MAX_TELEGRAM_SIZE = 49 * 1024 * 1024  # টেলিগ্রাম বট আপলোড লিমিট (~50MB)

# 🎬 YouTube বট-চেকে আটকালে ফলব্যাক হিসেবে ব্যবহৃত পাবলিক Piped API ইনস্ট্যান্স
# (Piped একটা ওপেন-সোর্স প্রাইভেসি-ফ্রেন্ডলি YouTube ফ্রন্টএন্ড — YouTube-এর সার্ভারে
# সরাসরি রিকোয়েস্ট না গিয়ে এই ইনস্ট্যান্সগুলো দিয়ে স্ট্রিম URL পাওয়া যায়)
PIPED_API_INSTANCES = [
    "https://pipedapi.kavin.rocks",
    "https://pipedapi-libre.kavin.rocks",
    "https://piped-api.privacy.com.de",
    "https://pipedapi.adminforge.de",
    "https://api.piped.yt",
    "https://pipedapi.drgns.space",
    "https://pipedapi.owo.si",
]


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
# (কোডটি ছোট রাখতে এখানে শুধু পরিবর্তিত অংশটি দেওয়া হলো)

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
            canvas_bg, card_bg, border_c, text_c, sub_c = (0, 0, 0, 0), "#131e30", "#1e293b", "#ffffff", "#64748b"
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


# -------------------------------------------------------------
# 🎬 নতুন ফিচার: ভিডিও ডাউনলোডার (yt-dlp ভিত্তিক, সব প্ল্যাটফর্ম সাপোর্ট)
# -------------------------------------------------------------
def cleanup_file(path: str):
    """ভিডিও পাঠানোর পর ডিস্ক থেকে টেম্প ফাইল মুছে ফেলে"""
    try:
        if path and os.path.exists(path):
            os.remove(path)
            parent_dir = os.path.dirname(path)
            if parent_dir and os.path.isdir(parent_dir):
                try:
                    os.rmdir(parent_dir)
                except OSError:
                    pass  # ডিরেক্টরি খালি না থাকলে সমস্যা নেই
    except Exception:
        pass


def extract_youtube_id(url: str):
    """YouTube URL (watch, youtu.be, shorts, embed, mobile) থেকে ১১-ক্যারেক্টার ভিডিও আইডি বের করে"""
    patterns = [
        r"(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/|youtube\.com/embed/|m\.youtube\.com/watch\?v=)([A-Za-z0-9_-]{11})",
    ]
    for p in patterns:
        m = re.search(p, url)
        if m:
            return m.group(1)
    return None


def fetch_piped_stream(video_id: str):
    """
    একাধিক পাবলিক Piped ইনস্ট্যান্স ক্রমান্বয়ে ট্রাই করে স্ট্রিম তথ্য আনে।
    প্রথমে প্রোগ্রেসিভ (audio+video একসাথে থাকা) mp4 স্ট্রিম খোঁজে — এতে ffmpeg লাগে না।
    না পেলে HLS মাস্টার প্লেলিস্ট রিটার্ন করে (ffmpeg দিয়ে মার্জ করতে হবে)।
    """
    for base in PIPED_API_INSTANCES:
        try:
            res = requests.get(f"{base}/streams/{video_id}", timeout=12)
            if res.status_code != 200:
                continue
            data = res.json()
            title = data.get("title") or "video"

            video_streams = data.get("videoStreams", []) or []
            progressive = [
                s for s in video_streams
                if not s.get("videoOnly", True) and s.get("url")
            ]
            progressive.sort(key=lambda s: (s.get("height") or 0), reverse=True)
            for s in progressive:
                h = s.get("height") or 0
                if h and h <= 720:
                    return {"type": "progressive", "url": s["url"], "title": title}
            if progressive:
                # কোনোটাই ৭২০p বা তার নিচে না থাকলে সবচেয়ে ছোট রেজোলিউশনেরটা নেয়
                return {"type": "progressive", "url": progressive[-1]["url"], "title": title}

            hls_url = data.get("hls")
            if hls_url:
                return {"type": "hls", "url": hls_url, "title": title}
        except Exception:
            continue
    return None


def download_progressive_stream(url: str, out_path: str, max_bytes: int) -> bool:
    """সরাসরি প্রোগ্রেসিভ mp4 স্ট্রিম ডাউনলোড করে, সাইজ লিমিট ছাড়ালে থামিয়ে দেয়"""
    try:
        with requests.get(url, stream=True, timeout=60) as r:
            r.raise_for_status()
            total = 0
            with open(out_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=1024 * 256):
                    if not chunk:
                        continue
                    total += len(chunk)
                    if total > max_bytes:
                        return False
                    f.write(chunk)
        return True
    except Exception:
        return False


def download_hls_stream(hls_url: str, out_path: str) -> bool:
    """ffmpeg দিয়ে HLS (m3u8) স্ট্রিম একটা mp4 ফাইলে মার্জ করে (audio+video)"""
    try:
        result = subprocess.run(
            ["ffmpeg", "-y", "-i", hls_url, "-c", "copy", "-bsf:a", "aac_adtstoasc", out_path],
            capture_output=True, timeout=180
        )
        return result.returncode == 0 and os.path.exists(out_path)
    except Exception:
        return False


@app.get("/debug")
def debug_info():
    """
    🔍 ডায়াগনস্টিক এন্ডপয়েন্ট — ভিডিও ডাউনলোড ঠিকভাবে কনফিগার হয়েছে কিনা যাচাই করতে।
    কোনো সংবেদনশীল কুকি ডেটা এক্সপোজ করে না, শুধু স্ট্যাটাস দেখায়।
    """
    info = {
        "yt_dlp_installed": yt_dlp is not None,
        "yt_dlp_version": None,
        "invidious_plugin_loaded": False,
        "cookies_env_set": False,
        "cookies_file_path": None,
        "cookies_file_exists": False,
        "cookies_file_size_bytes": None,
        "proxy_env_set": False,
    }

    if yt_dlp:
        try:
            info["yt_dlp_version"] = yt_dlp.version.__version__
        except Exception:
            info["yt_dlp_version"] = "unknown"

        try:
            # Invidious প্লাগইন লোড হলে extractor list-এ থাকার কথা
            extractor_names = [e.IE_NAME for e in yt_dlp.extractor.gen_extractors() if hasattr(e, "IE_NAME")]
            info["invidious_plugin_loaded"] = any("invidious" in (n or "").lower() for n in extractor_names)
        except Exception as e:
            info["invidious_plugin_loaded"] = f"check failed: {str(e)}"

    cookies_path = os.environ.get("YTDLP_COOKIES_FILE", "").strip()
    if cookies_path:
        info["cookies_env_set"] = True
        info["cookies_file_path"] = cookies_path
        info["cookies_file_exists"] = os.path.exists(cookies_path)
        if info["cookies_file_exists"]:
            try:
                info["cookies_file_size_bytes"] = os.path.getsize(cookies_path)
            except Exception:
                pass

    info["proxy_env_set"] = bool(os.environ.get("YTDLP_PROXY", "").strip())

    return info


@app.get("/download")
def download_video(url: str):
    """
    যেকোনো পাবলিক প্ল্যাটফর্মের (YouTube, Facebook, Instagram, TikTok,
    Twitter/X, ইত্যাদি) ভিডিও লিংক দিলে yt-dlp দিয়ে ডাউনলোড করে ফাইল রিটার্ন করে।
    """
    if not yt_dlp:
        return {"error": "yt-dlp ইনস্টল করা নেই। requirements.txt-এ yt-dlp যোগ করুন।"}

    tmp_dir = tempfile.mkdtemp(prefix="vid_")
    out_template = os.path.join(tmp_dir, f"{uuid.uuid4().hex}.%(ext)s")

    ydl_opts = {
        "outtmpl": out_template,
        "format": "best[filesize<49M]/best[height<=720]/best",
        "merge_output_format": "mp4",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "max_filesize": MAX_TELEGRAM_SIZE,
        "socket_timeout": 30,
        "retries": 3,
        # 🔧 YouTube-এর "Sign in to confirm you're not a bot" বট-চেক এড়াতে
        # একাধিক ক্লায়েন্ট ক্রমান্বয়ে ট্রাই করা হয় (tv/android সাধারণত কম কড়াকড়ির শিকার হয়)
        "extractor_args": {
            "youtube": {
                "player_client": ["tv", "android", "ios", "web"],
            }
        },
        "http_headers": {
            "User-Agent": "com.google.android.youtube/19.09.37 (Linux; U; Android 14) gzip"
        },
    }

    # 🌐 ঐচ্ছিক: রেসিডেনশিয়াল প্রক্সি দেওয়া থাকলে ব্যবহার করবে (env var: YTDLP_PROXY)
    # Render-এর ডেটাসেন্টার IP প্রায়ই YouTube ব্লক করে; কুকিজ + আপডেটেড yt-dlp দিয়েও
    # কাজ না করলে এটাই সবচেয়ে নির্ভরযোগ্য (কিন্তু পেইড) সমাধান।
    proxy_url = os.environ.get("YTDLP_PROXY", "").strip()
    if proxy_url:
        ydl_opts["proxy"] = proxy_url

    # 🍪 ঐচ্ছিক: কুকিজ ফাইল দেওয়া থাকলে ব্যবহার করবে (env var দিয়ে সেট করুন YTDLP_COOKIES_FILE)
    # এটা বট-চেক এড়াতে সবচেয়ে নির্ভরযোগ্য উপায়, বিশেষ করে বয়স-সীমাবদ্ধ/প্রাইভেট ভিডিওর জন্য।
    #
    # ⚠️ গুরুত্বপূর্ণ: Render-এর Secret File মাউন্ট (/etc/secrets/...) READ-ONLY।
    # yt-dlp ব্যবহারের পর সেশন কুকি আপডেট হলে সেটা একই ফাইলে লিখতে চেষ্টা করে,
    # read-only পাথে লিখলে "[Errno 30] Read-only file system" এরর দেয়।
    # তাই প্রতি রিকোয়েস্টে ফাইলটা একটা লিখনযোগ্য টেম্প কপিতে নিয়ে সেটা ব্যবহার করা হয়।
    source_cookies_path = os.environ.get("YTDLP_COOKIES_FILE", "").strip()
    if source_cookies_path and os.path.exists(source_cookies_path):
        writable_cookies_path = os.path.join(tmp_dir, "cookies.txt")
        try:
            import shutil
            shutil.copy(source_cookies_path, writable_cookies_path)
            ydl_opts["cookiefile"] = writable_cookies_path
        except Exception:
            pass  # কপি ব্যর্থ হলে কুকি ছাড়াই এগিয়ে যাবে

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filepath = ydl.prepare_filename(info)

            # merge_output_format প্রয়োগ হলে এক্সটেনশন বদলে যেতে পারে, তাই যাচাই করি
            if not os.path.exists(filepath):
                base, _ = os.path.splitext(filepath)
                for ext in ["mp4", "mkv", "webm"]:
                    candidate = base + "." + ext
                    if os.path.exists(candidate):
                        filepath = candidate
                        break

        if not os.path.exists(filepath):
            cleanup_file(filepath)
            return {"error": "ডাউনলোড ব্যর্থ হয়েছে, ফাইল পাওয়া যায়নি।"}

        size = os.path.getsize(filepath)
        if size > MAX_TELEGRAM_SIZE:
            cleanup_file(filepath)
            return {"error": "ভিডিওটি প্রায় ৫০MB এর বেশি, টেলিগ্রাম বট দিয়ে পাঠানো সম্ভব নয়।"}

        title = (info.get("title") or "video")
        safe_title = "".join(c for c in title if c.isalnum() or c in " _-").strip()[:60] or "video"

        return FileResponse(
            path=filepath,
            media_type="video/mp4",
            filename=f"{safe_title}.mp4",
            background=BackgroundTask(cleanup_file, filepath),
        )

    except yt_dlp.utils.DownloadError as e:
        err_str = str(e)
        is_bot_check = "sign in" in err_str.lower() or "not a bot" in err_str.lower()

        # 🔁 বট-চেকে আটকালে Piped ফলব্যাক ট্রাই করা হয় (YouTube সার্ভারকে বাইপাস করে)
        if is_bot_check:
            video_id = extract_youtube_id(url)
            if video_id:
                stream_info = fetch_piped_stream(video_id)
                if stream_info:
                    fallback_path = os.path.join(tmp_dir, f"{uuid.uuid4().hex}.mp4")
                    success = False
                    if stream_info["type"] == "progressive":
                        success = download_progressive_stream(stream_info["url"], fallback_path, MAX_TELEGRAM_SIZE)
                    else:
                        success = download_hls_stream(stream_info["url"], fallback_path)

                    if success and os.path.exists(fallback_path) and 0 < os.path.getsize(fallback_path) <= MAX_TELEGRAM_SIZE:
                        raw_title = stream_info["title"]
                        safe_title = "".join(c for c in raw_title if c.isalnum() or c in " _-").strip()[:60] or "video"
                        return FileResponse(
                            path=fallback_path,
                            media_type="video/mp4",
                            filename=f"{safe_title}.mp4",
                            background=BackgroundTask(cleanup_file, fallback_path),
                        )
                    cleanup_file(fallback_path)

        cleanup_file(tmp_dir)
        version_info = getattr(yt_dlp.version, "__version__", "unknown")
        return {
            "error": f"লিংক থেকে ভিডিও পাওয়া যায়নি বা সাপোর্টেড নয়: {str(e)}",
            "yt_dlp_version": version_info,
        }
    except Exception as e:
        cleanup_file(tmp_dir)
        return {"error": str(e)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
