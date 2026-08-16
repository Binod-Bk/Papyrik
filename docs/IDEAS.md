# Papyrik — Post-launch ideas

Ideas captured during the 3-day build. **Not** part of the locked scope — revisit
after v1 ships.

---

## Smart page-number detection & removal (v2 flagship)

**Pitch:** Detect page numbers that *other* tools stamped into a PDF, then remove
or renumber them. Almost no consumer PDF tool does this for foreign page numbers —
a real "why Papyrik" differentiator.

### What's feasible
Detection via a strong heuristic that naive text search misses:

1. Read every text span per page with its bounding box (`page.get_text("dict")`).
2. Keep short, standalone runs near the margins (bottom-center, corners, etc.).
3. Check whether the value **increments by 1 across consecutive pages**
   (`1,2,3…`, roman `i,ii,iii…`, or patterns like `Page 3 of 20`).
4. A run that increments in a fixed position across the whole document is almost
   certainly a page number.

Removal of a **text-layer** number is feasible with PyMuPDF redaction:
`page.add_redact_annot(bbox)` + `page.apply_redactions()` deletes the underlying
content. Page numbers sit in blank margins, so this leaves a clean gap, not a
smear. "Update" = remove + re-stamp with `enhance.page_numbers`.

### Hard limits (be honest in the UI)
- **Scanned / rasterized numbers**: baked into image pixels → would need
  inpainting (image/ML problem). Not reliably removable. Same wall as flattened
  watermarks.
- **False positives**: a numbered list, a year, or a figure label can look like a
  page number. So it can NOT be a silent "remove all".

### Required UX
A **preview + confirm** step: "Found these N page numbers — remove them?" with the
detected locations highlighted, so the user approves before anything is deleted.

### Rough shape of work
- `core/operations/detect.py` — pure detection returning candidate spans + bboxes
  per page, with a confidence signal from the increment check.
- Extend `enhance` / a new `redact` helper for the removal via redaction.
- A preview dialog in the UI (highlight candidates on the thumbnails/page viewer).
- Tests over synthetic fixtures with known page numbers in various positions.

Estimated: a day-plus on its own. Ship v1 first.

---

## Other parking-lot ideas
- Watermark as a removable layer (OCG) so Papyrik's own watermarks can be removed
  later. Tradeoff: OCG content-removal is fiddly in PyMuPDF; annotations are
  simpler but render/print as annotations.
