"""Literal audio channel policies are metadata, not annotation file paths."""

import pytest
import yaml

from pyannote.database.custom import gather_loaders
from pyannote.database.registry import Registry

OMITTED = object()


def protocol_yaml(tmp_path, value=OMITTED):
    (tmp_path / "files.lst").write_text("one\ntwo\n")
    (tmp_path / "annotations.rttm").write_text(
        "SPEAKER one 1 0 1 <NA> <NA> speaker <NA> <NA>\n"
        "SPEAKER two 1 0 1 <NA> <NA> speaker <NA> <NA>\n"
    )
    subset = {"uri": "files.lst", "annotation": "annotations.rttm"}
    if value is not OMITTED:
        subset["channel"] = value
    spec = {
        "scope": "file",
        "versions": {"original": {}},
        **{split: dict(subset) for split in ("train", "development", "test")},
    }
    config = {
        "Protocols": {
            "Example": {"SpeakerDiarization": {"Raw": spec}},
            "X": {
                "SpeakerDiarization": {
                    "Compound": {
                        split: {"Example.SpeakerDiarization.Raw@original": [split]}
                        for split in ("train", "development", "test")
                    }
                }
            },
        }
    }
    path = tmp_path / "database.yml"
    path.write_text(yaml.safe_dump(config))
    registry = Registry()
    registry.load_database(path)
    return registry


@pytest.mark.parametrize("value", [OMITTED, None, 0, 2, "downmix", "all", "random"])
@pytest.mark.parametrize("compound", [False, True])
def test_values_survive_versioned_and_compound_protocols(tmp_path, value, compound):
    registry = protocol_yaml(tmp_path, value)
    protocol = registry.get_protocol(
        "X.SpeakerDiarization.Compound"
        if compound
        else "Example.SpeakerDiarization.Raw@original"
    )
    for split in ("train", "development", "test"):
        # Database iteration is metadata inspection, not audio validation. The
        # consumer rejects random selections when actually validating a model.
        files = list(getattr(protocol, split)())
        assert len(files) == 2
        for file in files:
            if value is OMITTED:
                assert "channel" not in file
            else:
                assert file["channel"] == value
                assert type(file["channel"]) is type(value)
            assert file["annotation"].labels() == ["speaker"]


@pytest.mark.parametrize("value", [-1, -2, True, False, 1.5, 0.0, [], {}])
def test_invalid_literal_channels_fail_clearly(tmp_path, value):
    registry = protocol_yaml(tmp_path, value)
    protocol = registry.get_protocol("Example.SpeakerDiarization.Raw@original")
    with pytest.raises(ValueError, match="channel must be"):
        next(protocol.train())


@pytest.mark.parametrize("template", [False, True])
def test_channel_mapping_files_are_still_loaded(tmp_path, template):
    if template:
        for uri, channel in [("one", 0), ("two", 2)]:
            (tmp_path / f"{uri}.map").write_text(f"{uri} {channel}\n")
        value = "{uri}.map"
    else:
        (tmp_path / "channels.map").write_text("one 0\ntwo 2\n")
        value = "channels.map"
    protocol = protocol_yaml(tmp_path, value).get_protocol(
        "Example.SpeakerDiarization.Raw@original"
    )
    assert [file["channel"] for file in protocol.train()] == [0, 2]


@pytest.mark.parametrize("token", ["random", "downmix", "all"])
def test_only_channel_reserves_policy_strings(tmp_path, token):
    with pytest.raises(FileNotFoundError):
        gather_loaders({"domain": token}, tmp_path / "database.yml")
