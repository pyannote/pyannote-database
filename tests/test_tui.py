"""Headless interaction tests for the optional configuration browser."""

import asyncio
from pathlib import Path

import pytest

pytest.importorskip("textual")

from textual.widgets import Tree
from typer.testing import CliRunner

from pyannote.database.cli import app
from pyannote.database.tui import DatabaseBrowser


@pytest.fixture(autouse=True)
def fast_preload_delays(monkeypatch):
    monkeypatch.setattr(DatabaseBrowser, "STARTUP_PRELOAD_DELAY", 0.01)
    monkeypatch.setattr(DatabaseBrowser, "IDLE_PRELOAD_DELAY", 0.001)


def test_navigation_and_reload(tmp_path):
    path = tmp_path / "database.yml"
    path.write_text(
        "Protocols:\n  Example:\n    Collection:\n      Sample:\n        uri: files.lst\n"
    )
    browser = DatabaseBrowser(path)

    async def exercise():
        async with browser.run_test() as pilot:
            tree = browser.query_one(Tree)
            await pilot.press("down", "space", "down")
            assert tree.cursor_node.data == {"Task": "Collection"}
            path.write_text("Databases:\n  Example: audio/{uri}.wav\n")
            await pilot.press("r")
            assert browser.document == {"Databases": {"Example": "audio/{uri}.wav"}}
            path.write_text("[invalid")
            await pilot.press("r")
            assert "Databases" in browser.document
            await pilot.press("q")

    asyncio.run(exercise())


def test_example_configuration():
    browser = DatabaseBrowser(Path(__file__).parent / "data" / "database.yml")

    async def exercise():
        async with browser.run_test():
            assert "MyDatabase" in browser.document["Protocols"]

    asyncio.run(exercise())


@pytest.mark.parametrize("content", ["", "- item", "[invalid"])
def test_invalid_configuration(tmp_path, content):
    path = tmp_path / "database.yml"
    path.write_text(content)
    result = CliRunner().invoke(app, ["browse", str(path)])
    assert result.exit_code == 1
    assert "Cannot open" in result.output


def test_missing_configuration(tmp_path):
    result = CliRunner().invoke(app, ["browse", str(tmp_path / "missing.yml")])
    assert result.exit_code == 1
    assert "Cannot open" in result.output


def test_speech_statistics():
    from pyannote.core import Annotation, Segment, Timeline

    from pyannote.database.tui_stats import summarize_files

    annotation = Annotation()
    annotation[Segment(-2, 6), "a"] = "alice"
    annotation[Segment(4, 8), "b"] = "bob"
    # Same-speaker tracks must not count as overlapping speakers.
    annotation[Segment(1, 3), "c"] = "alice"
    stats = summarize_files(
        [
            {"annotation": annotation, "annotated": Timeline([Segment(0, 10)])},
            {"annotation": None, "annotated": Timeline([Segment(0, 10)])},
        ],
        diarization=True,
    )
    assert stats["files"] == 2
    assert stats["measured"] == 1
    assert stats["annotated"] == 10
    assert stats["speech"] == 8
    assert stats["overlap"] == 2
    assert stats["errors"]


def test_protocol_statistics():
    from pyannote.database.tui_stats import protocol_statistics, render_statistics

    summaries = protocol_statistics(
        Path(__file__).parent / "data" / "database.yml",
        "MyDatabase.SpeakerDiarization.MySpeakerDiarization",
    )
    assert summaries["train"]["files"] > 0
    assert summaries["train"]["measured"] == summaries["train"]["files"]
    assert render_statistics("Example", summaries)


def test_exact_speaker_counts():
    from io import StringIO

    from pyannote.core import Annotation, Segment, Timeline
    from rich.console import Console

    from pyannote.database.tui_stats import render_statistics, summarize_files

    annotation = Annotation()
    annotation[Segment(-1, 6), "a"] = "alice"
    annotation[Segment(1, 4), "duplicate"] = "alice"
    annotation[Segment(2, 6), "b"] = "bob"
    annotation[Segment(3, 5), "c"] = "charlie"
    annotation[Segment(4, 5), "d"] = "dana"
    # A simultaneous end/start must not create a spurious overlap.
    annotation[Segment(6, 7), "e"] = "eve"
    file = {"annotation": annotation, "annotated": Timeline([Segment(0, 8)])}
    stats = summarize_files([file, file], diarization=True)
    assert stats["speakers"] == {1: 6, 2: 4, 3: 2, 4: 2}
    assert stats["speech"] == 14
    assert stats["overlap"] == 8
    assert stats["annotated"] == 16
    output = StringIO()
    Console(file=output, width=120, color_system=None).print(
        render_statistics("Example", {"train": stats})
    )
    assert "4 speakers" in output.getvalue()
    assert "2.0s · 12.5%" in output.getvalue()


