#!/usr/bin/env python
# encoding: utf-8

# The MIT License (MIT)

# Copyright (c) 2020-2021 CNRS

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
# Vincent BRIGNATZ

"""Data loaders"""

from typing import Text
from pathlib import Path
import string
from pyannote.database.util import load_rttm, load_uem
import pandas as pd
from pyannote.core import Segment, Timeline, Annotation
from pyannote.database import ProtocolFile
from typing import Union, Any
import warnings


try:
    from spacy.tokens import Token
    from spacy.tokens import Doc

    Token.set_extension("time_start", default=None)
    Token.set_extension("time_end", default=None)
    Token.set_extension("confidence", default=0.0)

except ImportError:
    pass


def load_lst(file_lst):
    """Load LST file

    LST files provide a list of URIs (one line per URI)

    Parameter
    ---------
    file_lst : `str`
        Path to LST file.

    Returns
    -------
    uris : `list`
        List or uris
    """

    with open(file_lst, mode="r") as fp:
        lines = fp.readlines()
    return [line.strip() for line in lines]


def load_trial(file_trial):
    """Load trial file

    Trial files provide a list of two URIs and their reference

    Parameter
    ---------
    file_trial : `str`
        Path to trial file.

    Returns
    -------
    list_trial : `list`
        List of trial
    """

    trials = pd.read_table(
        file_trial, delim_whitespace=True, names=["reference", "uri1", "uri2"]
    )

    for _, reference, uri1, uri2 in trials.itertuples():
        yield {"reference": reference, "uri1": uri1, "uri2": uri2}


class RTTMLoader:
    """RTTM loader

    Can be used as a preprocessor.

    Parameters
    ----------
    path : str
        Path to RTTM file with optional ProtocolFile key placeholders
        (e.g. "/path/to/{database}/{subset}/{uri}.rttm")
    """

    def __init__(self, path: Text = None):
        super().__init__()

        self.path = path

        _, placeholders, _, _ = zip(*string.Formatter().parse(str(path)))
        self.placeholders_ = set(placeholders) - set([None])

        self.loaded_ = dict() if self.placeholders_ else load_rttm(path)

    def __call__(self, file: ProtocolFile) -> Annotation:

        uri = file["uri"]

        if uri not in self.loaded_:
            sub_file = {key: file[key] for key in self.placeholders_}
            loaded = load_rttm(self.path.format(**sub_file))
            if uri not in loaded:
                loaded[uri] = Annotation(uri=uri)
            if "uri" in self.placeholders_:
                return loaded[uri]
            self.loaded_.update(loaded)

        return self.loaded_[uri]


class UEMLoader:
    """UEM loader

    Can be used as a preprocessor.

    Parameters
    ----------
    path : str
        Path to UEM file with optional ProtocolFile key placeholders
        (e.g. "/path/to/{database}/{subset}/{uri}.uem")
    """

    def __init__(self, path: Text = None):
        super().__init__()

        self.path = path

        _, placeholders, _, _ = zip(*string.Formatter().parse(str(path)))
        self.placeholders_ = set(placeholders) - set([None])

        self.loaded_ = dict() if self.placeholders_ else load_uem(path)

    def __call__(self, file: ProtocolFile) -> Timeline:

        uri = file["uri"]

        if uri not in self.loaded_:
            sub_file = {key: file[key] for key in self.placeholders_}
            loaded = load_uem(self.path.format(**sub_file))
            if uri not in loaded:
                loaded[uri] = Timeline(uri=uri)
            if "uri" in self.placeholders_:
                return loaded[uri]
            self.loaded_.update(loaded)

        return self.loaded_[uri]


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

    def __call__(self, current_file: ProtocolFile) -> Union["Doc", None]:

        try:
            from spacy.vocab import Vocab
            from spacy.tokens import Doc
        except ImportError:
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

        duration.map :

            filename1 60.0
            filename2 123.450
            filename3 32.400

        domain.map :

            filename1 radio
            filename2 radio
            filename3 phone

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
        }
        self.data_ = pd.read_csv(
            mapping, names=names, dtype=dtype, delim_whitespace=True
        )

        # get colum 'value' dtype, allowing us to acces it during subset
        self.dtype = self.data_.dtypes["value"]

        if self.data_.duplicated(["uri"]).any():
            print(f"Found following duplicate key in file {mapping}")
            print(self.data_[self.data_.duplicated(["uri"], keep=False)])
            raise ValueError()

        self.data_ = self.data_.groupby("uri")

    def __call__(self, current_file: ProtocolFile) -> Any:
        uri = current_file["uri"]

        try:
            value = self.data_.get_group(uri).value.item()
        except KeyError:
            msg = f"Couldn't find mapping for {uri} in {self.mapping}"
            raise KeyError(msg)

        return value
