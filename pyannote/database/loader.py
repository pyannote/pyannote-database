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
from typing import Union
import warnings

try:
    from spacy.tokens import Token

    Token.set_extension("time_start", default=None)
    Token.set_extension("time_end", default=None)
    Token.set_extension("confidence", default=0.0)

except ImportError as e:
    pass


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


class CTMLoader:
    """CTM loader

    Parameter
    ---------
    ctm : Path
        Path to CTM file
    """

    def __init__(self, ctm: Path):
        self.ctm = ctm

        names = ["uri", "channel", "start", "duration", "word", "confidence"]
        dtype = {
            "uri": str,
            "start": float,
            "duration": float,
            "word": str,
            "confidence": float,
        }
        self.data_ = pd.read_csv(
            ctm, names=names, dtype=dtype, delim_whitespace=True
        ).groupby("uri")

    def __call__(self, current_file: ProtocolFile) -> Union["spacy.tokens.Doc", None]:

        try:
            from spacy.vocab import Vocab
            from spacy.tokens import Doc
        except ImportError as e:
            msg = "Cannot load CTM files because spaCy is not available."
            warnings.warn(msg)
            return None

        uri = current_file["uri"]

        try:
            lines = list(self.data_.get_group(uri).iterrows())
        except KeyError:
            lines = []

        words = [line.word for _, line in lines]
        doc = Doc(Vocab(), words=words)

        for token, (_, line) in zip(doc, lines):
            token._.time_start = line.start
            token._.time_end = line.start + line.duration
            token._.confidence = line.confidence

        return doc

class MAPLoader:
    """Mapping loader

    For generic files with format :
    {uri} {value}

    Exemples :

    file duration :

    filename1 60.0
    filename2 123.450
    filename3 32.400

    #TODO: 
    Add support for non numeric types

    Parameter
    ---------
    map : Path
        Path to mapping file
    """

    def __init__(self, mapping: Path):
        self.mapping = mapping

        names = ["uri", "value"]
        dtype = {
            "uri": str,
            "value": float
        }
        self.data_ = pd.read_csv(
            mapping, names=names, dtype=dtype, delim_whitespace=True
        ).groupby("uri").min() # if multiple duration are given, min takes the shorter one

    def __call__(self, current_file: ProtocolFile) -> Union["spacy.tokens.Doc", None]:
        uri = current_file["uri"]

        segments = []
        try:
            duration = self.data_.loc[uri]['value']
            segment = Segment(0, duration)
            segments.append(segment)
        except KeyError:
            msg = f"Couldn't find duration for {uri} in {self.mapping}"
            raise KeyError(msg)

        return Timeline(segments=segments, uri=uri)
