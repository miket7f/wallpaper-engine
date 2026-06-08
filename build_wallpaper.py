import os
import glob
import re
import requests
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
from bs4 import BeautifulSoup
from datetime import datetime

STATION = "41041"
IMAGE_URL = f"https://www.ndbc.noaa.gov/buoycam.php?station={STATION}"
STATION_URL = f"https://www.ndbc.noaa.gov/station_page.php?station={STATION}"
RAW_DIR = "raw_images"
OUTPUT_FILE = "latest_wallpaper.jpg"
MAX_IMAGES = 5  # 5 images * 200px (scaled) = 1000px height. Leaves 80px for text canvas.

def fetch_weather_from_page():
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        r = requests.get(STATION_URL, headers=headers, timeout=15)
        r.raise_for_status()
        
        soup = BeautifulSoup(r.text, 'html.parser')
        page_text = soup.get_text()
        
        # Helper 1: Extract string
        def extract_value(label_pattern, fallback="N/A"):
            match = re.search(label_pattern, page_text)
            if match:
                return re.sub(r'\s+', ' ', match.group(1)).strip()
            return fallback

        # Helper 2: Convert Fahrenheit to Celsius safely
        def to_celsius(temp_str):
            if temp_str == "N/A" or temp_str == "-": return "N/A"
            match = re.search(r"([-+]?\d*\.\d+|\d+)", temp_str)
            if match:
                val = float(match.group(1))
                if "F" in temp_str:
                    c_val = (val - 32) * 5.0 / 9.0
                    return f"{c_val:.1f} °C"
                return f"{val:.1f} °C" # In case NOAA unexpectedly switches to metric
            return temp_str

        wind_spd = extract_value(r"Wind Speed \(WSPD\):\s*([^\n\r]+)")
        wind_gst = extract_value(r"Wind Gust \(GST\):\s*([^\n\r]+)")
        wave_ht = extract_value(r"Significant Wave Height \(WVHT\):\s*([^\n\r]+)")
        dom_pd = extract_value(r"Dominant Wave Period \(DPD\):\s*([^\n\r]+)")
        
        # Apply C conversion
        air_temp = to_celsius(extract_value(r"Air Temperature \(ATMP\):\s*([^\n\r]+)"))
        water_temp = to_celsius(extract_value(r"Water Temperature \(WTMP\):\s*([^\n\r]+)"))
        
        # Clean up missing wave period data
        if dom_pd == "N/A" or "-" in dom_pd:
            # Fallback to Average Period if Dominant is missing
            avg_pd = extract_value(r"Average Wave Period \(APD\):\s*([^\n\r]+)")
            if avg_pd != "N/A" and "-" not in avg_pd:
                 wave_str = f"{wave_ht} @ {avg_pd} (Avg)"
            else:
                 wave_str = f"{wave_ht}" # Hide the period entirely if both are missing
        else:
            wave_str = f"{wave_ht} @ {dom_pd}"
        
        return (f"Station {STATION}   |   Wind: {wind_spd} (Gust: {wind_gst})   |   "
                f"Waves: {wave_str}   |   Air: {air_temp}   |   Water: {water_temp}")
                
    except Exception as e:
        print(f"Scraping failed: {e}")
        return f"Station {STATION} | Weather data temporarily unavailable"

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
        font = ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf", 32)
    except IOError:
        font = ImageFont.load_default()
        
    weather_str = fetch_weather_from_page()
    
    # Calculate text centering using modern Pillow metrics
    bbox = draw.textbbox((0, 0), weather_str, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    
    text_x = (1920 - text_w) // 2
    
    if y_offset > 0:
        text_y = (y_offset - text_h) // 2
    else:
        text_y = 20 
        
    draw.text((text_x, text_y), weather_str, fill="white", font=font)
    
    final_img.save(OUTPUT_FILE)
    print(f"Wallpaper generated successfully. Final resolution: {final_img.size}")

if __name__ == "__main__":
    main()
