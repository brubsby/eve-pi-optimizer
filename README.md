# EVE Online PI Toolkit

This toolkit automates the optimization of Planetary Interaction (PI) in EVE Online. It consists of two main tools:

- **Scanner (planet_scanner.py):** Uses Computer Vision (OpenCV) and OCR (Tesseract) to read planet resource data directly from game screenshots.
- **Optimizer (main.py):** Uses a Minimum Cost Maximum Flow algorithm to assign your characters to specific planets to maximize resource yield based on your specific production goals.

## Prerequisites

### System Requirements

- Python 3.10+
- Tesseract OCR Engine (Required for the scanner)
    - **Windows:** Download from [UB-Mannheim/tesseract](https://github.com/UB-Mannheim/tesseract/wiki) and ensure it's in your system PATH.
    - **Linux:** `sudo apt-get install tesseract-ocr`
    - **macOS:** `brew install tesseract`

### Python Dependencies

Install the required packages:

```bash
pip install opencv-python numpy pytesseract pyautogui networkx
```

## 1. The Scanner (planet_scanner.py)

This tool extracts data from screenshots of the Planetary Interaction UI. It identifies the planet name and the abundance (0-100) of every resource bar visible.

### Usage

**Option A: Scan a single file**

```bash
python planet_scanner.py path/to/screenshot.png
```

**Option B: Scan a directory of images**

This is useful for batch processing an entire solar system.

```bash
python planet_scanner.py path/to/screenshots_folder/
```

**Option C: Screen Capture**

If no arguments are provided, it attempts to take a screenshot of your primary monitor immediately.

```bash
python planet_scanner.py
```

### Calibration

The scanner assumes a full resource bar is 101 pixels wide. If your UI scaling is different (e.g., 4K monitor or UI scaling > 100%), you can adjust this:

```bash
python planet_scanner.py image.png --calibration 130
```

## 2. The Optimizer (main.py)

> **Note:** You may need to create this file based on the logic we discussed, or rename your existing optimization script to `main.py`.

This tool takes your character skills, planet data, and production targets, then calculates the mathematically perfect set of planets to visit.

### Configuration

Open `main.py` and configure the top section:

**Characters:** Define your alts and their limits.

```python
chars = [
    {'id': 'Toon1', 'max_visits': 5, 'banned': ['J105433 IV']}, # Can't handle lava planets?
    {'id': 'Toon2', 'max_visits': 5, 'banned': []}
]
```

**Targets:** Define what P1 materials you need for your factory.

```python
targets = {
    'Microorganisms': 2,
    'Base Metals': 1,
    # ...
}
```

**Planet Data:** Paste the JSON output from `planet_scanner.py` into the `planets` list variable.

### Usage

Run the script:

```bash
python main.py
```

It will output a step-by-step plan for each character:

```
Toon1:
  - Visit J105433 I -> Collect Microorganisms (Yield: 98)
  - Visit J105433 III -> Collect Base Metals (Yield: 85)
```

## Troubleshooting

- **Scanner reads "0" as "6":** This is an interpolation artifact. The current script uses Linear interpolation and Gaussian blurring to fix this. Ensure you are using the latest version of `planet_scanner.py`.
- **"Tesseract not found":** Ensure the Tesseract binary is installed on your OS, not just the Python wrapper.
- **"Display not found":** If running on a headless Linux server (WSL), you cannot use the screen capture mode. You must provide a file path or directory.