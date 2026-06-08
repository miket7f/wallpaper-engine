import os
import glob
import requests
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
from datetime import datetime

STATION = "41041"
IMAGE_URL = f"https://www.ndbc.noaa.gov/buoycam.php?station={STATION}"
DATA_URL = f"https://www.ndbc.noaa.gov/data/realtime2/{STATION}.txt"
RAW_DIR = "raw_images"
OUTPUT_FILE = "latest_wallpaper.jpg"
MAX_IMAGES = 5  # Mathematically ideal: (300px * 5) scaled to 1920 width = 1000px height.

def fetch_weather():
    try:
        r = requests.get(DATA_URL, timeout=10)
        lines = r.text.split('\n')
        headers = lines[0].replace("#", "").split()
        data = lines[2].split()
        
        def get_val(k):
            try: return data[headers.index(k)]
            except ValueError: return "N/A"
            
        return f"Station {STATION}   |   Wind: {get_val('WSPD')} m/s   |   Waves: {get_val('WVHT')} m   |   Air: {get_val('ATMP')} °C   |   Water: {get_val('WTMP')} °C"
    except Exception:
        return f"Station {STATION} | Weather data unavailable"

def main():
    os.makedirs(RAW_DIR, exist_ok=True)
    
    # 1. Fetch new image
    try:
        r = requests.get(IMAGE_URL, timeout=10)
        r.raise_for_status()
        new_img = Image.open(BytesIO(r.content))
        
        if new_img.size != (2880, 300):
            print("Received image is not 2880x300 (likely nighttime). Skipping update.")
            return
    except Exception as e:
        print(f"Failed to fetch image: {e}")
        return

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    new_img.save(os.path.join(RAW_DIR, f"{timestamp}.jpg"))

    # 2. Manage state
    images = sorted(glob.glob(os.path.join(RAW_DIR, "*.jpg")))
    while len(images) > MAX_IMAGES:
        os.remove(images.pop(0))

    imgs = [Image.open(img) for img in reversed(images)] # Newest on top
    
    # 3. Build the vertical stitch
    stitch_w = 2880
    stitch_h = 300 * len(imgs)
    stitch = Image.new('RGB', (stitch_w, stitch_h))
    
    for i, img in enumerate(imgs):
        stitch.paste(img, (0, i * 300))
        
    # 4. Scale to exactly 1920 width
    target_w = 1920
    # Dynamic height calculation handles the first few hours when < 5 images exist
    target_h = int(stitch_h * (target_w / stitch_w)) 
    stitch_resized = stitch.resize((target_w, target_h), Image.Resampling.LANCZOS)
    
    # 5. Create final 1080p canvas (Solid Black)
    final_img = Image.new('RGB', (1920, 1080), (0, 0, 0))
    
    # Paste images at the bottom, leaving the black space at the top
    y_offset = 1080 - target_h
    final_img.paste(stitch_resized, (0, y_offset))
    
    # 6. Overlay Weather Data in the top black bar
    draw = ImageDraw.Draw(final_img)
    try:
        # Using a slightly larger font size to fill the 80px bar elegantly
        font = ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf", 34)
    except IOError:
        font = ImageFont.load_default()
        
    weather_str = fetch_weather()
    
    # Calculate text centering
    # Using textbbox which is the modern standard for Pillow text measurement
    bbox = draw.textbbox((0, 0), weather_str, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    
    text_x = (1920 - text_w) // 2
    
    # Center the text perfectly within whatever space is left at the top
    # y_offset will be 80 once the repo has 5 images.
    if y_offset > 0:
        text_y = (y_offset - text_h) // 2
    else:
        # Fallback if the canvas fills up entirely (e.g., if you change MAX_IMAGES later)
        text_y = 20 
        
    draw.text((text_x, text_y), weather_str, fill="white", font=font)
    
    final_img.save(OUTPUT_FILE)
    print(f"Wallpaper generated successfully. Final resolution: {final_img.size}")

if __name__ == "__main__":
    main()
