"""Load and validate compound configurations before replacing a composer draft."""

from dataclasses import dataclass
from pathlib import Path

import yaml
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Select, Static

from .registry import Registry

SPLITS = ("train", "development", "test")


@dataclass
class LoadedCompound:
    path: Path
    document: dict
    registry: Registry
    name: str
    selections: dict


def compound_selections(registry, name):
    """Flatten nested meta-protocols and pin default aliases to explicit versions.

    Repeated references cannot be represented by independent checkboxes, so reject
    them rather than silently changing the number of files in a loaded compound.
    """
    if not name.startswith("X.SpeakerDiarization."):
        raise ValueError("Choose an X.SpeakerDiarization compound.")
    root = registry.get_protocol(name)
    selections = {split: set() for split in SPLITS}

    def expand(protocol_name, subset, target, ancestors):
        if subset not in SPLITS:
            raise ValueError(f"Unsupported source subset: {subset}")
        if subset == "test" and target != "test":
            raise ValueError(
                "Source test subsets can only enter compound test (including nested compounds)."
            )
        key = protocol_name, subset
        if key in ancestors:
            raise ValueError(f"Cyclic compound reference: {protocol_name} / {subset}")
        if ".SpeakerDiarization." not in protocol_name:
            raise ValueError(f"Not a diarization protocol: {protocol_name}")
        protocol = registry.get_protocol(protocol_name)
        if subset not in protocol.configuration:
            raise ValueError(f"Missing subset: {protocol_name} / {subset}")
        if protocol_name.startswith("X."):
            members = protocol.configuration[subset]
            if not isinstance(members, dict):
                raise ValueError(f"Expected a mapping for {protocol_name} / {subset}")
            for member, subsets in members.items():
                if not isinstance(subsets, list):
                    raise ValueError(f"Expected a list of subsets for {member}")
                for member_subset in subsets:
                    yield from expand(member, member_subset, target, ancestors | {key})
        else:
            version = getattr(protocol, "annotation_version", None)
            if version:
                protocol_name = protocol_name.partition("@")[0] + "@" + version["name"]
            yield protocol_name, subset

    for target in SPLITS:
        if target not in root.configuration:
            continue
        for source in expand(name, target, target, set()):
            if source in selections[target]:
                raise ValueError(
                    f"Repeated source in {target}: {source[0]} / {source[1]}. Checkboxes cannot preserve duplicates."
                )
            selections[target].add(source)
    if not any(selections.values()):
        raise ValueError("This compound has no source subsets.")
    return selections


class LoadCompoundScreen(ModalScreen):
    DEFAULT_CSS = """
    LoadCompoundScreen { align: center middle; background: $background 70%; }
    #load-compound-dialog { width: 80%; max-width: 100; height: auto; padding: 1 2; border: thick $primary; }
    #load-compound-dialog Static { height: auto; }
    #load-compound-dialog Input, #load-compound-dialog Select { margin: 1 0; }
    #load-compound-actions { height: 3; }
    #load-compound-actions Button { margin-right: 1; }
    """
    BINDINGS = [("escape", "cancel", "Cancel")]

    def __init__(self, path):
        super().__init__()
        self.initial_path = str(path)
        self.catalog = None

    def compose(self) -> ComposeResult:
        with Vertical(id="load-compound-dialog"):
            yield Static("Load an existing compound dataset", classes="title")
            yield Input(
                self.initial_path,
                placeholder="Path to compound YAML",
                id="load-compound-path",
            )
            yield Button("Read file", id="load-compound-read")
            yield Select([], prompt="Choose a compound", id="load-compound-name")
            yield Static(
                "Read the file, then select the compound to load. The current draft is replaced only after validation.",
                id="load-compound-status",
                markup=False,
            )
            with Horizontal(id="load-compound-actions"):
                yield Button(
                    "Load", id="load-compound-apply", variant="primary", disabled=True
                )
                yield Button("Cancel", id="load-compound-cancel")

    def action_cancel(self):
        self.dismiss(None)

    def on_input_changed(self, event):
        self.catalog = None
        self.query_one("#load-compound-apply", Button).disabled = True

    def on_input_submitted(self, event):
        self.read_file()

    def read_file(self):
        self.catalog = None
        self.query_one("#load-compound-apply", Button).disabled = True
        try:
            path = (
                Path(self.query_one("#load-compound-path", Input).value)
                .expanduser()
                .resolve()
            )
            with path.open(encoding="utf-8") as stream:
                document = yaml.safe_load(stream)
            registry = Registry()
            registry.load_database(path)
            if not isinstance(document, dict) or "X" not in registry.databases:
                raise ValueError("No X.SpeakerDiarization compounds found.")
            database = registry.get_database("X")
            names = sorted(
                getattr(database, "protocols_", {}).get("SpeakerDiarization", {})
            )
            versioned = {name.partition("@")[0] for name in names if "@" in name}
            names = [name for name in names if "@" in name or name not in versioned]
            if not names:
                raise ValueError("No X.SpeakerDiarization compounds found.")
            self.catalog = path, document, registry
            selector = self.query_one("#load-compound-name", Select)
            selector.set_options([(name, name) for name in names])
            selector.value = names[0]
            self.query_one("#load-compound-apply", Button).disabled = False
            self.query_one("#load-compound-status", Static).update(
                f"Found {len(names)} compound(s). Choose one and press Load."
            )
        except (
            OSError,
            UnicodeError,
            yaml.YAMLError,
            ValueError,
            KeyError,
            AttributeError,
        ) as error:
            self.query_one("#load-compound-status", Static).update(
                f"Cannot read: {error}"
            )

    def on_button_pressed(self, event):
        event.stop()
        if event.button.id == "load-compound-cancel":
            self.action_cancel()
        elif event.button.id == "load-compound-read":
            self.read_file()
        elif event.button.id == "load-compound-apply" and self.catalog:
            path, document, registry = self.catalog
            name = self.query_one("#load-compound-name", Select).value
            if not isinstance(name, str):
                return
            try:
                selections = compound_selections(
                    registry, f"X.SpeakerDiarization.{name}"
                )
            except (ValueError, KeyError, AttributeError) as error:
                self.query_one("#load-compound-status", Static).update(
                    f"Cannot load: {error}"
                )
                return
            self.dismiss(LoadedCompound(path, document, registry, name, selections))
