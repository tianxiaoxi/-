"""Extract text from source.pdf and write clean text."""
import os
import sys
import re
import fitz

sys.stdout.reconfigure(encoding='utf-8')

BOOK_DIR = os.path.dirname(os.path.abspath(__file__))
PDF_PATH = os.path.join(BOOK_DIR, "source.pdf")
OUT_PATH = os.path.join(BOOK_DIR, "extracted_text.txt")

doc = fitz.open(PDF_PATH)
total_pages = len(doc)
print(f"Total pages: {total_pages}")

def clean_line(line):
    line = re.sub(r'--\s*\d+\s+of\s+\d+\s*--', '', line)
    stripped = line.strip()
    if not stripped:
        return ''
    # Remove lines that are mostly non-text (OCR garbage)
    text_chars = sum(1 for c in stripped if c.isalpha() or c in '.!,;:?()[]{}"\'""''/\\-')
    ratio = text_chars / max(len(stripped), 1)
    if ratio < 0.3 and len(stripped) > 3:
        return ''
    if re.match(r'^\d{1,4}$', stripped):
        return ''
    return stripped

all_lines = []
for page_num in range(total_pages):
    page = doc[page_num]
    text = page.get_text("text")
    # Merge hyphenated words split across lines
    for line in text.split('\n'):
        cleaned = clean_line(line)
        if cleaned:
            all_lines.append(cleaned)
    if (page_num + 1) % 50 == 0:
        print(f"  Page {page_num + 1}/{total_pages}")

doc.close()

with open(OUT_PATH, 'w', encoding='utf-8') as f:
    f.write('\n'.join(all_lines))

print(f"Done! {len(all_lines)} lines -> extracted_text.txt")