def test_requirements_provenance_and_reload(tmp_path):
    child = tmp_path / "child.yml"
    child.write_text(
        "Protocols:\n  Example:\n    Collection:\n      Sample:\n        uri: files.lst\n"
    )
    root = tmp_path / "database.yml"
    root.write_text("Requirements: child.yml\n")
    browser = DatabaseBrowser(root)
    name = "Example.Collection.Sample"
    assert browser.registry.get_protocol(name).database_yml == child

    async def exercise():
        async with browser.run_test() as pilot:
            assert (name, child) in browser.node_paths.values()
            root.write_text(
                "Requirements: child.yml\nProtocols:\n  Example:\n    Collection:\n      Sample:\n        uri: replacement.lst\n"
            )
            with pytest.warns(UserWarning, match="Replacing existing"):
                await pilot.press("r")
            assert browser.registry.get_protocol(name).database_yml == root
            assert (name, root) in browser.node_paths.values()
            child.unlink()
            await pilot.press("r")
            # A failed requirements reload preserves the previous registry.
            assert browser.registry.get_protocol(name).database_yml == root

    asyncio.run(exercise())


def test_protocol_selection_shows_statistics():
    from io import StringIO

    from rich.console import Console
    from textual.widgets import Static, TabbedContent

    browser = DatabaseBrowser(Path(__file__).parent / "data" / "database.yml")

    async def exercise():
        async with browser.run_test(size=(100, 35)) as pilot:
            tree = browser.query_one(Tree)
            node = next(
                n
                for db in tree.root.children
                for task in db.children
                for n in task.children
                if str(n.label).startswith("MySpeakerDiarization ")
            )
            node.parent.parent.expand()
            node.parent.expand()
            await pilot.pause()
            tree.move_cursor(node)
            await pilot.pause()
            await browser.workers.wait_for_complete()
            assert browser.query_one(TabbedContent).active == "statistics-tab"
            assert browser.statistics_cache
            assert browser.query_one("#statistics", Static).display
            from pyannote.database.tui_stats import render_statistics

            name = "MyDatabase.SpeakerDiarization.MySpeakerDiarization"
            summaries = browser.statistics_cache[name]
            output = StringIO()
            Console(file=output, width=50).print(render_statistics(name, summaries))
            assert "1 speaker" in output.getvalue()
            assert "Overlapping speech" in output.getvalue()

    asyncio.run(exercise())


def test_disk_statistics_cache(tmp_path):
    import os
    import time

    from pyannote.database.registry import Registry
    from pyannote.database.tui_cache import StatisticsCache
    from pyannote.database.tui_stats import summarize_files

    config = tmp_path / "database.yml"
    config.write_text("{}")
    registry = Registry()
    registry.load_database(config)
    cache = StatisticsCache(registry, tmp_path / "cache")
    summaries = {"train": summarize_files([])}
    summaries["train"]["speakers"][2] = 3.0
    cache.put("Example", summaries)
    assert cache.get("Example") == summaries
    assert StatisticsCache(registry, tmp_path / "cache").get("Example") == summaries
    config.write_text("Databases: {}")
    assert StatisticsCache(registry, tmp_path / "cache").get("Example") is None
    expired = time.time() - cache.MAX_AGE - 1
    os.utime(cache.path("Example"), (expired, expired))
    assert cache.get("Example") is None
    cache.path("Example").write_text("invalid json")
    assert cache.get("Example") is None


