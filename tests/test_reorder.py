"""Unit tests for the pure drag-reorder computation."""

from __future__ import annotations

from papyrik.ui.thumbnail_view import compute_reorder


def test_move_first_to_end():
    assert compute_reorder(3, [0], drop_row=3) == [1, 2, 0]


def test_move_last_to_front():
    assert compute_reorder(3, [2], drop_row=0) == [2, 0, 1]


def test_move_middle_forward():
    assert compute_reorder(5, [1], drop_row=4) == [0, 2, 3, 1, 4]


def test_move_block_together():
    # Drag pages 0 and 1 to sit after page 3.
    assert compute_reorder(5, [0, 1], drop_row=4) == [2, 3, 0, 1, 4]


def test_drop_in_place_is_identity():
    assert compute_reorder(4, [2], drop_row=2) == [0, 1, 2, 3]


def test_result_is_always_a_permutation():
    for drop in range(6):
        order = compute_reorder(5, [1, 3], drop_row=drop)
        assert sorted(order) == [0, 1, 2, 3, 4]
