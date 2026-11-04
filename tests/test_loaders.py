from io import StringIO

import pytest
from pyannote.core import Annotation, Segment, Timeline

from pyannote.database.util import load_lab, load_mdtm, load_rttm, load_stm, load_uem


@pytest.mark.parametrize("keep_type", ["SPEAKER", "LEXEME"])
def test_load_rttm_preserves_tracks_and_filters_types(keep_type):
    rttm = StringIO(
        "SPEAKER second 1 2.0 1.0 <NA> <NA> bob <NA> <NA>\n"
        "LEXEME first 1 0.0 1.0 <NA> <NA> word <NA> <NA>\n"
        "SPEAKER first 1 1.0 2.0 <NA> <NA> alice <NA> <NA>\n"
        "SPEAKER first 1 1.0 2.0 <NA> <NA> bob <NA> <NA>\n"
        "SPEAKER second 1 0.0 3.0 <NA> <NA> alice <NA> <NA>\n"
        "SPEAKER empty 1 0.0 0.0 <NA> <NA> nobody <NA> <NA>\n"
        "SPEAKER empty 1 1.0 -1.0 <NA> <NA> nobody <NA> <NA>\n"
    )

    expected = {uri: Annotation(uri=uri) for uri in ["empty", "first", "second"]}
    if keep_type == "SPEAKER":
        expected["first"][Segment(1.0, 3.0), 2] = "alice"
        expected["first"][Segment(1.0, 3.0), 3] = "bob"
        expected["second"][Segment(2.0, 3.0), 0] = "bob"
        expected["second"][Segment(0.0, 3.0), 4] = "alice"
    else:
        expected["first"][Segment(0.0, 1.0), 1] = "word"

    actual = load_rttm(rttm, keep_type=keep_type)
    assert list(actual) == list(expected)
    for uri, annotation in actual.items():
        assert annotation.uri == uri
        assert annotation == expected[uri]


@pytest.mark.parametrize("loader", [load_rttm, load_stm, load_mdtm, load_uem])
def test_load_empty(loader):
    assert loader(StringIO("")) == {}


@pytest.mark.parametrize(
    "loader, template",
    [
        (load_stm, "{uri} 1 {label} {start} {end} <NA> words\n"),
        (load_mdtm, "{uri} 1 {start} {duration} speaker <NA> <NA> {label}\n"),
    ],
)
def test_annotation_loaders_preserve_tracks_and_labels(loader, template):
    rows = [
        ("second", 2.0, 3.0, "001"),
        ("first", 1.0, 3.0, "002"),
        ("second", 0.0, 3.0, "002"),
        ("first", 1.0, 3.0, "001"),
        ("empty", 0.0, 0.0, "003"),
        ("empty", 1.0, 0.0, "003"),
    ]
    content = "".join(
        template.format(
            uri=uri, start=start, end=end, duration=end - start, label=label
        )
        for uri, start, end, label in rows
    )
    expected = {uri: Annotation(uri=uri) for uri in ["empty", "first", "second"]}
    expected["first"][Segment(1.0, 3.0), 1] = "002"
    expected["first"][Segment(1.0, 3.0), 3] = "001"
    expected["second"][Segment(2.0, 3.0), 0] = "001"
    expected["second"][Segment(0.0, 3.0), 2] = "002"

    actual = loader(StringIO(content))
    assert list(actual) == list(expected)
    for uri, annotation in actual.items():
        assert annotation.uri == uri
        assert annotation == expected[uri]


def test_load_mdtm_preserves_na_label():
    annotation = load_mdtm(StringIO("file 1 0.0 1.0 speaker <NA> <NA> NA\n"))["file"]
    assert annotation[Segment(0.0, 1.0), 0] == "NA"


def test_load_uem_preserves_timelines():
    uem = StringIO(
        "second 1 2.0 3.0\n"
        "first 1 1.0 3.0\n"
        "second 1 0.0 3.0\n"
        "first 1 1.0 3.0\n"
        "empty 1 0.0 0.0\n"
        "empty 1 1.0 0.0\n"
    )
    expected = {
        "empty": Timeline(uri="empty"),
        "first": Timeline([Segment(1.0, 3.0)], uri="first"),
        "second": Timeline([Segment(0.0, 3.0), Segment(2.0, 3.0)], uri="second"),
    }
    actual = load_uem(uem)
    assert list(actual) == list(expected)
    for uri, timeline in actual.items():
        assert timeline.uri == uri
        assert timeline == expected[uri]


@pytest.mark.parametrize("uri", [None, "recording"])
def test_load_lab_preserves_tracks_labels_and_uri(uri):
    lab = StringIO("2.0 3.0 001\n0.0 3.0 002\n2.0 3.0 002\n0.0 0.0 003\n1.0 0.0 003\n")
    expected = Annotation(uri=uri)
    expected[Segment(2.0, 3.0), 0] = "001"
    expected[Segment(0.0, 3.0), 1] = "002"
    expected[Segment(2.0, 3.0), 2] = "002"

    actual = load_lab(lab, uri=uri)
    assert actual.uri == uri
    assert actual == expected


def test_load_lab_empty():
    annotation = load_lab(StringIO(""), uri="recording")
    assert annotation.uri == "recording"
    assert annotation == Annotation(uri="recording")