def test_statistics_priority_and_resume(monkeypatch, tmp_path):
    import threading

    from pyannote.database import tui_stats

    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    started = threading.Event()
    release = threading.Event()
    calls = []

    def steps(registry, name, subsets=None):
        calls.append((name, 1))
        if name == "first":
            started.set()
            release.wait(timeout=5)
        yield {"train": tui_stats.summarize_files([])}, "one file", 0, 1
        calls.append((name, 2))
        yield {"train": tui_stats.summarize_files([])}, "done", 1, 1

    monkeypatch.setattr(tui_stats, "iter_protocol_statistics", steps)
    browser = DatabaseBrowser(Path(__file__).parent / "data" / "database.yml")

    browser.preload_enabled = False

    async def exercise():
        async with browser.run_test() as pilot:
            browser.load_statistics(("first",))
            assert await asyncio.to_thread(started.wait, 3)
            browser.load_statistics(("second",))
            release.set()
            await browser.workers.wait_for_complete()
            assert calls == [("first", 1), ("second", 1), ("second", 2)]
            assert "second" in browser.statistics_cache
            assert "first" not in browser.statistics_cache
            browser.load_statistics(("first",))
            await browser.workers.wait_for_complete()
            assert calls[-1] == ("first", 2)
            assert calls.count(("first", 1)) == 1
            assert "first" in browser.statistics_cache
            browser.load_statistics(("first",))
            await pilot.pause()
            assert len(calls) == 4

    try:
        asyncio.run(exercise())
    finally:
        release.set()


@pytest.mark.parametrize("width", [17, 51, 100])
def test_stacked_bar_fills_width(width):
    from io import StringIO

    from rich.console import Console

    from pyannote.database.tui_stats import StackedDurationBar

    output = StringIO()
    Console(file=output, width=width, color_system=None).print(
        StackedDurationBar([(1, "grey50"), (2, "green"), (0.1, "magenta")])
    )
    assert output.getvalue().rstrip("\n") == "█" * width


def test_legend_stays_visible_when_scrolling():
    from textual.containers import VerticalScroll
    from textual.widgets import Static

    browser = DatabaseBrowser(Path(__file__).parent / "data" / "database.yml")

    async def exercise():
        async with browser.run_test(size=(100, 30)) as pilot:
            browser.query_one("#statistics", Static).update("detail\n" * 200)
            await pilot.pause()
            legend = browser.query_one("#legend", Static)
            before = legend.region
            browser.query_one("#statistics-scroll", VerticalScroll).scroll_end(
                animate=False
            )
            await pilot.pause()
            assert legend.region == before
            assert before.bottom <= browser.size.height
            assert before.height > 0

    asyncio.run(exercise())


@pytest.mark.parametrize(
    "seconds, expected",
    [
        (0, "0.0s"),
        (30, "30.0s"),
        (90, "1.5min"),
        (3600, "1h"),
        (37800, "10.5h"),
        (0.01, "<0.1s"),
    ],
)
def test_duration_units(seconds, expected):
    from pyannote.database.tui_stats import format_duration

    assert format_duration(seconds) == expected


def test_bar_caption_for_tiny_segment():
    from io import StringIO

    from rich.console import Console

    from pyannote.database.tui_stats import StackedDurationBar

    output = StringIO()
    Console(file=output, width=40, color_system=None).print(
        StackedDurationBar(
            [(1000, "green"), (0.01, "magenta")],
            ["1 speaker (16.7min)", "2 speakers (<0.1s)"],
        )
    )
    rendered = output.getvalue()
    lines = rendered.splitlines()
    assert "1 speaker" in lines[0]
    assert "16.7min" in lines[1]
    assert "2 speakers (<0.1s)" in "\n".join(lines[2:])
    assert "+--" not in rendered
    assert len(lines[0]) == 40


def test_wide_segment_labels_stay_inside_bar():
    from io import StringIO

    from rich.console import Console

    from pyannote.database.tui_stats import StackedDurationBar

    output = StringIO()
    Console(file=output, width=80, color_system=None).print(
        StackedDurationBar(
            [(1, "green"), (1, "magenta")],
            ["1 speaker (1h)", "2 speakers (1h)"],
        )
    )
    lines = output.getvalue().splitlines()
    assert len(lines) == 2
    assert "1 speaker" in lines[0][:40]
    assert "2 speakers" in lines[0][40:]
    assert all(len(line) == 80 for line in lines)


