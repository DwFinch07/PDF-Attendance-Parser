import pytesseract
from pdf2image import convert_from_path

# Path to tesseract
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

pages = convert_from_path("ITEMS/Attendence.pdf")

with open("Output.txt", "w", encoding="utf-8") as text_file:
    for i, page in enumerate(pages):
        page_text = pytesseract.image_to_string(page)
        text_file.write(f"\n\n--- PAGE {i+1} ---\n\n")
        text_file.write(page_text)