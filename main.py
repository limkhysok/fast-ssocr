import cv2
import numpy as np
import easyocr
from fastapi import FastAPI, UploadFile, File, HTTPException
import uvicorn
from typing import Annotated

app = FastAPI(title="A12E Precision Scraper")

# Initialize OCR (Optimized for numbers)
reader = easyocr.Reader(["en"], gpu=False)


def process_a12e_display(image_bytes):
    # Convert upload to OpenCV format
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        return None

    # 1. Focus on the Red Glow (HSV space is best for this)
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

    # Range for red (handles both ends of the hue spectrum)
    lower_red1 = np.array([0, 50, 50])
    upper_red1 = np.array([10, 255, 255])
    lower_red2 = np.array([160, 50, 50])
    upper_red2 = np.array([180, 255, 255])

    mask1 = cv2.inRange(hsv, lower_red1, upper_red1)
    mask2 = cv2.inRange(hsv, lower_red2, upper_red2)
    mask = cv2.bitwise_or(mask1, mask2)

    # 2. Thicken the segments (Dilation)
    # This closes gaps in the 7-segment display so '8' doesn't look like two '0's
    kernel = np.ones((3, 3), np.uint8)
    dilated = cv2.dilate(mask, kernel, iterations=1)

    return dilated


def format_weight(text):
    # Remove everything except digits
    digits = "".join(filter(str.isdigit, text))

    if not digits:
        return "0.0"

    # Force 1 decimal place logic (A12E standard)
    # Example: '1795' becomes '179.5', '940' becomes '94.0'
    val = float(digits) / 10
    return f"{val:.1f}"


@app.post("/extract-weight/", responses={400: {"description": "Invalid Image"}})
async def extract_weight(file: Annotated[UploadFile, File()]):
    contents = await file.read()
    processed_img = process_a12e_display(contents)

    if processed_img is None:
        raise HTTPException(status_code=400, detail="Invalid Image")

    # Run OCR
    results = reader.readtext(processed_img, detail=0)
    raw_text = "".join(results)

    # Apply our precision logic
    final_value = format_weight(raw_text)

    return {"raw_ocr": raw_text, "formatted_weight": final_value, "unit": "kg"}


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
