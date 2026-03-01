import math
from collections import Counter
from pathlib import Path
from typing import Optional

from textual.app import App, ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.reactive import reactive
from textual import events, work
from textual.widgets import Header, Footer, Label, ListItem, ListView, Static
from textual.worker import get_current_worker

from pyannote.database import registry as _registry
from pyannote.database.protocol import CollectionProtocol, SpeakerDiarizationProtocol
from pyannote.core import Annotation


def _duration_to_str(seconds: float) -> str:
    hours = math.floor(seconds / 3600)
    minutes = math.floor((seconds - 3600 * hours) / 60)
    return f"{hours}h{minutes:02d}m"


_COUNT_COLORS = ["green", "yellow", "orange1", "red", "magenta"]
_WINDOW_DURATIONS = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0]


def _speaker_color(n: int) -> str:
    """Rich color name for N simultaneous speakers (n >= 1)."""
    return _COUNT_COLORS[min(n - 1, len(_COUNT_COLORS) - 1)]


def _sweep_speaker_counts(annotation: Annotation) -> Counter:
    """Sweep-line: return Counter mapping simultaneous speaker count → duration."""
    events: list[tuple[float, int]] = []
    for segment, _, _ in annotation.itertracks(yield_label=True):
        events.append((segment.start, +1))
        events.append((segment.end, -1))
    # At equal times: process ends (-1) before starts (+1) so simultaneous
    # handoffs don't create spurious overlap.
    events.sort(key=lambda x: (x[0], x[1]))

    count_dur: Counter = Counter()
    current_count = 0
    prev_time: float | None = None

    for time, delta in events:
        if prev_time is not None and time > prev_time and current_count > 0:
            count_dur[current_count] += time - prev_time
        current_count += delta
        prev_time = time

    return count_dur


def _sliding_window_speaker_dist(
    annotation: Annotation, annotated: "Timeline", window: float = 20.0
) -> Counter:
    """Distinct-speaker count distribution over a sliding window.

    For each valid window start position t (i.e. [t, t+window] ⊆ an annotated
    segment), counts how many distinct speakers have any speech in [t, t+window].

    Uses a sweep-line over per-speaker *presence intervals*: speaker X is
    present for window start t iff X has a speech segment [a, b] with
    a − window ≤ t ≤ b, so each speech segment maps to presence interval
    [a − window, b] clipped to valid window-start positions.

    Returns Counter: distinct_speaker_count → total duration.
    """
    # Build per-speaker segment list
    speaker_segs: dict = {}
    for seg, _, label in annotation.itertracks(yield_label=True):
        speaker_segs.setdefault(label, []).append(seg)

    count_dur: Counter = Counter()

    for ann_seg in annotated:
        t_start = ann_seg.start
        t_end = ann_seg.end - window
        if t_end <= t_start:
            continue  # annotated segment shorter than window

        events: list[tuple[float, int]] = []
        for segs in speaker_segs.values():
            # Compute and merge presence intervals for this speaker
            presence = []
            for seg in segs:
                ps = max(t_start, seg.start - window)
                pe = min(t_end, seg.end)
                if ps < pe:
                    presence.append([ps, pe])
            if not presence:
                continue
            presence.sort()
            merged = [presence[0][:]]
            for ps, pe in presence[1:]:
                if ps <= merged[-1][1]:
                    merged[-1][1] = max(merged[-1][1], pe)
                else:
                    merged.append([ps, pe])
            for ps, pe in merged:
                events.append((ps, +1))
                events.append((pe, -1))

        if not events:
            count_dur[0] += t_end - t_start
            continue

        # Ends before starts at equal times → no spurious handoff overlap
        events.sort(key=lambda x: (x[0], x[1]))

        current_count = 0
        prev_time = t_start
        i = 0
        while i < len(events):
            t, delta = events[i]
            if t >= t_end:
                break
            if t > prev_time:
                count_dur[current_count] += t - prev_time
                prev_time = t
            while i < len(events) and events[i][0] == t:
                current_count += events[i][1]
                i += 1
        if prev_time < t_end:
            count_dur[current_count] += t_end - prev_time

    return count_dur


def _render_bar(items: list[tuple[str, str, float]], total: float, bar_width: int) -> str:
    """Single-line colored bar using proportional cumulative rounding.

    items: list of (color, fill_char, duration)
    """
    parts = []
    cumulative = 0.0
    for color, char, dur in items:
        cumulative_new = cumulative + bar_width * dur / total
        n_chars = round(cumulative_new) - round(cumulative)
        cumulative = cumulative_new
        if n_chars > 0:
            parts.append(f"[{color}]{char * n_chars}[/{color}]")
    return "".join(parts)


