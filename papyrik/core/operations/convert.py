"""Conversions: pdf->docx, pdf->images, images->pdf, pdf->text.

Pure functions - paths + params in, output path(s) out. Input files are never
modified. `pdf_to_docx` is best-effort on multi-column/table layouts (see
CLAUDE.md "Known-flaky") and is labelled as such in the UI.
"""

from __future__ import annotations

from pathlib import Path

import pymupdf


def _open_pdf(path: str | Path) -> pymupdf.Document:
    doc = pymupdf.open(str(path))
    if doc.needs_pass:
        doc.close()
        raise ValueError(
            f"'{Path(path).name}' is password-protected; decrypt it first."
        )
    return doc


def pdf_to_docx(input_pdf: str | Path, output: str | Path) -> Path:
    """Convert to Word (.docx). Best effort on complex layouts."""
    from pdf2docx import Converter  # imported lazily; it pulls in heavy deps

    # Fail fast on encrypted/corrupt input with our own clear message.
    _open_pdf(input_pdf).close()

    out = Path(output)
    out.parent.mkdir(parents=True, exist_ok=True)
    converter = Converter(str(input_pdf))
    try:
        converter.convert(str(out))
    finally:
        converter.close()
    return out


def pdf_to_images(input_pdf: str | Path, output_dir: str | Path,
                  fmt: str = "png", dpi: int = 150) -> list[Path]:
    """Render each page to an image file (png or jpg)."""
    fmt = fmt.lower().lstrip(".")
    if fmt not in {"png", "jpg", "jpeg"}:
        raise ValueError("fmt must be png or jpg.")
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = Path(input_pdf).stem
    outputs: list[Path] = []
    with _open_pdf(input_pdf) as doc:
        width = len(str(doc.page_count))
        for i in range(doc.page_count):
            pix = doc.load_page(i).get_pixmap(dpi=dpi)
            out = out_dir / f"{stem}_p{i + 1:0{width}d}.{fmt}"
            pix.save(str(out))
            outputs.append(out)
    return outputs


def images_to_pdf(images: list[str | Path], output: str | Path) -> Path:
    """Combine images into a single PDF, one image per page (in order)."""
    if not images:
        raise ValueError("images_to_pdf needs at least one image.")
    out = Path(output)
    out.parent.mkdir(parents=True, exist_ok=True)
    doc = pymupdf.open()
    try:
        for image in images:
            with pymupdf.open(str(image)) as img:
                pdf_bytes = img.convert_to_pdf()
            with pymupdf.open("pdf", pdf_bytes) as img_pdf:
                doc.insert_pdf(img_pdf)
        doc.save(str(out))
    finally:
        doc.close()
    return out


def pdf_to_text(input_pdf: str | Path, output: str | Path) -> Path:
    """Extract the text layer to a UTF-8 .txt file (form feed between pages)."""
    out = Path(output)
    out.parent.mkdir(parents=True, exist_ok=True)
    with _open_pdf(input_pdf) as doc:
        text = "\f".join(page.get_text() for page in doc)
    out.write_text(text, encoding="utf-8")
    return out
