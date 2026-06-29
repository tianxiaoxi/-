"""Clean extracted text: remove OCR garbage, merge paragraphs, identify chapters."""
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

BOOK_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT = os.path.join(BOOK_DIR, "extracted_text.txt")
OUTPUT_CLEAN = os.path.join(BOOK_DIR, "cleaned_text.txt")
OUTPUT_CHAPTERS = os.path.join(BOOK_DIR, "chapters_index.txt")

with open(INPUT, 'r', encoding='utf-8') as f:
    lines = f.readlines()

print(f"Read {len(lines)} lines")

# --- PASS 1: Mark garbage lines ---
# Lines that are clearly OCR garbage (mostly symbols, single chars, etc.)
def is_garbage(line):
    s = line.strip()
    if not s:
        return True
    # Single characters or very short gibberish
    if len(s) <= 2 and not s.isalpha():
        return True
    # Lines with very high non-alphanumeric ratio
    alnum = sum(1 for c in s if c.isalnum() or c in ' .,;:!?()[]{}"\'""''/\\-&')
    if len(s) > 5 and alnum / len(s) < 0.25:
        return True
    # Lines that are purely symbols
    if re.match(r'^[\s\-_=~|\\/:;.,\'"`´`°><^#@$%&*()+\[\]{}]+$', s):
        return True
    # Lines starting with common OCR fragment patterns
    if re.match(r'^[a-z]{1,3}$', s, re.IGNORECASE) and len(s) <= 3:
        return True
    return False

# --- PASS 2: Merge hyphenated words and short fragments ---
clean_lines = []
for line in lines:
    stripped = line.strip()
    if is_garbage(stripped):
        continue
    # Merge lines that end with hyphen (word was split across lines)
    if clean_lines and clean_lines[-1].endswith('-'):
        clean_lines[-1] = clean_lines[-1][:-1] + stripped
    else:
        clean_lines.append(stripped)

# --- PASS 3: Identify chapter boundaries ---
chapter_markers = [
    (r'^Introduction and Overview', 'Chapter 1: Introduction and Overview'),
    (r'^The Components of Interdependence', 'Chapter 2: The Components of Interdependence'),
    (r'^Antecedents of the Given Matrix', 'Chapter 3: Antecedents of the Given Matrix'),
    (r'^The Domain of 2.*Matrices', 'Chapter 4: The Domain of 2×2 Matrices'),
    (r'^Properties and Indices of Interdependence Patterns', 'Chapter 5: Properties and Indices of Interdependence Patterns'),
    (r'^Logical Analysis of the Transformation Process', 'Chapter 6: Logical Analysis of the Transformation Processes'),
    (r'^Origin and Evocation of Transformations', 'Chapter 7: Origin and Evocation of Transformations'),
    (r'^Processes of Attribution and Self-Presentation', 'Chapter 8: Processes of Attribution and Self-Presentation'),
    (r'^Interdependence in Triads', 'Chapter 9: Interdependence in Triads'),
    (r'^Negotiation and Coalition Formation', 'Chapter 10: Negotiation and Coalition Formation'),
    (r'^Epilogue', 'Chapter 11: Epilogue'),
    (r'^Bibliography', 'Bibliography'),
    (r'^Author Index', 'Author Index'),
    (r'^Subject Index', 'Subject Index'),
]

chapter_lines = {}  # chapter_name -> list of lines
current_chapter = "Front Matter"
chapter_lines[current_chapter] = []

for line in clean_lines:
    matched = False
    for pattern, name in chapter_markers:
        if re.match(pattern, line):
            current_chapter = name
            chapter_lines[current_chapter] = []
            matched = True
            break
    if not matched:
        chapter_lines[current_chapter].append(line)

# --- PASS 4: Merge into paragraphs ---
def merge_paragraphs(text_lines):
    """Merge short lines into paragraphs."""
    paragraphs = []
    current_para = []
    for line in text_lines:
        s = line.strip()
        if not s:
            if current_para:
                paragraphs.append(' '.join(current_para))
                current_para = []
            continue
        # If line is short and doesn't end with sentence-ending punctuation,
        # it's likely a continuation
        if current_para and not current_para[-1].endswith(('.', '!', '?', ':', ';')):
            current_para[-1] = current_para[-1] + ' ' + s
        else:
            current_para.append(s)
    if current_para:
        paragraphs.append(' '.join(current_para))
    return paragraphs

# Write cleaned output
with open(OUTPUT_CLEAN, 'w', encoding='utf-8') as f:
    f.write('\n\n'.join(clean_lines))

# Write chapter-organized output
with open(OUTPUT_CHAPTERS, 'w', encoding='utf-8') as f:
    for ch_name, ch_lines in chapter_lines.items():
        if not ch_lines:
            continue
        f.write(f"\n{'='*60}\n")
        f.write(f"## {ch_name}\n")
        f.write(f"{'='*60}\n\n")
        paras = merge_paragraphs(ch_lines)
        for para in paras:
            f.write(para + '\n\n')

print(f"Cleaned: {len(clean_lines)} lines -> {OUTPUT_CLEAN}")
print(f"Chapters written -> {OUTPUT_CHAPTERS}")
print(f"Chapters found: {list(chapter_lines.keys())}")