def test_conversation_distributions():
    from io import StringIO

    from pyannote.core import Annotation, Segment, Timeline
    from rich.console import Console

    from pyannote.database.tui_stats import render_distributions, summarize_files

    annotation = Annotation()
    annotation[Segment(0, 5), "a"] = "alice"
    annotation[Segment(1, 3), "duplicate"] = "alice"
    annotation[Segment(4, 8), "b"] = "bob"
    annotation[Segment(20, 30), "outside"] = "charlie"
    region = Timeline([Segment(0, 10)])
    stats = summarize_files(
        [
            {"annotation": annotation, "annotated": region, "duration": 3600},
            {"annotation": annotation, "annotated": region},
            {"annotation": Annotation(), "annotated": region, "duration": 60},
            {"annotation": None, "annotated": region, "duration": 7200},
        ],
        diarization=True,
    )
    assert stats["conversation_durations"] == {0: 2, 12: 1, 24: 1}
    assert stats["duration_sources"] == {"declared": 3, "annotated": 1}
    assert stats["conversation_speakers"] == {2: 2, 0: 1}
    output = StringIO()
    Console(file=output, width=50, color_system=None).print(render_distributions(stats))
    assert "Conversation duration · 4 files" in output.getvalue()
    assert "Speakers per conversation · 3 files" in output.getvalue()
    assert "█" in output.getvalue()


def test_incremental_distributions_match_batch():
    from pyannote.database.registry import Registry
    from pyannote.database.tui_stats import protocol_statistics, summarize_files

    registry = Registry()
    registry.load_database(Path(__file__).parent / "data" / "database.yml")
    name = "MyDatabase.SpeakerDiarization.MySpeakerDiarization"
    expected = summarize_files(registry.get_protocol(name).train(), diarization=True)
    assert protocol_statistics(registry, name)["train"] == expected


def test_subset_sections_are_distinct():
    from io import StringIO

    from rich.console import Console

    from pyannote.database.tui_stats import render_statistics, summarize_files

    output = StringIO()
    stats = summarize_files([])
    Console(file=output, width=60, color_system=None).print(
        render_statistics(
            "Example", {"train": stats, "development": stats, "test": stats}
        )
    )
    report = output.getvalue()
    for subset in ("TRAIN", "DEVELOPMENT", "TEST"):
        assert subset in report
    assert report.count("Time-based") == 3
    assert report.count("Conversation-based") == 3
    assert "╭" not in report
    assert "╰" not in report


def test_five_minute_bins_and_vertical_histogram():
    from io import StringIO

    from pyannote.core import Annotation, Segment, Timeline
    from rich.console import Console

    from pyannote.database.tui_stats import DistributionHistogram, summarize_files

    stats = summarize_files(
        [
            {
                "duration": duration,
                "annotation": Annotation(),
                "annotated": Timeline([Segment(0, 10)]),
            }
            for duration in (0, 299.9, 300, 599.9, 600)
        ],
        diarization=True,
    )
    assert stats["conversation_durations"] == {0: 2, 1: 2, 2: 1}
    output = StringIO()
    Console(file=output, width=40, color_system=None).print(
        DistributionHistogram([("0", 2), ("5", 2), ("10", 1)], "Duration (minutes)")
    )
    report = output.getvalue()
    assert "Conversations" in report
    assert "Duration (minutes)" in report
    assert "└" in report
    assert "0" in report and "5" in report and "10" in report
    assert all(len(line) <= 40 for line in report.splitlines())


def test_subset_navigation_shows_only_selected(tmp_path):
    from pyannote.database.tui_stats import summarize_files

    path = tmp_path / "database.yml"
    path.write_text(
        "Protocols:\n  Example:\n    SpeakerDiarization:\n      Sample:\n        train:\n          uri: train.lst\n        development:\n          uri: dev.lst\n        test:\n          uri: test.lst\n"
    )
    browser = DatabaseBrowser(path)
    name = "Example.SpeakerDiarization.Sample"
    summaries = {
        subset: summarize_files([]) for subset in ("train", "development", "test")
    }
    browser.statistics_cache[name] = summaries

    async def exercise():
        async with browser.run_test() as pilot:
            tree = browser.query_one(Tree)
            protocol = tree.root.children[0].children[0].children[0]
            protocol.parent.parent.expand()
            protocol.parent.expand()
            protocol.expand()
            await pilot.pause()
            tree.move_cursor(protocol)
            await pilot.pause()
            assert list(browser.visible_summaries(summaries)) == ["train"]
            await pilot.press("down", "down")
            assert browser.selected_subset == "development"
            assert list(browser.visible_summaries(summaries)) == ["development"]
            await pilot.press("down")
            assert list(browser.visible_summaries(summaries)) == ["test"]
            tree.move_cursor(protocol)
            await pilot.pause()
            assert list(browser.visible_summaries(summaries)) == ["train"]

    asyncio.run(exercise())


