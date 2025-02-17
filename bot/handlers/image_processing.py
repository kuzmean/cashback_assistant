from PIL import Image
import pytesseract
import io
import re
from telegram import Update
from telegram.ext import ContextTypes

async def handle_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Download photo
    photo_file = await update.message.photo[-1].get_file()
    photo_bytes = await photo_file.download_as_bytearray()
    
    # Process image
    image = Image.open(io.BytesIO(photo_bytes))
    text = pytesseract.image_to_string(image)
    
    # Try to parse cashback data
    parsed_data = parse_ocr_text(text)
    
    if parsed_data:
        # Save to database
        await save_cashback_data(update.effective_user.id, parsed_data)
        await update.message.reply_text("✅ Cashback data saved successfully!")
    else:
        await update.message.reply_text(
            "⚠️ Couldn't parse cashback data. Please enter manually:\n\n"
            "Bank: [Bank Name]\n"
            "Category: [Category]\n"
            "Cashback: [X]%"
        )

def parse_ocr_text(text: str) -> dict:
    # Example patterns to look for
    patterns = {
        'bank': r'(bank|card)\s*:\s*(\w+)',
        'category': r'(category|type)\s*:\s*(\w+)',
        'cashback': r'cashback\s*:\s*(\d+\.?\d*)%'
    }
    
    parsed = {}
    for key, pattern in patterns.items():
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            parsed[key] = match.group(2 if key == 'bank' else 1)
    return parsed if len(parsed) == 3 else None 