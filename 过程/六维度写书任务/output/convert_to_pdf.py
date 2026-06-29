"""将 docx 转为 PDF.

使用 Microsoft Word 渲染 docx → PDF（中文排版保真度最高）。
"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from pathlib import Path

BASE = Path(__file__).parent
DOCX_FILE = BASE / "直播间的因果地图——六道因果络认知手册.docx"
PDF_OUTPUT = BASE / "直播间的因果地图——六道因果络认知手册.pdf"


def main():
    if not DOCX_FILE.exists():
        print(f"[ERROR] 找不到文件: {DOCX_FILE}")
        return

    print(f"源文件: {DOCX_FILE.name}")
    print(f"文件大小: {DOCX_FILE.stat().st_size / 1024:.0f} KB")

    print("\n正在转换 docx → PDF（通过 Microsoft Word）...")
    try:
        from docx2pdf import convert
        convert(str(DOCX_FILE), str(PDF_OUTPUT))
    except Exception as e:
        print(f"[ERROR] docx2pdf 转换失败: {e}")
        return

    if PDF_OUTPUT.exists():
        kb = PDF_OUTPUT.stat().st_size / 1024
        print(f"[OK] 输出: {PDF_OUTPUT.name} ({kb:.0f} KB)")
    else:
        print("[ERROR] PDF 未生成")


if __name__ == "__main__":
    main()
