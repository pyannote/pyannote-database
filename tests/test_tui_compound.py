"""Compound composer behavior and exported protocol round trips."""

import asyncio
from io import StringIO

import pytest
import yaml

pytest.importorskip("textual")

from rich.console import Console
from textual.widgets import Input, Select, Static, TabbedContent

from pyannote.database.registry import Registry
from pyannote.database.tui import DatabaseBrowser
from pyannote.database.tui_compound import CompoundComposer, CompoundDraft, CompoundTree


@pytest.fixture
def browser(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    source = tmp_path / "database.yml"
    source.write_text(
        yaml.safe_dump(
            {
                "Protocols": {
                    "Demo": {
                        "SpeakerDiarization": {
                            "Sample": {
                                "scope": "file",
                                "versions": {
                                    "original": {"level": "turn", "closing": 1.0},
                                    "aligned": {"level": "word", "closing": 0.2},
                                    "mixed": {"level": "mixed", "closing": 0.0},
                                },
                                **{
                                    split: {
                                        "uri": f"{split}.lst",
                                        "annotation": "{version}.rttm",
                                        "annotated": "all.uem",
                                    }
                                    for split in ("train", "development", "test")
                                },
                            }
                        }
                    }
                },
            },
            sort_keys=False,
        )
    )
    for split in ("train", "development", "test"):
        (tmp_path / f"{split}.lst").write_text(f"{split}\n")
    (tmp_path / "all.uem").write_text("train 1 0 10\ndevelopment 1 0 10\ntest 1 0 10\n")
    for version in ("original", "aligned", "mixed"):
        (tmp_path / f"{version}.rttm").write_text(
            "".join(
                f"SPEAKER {split} 1 0 10 <NA> <NA> speaker <NA> <NA>\n"
                for split in ("train", "development", "test")
            )
        )
    app = DatabaseBrowser(source)
    app.preload_enabled = False
    app.STARTUP_PRELOAD_DELAY = 0.001
    app.IDLE_PRELOAD_DELAY = 0.001
    return app


def render(renderable):
    stream = StringIO()
    Console(file=stream, width=120, color_system=None).print(renderable)
    return stream.getvalue()


def test_test_sources_cannot_enter_train_or_development():
    draft = CompoundDraft()
    sources = [
        ("D.SpeakerDiarization.P@v", subset)
        for subset in ("train", "development", "test")
    ]
    for target in ("train", "development"):
        draft.toggle(target, sources)
        assert draft.selections[target] == set(sources[:2])
        draft.toggle(target, sources)
        assert not draft.selections[target]
    draft.toggle("test", sources)
    assert draft.selections["test"] == set(sources)


def test_export_revalidates_test_restriction(tmp_path):
    draft = CompoundDraft()
    draft.selections["development"].add(("D.SpeakerDiarization.P@v", "test"))
    with pytest.raises(ValueError, match="only enter compound test"):
        draft.document("New", tmp_path / "source.yml", tmp_path / "output.yml")


def test_composer_selection_stats_metadata_and_export(browser, tmp_path):
    original = browser.path.read_bytes()

    async def exercise():
        async with browser.run_test(size=(140, 48)) as pilot:
            await pilot.press("c")
            composer = browser.query_one(CompoundComposer)
            tree = composer.query_one(CompoundTree)
            assert browser.composing
            assert composer.display
            assert not browser.query_one("#browser-body").display
            assert len(composer.sources) == 9  # explicit versions, no default alias
            names = [
                f"Demo.SpeakerDiarization.Sample@{v}"
                for v in ("original", "aligned", "mixed")
            ]
            # Known statistics let us test exact, immediate contribution changes.
            for index, name in enumerate(names):
                browser.statistics_cache[name] = {
                    subset: {
                        "files": index + 1,
                        "annotated": (index + 1) * 10,
                        "errors": [],
                    }
                    for subset in ("train", "development", "test")
                }

            def leaf(source):
                return next(
                    tree.get_node_by_id(n)
                    for n, sources in composer.node_sources.items()
                    if tree.get_node_by_id(n).data == source
                )

            async def focus(source):
                node = leaf(source)
                ancestor = node.parent
                while ancestor:
                    ancestor.expand()
                    ancestor = ancestor.parent
                await pilot.pause()
                tree.move_cursor(node)
                tree.focus()
                await pilot.pause()
                return node

            a = (names[0], "development")
            b = (names[1], "development")
            await focus(a)
            await pilot.press("space")
            await focus(b)
            await pilot.press("space")
            assert composer.draft.selections["train"] == {a, b}
            summary = render(composer.render_summary())
            assert "TRAIN · 3 files · 30.0s" in summary
            assert "33.3%" in summary and "66.7%" in summary
            assert "turn-level · closing=1.0s" in leaf(a).label.plain
            assert "word-level · closing=0.2s" in leaf(b).label.plain
            assert "TRAIN sources" not in summary
            assert "Sample@" not in summary
            assert (
                composer.query_one("#compound-tabs", TabbedContent).active
                == "compound-train-tab"
            )
            assert "mixed-level · closing=0.0s" in leaf((names[2], "train")).label.plain
            await pilot.press("space")
            assert composer.draft.selections["train"] == {a}
            assert "TRAIN · 1 files · 10.0s" in render(composer.render_summary())
            await pilot.press("space")

            await focus((names[0], "test"))
            await pilot.press("space")
            assert (names[0], "test") not in composer.draft.selections["train"]
            assert "test only" in tree.cursor_node.label.plain
            await pilot.press("2")
            assert not composer.draft.selections["development"]
            await pilot.press("3")
            assert (
                composer.query_one("#compound-tabs", TabbedContent).active
                == "compound-test-tab"
            )
            assert composer.draft.selections["test"] == {(names[0], "test")}
            await focus((names[0], "train"))
            await pilot.press("2")
            assert (
                composer.query_one("#compound-tabs", TabbedContent).active
                == "compound-development-tab"
            )
            assert composer.draft.selections["development"] == {(names[0], "train")}

            await pilot.click("#compound-files")
            await pilot.pause()
            assert composer.metric == "files"
            output_dir = tmp_path / "export"
            output_dir.mkdir()
            output = output_dir / "compound.yml"
            await pilot.press("ctrl+s")
            browser.screen.query_one("#compound-output", Input).value = str(output)
            browser.screen.query_one("#compound-name", Input).value = "Combined"
            assert not output.exists()
            await pilot.press("ctrl+s")
            assert output.exists()
            exported = yaml.safe_load(output.read_text())
            assert exported["Requirements"] == ["../database.yml"]
            registry = Registry()
            registry.load_database(output)
            protocol = registry.get_protocol("X.SpeakerDiarization.Combined")
            assert {file["version"]["name"] for file in protocol.train()} == {
                "original",
                "aligned",
            }
            assert [file["uri"] for file in protocol.development()] == ["train"]
            assert [file["uri"] for file in protocol.test()] == ["test"]
            previous = output.read_bytes()
            await pilot.press("ctrl+s")
            browser.screen.query_one("#compound-name", Input).value = "Other"
            await pilot.press("ctrl+s")
            assert output.read_bytes() == previous
            assert "Cannot save" in str(
                browser.screen.query_one("#save-compound-status", Static).content
            )
            browser.screen.query_one("#compound-output", Input).value = str(
                browser.path
            )
            await pilot.press("ctrl+s")
            assert browser.path.read_bytes() == original
            await pilot.press("escape")
            assert browser.composing
            assert composer.protocol_name == "Combined"
            await pilot.press("escape")
            assert not browser.composing
            await pilot.press("c")
            assert composer.draft.selections["train"] == {a, b}

    asyncio.run(exercise())


def test_adjacent_checkboxes_click_independently_and_bulk_skip_test(browser):
    async def exercise():
        async with browser.run_test(size=(140, 40)) as pilot:
            await pilot.press("c")
            composer = browser.query_one(CompoundComposer)
            tree = composer.query_one(CompoundTree)
            assert not composer.query("#compound-target")

            async def click_checkbox(target):
                for y in range(tree.size.height):
                    x = 0
                    for segment in tree.render_line(y):
                        meta = segment.style.meta if segment.style else {}
                        if (
                            meta.get("compound_target") == target
                            and meta.get("compound_node") == tree.root.id
                        ):
                            await pilot.click("#compound-tree", offset=(x + 1, y))
                            return
                        x += segment.cell_length
                pytest.fail(f"Could not find {target} checkbox")

            await click_checkbox("train")
            assert len(composer.draft.selections["train"]) == 6
            assert not composer.draft.selections["development"]
            assert not composer.draft.selections["test"]
            assert tree.root.is_expanded
            await click_checkbox("development")
            assert len(composer.draft.selections["development"]) == 6
            await click_checkbox("test")
            assert len(composer.draft.selections["test"]) == 9
            await click_checkbox("train")
            assert not composer.draft.selections["train"]
            assert len(composer.draft.selections["development"]) == 6
            assert len(composer.draft.selections["test"]) == 9
            assert tree.root.is_expanded

    asyncio.run(exercise())


def test_loading_and_failed_statistics_are_not_reported_as_complete(browser):
    async def exercise():
        async with browser.run_test(size=(120, 40)) as pilot:
            await pilot.press("c")
            composer = browser.query_one(CompoundComposer)
            source = ("Demo.SpeakerDiarization.Sample@original", "train")
            composer.draft.selections["train"].add(source)
            assert "provisional" in render(composer.render_summary())
            browser.statistics_cache[source[0]] = {"train": {"error": "missing file"}}
            assert "provisional (1 incomplete)" in render(composer.render_summary())
            composer.highlighted = (source,)
            composer.refresh_focus()
            assert (
                "Error: missing file"
                in composer.query_one("#compound-focus", Static).content
            )
            del browser.statistics_cache[source[0]]
            composer.wake_statistics()
            await browser.workers.wait_for_complete()
            composer.refresh_statistics()
            summary = render(
                composer.query_one("#compound-summary-train", Static).content
            )
            assert "TRAIN · 1 files · 10.0s" in summary
            assert "provisional" not in summary

    asyncio.run(exercise())


def test_level_filter_preserves_hidden_selections_and_filters_bulk_toggles(browser):
    async def exercise():
        async with browser.run_test(size=(140, 45)) as pilot:
            await pilot.press("c")
            composer = browser.query_one(CompoundComposer)
            tree = composer.query_one(CompoundTree)
            turn = ("Demo.SpeakerDiarization.Sample@original", "train")
            composer.draft.selections["train"].add(turn)
            select = composer.query_one("#compound-level", Select)
            for level, version in [
                ("word", "aligned"),
                ("turn", "original"),
                ("mixed", "mixed"),
            ]:
                select.value = level
                await pilot.pause()
                visible = composer.node_sources[tree.root.id]
                assert len(visible) == 3
                assert {source[0] for source in visible} == {
                    f"Demo.SpeakerDiarization.Sample@{version}"
                }
                assert turn in composer.draft.selections["train"]
                assert len(composer.sources) == 9
                assert "[word / turn / mixed]" in tree.root.children[0].label.plain
            select.value = "word"
            await pilot.pause()
            assert (
                "1 selected hidden"
                in composer.query_one("#compound-filter-count", Static).content
            )
            tree.focus()
            await pilot.press("1")
            selected = composer.draft.selections["train"]
            assert selected == {
                turn,
                ("Demo.SpeakerDiarization.Sample@aligned", "train"),
                ("Demo.SpeakerDiarization.Sample@aligned", "development"),
            }
            _, document = composer.export_document()
            assert (
                "Demo.SpeakerDiarization.Sample@original"
                in document["Protocols"]["X"]["SpeakerDiarization"]["MyCompound"][
                    "train"
                ]
            )
            select.value = "unknown"
            await pilot.pause()
            assert not tree.root.children
            assert (
                "3 selected hidden"
                in composer.query_one("#compound-filter-count", Static).content
            )
            select.value = "all"
            await pilot.pause()
            assert len(composer.node_sources[tree.root.id]) == 9
            assert (
                "0 selected hidden"
                in composer.query_one("#compound-filter-count", Static).content
            )

    asyncio.run(exercise())


def test_commercial_flags_in_tree_treemap_legend_and_focus(browser):
    manifest = browser.path.with_name("manifest.yaml")
    manifest.write_text("licence:\n  commercial_use: false\n  name: Research only\n")

    async def exercise():
        async with browser.run_test(size=(140, 45)) as pilot:
            await pilot.press("c")
            composer = browser.query_one(CompoundComposer)
            tree = composer.query_one(CompoundTree)
            source = ("Demo.SpeakerDiarization.Sample@original", "train")
            composer.draft.selections["train"].add(source)
            browser.statistics_cache[source[0]] = {
                "train": {"files": 1, "annotated": 10}
            }
            composer.refresh_statistics()
            assert "NON-COMMERCIAL" in tree.root.children[0].label.plain
            summary = render(composer.render_summary())
            assert "1 NON-COMMERCIAL source(s)" in summary
            assert "NC · Demo" in summary
            composer.highlighted = (source,)
            composer.refresh_focus()
            focus = composer.query_one("#compound-focus", Static).content
            assert "Research only" in focus and str(manifest) in focus
            for value, expected in [("true", True), ("null", None), ('"false"', None)]:
                manifest.write_text(f"licence:\n  commercial_use: {value}\n")
                composer.populate()
                assert composer.commercial[source].allowed is expected
                summary = render(composer.render_summary())
                if expected is None:
                    assert "? commercial" in tree.root.children[0].label.plain
                    assert "1 commercial-use status unknown" in summary
                else:
                    composer.highlighted = (source,)
                    composer.refresh_focus()
                    assert (
                        "commercial: yes (catalog)"
                        in composer.query_one("#compound-focus", Static).content
                    )
                    assert "? commercial" not in tree.root.children[0].label.plain
                assert source in composer.draft.selections["train"]

    asyncio.run(exercise())


def test_load_existing_compound_and_save_updated_copy(browser, tmp_path):
    incoming = tmp_path / "existing.yml"
    incoming.write_text(
        yaml.safe_dump(
            {
                "Requirements": ["database.yml"],
                "Protocols": {
                    "X": {
                        "SpeakerDiarization": {
                            "Saved": {
                                "train": {
                                    "Demo.SpeakerDiarization.Sample": ["development"],
                                    "Demo.SpeakerDiarization.Sample@aligned": ["train"],
                                },
                                "test": {
                                    "Demo.SpeakerDiarization.Sample@original": ["test"]
                                },
                            },
                            "Unsafe": {
                                "train": {"Demo.SpeakerDiarization.Sample": ["test"]}
                            },
                        }
                    }
                },
            },
            sort_keys=False,
        )
    )
    original = incoming.read_bytes()

    async def exercise():
        async with browser.run_test(size=(140, 48)) as pilot:
            await pilot.press("c")
            composer = browser.query_one(CompoundComposer)
            await pilot.press("ctrl+o")
            browser.screen.query_one("#load-compound-path", Input).value = str(incoming)
            await pilot.pause()
            await pilot.click("#load-compound-read")
            browser.screen.query_one("#load-compound-name", Select).value = "Unsafe"
            await pilot.click("#load-compound-apply")
            assert (
                "only enter compound test"
                in browser.screen.query_one("#load-compound-status", Static).content
            )
            assert not any(composer.draft.selections.values())
            browser.screen.query_one("#load-compound-name", Select).value = "Saved"
            await pilot.pause(0.4)  # let the Load button's press animation finish
            await pilot.click("#load-compound-apply")
            await pilot.pause()
            assert browser.path == incoming
            assert composer.draft.selections["train"] == {
                ("Demo.SpeakerDiarization.Sample@original", "development"),
                ("Demo.SpeakerDiarization.Sample@aligned", "train"),
            }
            assert composer.draft.selections["test"] == {
                ("Demo.SpeakerDiarization.Sample@original", "test")
            }
            assert composer.protocol_name == "Saved"
            await pilot.press("ctrl+s")
            await pilot.press("ctrl+s")
            output = tmp_path / "existing-edited.yml"
            assert output.exists() and incoming.read_bytes() == original
            registry = Registry()
            with pytest.warns(UserWarning, match="Replacing existing"):
                registry.load_database(output)
            assert (
                len(list(registry.get_protocol("X.SpeakerDiarization.Saved").train()))
                == 2
            )

    asyncio.run(exercise())


def test_pdf_export_from_composer_preserves_hidden_selections(browser, tmp_path):
    pytest.importorskip("reportlab")
    pypdf = pytest.importorskip("pypdf")

    async def exercise():
        async with browser.run_test(size=(140, 48)) as pilot:
            await pilot.press("c")
            composer = browser.query_one(CompoundComposer)
            source = ("Demo.SpeakerDiarization.Sample@original", "train")
            composer.draft.selections["train"].add(source)
            browser.statistics_cache[source[0]] = {
                "train": {"files": 1, "annotated": 10}
            }
            composer.query_one("#compound-level", Select).value = "word"
            await pilot.press("ctrl+e")
            browser.screen.query_one("#compound-output", Input).value = str(
                tmp_path / "report.pdf"
            )
            await pilot.press("ctrl+e")
            await browser.workers.wait_for_complete()
            output = tmp_path / "report.pdf"
            reader = pypdf.PdfReader(output)
            assert len(reader.pages) == 3
            assert "1 files" in reader.pages[0].extract_text()
            assert "turn-level" in reader.pages[0].extract_text()
            assert not (tmp_path / "report.yml").exists()
            before = output.read_bytes()
            await pilot.press("ctrl+e")
            assert browser.screen.query_one("#compound-output", Input).value == str(
                output
            )
            await pilot.press("ctrl+e")
            await browser.workers.wait_for_complete()
            assert output.read_bytes() == before
            assert (
                "Cannot export PDF"
                in browser.screen.query_one("#save-compound-status", Static).content
            )

    asyncio.run(exercise())


@pytest.mark.parametrize("size", [(80, 24), (140, 48)])
def test_visualization_fills_panel_and_dialogs_cancel_without_changes(
    browser, tmp_path, size
):
    from textual.widgets import Button

    from pyannote.database.tui_save import SaveCompoundScreen
    from pyannote.database.tui_treemap import ContributionTreemap

    async def exercise():
        async with browser.run_test(size=size) as pilot:
            await pilot.press("c")
            composer = browser.query_one(CompoundComposer)
            source = ("Demo.SpeakerDiarization.Sample@original", "train")
            composer.draft.selections["train"].add(source)
            browser.statistics_cache[source[0]] = {
                "train": {"files": 2, "annotated": 30}
            }
            composer.refresh_statistics()
            await pilot.pause()
            right = composer.query_one("#compound-right")
            assert not right.query(Input)
            assert not right.query(Select)
            assert len(right.query(Button)) == 2
            assert not right.query("#compound-preview")
            metric = right.query_one("#compound-metric")
            assert metric.size.height == 1
            assert metric.region.bottom == right.content_region.bottom
            summary = composer.query_one("#compound-summary-train", Static)
            chart = next(
                block
                for block in summary.content.renderables
                if isinstance(block, ContributionTreemap)
            )
            assert chart.height >= summary.parent.content_size.height - 5
            assert summary.virtual_size.height <= summary.parent.content_size.height
            assert "Area: share" not in render(summary.content)
            assert "Details in the source tree" not in render(summary.content)
            assert chart.items == [(source, 30)]
            await pilot.click("#compound-files")
            chart = next(
                block
                for block in summary.content.renderables
                if isinstance(block, ContributionTreemap)
            )
            assert chart.items == [(source, 2)]
            assert composer.metric == "files"
            await pilot.press("m")
            assert composer.metric == "annotated"
            await pilot.resize_terminal(size[0] + 10, size[1] + 7)
            await pilot.pause()
            chart = next(
                block
                for block in summary.content.renderables
                if isinstance(block, ContributionTreemap)
            )
            assert chart.height >= summary.parent.content_size.height - 5
            assert summary.virtual_size.height <= summary.parent.content_size.height
            saved_path = composer.output_path
            for shortcut in ("ctrl+s", "ctrl+e"):
                await pilot.press(shortcut)
                dialog = browser.screen
                assert isinstance(dialog, SaveCompoundScreen)
                dialog.query_one("#compound-name", Input).value = "Cancelled"
                dialog.query_one("#compound-output", Input).value = str(
                    tmp_path / "cancelled.yml"
                )
                await pilot.pause()
                cancel = dialog.query_one("#save-compound-cancel")
                assert dialog.region.contains_region(cancel.region)
                await pilot.press("escape")
                assert browser.composing
                assert composer.output_path == saved_path
                assert composer.protocol_name == "MyCompound"
                assert composer.draft.selections["train"] == {source}
            assert not (tmp_path / "cancelled.yml").exists()
            await pilot.press("ctrl+o")
            await pilot.press("escape")
            assert composer.draft.selections["train"] == {source}

    asyncio.run(exercise())
