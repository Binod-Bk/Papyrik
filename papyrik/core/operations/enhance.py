"""Enhance: compress, watermark, page_numbers.

Pure functions - paths + params in, an output path out; the input file is never
modified. Rendering/stamping is done with PyMuPDF; image watermarks use Pillow
for opacity + arbitrary rotation.
"""

from __future__ import annotations

import io
from pathlib import Path

import pymupdf

# preset -> (jpeg quality, max pixel dimension before downscaling)
_COMPRESS_PRESETS: dict[str, tuple[int, int]] = {
    "high": (85, 4000),      # highest quality, least shrink
    "balanced": (60, 2000),
    "low": (40, 1200),       # smallest file, most loss
}

_POSITIONS = {
    "top-left", "top", "top-right",
    "left", "center", "right",
    "bottom-left", "bottom", "bottom-right",
}

# Accept the natural "-center" spellings as aliases of the compact names.
_POSITION_ALIASES = {
    "top-center": "top", "center-top": "top",
    "bottom-center": "bottom", "center-bottom": "bottom",
    "center-left": "left", "left-center": "left",
    "center-right": "right", "right-center": "right",
    "center-center": "center",
}


def _normalize_position(position: str) -> str:
    p = position.lower()
    p = _POSITION_ALIASES.get(p, p)
    if p not in _POSITIONS:
        raise ValueError(
            "position must be one of: top-left, top, top-right, left, center, "
            "right, bottom-left, bottom, bottom-right (and their -center forms)."
        )
    return p


def _open_pdf(path: str | Path) -> pymupdf.Document:
    doc = pymupdf.open(str(path))
    if doc.needs_pass:
        doc.close()
        raise ValueError(
            f"'{Path(path).name}' is password-protected; decrypt it first."
        )
    return doc


def _save(doc: pymupdf.Document, output: str | Path, **opts) -> Path:
    out = Path(output)
    out.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(out), **opts)
    return out


def _anchor(rect: pymupdf.Rect, position: str, margin: float = 40.0) -> pymupdf.Point:
    """A reference point inside `rect` for the given 9-grid position."""
    xs = {"left": rect.x0 + margin,
          "center": (rect.x0 + rect.x1) / 2,
          "right": rect.x1 - margin}
    ys = {"top": rect.y0 + margin,
          "center": (rect.y0 + rect.y1) / 2,
          "bottom": rect.y1 - margin}
    if position == "center":
        return pymupdf.Point(xs["center"], ys["center"])
    parts = position.split("-")
    if len(parts) == 1:
        word = parts[0]
        if word in ("top", "bottom"):
            return pymupdf.Point(xs["center"], ys[word])
        return pymupdf.Point(xs[word], ys["center"])
    return pymupdf.Point(xs[parts[1]], ys[parts[0]])  # e.g. "top-right"


# -- compress ------------------------------------------------------------

def compress(input_pdf: str | Path, output: str | Path,
             preset: str = "balanced") -> Path:
    """Shrink `input_pdf` by re-encoding images and cleaning the file.

    `preset` is one of "high", "balanced", "low" (quality high -> low).
    """
    if preset not in _COMPRESS_PRESETS:
        raise ValueError("preset must be one of: high, balanced, low.")
    quality, max_dim = _COMPRESS_PRESETS[preset]

    doc = _open_pdf(input_pdf)
    try:
        seen: set[int] = set()
        for page in doc:
            for info in page.get_images(full=True):
                xref = info[0]
                if xref in seen:
                    continue
                seen.add(xref)
                try:
                    pix = pymupdf.Pixmap(doc, xref)
                    if pix.alpha or (pix.n - pix.alpha) >= 4:  # RGBA/CMYK -> RGB
                        pix = pymupdf.Pixmap(pymupdf.csRGB, pix)
                    while max(pix.width, pix.height) > max_dim:
                        pix.shrink(1)  # halve dimensions
                    data = pix.tobytes(output="jpg", jpg_quality=quality)
                    page.replace_image(xref, stream=data)
                except Exception:
                    continue  # corrupt/odd images are normal, skip them
        return _save(doc, output, garbage=4, deflate=True, clean=True)
    finally:
        doc.close()


# -- watermark -----------------------------------------------------------

def watermark(input_pdf: str | Path, output: str | Path, *,
              text: str | None = None, image: str | Path | None = None,
              opacity: float = 0.3, rotation: int = 45,
              position: str = "center") -> Path:
    """Stamp a text OR image watermark on every page."""
    if bool(text) == bool(image):
        raise ValueError("Provide exactly one of text or image.")
    if not 0.0 <= opacity <= 1.0:
        raise ValueError("opacity must be between 0 and 1.")
    position = _normalize_position(position)

    doc = _open_pdf(input_pdf)
    try:
        if text:
            _watermark_text(doc, text, opacity, rotation, position)
        else:
            _watermark_image(doc, image, opacity, rotation, position)
        return _save(doc, output, garbage=3, deflate=True)
    finally:
        doc.close()


def _watermark_text(doc, text, opacity, rotation, position) -> None:
    fontsize = 48
    length = pymupdf.get_text_length(text, fontsize=fontsize)
    for page in doc:
        anchor = _anchor(page.rect, position)
        start = pymupdf.Point(anchor.x - length / 2, anchor.y + fontsize / 2)
        writer = pymupdf.TextWriter(page.rect, opacity=opacity,
                                    color=(0.5, 0.5, 0.5))
        writer.append(start, text, fontsize=fontsize)
        matrix = pymupdf.Matrix(1, 1).prerotate(rotation)
        writer.write_text(page, morph=(anchor, matrix))


def _watermark_image(doc, image, opacity, rotation, position) -> None:
    from PIL import Image

    img = Image.open(str(image)).convert("RGBA")
    if opacity < 1.0:
        alpha = img.split()[3].point(lambda a: int(a * opacity))
        img.putalpha(alpha)
    if rotation % 360:
        img = img.rotate(rotation, expand=True)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    stream = buf.getvalue()
    iw, ih = img.size

    for page in doc:
        rect = page.rect
        target_w = rect.width * 0.4
        target_h = target_w * ih / iw
        anchor = _anchor(rect, position)
        box = pymupdf.Rect(anchor.x - target_w / 2, anchor.y - target_h / 2,
                           anchor.x + target_w / 2, anchor.y + target_h / 2)
        page.insert_image(box, stream=stream, overlay=True, keep_proportion=True)


# -- page numbers --------------------------------------------------------

def page_numbers(input_pdf: str | Path, output: str | Path, *,
                 start: int = 1, position: str = "bottom-center") -> Path:
    """Stamp page numbers (default bottom-center)."""
    position = _normalize_position(position)
    fontsize = 11
    doc = _open_pdf(input_pdf)
    try:
        for i, page in enumerate(doc):
            label = str(start + i)
            anchor = _anchor(page.rect, position, margin=30)
            length = pymupdf.get_text_length(label, fontsize=fontsize)
            # Horizontally center the label on its anchor.
            point = pymupdf.Point(anchor.x - length / 2, anchor.y)
            page.insert_text(point, label, fontsize=fontsize, color=(0, 0, 0))
        return _save(doc, output, garbage=3, deflate=True)
    finally:
        doc.close()
