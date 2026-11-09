"""Read-only Textual browser for database configuration files."""

import asyncio
import os
import time
from pathlib import Path
from typing import Any

import yaml
from rich.syntax import Syntax
from rich.text import Text
from textual import work
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import (
    Footer,
    Header,
    ProgressBar,
    Static,
    TabbedContent,
    TabPane,
    Tree,
)

from .registry import Registry
from .tui_cache import StatisticsCache
from .tui_tree import StatisticsTree


class DatabaseBrowser(App):
    """Explore resolved protocols and their source configurations."""

    TITLE = "pyannote database browser"
    STARTUP_PRELOAD_DELAY = 3.0
    IDLE_PRELOAD_DELAY = 0.5
    CSS = """
    #tree-panel { width: 45%; border: solid $primary; }
    #bar-mode { height: auto; padding: 0 1; border-bottom: solid $primary; }
    #structure { width: 100%; height: 1fr; }
    #details { width: 55%; border: solid $secondary; padding: 1; }
    #statistics-scroll { height: 1fr; }
    #legend { height: auto; dock: bottom; border-top: solid $secondary; padding-top: 1; }
    """
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("r", "reload", "Reload"),
        ("space", "toggle", "Expand/collapse"),
        ("b", "bar_metric", "Bars: duration/files"),
    ]

    def __init__(self, path: Path | str):
        super().__init__()
        self.path = Path(path).expanduser().resolve()
        self.provenance_candidates = self.find_provenance_candidates(self.path, {})
        self.document = self.read_document()
        self.registry = self.read_registry()
        self.node_paths = {}
        self.node_subsets = {}
        self.default_subsets = {}
        self.protocol_subsets = {}
        self.selected_subset = "train"
        self.statistics_cache = {}
        self.disk_cache = StatisticsCache(self.registry)
        self.jobs = {}
        self.preload_enabled = True
        self.statistics_wakeup = asyncio.Event()
        self.selected_protocol = None
        self.priority_target = None
        self.statistics_running = False
        self.last_statistics_render = 0.0
        self.generation = 0
        self.ignore_disk_cache = False
        self.sub_title = str(self.path)

    def read_document(self) -> dict:
        with self.path.open(encoding="utf-8") as stream:
            document = yaml.safe_load(stream)
        if not isinstance(document, dict):
            raise ValueError("Expected a YAML mapping at the root.")
        return document

    def read_registry(self):
        registry = Registry()
        registry.load_database(self.path)
        return registry

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
            with Vertical(id="tree-panel"):
                yield Static(
                    "Bars: annotated duration · b to switch",
                    id="bar-mode",
                    markup=False,
                )
                yield StatisticsTree(self.path.name, id="structure")
            with TabbedContent(id="details"):
                with TabPane("Statistics", id="statistics-tab"):
                    with VerticalScroll(id="statistics-scroll"):
                        yield Static(id="source", markup=False)
                        yield Static(id="progress-label", markup=False)
                        yield ProgressBar(total=1, show_eta=False, id="progress")
                        yield Static(id="statistics")
                    yield Static(id="legend")
                with TabPane("Configuration", id="configuration-tab"):
                    with VerticalScroll():
                        yield Static(id="preview")
                with TabPane("Provenance", id="provenance-tab"):
                    yield Static(id="provenance-path", markup=False)
                    with VerticalScroll(id="provenance-scroll"):
                        yield Static(id="provenance-content")
        yield Footer()

    def on_mount(self) -> None:
        self.populate()
        self.query_one(Tree).focus()
        self.ensure_statistics_worker()

    def populate(self) -> None:
        tree = self.query_one(Tree)
        self.node_paths.clear()
        self.node_subsets.clear()
        self.default_subsets.clear()
        self.protocol_subsets.clear()
        tree.clear()
        tree.root.data = self.document
        for database_name in sorted(self.registry.databases):
            database = self.registry.get_database(database_name)
            db_node = tree.root.add(
                Text(database_name), data={"Database": database_name}
            )
            for task in sorted(getattr(database, "protocols_", {})):
                task_node = db_node.add(Text(task), data={"Task": task})
                for protocol_name in database.get_protocols(task):
                    name = f"{database_name}.{task}.{protocol_name}"
                    protocol = self.registry.get_protocol(name)
                    source = protocol.database_yml
                    relative = os.path.relpath(source, self.path.parent)
                    label = Text(protocol_name)
                    label.append(f"  [{relative}]", style="dim")
                    node = task_node.add(label, data=protocol.configuration)
                    self.node_paths[node.id] = (name, source)
                    available = [
                        subset
                        for subset in ("train", "development", "test", "files")
                        if subset in protocol.configuration
                    ]
                    self.default_subsets[name] = available[0] if available else "train"
                    self.protocol_subsets[name] = available or ["train"]
                    for subset in ("files", "train", "development", "test"):
                        if subset in protocol.configuration:
                            child = node.add_leaf(
                                Text(subset), data=protocol.configuration[subset]
                            )
                            self.node_paths[child.id] = (name, source)
                            self.node_subsets[child.id] = subset
        tree.root.expand()
        tree.move_cursor(tree.root)
        self.query_one(StatisticsTree).metrics = {}
        self.update_tree_statistics()
        self.show_value(self.document)

    def show_value(self, value: Any) -> None:
        self.query_one("#preview", Static).update(
            Syntax(
                yaml.safe_dump(value, sort_keys=False, allow_unicode=True),
                "yaml",
                word_wrap=True,
            )
        )

    def on_tree_node_highlighted(self, event: Tree.NodeHighlighted) -> None:
        self.show_value(event.node.data)
        path = self.node_paths.get(event.node.id, ())
        self.query_one("#source", Static).update(
            f"Defined in: {path[1]}"
            if path
            else f"Entry configuration: {self.path}\n{len(self.registry.configs)} configuration files loaded"
        )
        source = Path(path[1]) if path else self.path
        if not path and event.node is not self.query_one(Tree).root:
            sources = set()

            def collect_sources(node):
                if node.id in self.node_paths:
                    sources.add(Path(self.node_paths[node.id][1]))
                for child in node.children:
                    collect_sources(child)

            collect_sources(event.node)
            if len(sources) == 1:
                source = sources.pop()
        self.provenance_candidates = self.find_provenance_candidates(
            source, event.node.data
        )
        self.query_one("#provenance-path", Static).update("")
        if self.query_one(TabbedContent).active == "provenance-tab":
            self.load_provenance()
        self.load_statistics(path, self.node_subsets.get(event.node.id))
        self.query_one("#statistics-scroll", VerticalScroll).scroll_home(animate=False)

    def on_tabbed_content_tab_activated(
        self, event: TabbedContent.TabActivated
    ) -> None:
        if event.pane.id == "provenance-tab":
            self.load_provenance()

    @staticmethod
    def find_provenance_candidates(source, configuration):
        base = Path(source).parent
        candidates = []
        entries = [configuration] if isinstance(configuration, dict) else []
        entries += (
            [
                value
                for value in (configuration or {}).values()
                if isinstance(value, dict)
            ]
            if isinstance(configuration, dict)
            else []
        )
        for entry in entries:
            annotation = entry.get("annotation")
            if not isinstance(annotation, str):
                continue
            directory = Path(annotation).expanduser().parent
            if not directory.is_absolute():
                directory = base / directory
            while directory != base and directory.is_relative_to(base):
                if "{" not in str(directory):
                    candidates.append(directory / "provenance.yaml")
                directory = directory.parent
        candidates.extend(
            [base / "annotations" / "provenance.yaml", base / "provenance.yaml"]
        )
        return tuple(dict.fromkeys(candidates))

    @work(exclusive=True, group="provenance")
    async def load_provenance(self):
        candidates = self.provenance_candidates
        panel = self.query_one("#provenance-content", Static)
        panel.update("Looking for provenance.yaml…")

        def read_provenance():
            for path in candidates:
                try:
                    return path, path.read_text(encoding="utf-8")
                except FileNotFoundError:
                    continue
            return None, None

        try:
            path, source = await asyncio.to_thread(read_provenance)
        except (OSError, UnicodeError) as error:
            panel.update(Text(f"Cannot read provenance: {error}", style="red"))
            return
        if candidates != self.provenance_candidates:
            return
        if path is None:
            self.query_one("#provenance-path", Static).update("")
            panel.update(Text("No provenance.yaml found for this selection."))
        else:
            self.query_one("#provenance-path", Static).update(str(path))
            panel.update(Syntax(source, "yaml", line_numbers=True, word_wrap=True))
        self.query_one("#provenance-scroll", VerticalScroll).scroll_home(animate=False)

    def on_tree_node_expanded(self, event: Tree.NodeExpanded) -> None:
        node = event.node
        # Database nodes are direct children of the root. Skip the extra
        # expansion step when there is no task choice to make.
        if node.parent is self.query_one(Tree).root and len(node.children) == 1:
            node.children[0].expand()
        if node.parent is not None:
            self.statistics_wakeup.set()
        self.update_tree_statistics()
        self.ensure_statistics_worker()

    def on_tree_node_collapsed(self, event: Tree.NodeCollapsed) -> None:
        self.update_tree_statistics()

    def expanded_protocols(self):
        tree = self.query_one(StatisticsTree)
        names = []
        for node_id, (name, _) in self.node_paths.items():
            if node_id in self.node_subsets:
                continue
            node = tree.get_node_by_id(node_id)
            if not node.is_expanded:
                continue
            ancestor = node.parent
            while ancestor is not None and ancestor.is_expanded:
                ancestor = ancestor.parent
            if ancestor is None:
                names.append(name)
        return names

    def visible_summaries(self, summaries):
        if self.selected_subset in summaries:
            return {self.selected_subset: summaries[self.selected_subset]}
        return {"protocol": summaries["protocol"]} if "protocol" in summaries else {}

    def show_statistics(self, name, summaries):
        from .tui_stats import render_legend, render_statistics

        visible = self.visible_summaries(summaries)
        self.query_one("#statistics", Static).update(
            render_statistics(name, visible)
            if visible
            else Text(f"{self.selected_subset}: statistics not available yet.")
        )
        self.query_one("#legend", Static).update(render_legend(visible))

    def subset_ready(self, name, subset):
        return name in self.statistics_cache or (
            name in self.jobs and subset in self.jobs[name][0].completed
        )

    def load_statistics(self, path, subset=None):
        from .tui_stats import render_legend

        previous = (self.selected_protocol, self.selected_subset)
        self.selected_protocol = path[0] if path else None
        self.selected_subset = subset or self.default_subsets.get(
            self.selected_protocol, "train"
        )
        if path:
            self.priority_target = (self.selected_protocol, self.selected_subset)
            if previous != self.priority_target:
                self.statistics_wakeup.set()
        self.last_statistics_render = 0.0
        panel = self.query_one("#statistics", Static)
        progress = self.query_one("#progress", ProgressBar)
        label = self.query_one("#progress-label", Static)
        name = self.selected_protocol
        self.query_one("#legend", Static).update(
            render_legend(self.visible_summaries(self.statistics_cache.get(name, {})))
        )
        if name is None:
            panel.update(
                "Select a protocol or subset to see file counts and statistics."
            )
            progress.display = False
            label.update("")
        elif self.subset_ready(name, self.selected_subset):
            self.show_statistics(
                name,
                self.statistics_cache.get(name, self.jobs.get(name, (None, {}))[1]),
            )
            progress.display = False
            label.update("Loaded from cache · r to refresh")
        else:
            progress.display = True
            progress.update(total=None)
            label.update(f"Loading {name} in background…")
            self.show_statistics(name, self.jobs.get(name, (None, {}))[1])
        self.ensure_statistics_worker()

    def ensure_statistics_worker(self):
        if not self.statistics_running and self.next_statistics_protocol() is not None:
            self.statistics_running = True
            self.run_statistics()

    def next_statistics_protocol(self):
        if not self.query(StatisticsTree):
            return None
        if self.priority_target and not self.subset_ready(*self.priority_target):
            return self.priority_target[0]
        if not self.preload_enabled:
            return None
        eligible = self.expanded_protocols()
        tree = self.query_one(StatisticsTree)
        candidates = []
        for line in range(
            tree.scroll_offset.y, tree.scroll_offset.y + tree.size.height
        ):
            node = tree.get_node_at_line(line)
            path = self.node_paths.get(node.id) if node is not None else None
            if path and path[0] in eligible:
                candidates.append(path[0])
        candidates.extend(name for name in self.jobs if name in eligible)
        candidates.extend(eligible)
        candidates.extend(self.default_subsets)
        return next(
            (name for name in candidates if name not in self.statistics_cache), None
        )

    async def wait_for_statistics_priority(self, delay):
        try:
            await asyncio.wait_for(self.statistics_wakeup.wait(), timeout=delay)
        except TimeoutError:
            pass
        self.statistics_wakeup.clear()

    @work()
    async def run_statistics(self):
        from .tui_stats import SubsetStatisticsJob

        try:
            # Startup work yields immediately to navigation. Background scans
            # deliberately leave idle time between file-sized work units.
            await self.wait_for_statistics_priority(self.STARTUP_PRELOAD_DELAY)
            while (name := self.next_statistics_protocol()) is not None:
                if (
                    not self.priority_target
                    or name != self.priority_target[0]
                    or self.subset_ready(*self.priority_target)
                ):
                    await self.wait_for_statistics_priority(self.IDLE_PRELOAD_DELAY)
                    name = self.next_statistics_protocol()
                    if name is None:
                        break
                generation = self.generation
                cache = self.disk_cache
                if name not in self.jobs:
                    cached = (
                        None
                        if self.ignore_disk_cache
                        else await asyncio.to_thread(cache.get, name)
                    )
                    if generation != self.generation or not self.query(StatisticsTree):
                        continue
                    if cached is not None:
                        self.statistics_cache[name] = cached
                        self.update_tree_statistics()
                        if name == self.selected_protocol:
                            self.load_statistics((name,), self.selected_subset)
                        continue
                    self.jobs[name] = (
                        SubsetStatisticsJob(
                            self.registry,
                            name,
                            self.protocol_subsets.get(name, ("train",)),
                        ),
                        {},
                    )
                iterator, summaries = self.jobs[name]
                try:
                    # A single file is the scheduling unit. Paused iterators keep
                    # their loaders and accumulated results for later resumption.
                    preferred = (
                        self.priority_target[1]
                        if self.priority_target and name == self.priority_target[0]
                        else None
                    )
                    update = await asyncio.to_thread(iterator.advance, preferred)
                except Exception as error:
                    update = None
                    summaries = {"protocol": {"error": str(error)}}
                if generation != self.generation or not self.query(StatisticsTree):
                    continue
                if update is None:
                    summaries = iterator.summaries or summaries
                    self.jobs.pop(name, None)
                    self.statistics_cache[name] = summaries
                    self.update_tree_statistics()
                    await asyncio.to_thread(cache.put, name, summaries)
                    if name == self.selected_protocol:
                        self.load_statistics((name,), self.selected_subset)
                    continue
                summaries, message, completed, total = update
                self.jobs[name] = (iterator, summaries)
                if time.monotonic() - self.last_statistics_render >= 0.1:
                    self.last_statistics_render = time.monotonic()
                    self.update_tree_statistics()
                    if name == self.selected_protocol:
                        self.query_one("#progress-label", Static).update(
                            f"{message} · {completed}/{total} subsets complete"
                        )
                        self.query_one("#progress", ProgressBar).update(
                            total=total, progress=completed
                        )
                        self.show_statistics(name, summaries)
                        if self.subset_ready(name, self.selected_subset):
                            self.query_one("#progress", ProgressBar).display = False
                            self.query_one("#progress-label", Static).update(
                                f"{self.selected_subset} ready · other subsets loading in background"
                            )
                await asyncio.sleep(0)  # allow navigation to change priority
        finally:
            self.statistics_running = False

    def update_tree_statistics(self):
        if not self.query(StatisticsTree):
            return
        tree = self.query_one(StatisticsTree)
        eligible = self.expanded_protocols()
        done = sum(name in self.statistics_cache for name in self.default_subsets)
        self.sub_title = f"{self.path} · {done}/{len(self.default_subsets)} protocols loaded · background preload throttled"
        metrics = {}
        # Dataset and protocol rows remain navigation-only. Only subset rows
        # have meaningful, directly comparable file/duration totals.
        for node_id, subset in self.node_subsets.items():
            name = self.node_paths[node_id][0]
            summaries = self.statistics_cache.get(
                name, self.jobs.get(name, (None, {}))[1]
            )
            stats = summaries.get(subset)
            finished = self.subset_ready(name, subset)
            state = (
                "loading"
                if name in self.jobs
                or name in eligible
                or name == self.selected_protocol
                else "idle"
            )
            if finished:
                state = (
                    "unavailable"
                    if not stats or stats.get("error") or stats.get("errors")
                    else False
                )
            metrics[node_id] = (
                stats.get("files", 0) if stats else 0,
                stats.get("annotated", 0) if stats else 0,
                state,
            )
        old = tree.metrics
        tree.metrics = metrics
        for node_id in old.keys() | metrics.keys():
            if old.get(node_id) != metrics.get(node_id):
                node = tree.get_node_by_id(node_id)
                node.set_label(node.label)
        tree.refresh()

    def action_bar_metric(self):
        tree = self.query_one(StatisticsTree)
        tree.metric = "files" if tree.metric == "duration" else "duration"
        tree.refresh()
        metric = "annotated duration" if tree.metric == "duration" else "file count"
        self.query_one("#bar-mode", Static).update(f"Bars: {metric} · b to switch")

    def action_toggle(self) -> None:
        node = self.query_one(Tree).cursor_node
        if node is not None:
            node.toggle()

    def action_reload(self) -> None:
        try:
            document = self.read_document()
            registry = self.read_registry()
        except (OSError, UnicodeError, yaml.YAMLError, ValueError) as error:
            self.notify(str(error), title="Reload failed", severity="error")
            return
        self.generation += 1
        self.selected_protocol = None
        self.priority_target = None
        self.jobs.clear()
        self.ignore_disk_cache = True
        self.document = document
        self.registry = registry
        self.disk_cache = StatisticsCache(registry)
        self.statistics_cache.clear()
        self.populate()
        self.ensure_statistics_worker()
        self.notify("Configuration reloaded")