def test_speaker_ticks_center_on_bars():
    from io import StringIO

    from rich.console import Console

    from pyannote.database.tui_stats import DistributionHistogram

    output = StringIO()
    Console(file=output, width=43, color_system=None).print(
        DistributionHistogram([("1", 1), ("2", 1)], center_ticks=True)
    )
    lines = output.getvalue().splitlines()
    bars, ticks = lines[1], lines[3]
    for label in ("1", "2"):
        index = ticks.index(label)
        assert bars[index] == "1"  # count label is centered in the same bar


@pytest.mark.parametrize(
    "longest, expected",
    [(5, "1-second"), (45, "10-second"), (540, "1-minute"), (600, "5-minute")],
)
def test_adaptive_duration_histogram(longest, expected):
    from io import StringIO

    from rich.console import Console

    from pyannote.database.tui_stats import render_distributions, summarize_files

    stats = summarize_files([])
    stats["duration_values"] = [longest]
    stats["conversation_durations"] = {0: 1}
    output = StringIO()
    Console(file=output, width=100, color_system=None).print(
        render_distributions(stats)
    )
    assert expected in output.getvalue()


def test_histogram_counts_are_printed():
    from io import StringIO

    from rich.console import Console

    from pyannote.database.tui_stats import DistributionHistogram

    output = StringIO()
    Console(file=output, width=60, color_system=None).print(
        DistributionHistogram([("a", 17), ("b", 1), ("c", 4)])
    )
    lines = output.getvalue().splitlines()
    chart_rows = [line.split("│", 1)[1] for line in lines if "│" in line]
    # At width 60, each category occupies 18 columns. The short middle bar
    # occupies the last row, with its count immediately above it.
    assert chart_rows[-2][18:36].strip() == "1"
    assert "▃" in chart_rows[-1][18:36]
    assert all("1" not in row[18:36] for row in chart_rows[:-2])
    assert any("17" in line and "│" in line for line in lines)
    assert any("4" in line and "│" in line for line in lines)


def test_tree_bars_rescale_after_collapse(tmp_path, monkeypatch):
    from pyannote.database.tui_tree import StatisticsTree

    path = tmp_path / "database.yml"
    path.write_text("{}")
    browser = DatabaseBrowser(path)

    async def exercise():
        async with browser.run_test(size=(100, 35)) as pilot:
            monkeypatch.setattr(browser, "update_tree_statistics", lambda: None)
            tree = browser.query_one(StatisticsTree)
            folder = tree.root.add("Folder", expand=True)
            large = folder.add_leaf("Large")
            small = tree.root.add_leaf("Small")
            tree.metrics = {large.id: (100, 1000, False), small.id: (10, 100, False)}
            await pilot.pause()
            assert tree.visible_maximum() == 1000
            folder.collapse()
            await pilot.pause()
            assert tree.visible_maximum() == 100
            browser.action_bar_metric()
            assert tree.visible_maximum() == 10
            line = next(
                i for i in range(tree.size.height) if tree.get_node_at_line(i) is small
            )
            strip = tree.render_line(line)
            assert all(
                segment.style.bgcolor.get_truecolor().hex == "#36562d"
                for segment in strip
                if segment.text
            )

    asyncio.run(exercise())


