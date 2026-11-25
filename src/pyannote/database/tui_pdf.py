"""Three-page, vector A4 reports of a frozen compound composition."""

import json
from dataclasses import asdict, dataclass
from io import BytesIO
from pathlib import Path

import yaml

from .tui_treemap import partition, source_color


@dataclass(frozen=True)
class ReportSource:
    protocol: str
    subset: str
    files: int
    duration: float
    level: str
    closing: object
    commercial: bool | None
    status: str = ""
    errors: str = ""

    @property
    def key(self):
        return self.protocol, self.subset


@dataclass(frozen=True)
class CompoundReport:
    name: str
    metric: str
    created: str
    catalog: str
    splits: dict[str, list[ReportSource]]
    configuration: dict


def render_compound_pdf(report: CompoundReport) -> bytes:
    """Render exactly three A4 pages, with full details embedded as attachments.

    The visible legend is bounded to keep type legible even for large compounds.
    Complete selections, metadata, measurements and failures are attached as JSON,
    alongside the same YAML configuration produced by the composer.
    """
    import reportlab
    from pypdf import PdfReader, PdfWriter
    from reportlab.lib.colors import HexColor, white
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.pdfgen.canvas import Canvas

    if report.metric not in {"files", "annotated"}:
        raise ValueError("PDF metric must be 'files' or 'annotated'.")
    fonts = Path(reportlab.__file__).parent / "fonts"
    for name, filename in (
        ("CompoundSans", "Vera.ttf"),
        ("CompoundBold", "VeraBd.ttf"),
    ):
        if name not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(name, str(fonts / filename)))
    buffer = BytesIO()
    canvas = Canvas(buffer, pagesize=A4, pageCompression=1)
    canvas.setTitle(f"{report.name} - compound dataset")
    width, height = A4
    margin = 36
    content_width = width - 2 * margin

    def text(value, x, y, size=9, color="#334155", bold=False, max_width=None):
        value = str(value).replace("\n", " ")
        font = "CompoundBold" if bold else "CompoundSans"
        if (
            max_width is not None
            and pdfmetrics.stringWidth(value, font, size) > max_width
        ):
            while (
                value and pdfmetrics.stringWidth(value + "...", font, size) > max_width
            ):
                value = value[:-1]
            value += "..."
        canvas.setFont(font, size)
        canvas.setFillColor(HexColor(color))
        canvas.drawString(x, y, value)

    for page, (split, title) in enumerate(
        (("train", "Training"), ("development", "Development"), ("test", "Test")), 1
    ):
        rows = report.splits.get(split, [])

        def value(row):
            return row.files if report.metric == "files" else row.duration

        rows = sorted(rows, key=lambda row: (-value(row), row.key))
        total = sum(value(row) for row in rows)
        files = sum(row.files for row in rows)
        duration = sum(row.duration for row in rows)
        incomplete = sum(bool(row.status) for row in rows)
        restricted = sum(row.commercial is False for row in rows)
        unknown = sum(row.commercial is None for row in rows)
        text(
            "COMPOUND DATASET / DISCUSSION COPY",
            margin,
            height - 34,
            8,
            "#64748b",
            True,
        )
        text(title, margin, height - 69, 28, "#0f172a", True)
        text(
            f"X.SpeakerDiarization.{report.name}",
            margin,
            height - 92,
            11,
            max_width=content_width,
        )
        text(
            f"{duration / 3600:,.2f} annotated hours   |   {files:,} files   |   {len(rows)} sources",
            margin,
            height - 116,
            11,
            "#0f172a",
            True,
        )
        metric = "file count" if report.metric == "files" else "annotated duration"
        text(
            f"Rectangle area: {metric}. Percentages use the known total for this split.",
            margin,
            height - 134,
            8,
        )
        if incomplete:
            text(
                f"PROVISIONAL - {incomplete} source(s) pending, partial, or failed.",
                margin,
                height - 150,
                9,
                "#b45309",
                True,
            )
        else:
            text(
                "Statistics complete." if rows else "No sources selected.",
                margin,
                height - 150,
                9,
            )
        text(
            f"Commercial metadata: {restricted} non-commercial; {unknown} unknown.",
            margin,
            height - 166,
            9,
            "#991b1b" if restricted else "#854d0e" if unknown else "#334155",
        )

        chart_x, chart_y, chart_width, chart_height = margin, 342, content_width, 316
        canvas.setFillColor(HexColor("#f1f5f9"))
        canvas.rect(chart_x, chart_y, chart_width, chart_height, stroke=0, fill=1)
        if total > 0:
            by_key = {row.key: row for row in rows}
            for key, (x, y, w, h) in partition(
                [(row.key, value(row)) for row in rows],
                chart_width,
                chart_height,
                cell_aspect=1,
            ):
                row = by_key[key]
                canvas.setFillColor(HexColor(source_color(key, row.commercial)))
                canvas.setStrokeColor(white)
                canvas.setLineWidth(2)
                bottom = chart_y + chart_height - y - h
                canvas.rect(chart_x + x, bottom, w, h, stroke=1, fill=1)
                if w < 26 or h < 36:
                    continue
                label = row.protocol.partition(".")[0]
                if row.commercial is False:
                    label = "NC: " + label
                elif row.commercial is None:
                    label = "?: " + label
                font_size = min(16, max(8, min(w / 10, (h - 20) / 2)))
                label_width = pdfmetrics.stringWidth(label, "CompoundBold", font_size)
                label_x = chart_x + x + max(5, (w - label_width) / 2)
                text(
                    label,
                    label_x,
                    bottom + h / 2 + 3,
                    font_size,
                    "#ffffff",
                    True,
                    w - 10,
                )
                share = f"{value(row) / total:.1%}"
                share_width = pdfmetrics.stringWidth(share, "CompoundSans", 9)
                text(
                    share,
                    chart_x + x + (w - share_width) / 2,
                    bottom + h / 2 - 12,
                    9,
                    "#ffffff",
                )
        else:
            text(
                "No measured contribution yet" if rows else "No sources selected",
                chart_x + 20,
                chart_y + chart_height / 2,
                15,
                "#64748b",
                True,
            )

        text(
            "NC / red: non-commercial. ? / amber: commercial status unknown.",
            margin,
            327,
            8,
        )
        text("SOURCE DETAILS", margin, 305, 9, "#0f172a", True)
        max_rows = 8
        for index, row in enumerate(rows[:max_rows]):
            y = 286 - index * 23
            canvas.setFillColor(HexColor(source_color(row.key, row.commercial)))
            canvas.rect(margin, y - 1, 6, 6, stroke=0, fill=1)
            label = (
                row.protocol.replace(".SpeakerDiarization.", ".") + " / " + row.subset
            )
            text(label, margin + 12, y, 8, "#0f172a", True, content_width - 115)
            amount = (
                f"{value(row):,} files"
                if report.metric == "files"
                else f"{value(row) / 3600:,.2f} h"
            )
            text(amount, width - margin - 96, y, 8, "#0f172a")
            closing = f"{row.closing}s" if row.closing is not None else "unknown"
            permission = (
                "NON-COMMERCIAL"
                if row.commercial is False
                else "UNKNOWN"
                if row.commercial is None
                else "yes (catalog)"
            )
            detail = (
                f"{row.level}-level | closing: {closing} | commercial: {permission}"
            )
            if row.status:
                detail += f" | {row.status}"
            text(detail, margin + 12, y - 10, 7, max_width=content_width - 12)
        if len(rows) > max_rows:
            text(
                f"+ {len(rows) - max_rows} more sources. Complete details are in the attached composition.json.",
                margin,
                91,
                8,
                "#334155",
                max_width=content_width,
            )
        else:
            text(
                "Complete configuration and source details are attached to this PDF (YAML + JSON).",
                margin,
                91,
                7,
                max_width=content_width,
            )
        text(
            "Totals sum selected versions; recordings are not deduplicated. Tiny rectangles may be unlabeled.",
            margin,
            75,
            7,
            max_width=content_width,
        )
        canvas.setStrokeColor(HexColor("#cbd5e1"))
        canvas.line(margin, 63, width - margin, 63)
        text(f"Created {report.created}", margin, 48, 7)
        text(f"{page} / 3", width - margin - 25, 48, 8)
        text(f"Catalog: {report.catalog}", margin, 35, 6.5, max_width=content_width)
        canvas.showPage()
    canvas.save()

    writer = PdfWriter()
    writer.append(PdfReader(BytesIO(buffer.getvalue())))
    writer.add_metadata(
        {"/Title": f"{report.name} - compound dataset", "/Author": "pyannote.database"}
    )
    writer.add_attachment(
        "compound.yml",
        yaml.safe_dump(
            report.configuration, sort_keys=False, allow_unicode=True
        ).encode(),
    )
    writer.add_attachment(
        "composition.json",
        json.dumps(asdict(report), ensure_ascii=False, indent=2).encode(),
    )
    result = BytesIO()
    writer.write(result)
    return result.getvalue()


def write_compound_pdf(report: CompoundReport, output: Path) -> None:
    content = render_compound_pdf(report)
    with Path(output).open("xb") as stream:
        stream.write(content)