def _compute_subset_content(protocol_name: str, subset: str, panel_width: int = 50) -> str:
    """Compute stats for one subset of a protocol. Runs in a thread."""
    p = _registry.get_protocol(protocol_name)

    if isinstance(p, SpeakerDiarizationProtocol):
        skip_annotation = False
        skip_annotated = False
    elif isinstance(p, CollectionProtocol):
        skip_annotation = True
        skip_annotated = True
    else:
        return f"[red]Unsupported: {type(p).__name__}[/red]"

    num_files = 0
    speakers: set = set()
    duration = 0.0
    count_dur: Counter = Counter()    # simultaneous speaker count → total duration
    window_dists: dict[float, Counter] = {w: Counter() for w in _WINDOW_DURATIONS}
    speakers_per_file: list[int] = []

    try:
        for file in getattr(p, subset)():
            num_files += 1
            annotation = None
            if not skip_annotation:
                annotation = file.get("annotation") or Annotation(uri=file["uri"])
                file_speakers = annotation.labels()
                speakers.update(file_speakers)
                speakers_per_file.append(len(file_speakers))
                count_dur += _sweep_speaker_counts(annotation)
            if not skip_annotated:
                ann = file["annotated"]
                duration += ann.duration()
                if annotation is not None:
                    for _w in _WINDOW_DURATIONS:
                        window_dists[_w] += _sliding_window_speaker_dist(annotation, ann, _w)
    except (AttributeError, NotImplementedError):
        return ""

    if num_files == 0:
        return ""

    speech = sum(count_dur.values())

    lines = []

    # One-line stats header
    header = f"   {num_files} files"
    if not skip_annotated:
        header += f" / {_duration_to_str(duration)}"
    lines.append(header)

    # Speakers / file histogram
    if speakers_per_file:
        dist = Counter(speakers_per_file)
        max_count = max(dist.values())
        spk_values = sorted(dist.keys())
        col_width = max(3, len(str(max(spk_values))) + 1)
        bar_w = col_width - 1
        chart_height = 6
        bar_heights = {s: max(1, round(chart_height * dist[s] / max_count)) for s in spk_values}
        lines.append("")
        lines.append("   Number of speakers per file")
        for row in range(chart_height):
            threshold = chart_height - row
            parts = []
            for s in spk_values:
                if bar_heights[s] >= threshold:
                    parts.append(f"[blue]{'█' * bar_w}[/blue] ")
                else:
                    parts.append(" " * col_width)
            lines.append(f"   {''.join(parts)}")
        lines.append(f"   {'─' * (col_width * len(spk_values))}")
        lines.append(f"   {''.join(str(s).ljust(col_width) for s in spk_values)}")

    # Speakers in sliding window
    if any(window_dists[w] for w in _WINDOW_DURATIONS):
        bar_width = max(10, panel_width - 13)
        all_counts: set[int] = set()
        for w in _WINDOW_DURATIONS:
            all_counts.update(window_dists[w].keys())
        lines.append("")
        lines.append("   Number of speakers per window")
        for w in _WINDOW_DURATIONS:
            window_dist = window_dists[w]
            total_wd = sum(window_dist.values())
            if not total_wd:
                continue
            items = [
                ("dim" if n == 0 else _speaker_color(n), "░" if n == 0 else "█", window_dist[n])
                for n in sorted(window_dist.keys())
            ]
            lines.append(f"   {int(w):2d}s {_render_bar(items, total_wd, bar_width)}")
        legend_parts = [
            f"[{'dim' if n == 0 else _speaker_color(n)}]≤{n}spk[/{'dim' if n == 0 else _speaker_color(n)}]"
            for n in sorted(all_counts)
        ]
        lines.append(f"       {'  '.join(legend_parts)}")

    # Simultaneous speakers duration bar (last)
    if not skip_annotation and not skip_annotated and duration > 0:
        silence_dur = duration - speech
        items = [("dim", "░", silence_dur)]
        for n in sorted(count_dur):
            items.append((_speaker_color(n), "█", count_dur[n]))
        bar_width = max(10, panel_width - 9)
        legend_parts = []
        if 100 * silence_dur / duration >= 0.5:
            legend_parts.append("[dim]silence[/dim]")
        for n in sorted(count_dur):
            if 100 * count_dur[n] / duration >= 0.5:
                legend_parts.append(f"[{_speaker_color(n)}]{n}spk[/{_speaker_color(n)}]")
        lines.append("")
        lines.append("   Number of simultaneous speakers")
        lines.append(f"   {_render_bar(items, duration, bar_width)}")
        lines.append(f"   {'  '.join(legend_parts)}")

    return "\n".join(lines)