def test_preloading_continues_and_selection_takes_priority(tmp_path, monkeypatch):
    import threading

    from pyannote.database import tui_stats

    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    config = tmp_path / "database.yml"
    config.write_text(
        "Protocols:\n  Demo:\n    Collection:\n      A: {uri: a.lst}\n      B: {uri: b.lst}\n      C: {uri: c.lst}\n"
    )
    started = threading.Event()
    release = threading.Event()
    calls = []

    def steps(registry, name, subsets=None):
        calls.append((name[-1], 1))
        if name.endswith(".A"):
            started.set()
            release.wait(timeout=5)
        yield {"files": tui_stats.summarize_files([])}, "loading", 0, 1
        calls.append((name[-1], 2))
        yield {"files": tui_stats.summarize_files([])}, "complete", 1, 1

    monkeypatch.setattr(tui_stats, "iter_protocol_statistics", steps)
    browser = DatabaseBrowser(config)

    async def exercise():
        async with browser.run_test():
            assert await asyncio.to_thread(started.wait, 3)
            browser.load_statistics(("Demo.Collection.B",), "files")
            release.set()
            await browser.workers.wait_for_complete()
            assert calls[:3] == [("A", 1), ("B", 1), ("B", 2)]
            assert set(browser.statistics_cache) == {
                "Demo.Collection.A",
                "Demo.Collection.B",
                "Demo.Collection.C",
            }
            assert calls.count(("A", 1)) == 1
            assert calls.count(("A", 2)) == 1

    try:
        asyncio.run(exercise())
    finally:
        release.set()


def test_loading_bars_grow_and_change_color_on_completion(tmp_path):
    from rich.style import Style

    from pyannote.database.tui_tree import StatisticsTree

    config = tmp_path / "database.yml"
    config.write_text("{}")
    browser = DatabaseBrowser(config)

    async def exercise():
        async with browser.run_test() as pilot:
            tree = browser.query_one(StatisticsTree)
            pending = tree.root.add_leaf("Pending")
            ready = tree.root.add_leaf("Ready")
            tree.metrics = {
                pending.id: (10, 10, "loading"),
                ready.id: (100, 100, False),
            }
            await pilot.pause()
            line = next(
                i
                for i in range(tree.size.height)
                if tree.get_node_at_line(i) is pending
            )

            def colored_width(color):
                return sum(
                    segment.cell_length
                    for segment in tree.render_line(line)
                    if segment.style
                    and segment.style.bgcolor
                    and segment.style.bgcolor.get_truecolor().hex == color
                )

            before = colored_width("#52778a")
            assert before > 0
            assert "╱" not in tree.render_line(line).text
            assert "so far" in tree.render_label(pending, Style(), Style()).plain
            tree.metrics[pending.id] = (50, 50, "loading")
            assert colored_width("#52778a") > before
            tree.metrics[pending.id] = (50, 50, False)
            assert colored_width("#52778a") == 0
            assert colored_width("#184b61") > before
            assert "so far" not in tree.render_label(pending, Style(), Style()).plain

    asyncio.run(exercise())


def test_idle_preload_is_throttled_and_selection_wakes_it(tmp_path, monkeypatch):
    import time

    from pyannote.database import tui_stats

    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    monkeypatch.setattr(DatabaseBrowser, "STARTUP_PRELOAD_DELAY", 10)
    monkeypatch.setattr(DatabaseBrowser, "IDLE_PRELOAD_DELAY", 0.1)
    config = tmp_path / "database.yml"
    config.write_text(
        "Protocols:\n  Demo:\n    Collection:\n      A: {uri: a.lst}\n      B: {uri: b.lst}\n"
    )
    calls = []

    def steps(registry, name, subsets=None):
        calls.append((name, time.monotonic()))
        yield {"files": tui_stats.summarize_files([])}, "complete", 1, 1

    monkeypatch.setattr(tui_stats, "iter_protocol_statistics", steps)
    browser = DatabaseBrowser(config)

    async def exercise():
        async with browser.run_test():
            await asyncio.sleep(0.05)
            assert calls == []
            browser.load_statistics(("Demo.Collection.B",), "files")
            await asyncio.wait_for(browser.workers.wait_for_complete(), timeout=3)
            assert [name for name, _ in calls] == [
                "Demo.Collection.B",
                "Demo.Collection.A",
            ]
            assert calls[1][1] - calls[0][1] >= 0.09
            tree = browser.query_one(Tree)
            assert tree.metrics.keys() == browser.node_subsets.keys()
            assert all(
                node_id not in tree.metrics
                for node_id in browser.node_paths
                if node_id not in browser.node_subsets
            )

    asyncio.run(exercise())


