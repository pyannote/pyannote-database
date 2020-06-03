#!/usr/bin/env python
# encoding: utf-8

# The MIT License (MIT)

# Copyright (c) 2020 CNRS

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

# AUTHORS
# Hervé BREDIN - http://herve.niderb.fr

"""Data loaders"""

import pandas as pd
from pyannote.core import Segment, Timeline, Annotation
from pyannote.database import ProtocolFile
from pathlib import Path


class RTTMLoader:
    """RTTM loader
    
    Parameter
    ---------
    rttm : Path
        Path to RTTM file.
    """

    def __init__(self, rttm: Path):
        self.rttm = rttm

        names = [
            "NA1",
            "uri",
            "NA2",
            "start",
            "duration",
            "NA3",
            "NA4",
            "speaker",
            "NA5",
            "NA6",
        ]
        dtype = {"uri": str, "start": float, "duration": float, "speaker": str}
        self.data_ = pd.read_csv(
            rttm,
            names=names,
            dtype=dtype,
            delim_whitespace=True,
            keep_default_na=False,
        ).groupby("uri")

    def __call__(self, current_file: ProtocolFile) -> Annotation:
        uri = current_file["uri"]
        annotation = Annotation(uri=uri)

        try:
            turns = self.data_.get_group(uri).iterrows()
        except KeyError:
            turns = []

        for i, turn in turns:
            segment = Segment(turn.start, turn.start + turn.duration)
            if not segment:
                msg = f"Found empty segment in {self.rttm} for file {uri} around t={turn.start:.3f}s"
                raise ValueError(msg)
            annotation[segment, i] = turn.speaker

        return annotation


class UEMLoader:
    """UEM loader
    
    Parameter
    ---------
    uem : Path
        Path to UEM file.
    """

    def __init__(self, uem: Path):
        self.uem = uem

        names = ["uri", "NA1", "start", "end"]
        dtype = {"uri": str, "start": float, "end": float}
        self.data_ = pd.read_csv(
            uem, names=names, dtype=dtype, delim_whitespace=True
        ).groupby("uri")

    def __call__(self, current_file: ProtocolFile) -> Timeline:
        uri = current_file["uri"]

        try:
            regions = self.data_.get_group(uri).iterrows()
        except KeyError:
            regions = []

        segments = []
        for i, region in regions:
            segment = Segment(region.start, region.end)
            if not segment:
                msg = f"Found empty segment in {self.uem} for file {uri} around t={region.start:.3f}s"
                raise ValueError(msg)
            segments.append(segment)

        return Timeline(segments=segments, uri=uri)
