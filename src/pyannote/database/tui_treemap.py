"""Terminal treemaps with areas proportional to source contributions."""

import hashlib
from dataclasses import dataclass, field

from rich.style import Style
from rich.text import Text

PALETTE = ("#155e75", "#166534", "#6b21a8", "#92400e", "#1e40af", "#9d174d")


def source_color(source, commercial=True):
    if commercial is False:
        return "#991b1b"
    if commercial is None:
        return "#854d0e"
    digest = hashlib.sha256("/".join(source).encode()).digest()
    return PALETTE[int.from_bytes(digest[:2], "big") % len(PALETTE)]


def partition(items, width, height, *, cell_aspect=2):
    """Balanced recursive partition, preserving areas before terminal rounding.

    Items are (key, positive weight). Terminal cells are approximately twice as
    tall as wide. Small contributions may round to zero cells; the legend still
    shows their exact values.
    """
    items = sorted((item for item in items if item[1] > 0), key=lambda item: -item[1])

    def divide(entries, x, y, w, h):
        if not entries:
            return
        if len(entries) == 1:
            yield entries[0][0], (x, y, w, h)
            return
        total = sum(weight for _, weight in entries)
        accumulated = 0
        cuts = []
        for index, (_, weight) in enumerate(entries[:-1], 1):
            accumulated += weight
            cuts.append((abs(accumulated - total / 2), index, accumulated / total))
        _, cut, fraction = min(cuts)
        if w >= cell_aspect * h:
            yield from divide(entries[:cut], x, y, w * fraction, h)
            yield from divide(entries[cut:], x + w * fraction, y, w * (1 - fraction), h)
        else:
            yield from divide(entries[:cut], x, y, w, h * fraction)
            yield from divide(entries[cut:], x, y + h * fraction, w, h * (1 - fraction))

    return list(divide(items, 0, 0, width, height))


@dataclass
class ContributionTreemap:
    """Rich renderable; labels and percentages accompany a stable source color."""

    items: list  # (source, value)
    height: int = 9
    commercial: dict = field(default_factory=dict)

    def __rich_console__(self, console, options):
        width = options.max_width
        total = sum(value for _, value in self.items if value > 0)
        if not total or width < 4:
            yield Text(
                "No positive values available yet; see the source tree.",
                style="dim",
            )
            return
        cells = [[(" ", None) for _ in range(width)] for _ in range(self.height)]
        values = dict(self.items)
        for source, (x, y, w, h) in partition(self.items, width, self.height):
            left, right = round(x), min(width, round(x + w))
            top, bottom = round(y), min(self.height, round(y + h))
            if right <= left or bottom <= top:
                continue
            allowed = self.commercial.get(source, True)
            style = Style(
                color="white", bgcolor=source_color(source, allowed), bold=True
            )
            for row in range(top, bottom):
                for column in range(left, right):
                    cells[row][column] = (" ", style)
            # One terminal-cell gutter separates adjacent contributions.
            if right < width:
                right -= 1
                for row in range(top, bottom):
                    cells[row][right] = (" ", None)
            if bottom < self.height and bottom - top > 2:
                bottom -= 1
                for column in range(left, right):
                    cells[bottom][column] = (" ", None)
            available = right - left
            if available < 3:
                continue
            base = source[0].partition(".")[0]
            if allowed is False:
                base = f"NC · {base}"
            elif allowed is None:
                base = f"? · {base}"
            percentage = f"{values[source] / total:.1%}"
            labels = [base, percentage]
            if bottom - top == 1:
                labels = [f"{base} {percentage}"]
            start = top + max(0, (bottom - top - len(labels)) // 2)
            for row, label in zip(range(start, bottom), labels):
                text = Text(label)
                text.truncate(available, overflow="ellipsis")
                # Text.cell_len keeps wide Unicode names aligned in the terminal.
                offset = left + max(0, (available - text.cell_len) // 2)
                # Source names normally use ASCII. Rich handles any wide characters
                # when emitting each row below, so keep labels as whole spans.
                cells[row][offset] = (text.plain, style)
                for column in range(offset + 1, offset + text.cell_len):
                    cells[row][column] = ("", style)
        for row in cells:
            line = Text(no_wrap=True, overflow="crop")
            for character, style in row:
                line.append(character, style=style)
            yield line
