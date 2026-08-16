# PDFKit — Desktop PDF Toolkit

Offline desktop PDF toolkit. Everything iLovePDF/Smallpdf do, but local: no upload, no file size cap, no daily limit.

**Build window: 3 days. Scope is locked. Do not add features not listed here.**

## Non-goals (say no to these)

- True text editing with reflow — PDFs store positioned glyphs, not paragraphs. Out of scope.
- OCR, redaction, digital signatures, PDF/A compliance, form *creation*.
- Cloud sync, accounts, licensing, auto-update.
- Any web frontend. This is desktop only.

## Stack

- Python 3.11+
- PyQt6 — GUI
- PyMuPDF (`fitz`) — render, annotate, compress, images
- pypdf — merge, split, rotate, encrypt, metadata
- pdf2docx — PDF → Word
- Pillow — image handling
- PyInstaller — packaging

Pin every version in `requirements.txt`. No optional deps.

## Architecture

```
pdfkit/
  main.py              # entry point
  ui/
    main_window.py     # shell: sidebar tool list + central preview
    thumbnail_view.py  # page grid, drag-to-reorder, multi-select
    tool_panel.py      # right-hand panel, swaps per selected tool
  core/
    document.py        # PdfDocument wrapper — the single source of truth
    operations/        # one module per operation, pure functions
      pages.py         # merge split rotate reorder delete extract
      convert.py       # pdf->docx, pdf->images, images->pdf, pdf->text
      security.py      # encrypt decrypt permissions
      enhance.py       # compress watermark page_numbers
      annotate.py      # highlight text_note draw
      forms.py         # read + fill existing AcroForm fields
    batch.py           # apply any operation to a folder of files
  workers.py           # QThread wrappers — no long op runs on the UI thread
```

**Rules:**
- `core/` never imports from `ui/`. Every operation is a pure function: takes paths + params, returns a path. Testable without a GUI.
- Every operation runs in a QThread with progress signals. A frozen window is a bug.
- Never write over the input file. Always output to a new path, then let the user save.
- Wrap every operation in try/except and surface the real error in the UI. Corrupt PDFs are normal, not exceptional.

## Day plan

**Day 1 — shell + pages**
Main window, open/close files, page thumbnail grid with multi-select and drag-reorder, merge, split (by range and by every-N), rotate, delete, extract pages, reorder. Undo stack for page ops.

**Day 2 — convert, secure, enhance**
PDF→Word, PDF→images, images→PDF, PDF→text, compress (three quality presets), watermark (text + image, opacity/rotation/position), page numbers, encrypt/decrypt, view + edit metadata.

**Day 3 — annotate, batch, ship**
Highlight, sticky note, freehand draw, fill existing form fields, batch mode over a folder, PyInstaller build, README with screenshots.

## Definition of done

`dist/PDFKit.exe` launches on a clean Windows machine with no Python installed, and every listed operation works on the test corpus.

## Test corpus

Before writing operation code, collect `tests/fixtures/`: a scanned document, a 300-page file, a fillable government form, an encrypted PDF, a CJK-text PDF, and one deliberately corrupt file. Every operation gets tested against all six. This is where real PDF tools break.

## Known-flaky

`pdf2docx` handles simple layouts well and mangles multi-column and tables. Label the feature "best effort" in the UI. Do not spend day 3 trying to fix it.
