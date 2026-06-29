"""Final: extract chapters by printed page numbers with correct offset."""
import os, sys, re
import fitz

sys.stdout.reconfigure(encoding='utf-8')

BOOK_DIR = os.path.dirname(os.path.abspath(__file__))
PDF_PATH = os.path.join(BOOK_DIR, "source.pdf")
OUT_DIR = os.path.join(BOOK_DIR, "en_chapters")
os.makedirs(OUT_DIR, exist_ok=True)

# Offset: printed_page = pdf_page_index - 13
OFFSET = 13

# Chapter definitions: name -> (printed_start_page, printed_end_page)
CHAPTERS = [
    ("Preface", None, None),  # We'll find preface manually
    ("Ch01_Introduction_and_Overview", 1, 28),
    ("Ch02_Components_of_Interdependence", 29, 52),
    ("Ch03_Antecedents_of_Given_Matrix", 53, 74),
    ("Ch04_Domain_of_2x2_Matrices", 75, 110),
    ("Ch05_Properties_and_Indices", 111, 136),
    ("Ch06_Logical_Analysis_of_Transformations", 137, 166),
    ("Ch07_Origin_and_Evocation_of_Transformations", 167, 206),
    ("Ch08_Attribution_and_Self_Presentation", 207, 240),
    ("Ch09_Interdependence_in_Triads", 241, 278),
    ("Ch10_Negotiation_and_Coalition_Formation", 279, 312),
    ("Ch11_Epilogue", 313, 328),
    ("Bibliography", 329, 334),
    ("Author_Index", 335, 338),
    ("Subject_Index", 339, 358),
]

def is_garbage(s):
    if not s: return True
    if len(s) <= 2 and not s.isalpha(): return True
    alnum = sum(1 for c in s if c.isalnum() or c in ' .,;:!?()[]{}"\'""''/\\-&')
    if len(s) > 5 and alnum / max(len(s), 1) < 0.25: return True
    if re.match(r'^[\s\-_=~|\\/:;.,\'"`´`°><^#@$%&*()+\[\]{}]+$', s): return True
    return False

def is_header(s):
    """Check if line is a running page header (chapter title or 'INTERPERSONAL RELATIONS')."""
    s = s.strip()
    headers = [
        'INTERPERSONAL RELATIONS',
        'INTRODUCTION AND OVERVIEW',
        'THE COMPONENTS OF INTERDEPENDENCE',
        'ANTECEDENTS OF THE GIVEN MATRIX',
        'THE DOMAIN OF 2',
        'PROPERTIES AND INDICES',
        'LOGICAL ANALYSIS OF THE TRANSFORMATION',
        'ORIGIN AND EVOCATION OF TRANSFORMATIONS',
        'PROCESSES OF ATTRIBUTION AND SELF',
        'INTERDEPENDENCE IN TRIADS',
        'NEGOTIATION AND COALITION',
        'EPILOGUE',
        'BIBLIOGRAPHY',
        'AUTHOR INDEX',
        'SUBJECT INDEX',
        'PREFACE',
    ]
    upper = s.upper()
    for h in headers:
        if upper == h or upper.startswith(h):
            return True
    # Page numbers alone
    if re.match(r'^\d{1,4}$', s):
        return True
    return False

doc = fitz.open(PDF_PATH)

for ch_id, start_page, end_page in CHAPTERS:
    if start_page is None:
        continue  # Skip preface for now
    if end_page is None:
        end_page = start_page

    pdf_start = start_page + OFFSET
    pdf_end = min(end_page + OFFSET, len(doc) - 1)

    lines = []
    for pidx in range(pdf_start, pdf_end + 1):
        text = doc[pidx].get_text("text")
        for line in text.split('\n'):
            stripped = line.strip()
            if stripped == ch_id:  # Skip the .txt filename marker
                continue
            if is_garbage(stripped):
                continue
            if is_header(stripped):
                continue
            # Fix hyphenated words
            if lines and lines[-1].endswith('-'):
                lines[-1] = lines[-1][:-1] + stripped
            else:
                lines.append(stripped)

    # Merge into paragraphs
    paragraphs = []
    current = []
    for line in lines:
        if not line.strip():
            if current:
                paragraphs.append(' '.join(current))
                current = []
            continue
        if current and not current[-1].endswith(('.', '!', '?', ':', ';', ')', '"', "'")):
            current[-1] = current[-1] + ' ' + line
        else:
            current.append(line)
    if current:
        paragraphs.append(' '.join(current))

    out_path = os.path.join(OUT_DIR, f"{ch_id}.txt")
    with open(out_path, 'w', encoding='utf-8') as f:
        for para in paragraphs:
            f.write(para + '\n\n')

    chars = sum(len(p) for p in paragraphs)
    print(f"{ch_id}: {len(paragraphs)} paragraphs, ~{chars} chars")

doc.close()
print(f"\nWritten to: {OUT_DIR}")
