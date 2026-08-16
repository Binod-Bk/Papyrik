"""Generate the Papyrik test corpus into tests/fixtures/.

CLAUDE.md requires six fixtures that mirror where real PDF tools break:
a scanned (image-only) doc, a 300-page file, a fillable form, an encrypted
file, a CJK-text file, and a deliberately corrupt file.

These are synthesized so the test suite is reproducible on any machine. Run:

    python tests/make_fixtures.py
"""

from __future__ import annotations

import io
from pathlib import Path

import pymupdf  # PyMuPDF (the `fitz` alias is deprecated)
from PIL import Image, ImageDraw

FIXTURES = Path(__file__).parent / "fixtures"

# Password used by the encrypted fixture. Tests import this name.
ENCRYPTED_PASSWORD = "secret"


def make_scanned(path: Path) -> None:
    """An image-only page - pixels of text, no extractable text layer."""
    img = Image.new("RGB", (1000, 1400), "white")
    draw = ImageDraw.Draw(img)
    draw.text((80, 80), "SCANNED INVOICE  #4471", fill="black")
    draw.rectangle((60, 60, 940, 1340), outline="black", width=3)
    for i in range(6):
        y = 200 + i * 60
        draw.line((80, y, 920, y), fill=(120, 120, 120), width=2)

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=70)

    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)  # A4 points
    page.insert_image(page.rect, stream=buf.getvalue())
    doc.save(path)
    doc.close()


def make_large(path: Path, pages: int = 300) -> None:
    """A 300-page file - stresses anything that holds pages in memory."""
    doc = pymupdf.open()
    for i in range(pages):
        page = doc.new_page(width=595, height=842)
        page.insert_text((72, 72), f"Page {i + 1} of {pages}", fontsize=24)
    doc.save(path)
    doc.close()


def make_form(path: Path) -> None:
    """A fillable AcroForm with a text field and a checkbox."""
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((72, 90), "Application Form", fontsize=18)
    page.insert_text((72, 140), "Full name:", fontsize=11)

    name = pymupdf.Widget()
    name.field_name = "full_name"
    name.field_type = pymupdf.PDF_WIDGET_TYPE_TEXT
    name.rect = pymupdf.Rect(160, 128, 420, 150)
    name.field_value = ""
    page.add_widget(name)

    page.insert_text((72, 190), "Subscribe:", fontsize=11)
    check = pymupdf.Widget()
    check.field_name = "subscribe"
    check.field_type = pymupdf.PDF_WIDGET_TYPE_CHECKBOX
    check.rect = pymupdf.Rect(160, 178, 178, 196)
    check.field_value = False
    page.add_widget(check)

    doc.save(path)
    doc.close()


def make_encrypted(path: Path) -> None:
    """A password-protected file (AES-256, user password)."""
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((72, 72), "Confidential.", fontsize=14)
    doc.save(
        path,
        encryption=pymupdf.PDF_ENCRYPT_AES_256,
        owner_pw=ENCRYPTED_PASSWORD,
        user_pw=ENCRYPTED_PASSWORD,
    )
    doc.close()


def make_cjk(path: Path) -> None:
    """A file whose text layer is CJK - trips up naive font handling."""
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    # PyMuPDF ships built-in CJK fonts: china-s, china-t, japan, korea.
    page.insert_text((72, 100), "中文测试文档",
                     fontname="china-s", fontsize=24)
    page.insert_text((72, 160), "日本語のテスト",
                     fontname="japan", fontsize=24)
    page.insert_text((72, 220), "한국어 테스트",
                     fontname="korea", fontsize=24)
    doc.save(path)
    doc.close()


def make_corrupt(path: Path) -> None:
    """A file with a PDF header but garbage body - must fail to open."""
    path.write_bytes(b"%PDF-1.7\n" + b"\x00\xff\x13 not a real pdf body " * 40)


def main() -> None:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    make_scanned(FIXTURES / "scanned.pdf")
    make_large(FIXTURES / "large_300p.pdf")
    make_form(FIXTURES / "form.pdf")
    make_encrypted(FIXTURES / "encrypted.pdf")
    make_cjk(FIXTURES / "cjk.pdf")
    make_corrupt(FIXTURES / "corrupt.pdf")
    for f in sorted(FIXTURES.glob("*.pdf")):
        print(f"{f.name:20} {f.stat().st_size:>10,} bytes")


if __name__ == "__main__":
    main()
