"""A4 pagination, frozen data, and complete attachments in compound PDF exports."""

import json
from io import BytesIO

import pytest

pytest.importorskip("textual")
pytest.importorskip("reportlab")

from pyannote.database.tui_pdf import (
    CompoundReport,
    ReportSource,
    render_compound_pdf,
    write_compound_pdf,
)

pypdf = pytest.importorskip("pypdf")


@pytest.fixture
def report():
    return CompoundReport(
        name="Brainstorm",
        metric="annotated",
        created="2026-11-25 12:00 UTC",
        catalog="/catalog/database.yml",
        configuration={"Requirements": ["database.yml"]},
        splits={
            "train": [
                ReportSource(
                    "AMI.SpeakerDiarization.Raw@words",
                    "train",
                    100,
                    7200,
                    "word",
                    0.2,
                    True,
                ),
                ReportSource(
                    "MSDWILD.SpeakerDiarization.Raw@original",
                    "train",
                    20,
                    1800,
                    "mixed",
                    0.0,
                    False,
                ),
            ],
            "development": [],
            "test": [
                ReportSource(
                    "AppTek.SpeakerDiarization.Raw@original",
                    "test",
                    0,
                    0,
                    "unknown",
                    None,
                    None,
                    "incomplete / errors",
                    "missing annotations",
                )
            ],
        },
    )


def test_three_a4_pages_and_complete_embedded_data(report):
    reader = pypdf.PdfReader(BytesIO(render_compound_pdf(report)))
    assert len(reader.pages) == 3
    for page, title in zip(reader.pages, ("Training", "Development", "Test")):
        assert float(page.mediabox.width) == pytest.approx(595.2756, abs=0.01)
        assert float(page.mediabox.height) == pytest.approx(841.8898, abs=0.01)
        assert title in page.extract_text()
        assert "X.SpeakerDiarization.Brainstorm" in page.extract_text()
    assert "80.0%" in reader.pages[0].extract_text()
    assert "NC: MSDWILD" in reader.pages[0].extract_text()
    assert "No sources selected" in reader.pages[1].extract_text()
    assert "PROVISIONAL" in reader.pages[2].extract_text()
    assert "0 non-commercial; 1 unknown" in reader.pages[2].extract_text()
    data = json.loads(reader.attachments["composition.json"][0])
    assert data["splits"]["train"][0]["closing"] == 0.2
    assert data["splits"]["test"][0]["errors"] == "missing annotations"
    assert "compound.yml" in reader.attachments


def test_dense_report_stays_three_pages_with_all_sources_attached(report):
    report.splits["train"].clear()
    report.splits["train"].extend(
        ReportSource(
            f"Dataset{i}.SpeakerDiarization.LongProtocol@long_version",
            "train",
            1,
            i + 1,
            "turn",
            0,
            True,
        )
        for i in range(60)
    )
    reader = pypdf.PdfReader(BytesIO(render_compound_pdf(report)))
    assert len(reader.pages) == 3
    assert "+ 52 more sources" in reader.pages[0].extract_text()
    data = json.loads(reader.attachments["composition.json"][0])
    assert len(data["splits"]["train"]) == 60


def test_pdf_export_refuses_to_overwrite(report, tmp_path):
    output = tmp_path / "compound.pdf"
    output.write_bytes(b"original")
    with pytest.raises(FileExistsError):
        write_compound_pdf(report, output)
    assert output.read_bytes() == b"original"
