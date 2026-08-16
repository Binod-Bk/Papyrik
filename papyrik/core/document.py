"""PdfDocument - the single source of truth for an open file.

Wraps a PyMuPDF document and adds the UI-facing state the rest of the app
needs: the source path, a dirty flag, encryption handling, and page-thumbnail
rendering. This module lives in `core` and never imports from `papyrik.ui`.

Rendering returns a QPixmap because that is what the thumbnail grid consumes;
QtGui is a rendering library, not the widget/UI layer, so the core->ui rule is
respected. `render_png()` is a pure, Qt-free alternative for headless use.
"""

from __future__ import annotations

from pathlib import Path

import pymupdf
from PyQt6.QtGui import QImage, QPixmap


class PdfError(Exception):
    """Base class for document-open failures surfaced to the UI."""


class PdfCorruptError(PdfError):
    """The file is not a readable PDF."""


class PdfEncryptedError(PdfError):
    """The file needs a password that was missing or wrong."""


def is_encrypted(path: str | Path) -> bool:
    """True if `path` is a PDF that requires a password to read.

    Never raises for a merely-encrypted file; a corrupt file raises
    PdfCorruptError so callers can tell the two apart.
    """
    try:
        doc = pymupdf.open(path)
    except Exception as exc:  # unreadable / not a PDF
        raise PdfCorruptError(f"Cannot open '{Path(path).name}': {exc}") from exc
    try:
        return bool(doc.needs_pass)
    finally:
        doc.close()


class PdfDocument:
    """An open PDF plus its edit state.

    Parameters
    ----------
    path:
        File to open.
    password:
        Supplied when the file is encrypted. If the file needs a password and
        none (or a wrong one) is given, PdfEncryptedError is raised.
    """

    def __init__(self, path: str | Path, password: str | None = None) -> None:
        self.path = Path(path)
        self._doc: pymupdf.Document | None = None
        self._open(password)

    # -- lifecycle --------------------------------------------------------

    def _open(self, password: str | None) -> None:
        try:
            doc = pymupdf.open(self.path)
        except Exception as exc:
            raise PdfCorruptError(
                f"Cannot open '{self.path.name}': {exc}"
            ) from exc

        if doc.needs_pass:
            if password is None or not doc.authenticate(password):
                doc.close()
                raise PdfEncryptedError(
                    f"'{self.path.name}' is password-protected."
                )

        # Some files open but are structurally broken; touching page_count
        # forces PyMuPDF to parse the page tree and fail early if it must.
        try:
            _ = doc.page_count
        except Exception as exc:
            doc.close()
            raise PdfCorruptError(
                f"'{self.path.name}' is damaged: {exc}"
            ) from exc

        self._doc = doc

    def close(self) -> None:
        if self._doc is not None:
            self._doc.close()
            self._doc = None

    def __enter__(self) -> "PdfDocument":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    @property
    def is_open(self) -> bool:
        return self._doc is not None

    def _require_open(self) -> pymupdf.Document:
        if self._doc is None:
            raise PdfError("Operation on a closed document.")
        return self._doc

    # -- metadata ---------------------------------------------------------

    @property
    def page_count(self) -> int:
        return self._require_open().page_count

    def text_notes(self, index: int) -> list[tuple[tuple, str]]:
        """Sticky-note annotations on page `index` as ((x0,y0,x1,y1), text).

        Lets the UI show a note's text (the page render only shows its icon).
        """
        doc = self._require_open()
        if not 0 <= index < doc.page_count:
            raise IndexError(f"Page {index} out of range.")
        page = doc.load_page(index)
        notes: list[tuple[tuple, str]] = []
        for annot in page.annots() or ():
            if annot.type[1] == "Text":  # read fields during iteration
                r = annot.rect
                notes.append(((r.x0, r.y0, r.x1, r.y1),
                              annot.info.get("content", "")))
        return notes

    # -- saving -----------------------------------------------------------

    def save_as(self, path: str | Path) -> Path:
        """Write a plaintext (decrypted) copy of the open document to `path`.

        Used when opening an encrypted file: the app works on this decrypted
        copy so pure page operations never have to handle a password. The
        original file on disk is never touched.
        """
        doc = self._require_open()
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        doc.save(str(out), encryption=pymupdf.PDF_ENCRYPT_NONE)
        return out

    # -- rendering --------------------------------------------------------

    def render_png(self, index: int, dpi: int = 72) -> bytes:
        """Render page `index` (0-based) to PNG bytes. Qt-free, headless-safe."""
        doc = self._require_open()
        if not 0 <= index < doc.page_count:
            raise IndexError(f"Page {index} out of range (0..{doc.page_count - 1}).")
        page = doc.load_page(index)
        pix = page.get_pixmap(dpi=dpi)
        return pix.tobytes("png")

    def thumbnail(self, index: int, max_dim: int = 200) -> QPixmap:
        """Render page `index` (0-based) as a QPixmap no larger than `max_dim`.

        Requires a QGuiApplication instance (as any QPixmap use does).
        """
        doc = self._require_open()
        if not 0 <= index < doc.page_count:
            raise IndexError(f"Page {index} out of range (0..{doc.page_count - 1}).")
        page = doc.load_page(index)
        rect = page.rect
        scale = max_dim / max(rect.width, rect.height)
        matrix = pymupdf.Matrix(scale, scale)
        pix = page.get_pixmap(matrix=matrix, alpha=False)
        image = QImage(
            pix.samples, pix.width, pix.height, pix.stride,
            QImage.Format.Format_RGB888,
        )
        # .copy() detaches from PyMuPDF's buffer, which is freed after this call.
        return QPixmap.fromImage(image.copy())
