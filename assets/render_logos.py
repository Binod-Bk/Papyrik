"""Render the Papyrik logo SVGs to PNG (and a Windows .ico for the app)."""

from __future__ import annotations

from pathlib import Path

import pymupdf

HERE = Path(__file__).parent


def render(svg: Path, out: Path, size: int) -> None:
    doc = pymupdf.open(str(svg))
    page = doc[0]
    scale = size / page.rect.width
    pix = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=True)
    pix.save(str(out))
    doc.close()


def _load_font(size: int):
    from PIL import ImageFont
    for name in ("seguisb.ttf", "segoeui.ttf", "arialbd.ttf", "arial.ttf"):
        path = Path(r"C:\Windows\Fonts") / name
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def wordmark(mark_svg: Path, out: Path, text_rgba: tuple,
             mark_px: int = 200, pad: int = 36, gap: int = 44,
             font_size: int = 132) -> None:
    from PIL import Image, ImageDraw

    tmp = HERE / "_mark_tmp.png"
    render(mark_svg, tmp, mark_px)
    mark = Image.open(tmp).convert("RGBA")
    font = _load_font(font_size)

    probe = ImageDraw.Draw(Image.new("RGBA", (4, 4)))
    bbox = probe.textbbox((0, 0), "Papyrik", font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]

    width = pad + mark_px + gap + tw + pad
    height = pad + max(mark_px, th) + pad
    canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    canvas.alpha_composite(mark, (pad, (height - mark_px) // 2))
    draw = ImageDraw.Draw(canvas)
    draw.text((pad + mark_px + gap, (height - th) // 2 - bbox[1]),
              "Papyrik", font=font, fill=text_rgba)
    canvas.save(out)
    tmp.unlink()


def _font_for_width(text: str, target_w: float):
    from PIL import Image, ImageDraw
    probe = ImageDraw.Draw(Image.new("RGBA", (4, 4)))
    best = _load_font(8)
    size = 8
    while size < 800:
        font = _load_font(size)
        if probe.textlength(text, font=font) >= target_w:
            return font
        best = font
        size += 4
    return best


def wordmark_stacked(mark_svg: Path, out: Path, text_rgba: tuple,
                     mark_px: int = 320, gap: int = 30, pad: int = 24) -> None:
    """Square badge on top, 'Papyrik' centered below, matched to badge width."""
    from PIL import Image, ImageDraw

    tmp = HERE / "_mark_tmp.png"
    render(mark_svg, tmp, mark_px)
    mark = Image.open(tmp).convert("RGBA")

    font = _font_for_width("Papyrik", mark_px)  # name spans the badge width
    probe = ImageDraw.Draw(Image.new("RGBA", (4, 4)))
    bbox = probe.textbbox((0, 0), "Papyrik", font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]

    width = pad + mark_px + pad
    height = pad + mark_px + gap + th + pad
    canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    canvas.alpha_composite(mark, (pad, pad))
    draw = ImageDraw.Draw(canvas)
    draw.text(((width - tw) // 2 - bbox[0], pad + mark_px + gap - bbox[1]),
              "Papyrik", font=font, fill=text_rgba)
    canvas.save(out)
    tmp.unlink()


def main() -> None:
    for variant in ("light", "dark"):
        svg = HERE / f"logo-{variant}.svg"
        render(svg, HERE / f"logo-{variant}-512.png", 512)
        render(svg, HERE / f"logo-{variant}-256.png", 256)

    # Horizontal lockups with the "Papyrik" wordmark.
    wordmark(HERE / "logo-light.svg", HERE / "wordmark-light.png",
             text_rgba=(42, 39, 72, 255))       # dark ink for light backgrounds
    wordmark(HERE / "logo-dark.svg", HERE / "wordmark-dark.png",
             text_rgba=(246, 242, 230, 255))    # cream for dark backgrounds

    # Stacked lockups: badge on top, name below, matched to badge width.
    wordmark_stacked(HERE / "logo-light.svg", HERE / "stacked-light.png",
                     text_rgba=(42, 39, 72, 255))
    wordmark_stacked(HERE / "logo-dark.svg", HERE / "stacked-dark.png",
                     text_rgba=(246, 242, 230, 255))

    # A multi-size .ico from the light variant for the window / exe icon.
    from PIL import Image
    render(HERE / "logo-light.svg", HERE / "_ico_src.png", 256)
    img = Image.open(HERE / "_ico_src.png")
    img.save(HERE / "papyrik.ico",
             sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    (HERE / "_ico_src.png").unlink()
    print("rendered:", sorted(p.name for p in HERE.glob("*.png")),
          "+ papyrik.ico")


if __name__ == "__main__":
    main()
