from fastapi import FastAPI, Response, Query
from PIL import Image, ImageDraw, ImageFont
import requests
import io

app = FastAPI()

@app.get("/")
def home():
    return {"status": "DaVinci Font Preview Engine Running"}

@app.get("/preview")
def generate_preview(
    font_url: str, 
    text: str = "আমাদের ছোট নদী চলে বাঁকে বাঁকে\nDaVinci Premium Font Live Preview 2026"
):
    try:
        # Download Font File
        font_res = requests.get(font_url)
        font_bytes = io.BytesIO(font_res.content)
        
        # Create Canvas Image (Width: 1200px, Height: 630px)
        width, height = 1200, 630
        img = Image.new('RGB', (width, height), color='#0f172a') # Dark slate background
        draw = ImageDraw.Draw(img)
        
        # Load Font
        font_size = 52
        font = ImageFont.truetype(font_bytes, size=font_size)
        
        # Card Background Inside
        card_margin = 40
        draw.rounded_rectangle(
            [card_margin, card_margin, width - card_margin, height - card_margin],
            radius=20,
            fill='#1e293b',
            outline='#38bdf8',
            width=3
        )
        
        # Draw Header Tag
        draw.text((70, 70), "DaVinci Font Preview", fill="#38bdf8", font=font)
        
        # Draw Main Preview Text
        draw.multiline_text((70, 200), text, fill="#f8fafc", font=font, spacing=25)
        
        # Draw Footer Branding
        draw.text((70, 520), "Generated via @davinci_live_bot", fill="#94a3b8", font=font)
        
        # Output Buffer
        img_byte_arr = io.BytesIO()
        img.save(img_byte_arr, format='PNG')
        img_byte_arr = img_byte_arr.getvalue()
        
        return Response(content=img_byte_arr, media_type="image/png")
    
    except Exception as e:
        return {"error": str(e)}
