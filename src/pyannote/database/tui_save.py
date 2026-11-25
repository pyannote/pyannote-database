"""Modal save and PDF export forms for the compound composer."""

import asyncio

import yaml
from rich.syntax import Syntax
from rich.text import Text
from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Static


class SaveCompoundScreen(ModalScreen):
    DEFAULT_CSS = """
    SaveCompoundScreen { align: center middle; background: $background 70%; }
    #save-compound-dialog { width: 85%; max-width: 110; height: 85%; max-height: 38; padding: 1 2; border: thick $primary; }
    #save-compound-dialog Static { height: auto; }
    #save-compound-title { text-style: bold; margin-bottom: 1; }
    #save-compound-form { height: 1fr; }
    #save-compound-dialog Input { margin-bottom: 1; }
    #save-compound-preview { margin-top: 1; }
    #save-compound-status { max-height: 4; overflow-y: auto; margin: 1 0; }
    #save-compound-actions { height: 3; }
    #save-compound-actions Button { margin-right: 1; }
    """
    BINDINGS = [
        ("escape", "cancel", "Cancel"),
        Binding("ctrl+s", "submit", "Confirm", priority=True),
        Binding("ctrl+e", "submit", "Confirm", priority=True),
    ]

    def __init__(self, composer, kind="yaml"):
        super().__init__()
        self.composer = composer
        self.kind = kind
        self.busy = False

    def compose(self) -> ComposeResult:
        pdf = self.kind == "pdf"
        output = (
            self.composer.pdf_output_path
            or self.composer.output_path.with_suffix(".pdf")
            if pdf
            else self.composer.output_path
        )
        with Vertical(id="save-compound-dialog"):
            yield Static(
                "Export compound PDF" if pdf else "Save compound YAML",
                id="save-compound-title",
            )
            with VerticalScroll(id="save-compound-form"):
                yield Static("Protocol name (under X.SpeakerDiarization)")
                yield Input(self.composer.protocol_name, id="compound-name")
                yield Static("New PDF file" if pdf else "New YAML file")
                yield Input(str(output), id="compound-output")
                yield Static(
                    "Three A4 pages: training, development, test. Uses the current chart metric "
                    "and all selections, including hidden ones. Incomplete statistics are marked provisional."
                    if pdf
                    else "Review the YAML below. Existing files are never overwritten.",
                    markup=False,
                )
                yield Static(id="save-compound-preview")
            yield Static(
                "Relative paths use the current directory. Escape cancels.",
                id="save-compound-status",
                markup=False,
            )
            with Horizontal(id="save-compound-actions"):
                yield Button(
                    "Export PDF" if pdf else "Save YAML",
                    id="save-compound-confirm",
                    variant="primary",
                )
                yield Button("Cancel", id="save-compound-cancel")

    def on_mount(self):
        self.refresh_preview()
        self.query_one("#compound-name", Input).focus()

    def on_input_changed(self, event):
        event.stop()
        if self.is_mounted:
            self.refresh_preview()

    def on_input_submitted(self, event):
        event.stop()
        if event.input.id == "compound-name":
            self.query_one("#compound-output", Input).focus()
        else:
            self.action_submit()

    def values(self):
        return (
            self.query_one("#compound-name", Input).value.strip(),
            self.query_one("#compound-output", Input).value.strip(),
        )

    def refresh_preview(self):
        try:
            _, document = self.composer.export_document(*self.values())
        except (ValueError, OSError) as error:
            content = Text(str(error))
        else:
            if self.kind == "yaml":
                content = Syntax(
                    yaml.safe_dump(document, sort_keys=False, allow_unicode=True),
                    "yaml",
                    word_wrap=True,
                )
            else:
                metric = (
                    "file count"
                    if self.composer.metric == "files"
                    else "annotated duration"
                )
                counts = ", ".join(
                    f"{split}: {len(sources)} sources"
                    for split, sources in self.composer.draft.selections.items()
                )
                content = Text(
                    f"Treemap area: {metric}\n{counts}\nThe complete configuration and source details are attached inside the PDF."
                )
        self.query_one("#save-compound-preview", Static).update(content)

    def action_cancel(self):
        if not self.busy:
            self.dismiss(None)

    def on_button_pressed(self, event):
        event.stop()
        if event.button.id == "save-compound-cancel":
            self.action_cancel()
        elif event.button.id == "save-compound-confirm":
            self.action_submit()

    def show_error(self, error):
        operation = "export PDF" if self.kind == "pdf" else "save"
        self.query_one("#save-compound-status", Static).update(
            f"Cannot {operation}: {error}"
        )

    def finish(self, name, output):
        self.composer.protocol_name = name
        if self.kind == "pdf":
            self.composer.pdf_output_path = output
        else:
            if self.composer.output_path != output:
                self.composer.pdf_output_path = None
            self.composer.output_path = output
            self.composer.load_path = output
        self.composer.notify(
            f"Saved {output}",
            title="Compound PDF" if self.kind == "pdf" else "Compound dataset",
        )
        self.dismiss(output)

    def action_submit(self):
        if self.busy:
            return
        name, value = self.values()
        try:
            if self.kind == "pdf":
                output, report = self.composer.pdf_snapshot(name, value)
                self.busy = True
                for widget in self.query("Input, Button"):
                    widget.disabled = True
                self.query_one("#save-compound-status", Static).update(
                    "Exporting three A4 pages..."
                )
                self.export_pdf(name, output, report)
                return
            output, document = self.composer.export_document(name, value)
            content = yaml.safe_dump(document, sort_keys=False, allow_unicode=True)
            with output.open("x", encoding="utf-8") as stream:
                stream.write(content)
        except (ValueError, OSError) as error:
            self.show_error(error)
            return
        self.finish(name, output)

    @work(group="compound-pdf")
    async def export_pdf(self, name, output, report):
        from .tui_pdf import write_compound_pdf

        try:
            await asyncio.to_thread(write_compound_pdf, report, output)
        except (ValueError, OSError, ImportError) as error:
            self.show_error(error)
        else:
            self.finish(name, output)
        finally:
            self.busy = False
            if self.is_mounted:
                for widget in self.query("Input, Button"):
                    widget.disabled = False
