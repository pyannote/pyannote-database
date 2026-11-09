"""Tree rows with viewport-relative dataset-size backgrounds."""

from rich.segment import Segment
from rich.style import Style
from textual.strip import Strip
from textual.widgets import Tree

from .tui_stats import format_duration


class StatisticsTree(Tree):
    metric = "duration"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.metrics = {}

    def render_label(self, node, base_style, style):
        label = super().render_label(node, base_style, style)
        if node.id in self.metrics:
            files, duration, partial = self.metrics[node.id]
            # Provenance remains in the details panel; prioritize row statistics.
            source = label.plain.find("  [")
            if source >= 0:
                label = label[:source]
            if partial == "loading":
                label.append(
                    f"  {files} files · {format_duration(duration)} so far",
                    style="italic",
                )
            elif partial:
                label.append(
                    "  Unavailable" if partial == "unavailable" else "  Not loaded",
                    style="dim",
                )
            else:
                label.append(
                    f"  {files} files · {format_duration(duration)}", style="bold"
                )
        return label

    def visible_maximum(self):
        column = 1 if self.metric == "duration" else 0
        values = []
        for line in range(
            self.scroll_offset.y, self.scroll_offset.y + self.size.height
        ):
            node = self.get_node_at_line(line)
            if (
                node is not None
                and node.id in self.metrics
                and self.metrics[node.id][2] in (False, "loading")
            ):
                values.append(self.metrics[node.id][column])
        return max(values, default=0)

    def render_line(self, y):
        strip = super().render_line(y)
        node = self.get_node_at_line(y + self.scroll_offset.y)
        maximum = self.visible_maximum()
        if node is None or node.id not in self.metrics:
            return strip
        state = self.metrics[node.id][2]
        if state not in (False, "loading"):
            return strip
        if maximum <= 0:
            return strip
        value = self.metrics[node.id][1 if self.metric == "duration" else 0]
        width = min(self.size.width, round(self.size.width * value / maximum))
        if not width:
            return strip
        if state == "loading":
            color = "#52778a" if self.metric == "duration" else "#68835c"
        else:
            color = "#184b61" if self.metric == "duration" else "#36562d"
        # Override only the background; preserve cursor styling and click metadata.
        tinted = Strip(
            [
                Segment(
                    segment.text,
                    (segment.style or Style())
                    + Style(
                        bgcolor=color, color="white" if state == "loading" else None
                    ),
                    segment.control,
                )
                for segment in strip.crop(0, width)
            ]
        )
        return Strip.join([tinted, strip.crop(width)])
