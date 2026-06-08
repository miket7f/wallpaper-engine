import os
import glob
import requests
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from datetime import datetime

STATION = "41041"
IMAGE_URL = f"https://www.ndbc.noaa.gov/buoycam.php?station={STATION}"
DATA_URL = f"https://www.ndbc.noaa.gov/data/realtime2/{STATION}.txt"
RAW_DIR = "raw_images"
OUTPUT_FILE = "latest_wallpaper.jpg"
MAX_IMAGES = 10

def fetch_weather():
    try:
        r = requests.get(DATA_URL, timeout=10)
        lines = r.text.split('\n')
        headers = lines[0].replace("#", "").split()
        data = lines[2].split()
        
        def get_val(k):
            try: return data[headers.index(k)]
            except ValueError: return "N/A"
            
        return f"Station {STATION} | Wind: {get_val('WSPD')} m/s | Waves: {get_val('WVHT')} m | Air: {get_val('ATMP')} °C | Water: {get_val('WTMP')} °C"
    except Exception:
        return f"Station {STATION} | Weather data unavailable"

def main():
    os.makedirs(RAW_DIR, exist_ok=True)
    
    # 1. Fetch new image
    try:
        r = requests.get(IMAGE_URL, timeout=10)
        r.raise_for_status()
        new_img = Image.open(BytesIO(r.content))
        
        # Guard against nighttime HTML error pages or placeholders
        if new_img.size != (2880, 300):
            print("Received image is not 2880x300 (likely nighttime or offline). Skipping update.")
            return
    except Exception as e:
        print(f"Failed to fetch image: {e}")
        return

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    new_img.save(os.path.join(RAW_DIR, f"{timestamp}.jpg"))

    # 2. Manage state (keep only last 10)
    images = sorted(glob.glob(os.path.join(RAW_DIR, "*.jpg")))
    while len(images) > MAX_IMAGES:
        os.remove(images.pop(0))

    imgs = [Image.open(img) for img in reversed(images)] # Newest on top
    
    # 3. Build the composite
    # Always base math on 3000px height so the stitch scale remains consistent 
    # even during the first 10 hours while the repo is initially populated.
    stitch_w = 2880
    stitch_h_max = 300 * MAX_IMAGES
    stitch = Image.new('RGB', (stitch_w, stitch_h_max), (0, 0, 0))
    
    for i, img in enumerate(imgs):
        stitch.paste(img, (0, i * 300))
        
    target_h = 1080
    scale = target_h / stitch_h_max
    target_w = int(stitch_w * scale)
    stitch_resized = stitch.resize((target_w, target_h), Image.Resampling.LANCZOS)
    
    # 4. Create Background (Zoomed and blurred newest image)
    bg = imgs[0].copy()
    bg_scale = target_h / 300
    bg_w = int(stitch_w * bg_scale)
    bg = bg.resize((bg_w, target_h), Image.Resampling.LANCZOS)
    left = (bg_w - 1920) // 2
    bg = bg.crop((left, 0, left + 1920, target_h))
    bg = bg.filter(ImageFilter.GaussianBlur(radius=20))
    
    # 5. Final Composite
    final_img = Image.new('RGB', (1920, target_h))
    final_img.paste(bg, (0, 0))
    
    offset_x = (1920 - target_w) // 2
    final_img.paste(stitch_resized, (offset_x, 0))
    
    # 6. Overlay Weather Data
    draw = ImageDraw.Draw(final_img)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf", 32)
    except IOError:
        font = ImageFont.load_default()
        
    weather_str = fetch_weather()
    draw.text((30, 30), weather_str, fill="white", stroke_fill="black", stroke_width=2, font=font)
    
    final_img.save(OUTPUT_FILE)
    print("Wallpaper generated successfully.")

if __name__ == "__main__":
    main()
