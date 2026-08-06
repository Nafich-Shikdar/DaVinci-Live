# -------------------------------------------------------------
# IMPROVED AUTO LANGUAGE DETECTION (cmap + metadata)
# -------------------------------------------------------------
def detect_font_language(font_bytes: bytes, font_name: str = "") -> str:
    """
    ফন্টের ইউনিকোড cmap এবং name টেবিল মেটাডেটা বিশ্লেষণ করে
    নির্ভুল ভাষা কোড রিটার্ন করে: 'b' (বাংলা), 'e' (ইংরেজি), 'a' (আরবি), 'all' (মিশ্র)
    """
    try:
        font = TTFont(io.BytesIO(font_bytes))
        cmap = font.getBestCmap()
        if not cmap:
            return "all"

        has_bengali = any(0x0980 <= cp <= 0x09FF for cp in cmap.keys())
        has_arabic  = any(0x0600 <= cp <= 0x06FF for cp in cmap.keys())
        has_latin   = any(0x0041 <= cp <= 0x007A for cp in cmap.keys())

        # --- Step 1: Only one script present → direct match ---
        if has_bengali and not has_arabic and not has_latin:
            return "b"
        if has_arabic and not has_bengali and not has_latin:
            return "a"
        if has_latin and not has_bengali and not has_arabic:
            return "e"

        # --- Step 2: Multiple scripts → check name table metadata ---
        name_table = font.get('name')
        if name_table:
            for record in name_table.names:
                try:
                    raw_text = record.toUnicode().lower()
                except Exception:
                    continue

                # nameID 1 (family), 4 (full name), 16 (preferred family)
                if record.nameID in (1, 4, 16):
                    if any(kw in raw_text for kw in ['bengali', 'bangla', 'বাংলা']):
                        return "b"
                    if any(kw in raw_text for kw in ['arabic', 'عربي', 'العربية']):
                        return "a"
                    if 'english' in raw_text:
                        return "e"

                # nameID 9 (designer), 0 (copyright), 13/14 (license)
                if record.nameID in (0, 9, 13, 14):
                    if any(kw in raw_text for kw in ['bangladesh', 'bengal']):
                        return "b"
                    if any(kw in raw_text for kw in ['arab', 'مصر']):
                        return "a"

        # --- Step 3: Heuristics ---
        # Bengali + Arabic together → too ambiguous → all
        if has_bengali and has_arabic:
            return "all"

        # Bengali + Latin → typical for Bengali fonts → assume Bengali
        if has_bengali and has_latin:
            return "b"

        # Arabic + Latin → typical for Arabic fonts → assume Arabic
        if has_arabic and has_latin:
            return "a"

        # Fallback (shouldn't reach here normally)
        return "all"

    except Exception:
        return "all"


@app.get("/detect_language")
def detect_language(font_url: str, font_name: str = "font.ttf", inner_font: str = ""):
    """
    নতুন ইম্প্রুভড ল্যাঙ্গুয়েজ ডিটেকশন এন্ডপয়েন্ট।
    ফন্টের cmap ও name টেবিল মেটাডেটা ঘেঁটে নির্ভুল ভাষা নির্ধারণ করে।
    """
    try:
        raw_bytes = fetch_font_bytes_cached(font_url)
        target_bytes = raw_bytes

        # ZIP file handling
        if font_name.lower().endswith(".zip") or zipfile.is_zipfile(io.BytesIO(raw_bytes)):
            with zipfile.ZipFile(io.BytesIO(raw_bytes)) as zf:
                fonts = [f for f in zf.namelist() if f.lower().endswith(('.ttf', '.otf'))]
                if not fonts:
                    return {"language": "all", "error": "No font in zip"}
                target_file = fonts[0]
                if inner_font:
                    target_file = next((f for f in fonts if f.endswith(inner_font)), fonts[0])
                target_bytes = zf.read(target_file)

        lang = detect_font_language(target_bytes, font_name)
        return {"language": lang}

    except Exception as e:
        return {"language": "all", "error": str(e)}
