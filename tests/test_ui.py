"""Integration tests for the MainWindow orchestration.

These drive the real OperationWorker pipeline (off-thread) through the window's
gesture handlers and assert the version/undo stack behaves. Drag gestures
themselves aren't simulated - the drop handler just emits reorder_requested,
which we call directly - but everything downstream is the production path.

Run headless with QT_QPA_PLATFORM=offscreen (the suite sets it automatically).
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import pytest
from pypdf import PdfReader

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication, QInputDialog, QLineEdit  # noqa: E402

from papyrik.ui.main_window import MainWindow  # noqa: E402
from tests import make_fixtures  # noqa: E402

FIXTURES = make_fixtures.FIXTURES
PASSWORD = make_fixtures.ENCRYPTED_PASSWORD


def _fixture(name: str) -> Path:
    path = FIXTURES / name
    if not path.exists():
        make_fixtures.main()
    return path


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication(sys.argv)


@pytest.fixture(autouse=True)
def _no_blocking_error_modal(monkeypatch):
    # A modal QMessageBox.critical blocks forever headless; keep an unexpected
    # error surfacing as a failed assertion, never a hung suite.
    from PyQt6.QtWidgets import QMessageBox
    monkeypatch.setattr(
        QMessageBox, "critical",
        staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok),
    )


@pytest.fixture
def window(app):
    win = MainWindow()
    yield win
    win._saved = True  # avoid the unsaved-changes modal during teardown
    win.close()


def _wait(app, cond, timeout=60.0) -> bool:
    end = time.time() + timeout
    while time.time() < end:
        app.processEvents()
        if cond():
            return True
        time.sleep(0.01)
    return False


def _page_count(path) -> int:
    return len(PdfReader(str(path)).pages)


# -- open ----------------------------------------------------------------

def test_open_plain_seeds_version_stack(app, window):
    window._open_path(_fixture("cjk.pdf"))
    assert len(window._versions) == 1
    # Base version is a workdir copy (immutable undo baseline), not the original.
    assert window._versions[0].parent == window._workdir
    assert window._source_path == _fixture("cjk.pdf")


def test_save_overwrites_source_file(app, window, tmp_path):
    src = tmp_path / "work.pdf"
    src.write_bytes(_fixture("large_300p.pdf").read_bytes())
    window._open_path(src)

    window._on_rotate([0], 90)
    assert _wait(app, lambda: not window._busy)
    assert window._saved is False

    assert window.save() is True                # overwrites src, no dialog
    assert window._saved is True
    assert PdfReader(str(src)).pages[0].rotation % 360 == 90
    # Atomic save leaves no temp file behind.
    assert not list(tmp_path.glob("*.papyrik-tmp"))

    # Undo baseline is intact despite the overwrite.
    window.undo()
    assert _page_count(window._current) == 300
    assert PdfReader(str(window._current)).pages[0].rotation % 360 == 0


def test_enhance_edits_compose_then_save(app, window, tmp_path):
    import pymupdf

    src = tmp_path / "work.pdf"
    src.write_bytes(_fixture("large_300p.pdf").read_bytes())
    window._open_path(src)

    # Page numbers, then a watermark on top - both should land in one document.
    window._apply_edit(
        lambda s, d: __import__("papyrik.core.operations.enhance",
                                fromlist=["enhance"]).page_numbers(
            s, d, start=1, position="bottom-center"),
        busy="", done="",
    )
    assert _wait(app, lambda: not window._busy)
    window._apply_edit(
        lambda s, d: __import__("papyrik.core.operations.enhance",
                                fromlist=["enhance"]).watermark(
            s, d, text="DRAFT", opacity=0.3, rotation=45, position="center"),
        busy="", done="",
    )
    assert _wait(app, lambda: not window._busy)
    assert len(window._versions) == 3  # base + page numbers + watermark

    window.save()
    with pymupdf.open(str(src)) as doc:
        text = doc[0].get_text()
    assert "DRAFT" in text and "1" in text  # both edits present in saved file


def test_open_corrupt_shows_no_document(app, window, monkeypatch):
    shown = {}
    monkeypatch.setattr(window, "_error", lambda t, m: shown.update(title=t))
    window._open_path(_fixture("corrupt.pdf"))
    assert window._current is None
    assert "title" in shown


def test_open_encrypted_decrypts_to_workdir(app, window, monkeypatch):
    monkeypatch.setattr(
        QInputDialog, "getText",
        staticmethod(lambda *a, **k: (PASSWORD, True)),
    )
    window._open_path(_fixture("encrypted.pdf"))
    current = window._current
    assert current is not None
    # Working copy lives in the temp workdir, not the original location.
    assert current.parent == window._workdir
    assert _page_count(current) == 1


def test_open_encrypted_cancel_leaves_no_document(app, window, monkeypatch):
    monkeypatch.setattr(
        QInputDialog, "getText",
        staticmethod(lambda *a, **k: ("", False)),
    )
    window._open_path(_fixture("encrypted.pdf"))
    assert window._current is None


def test_encrypted_edit_then_undo_regression(app, window, monkeypatch):
    """Regression: after decrypting, a page op must not overwrite the base
    version, so undo returns to the freshly decrypted document."""
    monkeypatch.setattr(
        QInputDialog, "getText",
        staticmethod(lambda *a, **k: (PASSWORD, True)),
    )
    window._open_path(_fixture("encrypted.pdf"))
    base = window._current
    assert _page_count(base) == 1

    window._on_rotate([0], 90)
    assert _wait(app, lambda: not window._busy)
    assert len(window._versions) == 2
    assert window._current != base  # distinct file, base not clobbered

    window.undo()
    assert window._current == base
    assert PdfReader(str(window._current)).pages[0].rotation % 360 == 0


# -- version ops: delete / undo / rotate / reorder -----------------------

def test_delete_then_undo(app, window):
    window._open_path(_fixture("large_300p.pdf"))
    assert _page_count(window._current) == 300

    window._on_delete([0, 1, 2])
    assert _wait(app, lambda: not window._busy)
    assert len(window._versions) == 2
    assert _page_count(window._current) == 297

    window.undo()
    assert len(window._versions) == 1
    assert _page_count(window._current) == 300


def test_rotate_creates_new_version(app, window):
    window._open_path(_fixture("large_300p.pdf"))
    window._on_rotate([0], 90)
    assert _wait(app, lambda: not window._busy)
    assert len(window._versions) == 2
    reader = PdfReader(str(window._current))
    assert reader.pages[0].rotation % 360 == 90


def test_reorder_reverses(app, window):
    window._open_path(_fixture("large_300p.pdf"))
    src_last = PdfReader(str(window._current)).pages[299].extract_text().strip()

    window._on_reorder(list(reversed(range(300))))
    assert _wait(app, lambda: not window._busy)
    assert len(window._versions) == 2
    out_first = PdfReader(str(window._current)).pages[0].extract_text().strip()
    assert out_first == src_last


def test_undo_disabled_at_base(app, window):
    window._open_path(_fixture("cjk.pdf"))
    assert window.act_undo.isEnabled() is False
    window.undo()  # no-op, must not raise
    assert len(window._versions) == 1


# -- merge ---------------------------------------------------------------

def test_drag_reorder_moves_page_to_end(app, window):
    """The manual drop path: reorder_requested drives a real version op."""
    window._open_path(_fixture("large_300p.pdf"))
    first_text = PdfReader(str(window._current)).pages[0].extract_text().strip()

    # Emulate what _Grid.dropEvent computes when page 0 is dropped at the end.
    from papyrik.ui.thumbnail_view import compute_reorder

    order = compute_reorder(300, [0], drop_row=300)
    assert order[-1] == 0  # page 0 now last
    window._on_reorder(order)
    assert _wait(app, lambda: not window._busy)

    last_text = PdfReader(str(window._current)).pages[299].extract_text().strip()
    assert last_text == first_text


def test_grid_apply_move_first_to_end(app):
    from papyrik.ui.thumbnail_view import ThumbnailView

    view = ThumbnailView()
    view.set_page_count(5)
    view._grid._apply_move([0], 5)
    assert view._grid.visual_order() == [1, 2, 3, 4, 0]


def test_grid_move_selected_right_emits_new_order(app):
    from papyrik.ui.thumbnail_view import ThumbnailView

    view = ThumbnailView()
    view.set_page_count(4)
    view._grid.item(0).setSelected(True)
    captured: list[list[int]] = []
    view.reorder_requested.connect(captured.append)
    view._grid.move_selected("right")
    assert view._grid.visual_order() == [1, 0, 2, 3]  # page 0 nudged one right
    assert captured == [[1, 0, 2, 3]]


def test_grid_move_selected_left_at_edge_is_noop(app):
    from papyrik.ui.thumbnail_view import ThumbnailView

    view = ThumbnailView()
    view.set_page_count(4)
    view._grid.item(0).setSelected(True)
    captured: list[list[int]] = []
    view.reorder_requested.connect(captured.append)
    view._grid.move_selected("left")  # already at the left edge
    assert view._grid.visual_order() == [0, 1, 2, 3]
    assert captured == []


def test_page_viewer_reveals_note_text(app, window, monkeypatch, tmp_path):
    from PyQt6.QtCore import QPointF
    from papyrik.core.operations import annotate
    from papyrik.ui.page_viewer import PageViewer

    src = tmp_path / "noted.pdf"
    annotate.text_note(_fixture("cjk.pdf"), 0, (120, 150), "Hello note", src)
    window._open_path(src)

    viewer = PageViewer(window._current, 0, 1, window)
    assert len(viewer._notes) == 1

    # Clicking on the note icon location resolves to its text.
    (x0, y0, x1, y1), _content = viewer._notes[0]
    scale = viewer._scale()
    click = QPointF((x0 + x1) / 2 * scale, (y0 + y1) / 2 * scale)
    assert viewer._note_at(click) == "Hello note"
    # Clicking far away resolves to nothing.
    assert viewer._note_at(QPointF(1, 1)) is None
    viewer.close()


def test_view_page_opens_and_closes(app, window):
    window._open_path(_fixture("large_300p.pdf"))
    from papyrik.ui.page_viewer import PageViewer

    viewer = PageViewer(window._current, 0, 300, window)
    assert not viewer._image.pixmap().isNull()
    viewer._go(1)
    assert viewer._index == 1
    viewer._adjust_zoom(1)
    assert viewer._zoom == 3
    viewer.close()


def test_close_prompts_and_discards_when_unsaved(app, monkeypatch):
    from PyQt6.QtWidgets import QMessageBox

    win = MainWindow()
    win._open_path(_fixture("cjk.pdf"))
    win._saved = False
    workdir = win._workdir
    asked = {}

    def fake_warning(*a, **k):
        asked["yes"] = True
        return QMessageBox.StandardButton.Discard

    monkeypatch.setattr(QMessageBox, "warning", staticmethod(fake_warning))
    win.close()
    assert asked.get("yes")          # the user was prompted
    assert not workdir.exists()      # cleanup ran -> the close proceeded


def test_close_cancel_vetoes(app, monkeypatch):
    from PyQt6.QtWidgets import QMessageBox

    win = MainWindow()
    win._open_path(_fixture("cjk.pdf"))
    win._saved = False
    monkeypatch.setattr(
        QMessageBox, "warning",
        staticmethod(lambda *a, **k: QMessageBox.StandardButton.Cancel),
    )
    win.close()
    assert win._workdir.exists()     # cleanup skipped -> close was vetoed

    win._saved = True                # allow real teardown
    win.close()


def test_tool_panel_run_button_visibility(app):
    from papyrik.ui.tool_panel import ToolPanel

    panel = ToolPanel()
    panel.show_tool("PDF to Text")
    assert panel._run.isHidden() is False  # shown for runnable tools
    panel.show_tool("Rotate")  # gesture-only tool, no Run button
    assert panel._run.isHidden() is True


def test_convert_to_text_via_dispatch(app, window, monkeypatch, tmp_path):
    from PyQt6.QtWidgets import QFileDialog

    out = tmp_path / "out.txt"
    monkeypatch.setattr(
        QFileDialog, "getSaveFileName",
        staticmethod(lambda *a, **k: (str(out), "")),
    )
    window._open_path(_fixture("large_300p.pdf"))
    window._on_run_tool("PDF to Text")
    assert _wait(app, lambda: not window._busy)
    assert "Page 1 of 300" in out.read_text(encoding="utf-8")


def test_convert_to_text_warns_on_image_only(app, window, monkeypatch, tmp_path):
    from PyQt6.QtWidgets import QFileDialog, QMessageBox

    out = tmp_path / "empty.txt"
    monkeypatch.setattr(
        QFileDialog, "getSaveFileName",
        staticmethod(lambda *a, **k: (str(out), "")),
    )
    warned = {}
    monkeypatch.setattr(
        QMessageBox, "information",
        staticmethod(lambda *a, **k: warned.setdefault("shown", True)),
    )
    window._open_path(_fixture("scanned.pdf"))  # image-only, no text layer
    window._on_run_tool("PDF to Text")
    assert _wait(app, lambda: not window._busy)
    assert warned.get("shown")                 # user was told why it's empty
    assert out.read_text(encoding="utf-8").strip() == ""


def test_images_to_pdf_via_dispatch(app, window, monkeypatch, tmp_path):
    from PyQt6.QtWidgets import QFileDialog
    from papyrik.core.operations import convert

    pngs = convert.pdf_to_images(_fixture("cjk.pdf"), tmp_path, fmt="png")
    monkeypatch.setattr(
        QFileDialog, "getOpenFileNames",
        staticmethod(lambda *a, **k: ([str(p) for p in pngs + pngs], "")),
    )
    window._on_run_tool("Images to PDF")
    assert _wait(app, lambda: not window._busy)
    assert _page_count(window._current) == 2
    assert window._saved is False


def test_encrypt_via_dispatch(app, window, monkeypatch, tmp_path):
    from PyQt6.QtWidgets import QFileDialog, QInputDialog
    from papyrik.core.document import is_encrypted

    out = tmp_path / "enc.pdf"
    monkeypatch.setattr(
        QInputDialog, "getText",
        staticmethod(lambda *a, **k: ("hunter2", True)),
    )
    monkeypatch.setattr(
        QFileDialog, "getSaveFileName",
        staticmethod(lambda *a, **k: (str(out), "")),
    )
    window._open_path(_fixture("cjk.pdf"))
    window._on_run_tool("Encrypt")
    assert _wait(app, lambda: not window._busy)
    assert is_encrypted(out) is True


def test_decrypt_via_dispatch(app, window, monkeypatch, tmp_path):
    from PyQt6.QtWidgets import QFileDialog, QInputDialog
    from papyrik.core.document import is_encrypted

    out = tmp_path / "dec.pdf"
    monkeypatch.setattr(
        QFileDialog, "getOpenFileName",
        staticmethod(lambda *a, **k: (str(_fixture("encrypted.pdf")), "")),
    )
    monkeypatch.setattr(
        QInputDialog, "getText",
        staticmethod(lambda *a, **k: (PASSWORD, True)),
    )
    monkeypatch.setattr(
        QFileDialog, "getSaveFileName",
        staticmethod(lambda *a, **k: (str(out), "")),
    )
    window._on_run_tool("Decrypt")  # standalone; no open document needed
    assert _wait(app, lambda: not window._busy)
    assert is_encrypted(out) is False


def test_compress_via_dispatch(app, window, monkeypatch):
    from PyQt6.QtWidgets import QInputDialog

    monkeypatch.setattr(
        QInputDialog, "getItem",
        staticmethod(lambda *a, **k: ("low", True)),
    )
    window._open_path(_fixture("scanned.pdf"))
    window._on_run_tool("Compress")
    assert _wait(app, lambda: not window._busy)
    assert len(window._versions) == 2          # applied as a new version
    assert window._saved is False
    assert _page_count(window._current) == 1


def test_page_numbers_via_dispatch(app, window, monkeypatch):
    import pymupdf
    from PyQt6.QtWidgets import QInputDialog

    monkeypatch.setattr(
        QInputDialog, "getInt", staticmethod(lambda *a, **k: (1, True)))
    monkeypatch.setattr(
        QInputDialog, "getItem",
        staticmethod(lambda *a, **k: ("bottom-center", True)))
    window._open_path(_fixture("large_300p.pdf"))
    window._on_run_tool("Page Numbers")
    assert _wait(app, lambda: not window._busy)
    assert len(window._versions) == 2
    with pymupdf.open(str(window._current)) as doc:
        assert "3" in doc[2].get_text()


def test_watermark_via_dispatch(app, window, monkeypatch):
    import pymupdf
    from papyrik.ui.watermark_dialog import WatermarkDialog

    monkeypatch.setattr(WatermarkDialog, "exec", lambda self: 1)
    monkeypatch.setattr(
        WatermarkDialog, "params",
        lambda self: {"text": "DRAFT", "opacity": 0.3,
                      "rotation": 45, "position": "center"},
    )
    window._open_path(_fixture("cjk.pdf"))
    window._on_run_tool("Watermark")
    assert _wait(app, lambda: not window._busy)
    assert len(window._versions) == 2
    with pymupdf.open(str(window._current)) as doc:
        assert "DRAFT" in doc[0].get_text()


def test_annotate_via_dispatch(app, window, monkeypatch):
    import pymupdf
    from papyrik.ui.annotation_view import AnnotationView

    monkeypatch.setattr(AnnotationView, "__init__",
                        lambda self, *a, **k: QDialog_init(self))
    monkeypatch.setattr(AnnotationView, "exec", lambda self: 1)
    monkeypatch.setattr(
        AnnotationView, "result_annotations",
        lambda self: {"highlights": [(72, 90, 300, 130)],
                      "notes": [((100, 200), "note")],
                      "strokes": [[(72, 72), (120, 100)]]},
    )
    window._open_path(_fixture("cjk.pdf"))
    window._on_run_tool("Highlight")
    assert _wait(app, lambda: not window._busy)
    assert len(window._versions) == 2
    with pymupdf.open(str(window._current)) as doc:
        types = [a.type[1] for a in doc[0].annots()]
    assert "Highlight" in types and "Text" in types and "Ink" in types


def QDialog_init(obj):
    from PyQt6.QtWidgets import QDialog
    QDialog.__init__(obj)
    obj.page = 0


def test_annotation_view_returns_pdf_coords_and_undo(app, window):
    from PyQt6.QtCore import QPointF, QRectF
    from papyrik.ui.annotation_view import AnnotationView

    window._open_path(_fixture("cjk.pdf"))
    view = AnnotationView(window._current, 0, "highlight", window)

    # Annotations are stored in PDF points and returned unchanged.
    view._canvas.highlights.append(QRectF(QPointF(10, 20), QPointF(110, 70)))
    view._canvas._order.append("highlight")
    view._canvas.notes.append((QPointF(50, 60), "hi"))
    view._canvas._order.append("note")
    assert view.result_annotations()["highlights"][0] == (10.0, 20.0, 110.0, 70.0)

    # Undo removes only the last annotation (the note), not the highlight.
    view._canvas.undo()
    result = view.result_annotations()
    assert result["notes"] == []
    assert len(result["highlights"]) == 1
    view.close()


def test_annotation_note_click_finds_existing(app, window):
    from PyQt6.QtCore import QPointF
    from papyrik.ui.annotation_view import AnnotationView

    window._open_path(_fixture("cjk.pdf"))
    view = AnnotationView(window._current, 0, "note", window)
    view.resize(600, 700)
    view._canvas.notes.append((QPointF(100, 120), "original"))
    # A click very near the note resolves to that note (edit), not a new one.
    assert view._canvas._note_at(QPointF(101, 121)) == 0
    # A click far away resolves to no existing note (would create a new one).
    assert view._canvas._note_at(QPointF(400, 400)) is None
    view.close()


def test_fill_form_via_dispatch(app, window, monkeypatch):
    from papyrik.core.operations import forms
    from papyrik.ui.form_dialog import FormDialog

    monkeypatch.setattr(FormDialog, "exec", lambda self: 1)
    monkeypatch.setattr(FormDialog, "values",
                        lambda self: {"full_name": "Binod B K"})
    window._open_path(_fixture("form.pdf"))
    window._on_run_tool("Fill Form")
    assert _wait(app, lambda: not window._busy)
    assert len(window._versions) == 2
    filled = {f["name"]: f["value"] for f in forms.read_fields(window._current)}
    assert filled["full_name"] == "Binod B K"


def test_fill_form_no_fields_shows_info(app, window, monkeypatch):
    from PyQt6.QtWidgets import QMessageBox

    shown = {}
    monkeypatch.setattr(QMessageBox, "information",
                        staticmethod(lambda *a, **k: shown.setdefault("i", True)))
    window._open_path(_fixture("cjk.pdf"))  # no form fields
    window._on_run_tool("Fill Form")
    assert shown.get("i")
    assert len(window._versions) == 1  # nothing applied


def test_metadata_edit_via_dispatch(app, window, monkeypatch):
    from papyrik.core.operations import metadata as metadata_ops
    from papyrik.ui.metadata_dialog import MetadataDialog

    monkeypatch.setattr(MetadataDialog, "exec", lambda self: 1)
    monkeypatch.setattr(
        MetadataDialog, "values",
        lambda self: {**metadata_ops.read_metadata(window._current),
                      "title": "Edited Title", "author": "Binod"},
    )
    window._open_path(_fixture("cjk.pdf"))
    window._on_run_tool("Metadata")
    assert _wait(app, lambda: not window._busy)
    assert len(window._versions) == 2          # new version pushed
    assert window._saved is False
    back = metadata_ops.read_metadata(window._current)
    assert back["title"] == "Edited Title"
    assert back["author"] == "Binod"


def test_merge_loads_result(app, window):
    window._open_path(_fixture("cjk.pdf"))  # prime, then replace via merge
    monkeypatch_files = [str(_fixture("cjk.pdf")), str(_fixture("large_300p.pdf"))]

    # merge_files reads a file dialog; call the worker path directly instead.
    from papyrik.core.operations import pages

    out = window._next_path()
    done = {}
    window._set_busy(True, "Merging…")
    window._launch(
        pages.merge, [Path(p) for p in monkeypatch_files], out,
        on_ok=lambda r: (window._versions.__setitem__(slice(None), [Path(str(r))]),
                         window._set_busy(False), done.update(ok=True)),
    )
    assert _wait(app, lambda: "ok" in done)
    assert _page_count(window._current) == 301
