"""Area preservation and terminal rendering of composition treemaps."""

from io import StringIO

import pytest

pytest.importorskip("textual")

from rich.console import Console

from pyannote.database.tui_treemap import ContributionTreemap, partition


def test_rectangles_preserve_relative_area_without_overlap():
    items = [
        (str(index), weight) for index, weight in enumerate([100, 25, 10, 1, 0.001, 0])
    ]
    rectangles = partition(items, 60, 9)
    total = sum(weight for _, weight in items)
    assert len(rectangles) == 5
    for key, (x, y, width, height) in rectangles:
        assert width * height == pytest.approx(60 * 9 * dict(items)[key] / total)
        assert x >= 0 and y >= 0
        assert x + width <= 60 + 1e-9 and y + height <= 9 + 1e-9
        for other, (ox, oy, ow, oh) in rectangles:
            if other == key:
                continue
            overlap_width = min(x + width, ox + ow) - max(x, ox)
            overlap_height = min(y + height, oy + oh) - max(y, oy)
            assert overlap_width <= 1e-9 or overlap_height <= 1e-9


@pytest.mark.parametrize("width", [20, 60])
def test_render_rectangles_and_percentages_at_terminal_width(width):
    stream = StringIO()
    console = Console(file=stream, width=width, color_system=None)
    console.print(
        ContributionTreemap(
            [
                (("AMI.SpeakerDiarization.Raw@words", "train"), 30),
                (("AMI.SpeakerDiarization.Raw@turns", "train"), 10),
            ]
        )
    )
    output = stream.getvalue()
    assert "75.0%" in output and "25.0%" in output
    assert "AMI" in output
    assert all(
        name not in output
        for name in ("Raw", "words", "turns", "train", "SpeakerDiarization")
    )
    assert len(output.splitlines()) == 9
    assert all(len(line) <= width for line in output.splitlines())
