"""Interactive composition of explicit, versioned diarization subsets."""

import os
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from rich.console import Group
from rich.style import Style
from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Button, Select, Static, TabbedContent, TabPane, Tree

from .tui_metadata import read_commercial_use
from .tui_stats import format_duration
from .tui_treemap import ContributionTreemap

SPLITS = ("train", "development", "test")


def version_description(version):
    metadata = (version or {}).get("metadata", {})
    level = metadata.get("level")
    closing = metadata.get("closing")
    return (
        (f"{level}-level" if level else "level unknown")
        + " · "
        + (f"closing={closing}s" if closing is not None else "closing unknown")
    )


def error_details(stats):
    errors = [stats["error"]] if stats.get("error") else stats.get("errors", [])
    return "\n".join(dict.fromkeys(str(error) for error in errors))


@dataclass
class CompoundDraft:
    """Selections are (fully qualified protocol including version, source subset)."""

    selections: dict = field(default_factory=lambda: {split: set() for split in SPLITS})

    def toggle(self, target, sources):
        eligible = {
            source for source in sources if target == "test" or source[1] != "test"
        }
        selected = self.selections[target]
        if eligible and eligible <= selected:
            selected.difference_update(eligible)
        else:
            selected.update(eligible)

    def document(self, name, source, output):
        if not name or any(c.isspace() or c in ".@" for c in name):
            raise ValueError("Use a protocol name without whitespace, '.' or '@'.")
        if not any(self.selections.values()):
            raise ValueError("Select at least one source subset.")
        subsets = {}
        for target, selected in self.selections.items():
            members = {}
            for protocol, subset in sorted(selected):
                if subset == "test" and target != "test":
                    raise ValueError(
                        "Source test subsets can only enter compound test."
                    )
                members.setdefault(protocol, []).append(subset)
            if members:
                subsets[target] = members
        return {
            "Requirements": [os.path.relpath(source, output.parent)],
            "Protocols": {"X": {"SpeakerDiarization": {name: subsets}}},
        }


class CompoundTree(Tree):
    BINDINGS = [
        ("space", "check", "Toggle checkbox"),
        ("left", "close_branch", "Collapse"),
        ("right", "open_branch", "Expand"),
        ("1", "check('train')", "Toggle train"),
        ("2", "check('development')", "Toggle dev"),
        ("3", "check('test')", "Toggle test"),
    ]

    def action_check(self, target=None):
        self.app.query_one(CompoundComposer).toggle_node(self.cursor_node, target)

    async def _on_click(self, event):
        target = event.style.meta.get("compound_target")
        if target is None:
            await super()._on_click(event)
            return
        event.stop()
        event.prevent_default()
        node_id = event.style.meta["compound_node"]
        node = self.root if node_id == self.root.id else self.get_node_by_id(node_id)
        self.move_cursor(node)
        self.focus()
        self.app.query_one(CompoundComposer).toggle_node(node, target)

    def action_close_branch(self):
        node = self.cursor_node
        if node is not None:
            if node.is_expanded:
                node.collapse()
            elif node.parent is not None:
                self.move_cursor(node.parent)

    def action_open_branch(self):
        node = self.cursor_node
        if node is not None:
            if not node.is_expanded:
                node.expand()
            elif node.children:
                self.move_cursor(node.children[0])


