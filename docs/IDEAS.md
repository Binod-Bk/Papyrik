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

## Annotation editing (post-launch enhancement)

**Pitch:** Edit annotations Papyrik created, even after save/close/reopen —
move a sticky note, re-word it, delete a highlight or drawing.

**Why it's feasible (unlike watermark removal):** highlights, sticky notes and
ink are real PDF annotation objects, not marks baked into the page content. They
can be enumerated, moved, edited and deleted.

**Why it doesn't work today:** the annotator only *adds* — it starts with a blank
overlay and never loads the page's existing annotations as editable objects.

### Shape of work
- On opening the annotator, read existing annotations into the canvas:
  Highlight -> rect, Text -> point + `info["content"]`, Ink -> `annot.vertices`
  stroke lists.
- Render the page background with `get_pixmap(annots=False)` so annotations
  aren't drawn twice.
- Add a select/move tool: click to select, drag to move, Delete to remove; note
  text edit already exists (click a note).
- On Apply, delete only the annotation types we manage (Highlight, Text, Ink) —
  never Widget/form annotations — then re-add from the canvas state.
- Tests over a fixture with known annotations: load -> move/edit/delete ->
  round-trip.

Estimated: ~half a day. Deferred to keep the 3-day ship on track. (Note-*viewing*
was pulled forward and shipped in v1.)

---

## Other parking-lot ideas
- Watermark as a removable layer (OCG) so Papyrik's own watermarks can be removed
  later. Tradeoff: OCG content-removal is fiddly in PyMuPDF; annotations are
  simpler but render/print as annotations.
