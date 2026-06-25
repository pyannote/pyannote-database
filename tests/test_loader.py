#!/usr/bin/env python
# encoding: utf-8

# The MIT License (MIT)

# Copyright (c) 2025- pyannoteAI

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND.

"""Tests for multichannel-aware RTTM loading (load_rttm + RTTMLoader)."""

from pathlib import Path

from pyannote.core import Annotation
from pyannote.database.loader import RTTMLoader
from pyannote.database.protocol.protocol import ProtocolFile
from pyannote.database.util import load_rttm

RTTMS = Path(__file__).parent / "data" / "rttms"
SINGLE = str(RTTMS / "train.rttm")          # single-channel: filename1 / filename2 on channel 1
MULTI = str(RTTMS / "multichannel.rttm")    # conv1: ch1=speaker_A (x2), ch2=speaker_B ; conv2: ch1=speaker_C


def n_segments(annotation: Annotation) -> int:
    return len(list(annotation.itertracks()))


# --------------------------------------------------------------------------- #
# load_rttm — backward compatibility (keep_channel=False, the default)
# --------------------------------------------------------------------------- #

def test_load_rttm_default_shape_unchanged():
    annotations = load_rttm(SINGLE)
    assert set(annotations) == {"filename1", "filename2"}
    assert isinstance(annotations["filename1"], Annotation)
    assert annotations["filename1"].labels() == ["speaker_A"]
    assert annotations["filename2"].labels() == ["speaker_B"]


def test_load_rttm_default_merges_channels():
    # without keep_channel, all channels of a uri collapse into one Annotation
    annotations = load_rttm(MULTI)
    assert set(annotations) == {"conv1", "conv2"}
    assert isinstance(annotations["conv1"], Annotation)
    assert set(annotations["conv1"].labels()) == {"speaker_A", "speaker_B"}
    assert n_segments(annotations["conv1"]) == 3  # A, B, A


# --------------------------------------------------------------------------- #
# load_rttm — keep_channel=True
# --------------------------------------------------------------------------- #

def test_load_rttm_keep_channel_shape():
    annotations = load_rttm(MULTI, keep_channel=True)
    # {uri: {channel: Annotation}}
    assert set(annotations) == {"conv1", "conv2"}
    assert set(annotations["conv1"]) == {1, 2}
    assert set(annotations["conv2"]) == {1}
    assert all(isinstance(channel, int) for channel in annotations["conv1"])
    assert isinstance(annotations["conv1"][1], Annotation)


def test_load_rttm_keep_channel_content():
    annotations = load_rttm(MULTI, keep_channel=True)
    assert annotations["conv1"][1].labels() == ["speaker_A"]
    assert annotations["conv1"][2].labels() == ["speaker_B"]
    assert n_segments(annotations["conv1"][1]) == 2  # two speaker_A turns on channel 1
    assert n_segments(annotations["conv1"][2]) == 1
    assert annotations["conv2"][1].labels() == ["speaker_C"]


def test_load_rttm_keep_channel_single_channel_file():
    # an ordinary single-channel file is simply nested under channel 1
    annotations = load_rttm(SINGLE, keep_channel=True)
    assert set(annotations["filename1"]) == {1}
    assert annotations["filename1"][1].labels() == ["speaker_A"]


# --------------------------------------------------------------------------- #
# RTTMLoader — channel-aware preprocessor
# --------------------------------------------------------------------------- #

def test_rttmloader_without_channel_is_backward_compatible():
    loader = RTTMLoader(MULTI)
    annotation = loader(ProtocolFile({"uri": "conv1"}))
    assert isinstance(annotation, Annotation)
    assert set(annotation.labels()) == {"speaker_A", "speaker_B"}
    assert n_segments(annotation) == 3


def test_rttmloader_selects_requested_channel():
    loader = RTTMLoader(MULTI)
    channel1 = loader(ProtocolFile({"uri": "conv1", "channel": 1}))
    channel2 = loader(ProtocolFile({"uri": "conv1", "channel": 2}))
    assert channel1.labels() == ["speaker_A"]
    assert channel2.labels() == ["speaker_B"]


def test_rttmloader_missing_channel_returns_empty_annotation():
    loader = RTTMLoader(MULTI)
    # conv2 has only channel 1 -> asking for channel 2 yields an empty Annotation
    annotation = loader(ProtocolFile({"uri": "conv2", "channel": 2}))
    assert isinstance(annotation, Annotation)
    assert n_segments(annotation) == 0


def test_rttmloader_unknown_uri_returns_empty_annotation():
    loader = RTTMLoader(MULTI)
    annotation = loader(ProtocolFile({"uri": "does_not_exist"}))
    assert isinstance(annotation, Annotation)
    assert n_segments(annotation) == 0


def test_rttmloader_single_channel_no_channel_equals_channel_one():
    # for a plain single-channel file, the channel-agnostic result must match channel 1
    loader = RTTMLoader(SINGLE)
    merged = loader(ProtocolFile({"uri": "filename1"}))
    channel1 = loader(ProtocolFile({"uri": "filename1", "channel": 1}))
    assert merged == channel1


def test_rttmloader_accepts_string_channel():
    # channel coming from a mapping file may be a numeric string
    loader = RTTMLoader(MULTI)
    annotation = loader(ProtocolFile({"uri": "conv1", "channel": "2"}))
    assert annotation.labels() == ["speaker_B"]


def test_rttmloader_resolves_lazy_channel():
    # mimics a protocol: both 'channel' and 'annotation' are lazy keys, and
    # resolving 'annotation' must pull the lazily-computed 'channel' (as a
    # `channel:` entry in database.yml would, via gather_loaders).
    lazy = {"channel": lambda f: 2, "annotation": RTTMLoader(MULTI)}
    file = ProtocolFile({"uri": "conv1"}, lazy=lazy)
    assert file["annotation"].labels() == ["speaker_B"]