class CompoundComposer(Horizontal):
    DEFAULT_CSS = """
    CompoundComposer { display: none; height: 1fr; }
    #compound-picker { width: 45%; border: solid $primary; }
    #compound-right { width: 55%; border: solid $secondary; }
    #compound-help, #compound-focus, #compound-filter-count { height: auto; padding: 0 1; }
    #compound-focus { border-top: solid $primary; }
    #compound-level { margin: 0 1; width: 1fr; }
    #compound-metric { height: 1; align-horizontal: center; }
    #compound-metric Button { height: 1; min-width: 12; border: none; margin: 0 1; padding: 0 1; }
    #compound-tree { height: 1fr; }
    #compound-tabs { height: 1fr; }
    .compound-summary { height: auto; padding: 0; }
    """
    BINDINGS = [
        ("m", "toggle_metric", "Duration / Files"),
        ("ctrl+s", "save", "Save YAML"),
        ("ctrl+e", "export_pdf", "Export PDF"),
        ("ctrl+o", "load_compound", "Load compound"),
    ]

    def __init__(self, browser, **kwargs):
        super().__init__(**kwargs)
        self.browser = browser
        self.draft = CompoundDraft()
        self.sources = {}
        self.commercial = {}
        self.node_sources = {}
        self.node_titles = {}
        self.database_nodes = {}
        self.database_levels = defaultdict(set)
        self.highlighted = ()
        self.space_target = "train"
        self.metric = "annotated"
        self.level = "all"
        self.loaded_name = None
        self.protocol_name = "MyCompound"
        self.output_path = browser.path.with_name("compound.yml")
        self.pdf_output_path = None
        self.load_path = None

    def compose(self) -> ComposeResult:
        with Vertical(id="compound-picker"):
            yield Static(
                "Checkbox order: [Train] [Dev] [Test] · Esc: browse\n"
                "Click or 1/2/3: toggle · Space: repeat last column\n"
                "←/→ or Enter: expand/collapse · branch checkbox = all eligible\n"
                "Ctrl+S: save · Ctrl+E: PDF · Ctrl+O: load",
                id="compound-help",
                markup=False,
            )
            yield Select(
                [
                    ("Level: all", "all"),
                    ("Level: word", "word"),
                    ("Level: turn", "turn"),
                    ("Level: mixed", "mixed"),
                    ("Level: unknown", "unknown"),
                ],
                value="all",
                allow_blank=False,
                id="compound-level",
            )
            yield Static(id="compound-filter-count", markup=False)
            yield CompoundTree("Source diarization protocols", id="compound-tree")
            yield Static(id="compound-focus", markup=False)
        with Vertical(id="compound-right"):
            with TabbedContent(id="compound-tabs"):
                for split, title in zip(SPLITS, ("Train", "Development", "Test")):
                    with TabPane(title, id=f"compound-{split}-tab"):
                        with VerticalScroll():
                            yield Static(
                                id=f"compound-summary-{split}",
                                classes="compound-summary",
                            )
            with Horizontal(id="compound-metric"):
                yield Button("● Duration", id="compound-duration", variant="primary")
                yield Button("○ Files", id="compound-files")

    def on_mount(self):
        self.populate()

    def populate(self):
        tree = self.query_one(CompoundTree)
        tree.clear()
        tree.root.set_label("Source diarization protocols")
        self.sources.clear()
        self.commercial.clear()
        self.node_sources.clear()
        self.node_titles.clear()
        self.database_nodes.clear()
        self.database_levels.clear()
        self.highlighted = ()
        registry = self.browser.registry
        manifests = {}
        for database_name in sorted(registry.databases):
            # Select concrete sources, so a nested meta-protocol cannot hide test data.
            if database_name == "X":
                continue
            database = registry.get_database(database_name)
            if "SpeakerDiarization" not in getattr(database, "protocols_", {}):
                continue
            db_node = tree.root.add(database_name)
            self.database_nodes[db_node.id] = database_name
            groups = defaultdict(list)
            names = database.get_protocols("SpeakerDiarization")
            versioned = {name.partition("@")[0] for name in names if "@" in name}
            for name in names:
                if "@" not in name and name in versioned:
                    continue  # hide the duplicate alias of the first version
                groups[name.partition("@")[0]].append(name)
            for base, names in sorted(groups.items()):
                protocol_node = db_node.add(base)
                subset_nodes = {}
                for name in names:
                    full_name = f"{database_name}.SpeakerDiarization.{name}"
                    protocol = registry.get_protocol(full_name)
                    path = protocol.database_yml
                    if path not in manifests:
                        manifests[path] = read_commercial_use(path)
                    version = getattr(protocol, "annotation_version", None)
                    for subset in SPLITS:
                        if subset not in protocol.configuration:
                            continue
                        source = (full_name, subset)
                        self.sources[source] = version
                        self.commercial[source] = manifests[path]
                        level = (version or {}).get("metadata", {}).get("level")
                        if level not in {"word", "turn", "mixed"}:
                            level = "unknown"
                        self.database_levels[database_name].add(level)
                        if self.level != "all" and level != self.level:
                            continue
                        if subset not in subset_nodes:
                            subset_nodes[subset] = protocol_node.add(subset)
                        version_name = name.partition("@")[2] or "unversioned"
                        title = f"{version_description(version)} · {version_name}"
                        node = subset_nodes[subset].add_leaf(title, data=source)
                        self.node_sources[node.id] = (source,)
                        self.node_titles[node.id] = title
                if not protocol_node.children:
                    protocol_node.remove()
            if not db_node.children:
                db_node.remove()

        def collect(node):
            if node.id not in self.node_sources:
                self.node_sources[node.id] = tuple(
                    source for child in node.children for source in collect(child)
                )
                self.node_titles[node.id] = node.label.plain
            return self.node_sources[node.id]

        collect(tree.root)
        for selected in self.draft.selections.values():
            selected.intersection_update(self.sources)
        tree.root.expand()
        tree.move_cursor(tree.root)
        self.refresh_statistics()

    def on_tree_node_highlighted(self, event):
        event.stop()
        self.highlighted = (event.node.data,) if event.node.data else ()
        self.refresh_focus()
        self.wake_statistics()

    def refresh_focus(self):
        text = "Select versions independently; multiple versions are allowed."
        if self.highlighted:
            source = self.highlighted[0]
            stats, state = self.source_statistics(source)
            text = (
                f"{source[0]} / {source[1]}\n"
                f"{version_description(self.sources[source])}\n"
                f"{stats.get('files', 0):,} files · "
                f"{format_duration(stats.get('annotated', 0))} annotated"
                + (f" · {state}" if state else "")
            )
            if errors := error_details(stats):
                text += f"\nError: {errors}"
            commercial = self.commercial[source]
            text += (
                f"\n{commercial.label} · {commercial.licence or 'licence unspecified'}"
            )
            text += f"\nSource: {commercial.manifest}"
            if commercial.note:
                text += f"\n{commercial.note}"
        self.query_one("#compound-focus", Static).update(text)

    def on_tree_node_expanded(self, event):
        event.stop()
        self.wake_statistics()

    def on_tree_node_collapsed(self, event):
        event.stop()

    def on_tree_node_selected(self, event):
        event.stop()

    def on_tabbed_content_tab_activated(self, event):
        event.stop()
        if self.is_mounted and self.browser.composing:
            self.refresh_charts()

    def on_resize(self):
        if self.is_mounted and self.browser.composing:
            self.refresh_charts()

    def on_select_changed(self, event):
        event.stop()
        if event.select.id == "compound-level" and event.value != self.level:
            self.level = str(event.value)
            self.populate()
            self.wake_statistics()
            return
        self.refresh_statistics()

    def set_metric(self, metric):
        self.metric = metric
        for suffix, value, title in (
            ("duration", "annotated", "Duration"),
            ("files", "files", "Files"),
        ):
            button = self.query_one(f"#compound-{suffix}", Button)
            active = metric == value
            button.label = f"{'●' if active else '○'} {title}"
            button.variant = "primary" if active else "default"
        self.refresh_charts()

    def action_toggle_metric(self):
        self.set_metric("files" if self.metric == "annotated" else "annotated")

    def on_button_pressed(self, event):
        if event.button.id in {"compound-duration", "compound-files"}:
            event.stop()
            self.set_metric(
                "files" if event.button.id == "compound-files" else "annotated"
            )

    def toggle_node(self, node, target=None):
        if node is None:
            return
        if target is not None:
            self.space_target = target
        target = self.space_target
        sources = self.node_sources.get(node.id, ())
        self.draft.toggle(target, sources)
        self.query_one(
            "#compound-tabs", TabbedContent
        ).active = f"compound-{target}-tab"
        blocked = target != "test" and any(s[1] == "test" for s in sources)
        if blocked:
            self.notify("Source test subsets are reserved for compound test; skipped.")
        self.refresh_statistics()
        self.wake_statistics()

    def wake_statistics(self):
        if self.browser.composing:
            self.browser.statistics_wakeup.set()
            self.browser.ensure_statistics_worker()

    def statistics_targets(self):
        # Selected contributions first, then the highlighted and visible version rows.
        targets = [s for split in SPLITS for s in sorted(self.draft.selections[split])]
        targets.extend(self.highlighted)
        tree = self.query_one(CompoundTree)
        for line in range(
            tree.scroll_offset.y, tree.scroll_offset.y + tree.size.height
        ):
            node = tree.get_node_at_line(line)
            if node is not None and node.data:
                targets.append(node.data)
        return list(dict.fromkeys(targets))

    def source_statistics(self, source):
        name, subset = source
        summaries = self.browser.statistics_cache.get(
            name, self.browser.jobs.get(name, (None, {}))[1]
        )
        stats = summaries.get(subset, summaries.get("protocol", {}))
        if stats.get("error") or stats.get("errors"):
            state = "incomplete / errors"
        elif not self.browser.subset_ready(name, subset):
            state = "loading" if name in self.browser.jobs else "pending"
        else:
            state = "" if stats else "unavailable"
        return stats, state

    def refresh_statistics(self):
        if not self.is_mounted:
            return
        tree = self.query_one(CompoundTree)
        visible = set(self.node_sources.get(tree.root.id, ()))
        selected = set().union(*self.draft.selections.values())
        self.query_one("#compound-filter-count", Static).update(
            f"Showing {len(visible)}/{len(self.sources)} source versions/subsets"
            f" · {len(selected - visible)} selected hidden"
        )
        for node_id, sources in self.node_sources.items():
            # Tree.clear() may retain the previous root in its ID lookup table.
            node = (
                tree.root if node_id == tree.root.id else tree.get_node_by_id(node_id)
            )
            label = Text()
            for target in SPLITS:
                eligible = {s for s in sources if target == "test" or s[1] != "test"}
                checked = len(eligible & self.draft.selections[target])
                mark = (
                    "!"
                    if not eligible
                    else "x"
                    if checked == len(eligible)
                    else "−"
                    if checked
                    else " "
                )
                label.append(
                    f"[{mark}]",
                    style=Style(
                        color="green" if checked else None,
                        dim=not eligible,
                        underline=target == self.space_target,
                        meta={"compound_target": target, "compound_node": node_id},
                    ),
                )
                label.append(" ")
            permissions = {self.commercial[source].allowed for source in sources}
            if False in permissions:
                label.append(
                    "NON-COMMERCIAL · " if permissions == {False} else "includes NC · ",
                    style="bold red",
                )
            if None in permissions:
                label.append("? commercial · ", style="yellow")
            if node.data:
                version = self.sources[node.data]
                level = (version or {}).get("metadata", {}).get("level")
                color = {"word": "cyan", "turn": "green", "mixed": "magenta"}.get(
                    level, "yellow"
                )
                label.append(self.node_titles[node_id], style=color)
                stats, state = self.source_statistics(node.data)
                label.append(
                    f" · {stats.get('files', 0)} files · {format_duration(stats.get('annotated', 0))}"
                )
                if state:
                    label.append(f" ({state})", style="dim")
            else:
                label.append(self.node_titles[node_id])
                if node_id in self.database_nodes:
                    levels = self.database_levels[self.database_nodes[node_id]]
                    label.append(" [")
                    available = [
                        level
                        for level in ("word", "turn", "mixed", "unknown")
                        if level in levels
                    ]
                    for index, level in enumerate(available):
                        if index:
                            label.append(" / ")
                        label.append(
                            level,
                            style={
                                "word": "cyan",
                                "turn": "green",
                                "mixed": "magenta",
                            }.get(level, "yellow"),
                        )
                    label.append("]")
                label.append(f" ({len(sources)} sources)", style="dim")
            if not sources or all(s[1] == "test" for s in sources):
                label.append(
                    " · test only" if sources else " · no sources", style="dim"
                )
            if node.label != label:
                node.set_label(label)
        self.refresh_charts()
        self.refresh_focus()

    def refresh_charts(self):
        for split in SPLITS:
            self.query_one(f"#compound-summary-{split}", Static).update(
                self.render_summary(split)
            )

    def render_summary(self, selected_split=None):
        blocks = []
        destinations = defaultdict(set)
        for target, selected in self.draft.selections.items():
            for name, subset in selected:
                destinations[(name.partition("@")[0], subset)].add(target)
        for split in (selected_split,) if selected_split else SPLITS:
            rows = [
                (source, *self.source_statistics(source))
                for source in sorted(self.draft.selections[split])
            ]
            files = sum(stats.get("files", 0) for _, stats, _ in rows)
            duration = sum(stats.get("annotated", 0) for _, stats, _ in rows)
            incomplete = sum(bool(state) for _, _, state in rows)
            heading = Text(
                f"{split.upper()} · {files:,} files · {format_duration(duration)}",
                style="bold",
            )
            if incomplete:
                heading.append(
                    f" · provisional ({incomplete} incomplete)", style="yellow"
                )
            blocks.append(heading)
            if not rows:
                blocks.append(Text("No sources selected.\n", style="dim"))
                continue
            commercial = {
                source: self.commercial[source].allowed for source, _, _ in rows
            }
            restricted = sum(value is False for value in commercial.values())
            unknown = sum(value is None for value in commercial.values())
            if restricted or unknown:
                status = Text()
                if restricted:
                    status.append(
                        f"{restricted} NON-COMMERCIAL source(s) · ", style="bold red"
                    )
                if unknown:
                    status.append(
                        f"{unknown} commercial-use status unknown", style="yellow"
                    )
                blocks.append(status)
            if any(
                len(targets) > 1 and split in targets
                for targets in destinations.values()
            ):
                blocks.append(
                    Text(
                        "Shared source subsets across destination splits (including versions).",
                        style="bold yellow",
                    )
                )
            height = 9
            if selected_split:
                viewport = self.query_one(
                    f"#compound-summary-{split}"
                ).parent.content_size
                width = max(1, viewport.width)
                header_height = sum(
                    len(block.wrap(self.app.console, width)) for block in blocks
                )
                height = max(1, viewport.height - header_height)
            blocks.append(
                ContributionTreemap(
                    [(source, stats.get(self.metric, 0)) for source, stats, _ in rows],
                    commercial=commercial,
                    height=height,
                )
            )
        return Group(*blocks)

    def export_document(self, name=None, output=None):
        name = (self.protocol_name if name is None else name).strip()
        value = str(self.output_path if output is None else output).strip()
        if not value:
            raise ValueError("Enter a new file path.")
        output = Path(value).expanduser().resolve()
        registry = self.browser.registry
        if "X" in registry.databases:
            database = registry.get_database("X")
            if name != self.loaded_name and name in getattr(
                database, "protocols_", {}
            ).get("SpeakerDiarization", {}):
                raise ValueError(
                    f"X.SpeakerDiarization.{name} already exists; choose a new name."
                )
        return output, self.draft.document(name, self.browser.path, output)

    def action_save(self):
        from .tui_save import SaveCompoundScreen

        self.app.push_screen(SaveCompoundScreen(self))

    def action_load_compound(self):
        from .tui_import import LoadCompoundScreen

        path = str(self.load_path or self.output_path)
        self.app.push_screen(LoadCompoundScreen(path), self.apply_loaded_compound)

    def apply_loaded_compound(self, loaded):
        if loaded is None:
            return
        from .tui_cache import StatisticsCache

        browser = self.browser
        browser.generation += 1
        browser.selected_protocol = None
        browser.priority_target = None
        browser.jobs.clear()
        browser.statistics_cache.clear()
        browser.path = loaded.path
        browser.document = loaded.document
        browser.registry = loaded.registry
        browser.disk_cache = StatisticsCache(loaded.registry)
        browser.ignore_disk_cache = False
        self.loaded_name = loaded.name.partition("@")[0]
        self.draft = CompoundDraft(loaded.selections)
        self.level = "all"
        self.query_one("#compound-level", Select).value = "all"
        self.protocol_name = self.loaded_name
        self.output_path = loaded.path.with_name(loaded.path.stem + "-edited.yml")
        self.pdf_output_path = None
        self.load_path = loaded.path
        browser.populate()
        self.populate()
        self.notify(f"Loaded X.SpeakerDiarization.{loaded.name}.")
        self.query_one(CompoundTree).focus()
        self.wake_statistics()

    def pdf_snapshot(self, name=None, output=None):
        from .tui_pdf import CompoundReport, ReportSource

        name = self.protocol_name if name is None else name
        if output is None:
            output = self.pdf_output_path or self.output_path.with_suffix(".pdf")
        output, document = self.export_document(name, output)
        splits = {}
        for split, sources in self.draft.selections.items():
            rows = []
            for source in sorted(sources):
                stats, state = self.source_statistics(source)
                metadata = (self.sources[source] or {}).get("metadata", {})
                rows.append(
                    ReportSource(
                        protocol=source[0],
                        subset=source[1],
                        files=int(stats.get("files", 0)),
                        duration=float(stats.get("annotated", 0)),
                        level=metadata.get("level", "unknown"),
                        closing=metadata.get("closing"),
                        commercial=self.commercial[source].allowed,
                        status=state,
                        errors=error_details(stats),
                    )
                )
            splits[split] = rows
        report = CompoundReport(
            name=name.strip(),
            metric=self.metric,
            created=datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC"),
            catalog=str(self.browser.path),
            splits=splits,
            configuration=document,
        )
        return output, report

    def action_export_pdf(self):
        from .tui_save import SaveCompoundScreen

        self.app.push_screen(SaveCompoundScreen(self, kind="pdf"))
