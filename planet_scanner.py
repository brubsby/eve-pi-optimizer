import cv2
import numpy as np
import pytesseract
import json
import argparse
import sys
import os
import shutil
import difflib
import re

# --- CONFIGURATION ---
# Recalibrated based on verified data (User measure: 101px)
DEFAULT_BAR_WIDTH_PX = 101

# STRICT ALLOWLIST
# The script will now IGNORE any text that doesn't vaguely resemble these names.
KNOWN_RESOURCES = [
    "Aqueous Liquids", "Autotrophs", "Base Metals", "Carbon Compounds", 
    "Complex Organisms", "Felsic Magma", "Heavy Metals", "Industrial Fibers", 
    "Ionic Solutions", "Microorganisms", "Noble Gas", "Noble Metals", 
    "Non-CS Crystals", "Planktic Colonies", "Reactive Gas", "Suspended Plasma"
]

def take_screenshot():
    try:
        import pyautogui
        try:
            screenshot = pyautogui.screenshot()
            return cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
        except Exception as e:
            print(f"Error: Could not access display for screenshot. ({e})")
            return None
    except ImportError:
        print("Error: 'pyautogui' not installed.")
        return None
    except KeyError:
        print("Error: DISPLAY environment variable not found.")
        return None

def preprocess_for_ocr(image_roi, invert=True):
    """
    Upscales and cleans the image for Tesseract.
    """
    h, w = image_roi.shape
    
    # CHANGED: Use Linear interpolation + Gaussian Blur to de-pixelate.
    # Linear is smoother than Nearest (blocky) but sharper than Cubic (blurry).
    scaled = cv2.resize(image_roi, (w * 3, h * 3), interpolation=cv2.INTER_LINEAR)
    
    # Denoise: Slight Gaussian Blur to smooth pixel "steps" into continuous strokes.
    # This prevents Tesseract from misreading jagged pixel edges as extra characters (e.g. 3 -> 9).
    blurred = cv2.GaussianBlur(scaled, (3, 3), 0)
    
    # Invert (Black text on white background is best for Tesseract)
    if invert:
        blurred = cv2.bitwise_not(blurred)
    
    # Otsu's Binarization (Auto-find best threshold)
    _, binary = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
    
    return binary

def clean_resource_name(raw_text):
    """
    Strict Fuzzy Matching. Returns None if no valid EVE resource is found.
    """
    clean = raw_text.strip()
    if len(clean) < 3: return None
        
    # Remove common OCR garbage
    clean = clean.replace(":", "").replace(".", "").replace("|", "I").replace("!", "")
    
    # Fuzzy Match
    matches = difflib.get_close_matches(clean, KNOWN_RESOURCES, n=1, cutoff=0.45)
    
    if matches:
        return matches[0]
    
    return None # REJECT garbage

