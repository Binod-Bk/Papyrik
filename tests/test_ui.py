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


@pytest.fixture
def window(app):
    win = MainWindow()
    yield win
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
    assert window._versions[0] == _fixture("cjk.pdf")


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
