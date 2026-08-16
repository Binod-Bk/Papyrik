# Claude Code kickoff

## Setup

```bash
mkdir pdfkit && cd pdfkit
git init
# drop CLAUDE.md in the root, then:
claude
```

## Prompt 1 — scaffold (paste this first)

> Read CLAUDE.md. Scaffold the full directory structure with empty modules and correct imports. Write requirements.txt with pinned versions, .gitignore, and a main.py that opens an empty PyQt6 window with the sidebar/preview/tool-panel three-pane layout from the spec. Don't implement any PDF operations yet. Run it to confirm the window opens before you finish.

## Prompt 2 — document core

> Implement core/document.py: a PdfDocument class wrapping PyMuPDF that handles open, close, page count, page thumbnail rendering as QPixmap, and dirty-state tracking. Write tests/test_document.py covering open, corrupt-file handling, and encrypted-file detection. Run the tests.

## Prompt 3 — page operations

> Implement core/operations/pages.py: merge, split_by_range, split_every_n, rotate, delete_pages, extract_pages, reorder. Pure functions, paths in and paths out, never mutate the input file. Write tests for each against tests/fixtures/. Run them.

## Prompt 4 — wire the UI

> Implement ui/thumbnail_view.py with a page grid: multi-select, drag-to-reorder, and rotate/delete via context menu. Wire it to the page operations through workers.py so nothing blocks the UI thread. Add an undo stack for page operations.

## Day 1 done when

You can open a PDF, see thumbnails, reorder pages by dragging, rotate and delete pages, undo it, merge two files, split one, and save the result.

## Working rules

- One prompt per module. Don't ask for the whole app in one go — it produces plausible code that doesn't run.
- After every prompt: run it. Don't accept code you haven't executed.
- `git commit` after each working module. Small commits mean you can throw away a bad hour instead of a bad day.
- If Claude Code proposes a feature that isn't in CLAUDE.md, say no. Scope creep is what kills the 3 days.
- Stuck for more than 30 minutes on one thing: stub it, note it, move on. Come back on day 3.
