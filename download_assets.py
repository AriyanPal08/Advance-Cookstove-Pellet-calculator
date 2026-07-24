import os
import sys
import re
import time
import urllib.request
import json
import urllib.parse

def slugify(name):
    return re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')

def download_image(url, save_path):
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
        with urllib.request.urlopen(req, timeout=30) as response:
            with open(save_path, 'wb') as f:
                f.write(response.read())
        print(f"  -> Saved {save_path}")
        return True
    except Exception as e:
        print(f"  -> Failed to download: {e}")
        return False

def process_item(name, prompt, folder, software_dir):
    slug = slugify(name)
    save_path = os.path.join(software_dir, 'static', 'img', folder, f"{slug}.jpg")
    if os.path.exists(save_path):
        return
        
    print(f"Generating image for: {name}")
    encoded_prompt = urllib.parse.quote(prompt)
    img_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=600&height=600&nologo=true"
    
    download_image(img_url, save_path)
    time.sleep(1) # Be nice to the API

def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    software_dir = os.path.join(base_dir, 'software')
    
    # Create directories
    os.makedirs(os.path.join(software_dir, 'static', 'img', 'dishes'), exist_ok=True)
    os.makedirs(os.path.join(software_dir, 'static', 'img', 'pellets'), exist_ok=True)
    os.makedirs(os.path.join(software_dir, 'static', 'img', 'utensils'), exist_ok=True)
    
    # Fetch data from local API
    try:
        req = urllib.request.Request("http://127.0.0.1:5000/api/init")
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode())
    except Exception as e:
        print(f"Failed to fetch data from API: {e}. Make sure the Flask server is running.")
        return

    print("\n--- Generating Dishes ---")
    for dish in data.get('dishes', []):
        prompt = f"A professional top-down food photography shot of Indian dish {dish['name']} in a nice bowl, dark background, cinematic lighting"
        process_item(dish['name'], prompt, 'dishes', software_dir)

    print("\n--- Generating Pellets ---")
    for pellet in data.get('pellets', []):
        prompt = f"Macro photography of {pellet['name']} biomass wood pellets. Small cylindrical compressed bio-fuel pellets in a pile. Professional studio lighting, isolated."
        process_item(pellet['name'], prompt, 'pellets', software_dir)

    print("\n--- Generating Utensils ---")
    for utensil in data.get('utensils', []):
        name = utensil['name']
        prompt = f"Professional product photography of a cooking vessel: {name}. Clean, isolated on a studio background, metallic reflections."
        process_item(name, prompt, 'utensils', software_dir)
            
    print("\nAll done!")

if __name__ == '__main__':
    main()