def process_image(img, full_bar_width, filename=None):
    if img is None: return None

    if shutil.which('tesseract') is None:
        print("CRITICAL ERROR: 'tesseract' is not installed.")
        sys.exit(1)

    h, w = img.shape[:2]
    # Crop to relevant UI area
    roi = img[0:min(600, h), 0:min(500, w)]
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    
    # --- Planet Name Extraction ---
    # The header text is usually very bright white. 
    # Adjusted Crop based on user feedback (skipping Search bar)
    # Y: 125:155 
    # X: 90:300
    header_roi = gray[125:155, 90:min(300, w)] 
    
    # Pre-threshold to isolate white text
    # Using 150 to catch pixels before they fade
    _, header_pre_thresh = cv2.threshold(header_roi, 150, 255, cv2.THRESH_BINARY)
    
    # --- Upscale & Clean ---
    # Pass the binary thresholded image to be smoothed by Linear/Blur upscaling
    processed_header = preprocess_for_ocr(header_pre_thresh, invert=True)
    
    # ADDED: Padding/Border
    # Tesseract struggles with text touching the edge. Adding a 20px white border helps it see spaces.
    processed_header = cv2.copyMakeBorder(processed_header, 20, 20, 20, 20, cv2.BORDER_CONSTANT, value=255)

    # --- DEBUG SAVE ---
    # Saves 'debug_planet_header.png' to check if '0' looks clear
    cv2.imwrite("debug_planet_header.png", processed_header)
    
    planet_name = "Unknown"
    try:
        # psm 7 = Treat as single text line
        # whitelist = Uppercase + Digits + Space
        planet_name_raw = pytesseract.image_to_string(
            processed_header, 
            config='--psm 7 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 '
        ).strip()
        
        planet_name = planet_name_raw.split('\n')[0]
        planet_name = planet_name.replace("Build", "").replace("Scan", "").strip()
        planet_name = re.sub(r'^[^a-zA-Z0-9]+', '', planet_name)
        if "|" in planet_name: planet_name = planet_name.replace("|", "I")
        
        # --- FILENAME FALLBACK ---
        # If a filename was provided, check if it looks similar to the OCR result.
        # If it does, trust the filename (it is likely cleaner than the OCR).
        if filename:
            # Extract just the name "J105433 I" from "screenshots/J105433 I.png"
            file_base = os.path.splitext(os.path.basename(filename))[0]
            
            # Check similarity ratio (0.0 to 1.0)
            # If the OCR got "J165433" and filename is "J105433 I", this ratio will be high (~0.7-0.8)
            ratio = difflib.SequenceMatcher(None, planet_name, file_base).ratio()
            
            # Threshold: 0.5 allows for significant OCR errors while preventing
            # total mismatches (like using the wrong file for a planet).
            if ratio > 0.5:
                planet_name = file_base

    except pytesseract.TesseractNotFoundError:
        print("Error: Tesseract not found."); sys.exit(1)

    # --- Resource Bar Detection ---
    # Threshold for the bars (light grey)
    _, bar_mask = cv2.threshold(gray, 100, 255, cv2.THRESH_BINARY)
    contours, _ = cv2.findContours(bar_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    resources = {}
    bounding_boxes = [cv2.boundingRect(c) for c in contours]
    bounding_boxes.sort(key=lambda x: x[1]) # Sort by Y
    
    processed_y_coords = []

    for x, y, bw, bh in bounding_boxes:
        # Stricter Geometric Filters
        if bh < 4 or bh > 25: continue # Bars are thin
        if bw < 15: continue # Must have some length
        
        # CHANGED: Lowered from 3 to 2.5 to catch shorter bars (e.g. 23%)
        if (bw / float(bh)) < 2.5: continue 
        
        # De-duplicate
        is_duplicate = False
        for py in processed_y_coords:
            if abs(py - y) < 10:
                is_duplicate = True; break
        if is_duplicate: continue
        processed_y_coords.append(y)
        
        # --- Extract Resource Name ---
        text_roi_x_end = x - 5
        text_roi_x_start = max(0, x - 250)
        text_roi_y_start = max(0, y - 5)
        text_roi_y_end = min(gray.shape[0], y + bh + 5)
        
        text_roi = gray[text_roi_y_start:text_roi_y_end, text_roi_x_start:text_roi_x_end]
        
        # Process text area
        processed_text_roi = preprocess_for_ocr(text_roi, invert=True)
        raw_name = pytesseract.image_to_string(processed_text_roi, config='--psm 7').strip()
        
        # STRICT MATCHING
        final_name = clean_resource_name(raw_name)
        
        if not final_name:
            continue
            
        # --- Calculate Abundance ---
        # Using round() to handle edges cases like 35.9 -> 36
        abundance = int(round((bw / full_bar_width) * 100))
        if abundance > 100: abundance = 100
        
        resources[final_name] = abundance

    return {
        "id": planet_name,
        "resources": resources
    }

def main():
    parser = argparse.ArgumentParser(description="Extract EVE Online Planet Interaction data.")
    parser.add_argument('path', nargs='?', help="Path to screenshot file or directory.")
    parser.add_argument('--calibration', type=int, default=DEFAULT_BAR_WIDTH_PX, help="Pixel width of 100% bar.")
    args = parser.parse_args()

    # 1. Screenshot Mode (No path provided)
    if not args.path:
        print("No path provided. Attempting to capture screen...", file=sys.stderr)
        img = take_screenshot()
        if img is None: sys.exit(1)
        
        result = process_image(img, args.calibration, None)
        if result:
            print(json.dumps(result, indent=4))
        else:
            print("Error: Processing failed.")
        return

    # 2. Directory Mode
    if os.path.isdir(args.path):
        results = []
        valid_exts = ('.png', '.jpg', '.jpeg', '.bmp', '.tif', '.tiff')
        
        # Sort files to ensure deterministic output order
        files = sorted([f for f in os.listdir(args.path) if f.lower().endswith(valid_exts)])
        
        if not files:
            print(f"No image files found in directory '{args.path}'", file=sys.stderr)
            return

        for f in files:
            file_path = os.path.join(args.path, f)
            img = cv2.imread(file_path)
            
            if img is not None:
                # Pass file_path for filename fallback
                res = process_image(img, args.calibration, file_path)
                if res:
                    results.append(res)
            else:
                print(f"Warning: Could not read image '{f}'", file=sys.stderr)
        
        # Output single JSON list of all planets
        print(json.dumps(results, indent=4))
        return

    # 3. Single File Mode
    if os.path.isfile(args.path):
        if not os.path.exists(args.path):
            print(f"Error: File '{args.path}' not found."); sys.exit(1)
            
        img = cv2.imread(args.path)
        if img is None:
            print(f"Error: Failed to read image file '{args.path}'.")
            sys.exit(1)
            
        result = process_image(img, args.calibration, args.path)
        if result:
            print(json.dumps(result, indent=4))
        else:
            print("Error: Processing failed.")
        return

    # 4. Invalid Path
    print(f"Error: Path '{args.path}' not found.")
    sys.exit(1)

if __name__ == "__main__":
    main()
