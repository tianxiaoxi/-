"""将 docx 转为真正防复制的 PDF（每页转为图片，文字不可选中）。

明水印：透明可见的 "天小析出品"（15% 透明度）
暗水印：嵌入元数据的 "作者：杨欣 时间 2026年6月24日"
防复制：每页渲染为高 DPI 图片，文字不可选中/复制
权限：禁止打印、禁止修改
"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from pathlib import Path
import fitz  # PyMuPDF
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import pikepdf

BASE = Path(__file__).parent
DOCX_FILE = BASE / "直播间的因果地图——六道因果络认知手册.docx"
PDF_TEMP = BASE / "_temp_raw.pdf"
PDF_IMAGES = BASE / "_temp_images.pdf"
WATERMARK_PDF = BASE / "_watermark.pdf"
PDF_OUTPUT = BASE / "直播间的因果地图——六道因果络认知手册.pdf"

# 水印参数
VISIBLE_WATERMARK_TEXT = "天小析出品"
DARK_WATERMARK_TEXT = "作者：杨欣 时间 2026年6月24日"
WATERMARK_OPACITY = 0.15  # 15% 透明度

FONT_SIZES = {
    "large": 48,
    "small": 20,
}


def find_chinese_font():
    candidates = [
        ("C:/Windows/Fonts/simkai.ttf", "SimKai"),
        ("C:/Windows/Fonts/simsun.ttc", "SimSun"),
        ("C:/Windows/Fonts/simhei.ttf", "SimHei"),
        ("C:/Windows/Fonts/msyh.ttc", "MicrosoftYaHei"),
        ("C:/Windows/Fonts/msyhbd.ttc", "MicrosoftYaHeiBold"),
    ]
    for p, name in candidates:
        if Path(p).exists():
            pdfmetrics.registerFont(TTFont(name, p))
            return name
    return None


def step1_docx_to_pdf():
    """Step 1: docx -> 原始 PDF"""
    if PDF_TEMP.exists():
        print(f"Step 1: skip (exists): {PDF_TEMP.name}")
        return True

    print("Step 1: docx -> PDF ...")
    try:
        from docx2pdf import convert
        convert(str(DOCX_FILE), str(PDF_TEMP))
        if PDF_TEMP.stat().st_size > 1000:
            print(f"  [OK] {PDF_TEMP.name} ({PDF_TEMP.stat().st_size / 1024:.0f} KB)")
            return True
    except Exception as e:
        print(f"  docx2pdf failed: {e}")

    print("  [ERROR] cannot generate raw PDF")
    return False


def step2_rasterize_to_images():
    """Step 2: render every page as image, text becomes non-selectable"""
    if PDF_IMAGES.exists():
        print(f"Step 2: skip (exists): {PDF_IMAGES.name}")
        return

    print("Step 2: rendering each page as image ...")

    src = fitz.open(str(PDF_TEMP))
    num = len(src)
    print(f"  {num} pages, DPI=200")

    img_doc = fitz.open()

    for i in range(num):
        page = src[i]
        pix = page.get_pixmap(dpi=200)
        img_bytes = pix.tobytes("png")

        new_page = img_doc.new_page(width=595, height=842)
        rect = fitz.Rect(0, 0, 595, 842)
        new_page.insert_image(rect, stream=img_bytes, keep_proportion=True)

    img_doc.save(str(PDF_IMAGES))
    img_doc.close()
    src.close()

    kb = PDF_IMAGES.stat().st_size / 1024
    print(f"  [OK] {PDF_IMAGES.name} ({kb:.0f} KB)")


def step3_create_watermark(font_name: str):
    """Step 3: generate transparent watermark PDF (single page)"""
    print("Step 3: creating watermark PDF ...")

    c = canvas.Canvas(str(WATERMARK_PDF), pagesize=A4)
    pw, ph = A4

    # 大号对角线水印（页面中央）
    c.saveState()
    c.setFont(font_name, FONT_SIZES["large"])
    c.setFillAlpha(WATERMARK_OPACITY)
    c.setFillColorRGB(0.4, 0.4, 0.4)
    c.translate(pw / 2, ph / 2)
    c.rotate(30)
    c.drawCentredString(0, 0, VISIBLE_WATERMARK_TEXT)
    c.restoreState()

    # 小号页脚水印
    c.saveState()
    c.setFont(font_name, FONT_SIZES["small"])
    c.setFillAlpha(WATERMARK_OPACITY)
    c.setFillColorRGB(0.4, 0.4, 0.4)
    c.drawCentredString(pw / 2, 3 * cm, VISIBLE_WATERMARK_TEXT)
    c.restoreState()

    c.showPage()
    c.save()
    print(f"  [OK] {WATERMARK_PDF.name}")


def step4_watermark_and_encrypt():
    """Step 4: overlay watermark + dark watermark + encrypt"""
    print("Step 4: overlay watermark + encrypt ...")

    main = pikepdf.Pdf.open(str(PDF_IMAGES))
    wm = pikepdf.Pdf.open(str(WATERMARK_PDF))
    wm_page = wm.pages[0]
    num = len(main.pages)
    print(f"  {num} pages, applying watermark...")

    for i in range(num):
        main.pages[i].add_overlay(wm_page)

    # 暗水印：写入 PDF 元数据
    with main.open_metadata() as meta:
        meta["dc:creator"] = ["杨欣"]
        meta["dc:description"] = DARK_WATERMARK_TEXT
        meta["dc:date"] = "2026-06-24"
        meta["xmp:CreatorTool"] = f"{VISIBLE_WATERMARK_TEXT} - {DARK_WATERMARK_TEXT}"

    # 加密：禁止打印、禁止复制、禁止修改
    main.save(
        str(PDF_OUTPUT),
        encryption=pikepdf.Encryption(
            owner="GrowthPlan_2026_Secure_XinYang_Liudimensions",
            user="",
            allow=pikepdf.Permissions(),
        ),
    )

    main.close()
    wm.close()

    kb = PDF_OUTPUT.stat().st_size / 1024
    print(f"  [OK] {PDF_OUTPUT.name} ({kb:.0f} KB)")


def cleanup():
    for f in [PDF_TEMP, PDF_IMAGES, WATERMARK_PDF]:
        if f.exists():
            f.unlink()
            print(f"  [OK] cleaned: {f.name}")


def main():
    font = find_chinese_font()
    if not font:
        print("[ERROR] no Chinese font found")
        return

    print(f"Font: {font}")
    print(f"Visible watermark: \"{VISIBLE_WATERMARK_TEXT}\" (opacity {WATERMARK_OPACITY*100:.0f}%)")
    print(f"Dark watermark: \"{DARK_WATERMARK_TEXT}\"")
    print()

    if not step1_docx_to_pdf():
        return

    step2_rasterize_to_images()
    step3_create_watermark(font)
    step4_watermark_and_encrypt()
    cleanup()

    print(f"\n{'='*60}")
    print(f"[DONE]")
    print(f"  Output: {PDF_OUTPUT.name}")
    print(f"  Visible watermark: \"{VISIBLE_WATERMARK_TEXT}\"")
    print(f"  Dark watermark: \"{DARK_WATERMARK_TEXT}\"")
    print(f"  Anti-copy: pages are images, text cannot be selected/copied")
    print(f"  Permissions: no print, no edit")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
