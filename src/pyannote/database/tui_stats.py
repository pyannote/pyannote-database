"""Subset summaries for the interactive browser."""

import math
from collections import Counter

from pyannote.core import Annotation, Timeline
from rich.console import Group
from rich.rule import Rule
from rich.text import Text

from pyannote.database.registry import Registry


def speaker_count_durations(annotation):
    """Duration with exactly N distinct speakers (annotation already cropped)."""
    events = Counter()
    for label in annotation.labels():
        # Merge each speaker's tracks before counting simultaneous speakers.
        for segment in annotation.label_timeline(label).support():
            events[segment.start] += 1
            events[segment.end] -= 1
    durations = Counter()
    active = 0
    previous = None
    for timestamp, change in sorted(events.items()):
        if previous is not None and active and timestamp > previous:
            durations[active] += timestamp - previous
        active += change
        previous = timestamp
    return durations


DURATION_BIN_SECONDS = 300


def summarize_files(files, diarization=False):
    result = dict(
        files=0,
        measured=0,
        annotated=0.0,
        speech=0.0,
        overlap=0.0,
        speakers=Counter(),
        errors=[],
        conversation_durations=Counter(),
        conversation_speakers=Counter(),
        duration_sources=Counter(),
        duration_values=[],
    )
    for file in files:
        result["files"] += 1
        if not diarization:
            continue
        duration = None
        try:
            candidate = file.get("duration")
            if (
                candidate is not None
                and math.isfinite(float(candidate))
                and float(candidate) >= 0
            ):
                duration = float(candidate)
                result["duration_sources"]["declared"] += 1
        except (KeyError, TypeError, ValueError, OSError):
            pass
        if duration is not None:
            result["conversation_durations"][int(duration // DURATION_BIN_SECONDS)] += 1
            result["duration_values"].append(duration)
        try:
            annotated = file["annotated"]
            if duration is None and isinstance(annotated, Timeline):
                duration = annotated.support().duration()
                result["conversation_durations"][
                    int(duration // DURATION_BIN_SECONDS)
                ] += 1
                result["duration_sources"]["annotated"] += 1
                result["duration_values"].append(duration)
            annotation = file["annotation"]
            if not isinstance(annotation, Annotation) or not isinstance(
                annotated, Timeline
            ):
                raise ValueError("Missing annotation or annotated regions")
            annotated = annotated.support()
            annotation = annotation.crop(annotated)
            durations = speaker_count_durations(annotation)
            result["annotated"] += annotated.duration()
            result["speakers"].update(durations)
            result["speech"] += sum(durations.values())
            result["overlap"] += sum(
                value for count, value in durations.items() if count >= 2
            )
            result["measured"] += 1
            result["conversation_speakers"][len(annotation.labels())] += 1
        except Exception as error:
            if len(result["errors"]) < 3:
                result["errors"].append(str(error))
    return result


def iter_protocol_statistics(registry, name, subsets=None):
    """Yield after each file so a scheduler can pause without losing work."""
    protocol = registry.get_protocol(name)
    summaries = {}
    if subsets is None:
        subsets = (
            ("files",) if ".Collection." in name else ("train", "development", "test")
        )
    for index, subset in enumerate(subsets):
        yield summaries, f"Opening {subset} annotations…", index, len(subsets)
        try:
            result = summarize_files([])
            summaries[subset] = result
            for file in getattr(protocol, subset)():
                item = summarize_files([file], ".SpeakerDiarization." in name)
                for key in ("files", "measured", "annotated", "speech", "overlap"):
                    result[key] += item[key]
                for key in (
                    "speakers",
                    "conversation_durations",
                    "conversation_speakers",
                    "duration_sources",
                ):
                    result[key].update(item[key])
                result["duration_values"].extend(item["duration_values"])
                result["errors"] = (result["errors"] + item["errors"])[:3]
                yield (
                    summaries,
                    f"{subset}: {result['files']} files processed",
                    index,
                    len(subsets),
                )
        except (NotImplementedError, AttributeError):
            summaries.pop(subset, None)
        except Exception as error:
            summaries[subset] = {"error": str(error)}
        yield summaries, f"{subset} complete", index + 1, len(subsets)
    return summaries


class SubsetStatisticsJob:
    """Pause and resume each subset independently at file boundaries."""

    def __init__(self, registry, name, subsets):
        self.registry = registry
        self.name = name
        self.subsets = tuple(subsets)
        self.iterators = {}
        self.completed = set()
        self.summaries = {}

    def advance(self, preferred=None):
        pending = [subset for subset in self.subsets if subset not in self.completed]
        if not pending:
            return None
        subset = preferred if preferred in pending else pending[0]
        if subset not in self.iterators:
            self.iterators[subset] = iter_protocol_statistics(
                self.registry, self.name, subsets=(subset,)
            )
        try:
            update = next(self.iterators[subset], None)
        except Exception as error:
            self.summaries[subset] = {"error": str(error)}
            update = None
        if update is None:
            self.completed.add(subset)
            self.iterators.pop(subset, None)
            message = f"{subset} complete"
            if len(self.completed) == len(self.subsets):
                return None
        else:
            summaries, message, _, _ = update
            self.summaries.update(summaries)
        return self.summaries, message, len(self.completed), len(self.subsets)


def protocol_statistics(path, name):
    if isinstance(path, Registry):
        registry = path
    else:
        registry = Registry()
        registry.load_database(path)
    summaries = {}
    for summaries, *_ in iter_protocol_statistics(registry, name):
        pass
    return summaries


OVERLAP_COLORS = ("magenta", "cyan", "yellow", "bright_red", "bright_blue")


def speaker_color(count):
    return OVERLAP_COLORS[(count - 2) % len(OVERLAP_COLORS)]


def overlap_counts(summaries):
    return sorted(
        {
            count
            for stats in summaries.values()
            for count in stats.get("speakers", {})
            if count >= 2
        }
    )


class StackedDurationBar:
    """Render proportional segments at the actual available terminal width."""

    def __init__(self, segments, captions=None):
        self.captions = captions
        self.segments = [(max(0, value), color) for value, color in segments]

    def __rich_console__(self, console, options):
        width = max(0, options.max_width)
        total = sum(value for value, _ in self.segments)
        if not total or not width:
            yield Text("")
            return
        exact = [width * value / total for value, _ in self.segments]
        sizes = [int(value) for value in exact]
        # Largest remainder allocation fills the width without rounding drift.
        for index in sorted(
            range(len(sizes)), key=lambda i: exact[i] - sizes[i], reverse=True
        )[: width - sum(sizes)]:
            sizes[index] += 1
        if self.captions is None:
            bar = Text(no_wrap=True)
            for size, (_, color) in zip(sizes, self.segments):
                bar.append("█" * size, style=color)
            yield bar
            return

        labels = Text(no_wrap=True)
        durations = Text(no_wrap=True)
        below = Text()
        for size, (value, color), caption in zip(sizes, self.segments, self.captions):
            label, separator, detail = caption.partition(" (")
            detail = detail.removesuffix(")") if separator else ""
            fits = size >= len(label) + 2
            detail_fits = fits and size >= len(detail) + 2
            # Background bands keep the proportions visible behind readable text.
            style = f"bold black on {color}"
            labels.append(label.center(size) if fits else " " * size, style=style)
            durations.append(
                detail.center(size) if detail_fits else " " * size,
                style=f"black on {color}",
            )
            if value > 0 and not (fits and detail_fits):
                if below.plain:
                    below.append("   ")
                below.append("■ ", style=color)
                below.append(caption, style=color)
        yield labels
        yield durations
        if below.plain:
            yield below


def format_duration(seconds):
    if seconds >= 3600:
        return f"{seconds / 3600:.2f}".rstrip("0").rstrip(".") + "h"
    if seconds >= 60:
        return f"{seconds / 60:.1f}".rstrip("0").rstrip(".") + "min"
    if 0 < seconds < 0.1:
        return "<0.1s"
    return f"{seconds:.1f}s"


class DistributionHistogram:
    """Vertical count histogram; continue wide ranges on additional panels."""

    def __init__(self, rows, axis="", center_ticks=False):
        self.rows = rows
        self.axis = axis
        self.center_ticks = center_ticks

    def __rich_console__(self, console, options):
        maximum = max((count for _, count in self.rows), default=0)
        step = max(1, math.ceil(maximum / 6))
        height = max(1, math.ceil(maximum / step))
        ceiling = height * step
        gutter = len(str(ceiling)) + 2
        available = max(2, options.max_width - gutter)
        capacity = max(1, available // max(3, len(str(maximum)) + 1))
        for offset in range(0, len(self.rows), capacity):
            rows = self.rows[offset : offset + capacity]
            cell = max(2, available // len(rows))
            if len(self.rows) > capacity:
                yield Text(f"{rows[0][0]}–{rows[-1][0]} (continued range)", style="dim")
            yield Text("Conversations", style="dim")
            for level in range(height, 0, -1):
                line = Text(f"{level * step:>{gutter - 2}} │")
                for _, count in rows:
                    fraction = max(0, min(1, count / step - (level - 1)))
                    blocks = " ▁▂▃▄▅▆▇█"
                    block = blocks[min(8, math.ceil(fraction * 8))]
                    label_level = max(1, min(height, math.floor(count / step)))
                    if 0 < count < step and level == 2:
                        # The fractional bar occupies row 1; label it in the
                        # immediately adjacent row, centered over its width.
                        line.append(str(count).center(cell - 1), style="bold cyan")
                        line.append(" ")
                    elif count >= step and level == label_level:
                        line.append(
                            str(count).center(cell - 1), style="bold black on cyan"
                        )
                        line.append(" ")
                    else:
                        line.append(block * (cell - 1) + " ", style="cyan")
                yield line
            yield Text(" " * (gutter - 2) + "0└" + "─" * (cell * len(rows)))
            ticks = [" "] * (cell * len(rows))
            next_free = 0
            for index, (label, _) in enumerate(rows):
                start = index * cell
                if self.center_ticks:
                    start += max(0, (cell - 1 - len(label)) // 2)
                if start >= next_free and start + len(label) <= len(ticks):
                    ticks[start : start + len(label)] = label
                    next_free = start + len(label) + 1
            yield Text(" " * gutter + "".join(ticks))
            yield Text(self.axis, style="dim")


def render_distributions(stats):
    durations = stats.get("conversation_durations", {})
    speakers = stats.get("conversation_speakers", {})
    sources = stats.get("duration_sources", {})
    sections = []
    if durations:
        values = stats.get("duration_values", [])
        longest = max(values, default=600)
        bin_seconds = (
            1 if longest < 10 else 10 if longest < 60 else 60 if longest < 600 else 300
        )
        if values:
            durations = Counter(int(value // bin_seconds) for value in values)
        unit = "seconds" if bin_seconds < 60 else "minutes"
        step = bin_seconds if bin_seconds < 60 else bin_seconds // 60
        sections.append(
            Text(
                f"\nConversation duration · {sum(durations.values())} files",
                style="bold",
            )
        )
        sections.append(
            DistributionHistogram(
                [
                    (str(index * step), durations.get(index, 0))
                    for index in range(max(durations) + 1)
                ],
                axis=f"Duration ({unit}) · {step}-{unit[:-1]} bins [start, start + {step})",
            )
        )
        sections.append(
            Text(
                f"{sources.get('declared', 0)} declared durations · "
                f"{sources.get('annotated', 0)} annotated-duration fallbacks",
                style="dim",
            )
        )
    if speakers:
        sections.append(
            Text(
                f"\nSpeakers per conversation · {sum(speakers.values())} files",
                style="bold",
            )
        )
        sections.append(
            DistributionHistogram(
                [
                    (str(count), speakers.get(count, 0))
                    for count in range(max(speakers) + 1)
                ],
                axis="Number of distinct speakers",
                center_ticks=True,
            )
        )
        sections.append(
            Text(
                "Distinct speakers in annotated regions · bars count files", style="dim"
            )
        )
    return Group(*sections)


def render_legend(summaries):
    legend = Text()
    legend.append("■ Non-speech", style="grey50")
    legend.append("  ")
    legend.append("■ 1 speaker", style="green")
    for count in overlap_counts(summaries):
        legend.append("  ")
        legend.append(f"■ {count} speakers", style=speaker_color(count))
    legend.append("\nSpeech includes overlap · % of annotated time")
    return legend


def render_statistics(name, summaries):
    sections = [Text(name, style="bold")]
    counts = overlap_counts(summaries)
    count_colors = {count: speaker_color(count) for count in counts}
    for subset, stats in summaries.items():
        sections.append(Text(subset.upper(), style="bold"))
        if "error" in stats:
            sections.append(Text(stats["error"], style="red"))
            continue
        total = stats["annotated"]

        def duration(value):
            return f"{format_duration(value)} · {value / total:.1%}" if total else "—"

        measured = stats["measured"]
        content = [
            Rule("Time-based", style="bold"),
            Text(
                f"{measured}/{stats['files']} files with usable annotations",
                style="dim",
            ),
        ]
        content.append(
            Text(
                f"Annotated {format_duration(total)} · Speech {format_duration(stats['speech'])}"
                f"\nOverlapping speech {format_duration(stats['overlap'])}"
                if measured
                else "No usable annotations yet."
            )
        )
        if total:
            values = [max(0, total - stats["speech"]), stats["speakers"].get(1, 0)]
            values.extend(stats["speakers"].get(count, 0) for count in counts)
            colors = ["grey50", "green", *(count_colors[count] for count in counts)]
            labels = [
                "Non-speech",
                "1 speaker",
                *(f"{count} speakers" for count in counts),
            ]
            captions = [
                f"{label} ({duration(value)})" for label, value in zip(labels, values)
            ]
            content.append(StackedDurationBar(list(zip(values, colors)), captions))
        content.extend(
            [
                Text(""),
                Rule("Conversation-based", style="bold"),
                Text(
                    f"{stats['files']} conversations · one file per conversation",
                    style="bold",
                ),
                render_distributions(stats),
            ]
        )
        if not stats.get("conversation_durations") and not stats.get(
            "conversation_speakers"
        ):
            content.append(
                Text("Distributions unavailable until metadata is loaded.", style="dim")
            )
        for error in stats["errors"]:
            content.append(Text(error, style="yellow"))
        sections.extend(content)
        sections.append(Text(""))
    return Group(
        *sections,
        Text(
            "Measured = files with usable annotations; unavailable files are excluded.\n"
            "Annotated regions follow the protocol, including its inferred bounds."
        ),
    )
