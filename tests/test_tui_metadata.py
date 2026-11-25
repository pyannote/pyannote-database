import pytest

from pyannote.database.tui_metadata import read_commercial_use


@pytest.mark.parametrize(
    "contents",
    [
        None,
        "[broken",
        "[]",
        "licence: missing",
        "licence: {}",
        "licence: {commercial_use: 1}",
    ],
)
def test_missing_or_invalid_commercial_metadata_is_unknown(tmp_path, contents):
    if contents is not None:
        (tmp_path / "manifest.yaml").write_text(contents)
    result = read_commercial_use(tmp_path / "database.yml")
    assert result.allowed is None
    assert result.label == "commercial: unknown"


def test_us_spelling_and_yml_manifest(tmp_path):
    (tmp_path / "manifest.yml").write_text(
        "license: {commercial_use: false, name: Research only}"
    )
    result = read_commercial_use(tmp_path / "database.yml")
    assert result.allowed is False
    assert result.licence == "Research only"
    assert result.manifest == tmp_path / "manifest.yml"