class DatabaseList(ListView):
    def __init__(self, databases: list[str], **kwargs):
        super().__init__(**kwargs)
        self._databases = databases

    def compose(self) -> ComposeResult:
        for db in self._databases:
            yield ListItem(Label(db), name=db)

    def on_key(self, event: events.Key) -> None:
        if event.key == "right":
            target = self.app.query_one(ProtocolList)
            target.focus()
            target.index = None
            if target.query(ListItem):
                target.index = 0
            event.stop()

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        if event.item is None:
            return
        db_name = event.item.name
        self.app.query_one(ProtocolList).database = db_name
        db = _registry.get_database(db_name)
        protocols = [
            f"{db_name}.{task}.{protocol}"
            for task in db.get_tasks()
            for protocol in db.get_protocols(task)
        ]
        for panel in self.app.query(SubsetPanel):
            panel.protocol = None
            panel.preload(protocols)


class ProtocolList(ListView):
    database: reactive[Optional[str]] = reactive(None, recompose=True)

    def compose(self) -> ComposeResult:
        if self.database is None:
            return
        db = _registry.get_database(self.database)
        for task in db.get_tasks():
            for protocol in db.get_protocols(task):
                full_name = f"{self.database}.{task}.{protocol}"
                yield ListItem(Label(f"{task} / {protocol}"), name=full_name)

    def on_key(self, event: events.Key) -> None:
        if event.key == "left":
            target = self.app.query_one(DatabaseList)
            target.focus()
            target.index = None
            if target.query(ListItem):
                target.index = 0
            event.stop()

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        if event.item is None:
            return
        for panel in self.app.query(SubsetPanel):
            panel.protocol = event.item.name


class SubsetPanel(VerticalScroll):
    protocol: reactive[Optional[str]] = reactive(None, init=False)

    def __init__(self, subset: str, **kwargs):
        super().__init__(**kwargs)
        self._subset = subset
        self._cache: dict[tuple[str, int], str] = {}

    def on_mount(self) -> None:
        self.border_title = self._subset

    def compose(self) -> ComposeResult:
        yield Static(classes="subset-content")

    def watch_protocol(self, protocol: Optional[str]) -> None:
        content_widget = self.query_one(".subset-content", Static)
        if protocol is None:
            content_widget.update("")
            return
        width = self.size.width
        if (protocol, width) in self._cache:
            content_widget.update(self._cache[(protocol, width)])
            return
        content_widget.update("Loading...")
        self._fetch_stats(protocol, width)

    def preload(self, protocol_names: list[str]) -> None:
        self._preload_stats(protocol_names, self.size.width)

    @work(thread=True, exclusive=True, group="active")
    def _fetch_stats(self, protocol_name: str, panel_width: int) -> None:
        content = _compute_subset_content(protocol_name, self._subset, panel_width)
        self._cache[(protocol_name, panel_width)] = content
        self.app.call_from_thread(self._show_if_current, protocol_name, panel_width, content)

    @work(thread=True, exclusive=True, group="preload")
    def _preload_stats(self, protocol_names: list[str], panel_width: int) -> None:
        worker = get_current_worker()
        for protocol_name in protocol_names:
            if worker.is_cancelled:
                break
            if (protocol_name, panel_width) in self._cache:
                continue
            content = _compute_subset_content(protocol_name, self._subset, panel_width)
            self._cache[(protocol_name, panel_width)] = content
            self.app.call_from_thread(self._show_if_current, protocol_name, panel_width, content)

    def _show_if_current(self, protocol_name: str, panel_width: int, content: str) -> None:
        if self.protocol == protocol_name and self.size.width == panel_width:
            self.query_one(".subset-content", Static).update(content)


class RegistryApp(App):
    CSS_PATH = "tui.tcss"
    TITLE = "pyannote.database"
    BINDINGS = [("q", "quit", "Quit")]

    def __init__(self, registry_path: Optional[Path] = None, **kwargs):
        super().__init__(**kwargs)
        if registry_path is not None:
            _registry.load_database(registry_path)
        self._databases = list(_registry.databases)

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="top-row"):
            yield DatabaseList(self._databases, id="databases")
            yield ProtocolList(id="protocols")
        with Horizontal(id="bottom-row"):
            yield SubsetPanel("train", id="train")
            yield SubsetPanel("development", id="development")
            yield SubsetPanel("test", id="test")
        yield Footer()
