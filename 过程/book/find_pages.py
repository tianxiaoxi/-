"""Simple: extract text by printed page ranges using PDF page offset."""
import os, sys, re
import fitz

sys.stdout.reconfigure(encoding='utf-8')

BOOK_DIR = os.path.dirname(os.path.abspath(__file__))
PDF_PATH = os.path.join(BOOK_DIR, "source.pdf")
OUT_EN = os.path.join(BOOK_DIR, "book_en.txt")

# Printed pages in the book (as listed in TOC):
# We need to map printed pages to PDF pages (0-indexed)
# From earlier reading:
#   PDF page 0 = "1 of 358"  (back cover blurb)
#   PDF page 4 = "5 of 358"  (title "Interpersonal Relations")
#   PDF page 6 = "7 of 358"  (title page with authors)
#   PDF page 7 = "8 of 358"  (copyright)
#   PDF page 8 = "9 of 358"  (Preface)
#   PDF page 9 = "10 of 358" (Contents)
#   PDF page 10= "11 of 358" (blank/decorative)
# The printed "page 1" would be PDF page 11 or 12.
# Let's check by reading PDF page 11 (0-indexed)

doc = fitz.open(PDF_PATH)

# Check pages around where printed page 1 should be
for pidx in range(10, 16):
    text = doc[pidx].get_text("text")
    # Show first 200 chars
    preview = text[:200].replace('\n', ' | ')
    print(f"PDF page {pidx}: {preview}")

doc.close()
