import pytest
import yaml

pytest.importorskip("textual")

from pyannote.database.registry import Registry
from pyannote.database.tui_import import compound_selections


def registry_with_compounds(tmp_path, compounds):
    path = tmp_path / "database.yml"
    path.write_text(
        yaml.safe_dump(
            {
                "Protocols": {
                    "Demo": {
                        "SpeakerDiarization": {
                            "P": {
                                "scope": "file",
                                "versions": {"original": {}, "words": {}},
                                **{
                                    split: {"uri": "files.lst"}
                                    for split in ("train", "development", "test")
                                },
                            }
                        }
                    },
                    "X": {"SpeakerDiarization": compounds},
                }
            },
            sort_keys=False,
        )
    )
    registry = Registry()
    registry.load_database(path)
    return registry


def test_flatten_compound_and_pin_default_version(tmp_path):
    registry = registry_with_compounds(
        tmp_path,
        {
            "Inner": {"train": {"Demo.SpeakerDiarization.P@words": ["development"]}},
            "Outer": {
                "train": {
                    "X.SpeakerDiarization.Inner": ["train"],
                    "Demo.SpeakerDiarization.P": ["train"],
                }
            },
        },
    )
    assert compound_selections(registry, "X.SpeakerDiarization.Outer") == {
        "train": {
            ("Demo.SpeakerDiarization.P@words", "development"),
            ("Demo.SpeakerDiarization.P@original", "train"),
        },
        "development": set(),
        "test": set(),
    }


@pytest.mark.parametrize(
    "compounds, message",
    [
        (
            {"Bad": {"train": {"Demo.SpeakerDiarization.P": ["test"]}}},
            "only enter compound test",
        ),
        (
            {
                "Bad": {"train": {"X.SpeakerDiarization.Inner": ["development"]}},
                "Inner": {"development": {"Demo.SpeakerDiarization.P": ["test"]}},
            },
            "only enter compound test",
        ),
        ({"Bad": {"train": {"X.SpeakerDiarization.Bad": ["train"]}}}, "Cyclic"),
        (
            {"Bad": {"train": {"Demo.SpeakerDiarization.P": ["train", "train"]}}},
            "Repeated source",
        ),
    ],
)
def test_reject_imports_that_cannot_be_represented_safely(tmp_path, compounds, message):
    registry = registry_with_compounds(tmp_path, compounds)
    with pytest.raises(ValueError, match=message):
        compound_selections(registry, "X.SpeakerDiarization.Bad")