def test_latest_subset_preempts_and_resumes_within_protocol(tmp_path, monkeypatch):
    import threading

    from pyannote.database import tui_stats

    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    config = tmp_path / "database.yml"
    config.write_text(
        "Protocols:\n  Demo:\n    SpeakerDiarization:\n      P:\n        train: {uri: a.lst}\n        development: {uri: b.lst}\n        test: {uri: c.lst}\n"
    )
    started, release = threading.Event(), threading.Event()
    calls = []

    def steps(registry, name, subsets=None):
        subset = subsets[0]
        calls.append((subset, 1))
        if subset == "train":
            started.set()
            release.wait(timeout=5)
        yield {subset: tui_stats.summarize_files([])}, "one file", 0, 1
        calls.append((subset, 2))
        yield {subset: tui_stats.summarize_files([])}, "done", 1, 1

    monkeypatch.setattr(tui_stats, "iter_protocol_statistics", steps)
    browser = DatabaseBrowser(config)
    browser.preload_enabled = False
    name = "Demo.SpeakerDiarization.P"

    async def exercise():
        async with browser.run_test():
            browser.load_statistics((name,), "train")
            assert await asyncio.to_thread(started.wait, 3)
            browser.load_statistics((name,), "test")
            browser.load_statistics((name,), "development")
            release.set()
            await browser.workers.wait_for_complete()
            assert calls == [("train", 1), ("development", 1), ("development", 2)]
            assert browser.subset_ready(name, "development")
            assert not browser.subset_ready(name, "train")
            browser.load_statistics((name,), "train")
            await browser.workers.wait_for_complete()
            assert calls[-1] == ("train", 2)
            assert calls.count(("train", 1)) == 1
            browser.load_statistics((name,), "test")
            await browser.workers.wait_for_complete()
            assert set(browser.statistics_cache[name]) == {
                "train",
                "development",
                "test",
            }

    try:
        asyncio.run(exercise())
    finally:
        release.set()


def test_provenance_tab_shows_annotations_sidecar(tmp_path):
    from textual.widgets import Static, TabbedContent

    source = "# original comments survive\nProtocols:\n  Demo:\n    Collection:\n      P:\n        uri: files.lst\n"
    child = tmp_path / "child.yml"
    child.write_text(source)
    provenance = tmp_path / "annotations" / "provenance.yaml"
    provenance.parent.mkdir()
    provenance.write_text("# provenance comment\ndataset: Demo\ngenerator: build.py\n")
    root = tmp_path / "database.yml"
    root.write_text("Requirements: child.yml\n")
    browser = DatabaseBrowser(root)
    browser.preload_enabled = False

    async def exercise():
        async with browser.run_test() as pilot:
            tree = browser.query_one(Tree)
            protocol = tree.root.children[0].children[0].children[0]
            protocol.parent.parent.expand()
            protocol.parent.expand()
            await pilot.pause()
            tree.move_cursor(protocol)
            browser.query_one(TabbedContent).active = "provenance-tab"
            await pilot.pause()
            await browser.workers.wait_for_complete()
            assert browser.query_one("#provenance-path", Static).content == str(
                provenance
            )
            assert (
                browser.query_one("#provenance-content", Static).content.code
                == provenance.read_text()
            )
            provenance.unlink()
            browser.load_provenance()
            await browser.workers.wait_for_complete()
            assert (
                "No provenance.yaml found"
                in browser.query_one("#provenance-content", Static).content.plain
            )
            tree.move_cursor(tree.root)
            await pilot.pause()
            await browser.workers.wait_for_complete()
            assert (
                "No provenance.yaml found"
                in browser.query_one("#provenance-content", Static).content.plain
            )

    asyncio.run(exercise())


def test_provenance_candidates_prefer_annotation_version(tmp_path):
    candidates = DatabaseBrowser.find_provenance_candidates(
        tmp_path / "database.yml",
        {"train": {"annotation": "annotations/rttm/aligned/{uri}.rttm"}},
    )
    assert candidates[0] == tmp_path / "annotations/rttm/aligned/provenance.yaml"
    assert tmp_path / "annotations/provenance.yaml" in candidates
    assert tmp_path / "database.yml" not in candidates
