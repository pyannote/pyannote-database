#!/usr/bin/env python
# encoding: utf-8

# The MIT License (MIT)

# Copyright (c) 2016-2020 CNRS

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

import yaml
from pathlib import Path
import warnings
import pandas as pd
from pyannote.core import Segment, Timeline, Annotation
from .protocol.protocol import ProtocolFile
from .config import get_database_yml

from typing import Text
from typing import Union
from typing import Dict
from typing import List

DatabaseName = Text
PathTemplate = Text


class PyannoteDatabaseException(Exception):
    pass


class FileFinder:
    """Database file finder

    Parameters
    ----------
    database_yml : str, optional
        Path to database configuration file in YAML format (see below).
        When not provided, pyannote.database will first use file 'database.yml'
        in current working directory if it exists. If it does not exist, it will
        use the path provided by the PYANNOTE_DATABASE_CONFIG environment
        variable. If empty or not set, defaults to '~/.pyannote/database.yml'.

    Configuration file
    ------------------
    Here are a few examples of what is expected in the configuration file.

    # support for multiple databases
    database1: /path/to/database1/{uri}.wav
    database2: /path/to/database2/{uri}.wav

    # files are spread over multiple directory
    database3:
      - /path/to/database3/1/{uri}.wav
      - /path/to/database3/2/{uri}.wav

    # supports * (and **) globbing
    database4: /path/to/database4/*/{uri}.wav

    See also
    --------
    pathlib.Path.glob
    """

    def __init__(self, database_yml: Text = None):

        super().__init__()

        self.database_yml = get_database_yml(database_yml=database_yml)

        with open(self.database_yml, "r") as fp:
            config = yaml.load(fp, Loader=yaml.SafeLoader)

        self.config_: Dict[DatabaseName, Union[PathTemplate, List[PathTemplate]]] = {
            str(database): path
            for database, path in config.get("Databases", dict()).items()
        }

    def __call__(self, current_file: ProtocolFile) -> Path:
        """Look for current file

        Parameter
        ---------
        current_file : ProtocolFile
            Protocol file.

        Returns
        -------
        path : Path
            Path to file.

        Raises
        ------
        FileNotFoundError when the file could not be found or when more than one
        matching file were found.
        """

        uri = current_file["uri"]
        database = current_file["database"]

        # read
        path_templates = self.config_[database]
        if isinstance(path_templates, Text):
            path_templates = [path_templates]

        searched = []
        found = []

        for path_template in path_templates:

            path = Path(path_template.format(uri=uri, database=database))
            if not path.is_absolute():
                path = self.database_yml.parent / path
            searched.append(path)

            # paths with "*" or "**" patterns are split into two parts,
            # - the root part (from the root up to the first occurrence of *)
            # - the pattern part (from the first occurrence of * to the end)
            #   which is looked for (inside root) using Path.glob
            # Example with path = '/path/to/**/*/file.wav'
            #   root = '/path/to'
            #   pattern = '**/*/file.wav'

            if "*" in str(path):
                parts = path.parent.parts
                for p, part in enumerate(parts):
                    if "*" in part:
                        break

                root = path.parents[len(parts) - p]
                pattern = str(path.relative_to(root))
                found_ = root.glob(pattern)
                found.extend(found_)

            # a path without "*" patterns is supposed to be an actual file
            elif path.is_file():
                found.append(path)

        if len(found) == 1:
            return found[0]

        if len(found) == 0:
            msg = f'Could not find file "{uri}" in the following location(s):'
            for path in searched:
                msg += f"\n - {path}"
            raise FileNotFoundError(msg)

        if len(found) > 1:
            msg = (
                f'Looked for file "{uri}" and found more than one '
                f"({len(found)}) matching locations: "
            )
            for path in found:
                msg += f"\n - {path}"
            raise FileNotFoundError(msg)


def get_unique_identifier(item):
    """Return unique item identifier

    The complete format is {database}/{uri}_{channel}:
    * prefixed by "{database}/" only when `item` has a 'database' key.
    * suffixed by "_{channel}" only when `item` has a 'channel' key.

    Parameters
    ----------
    item : dict
        Item as yielded by pyannote.database protocols

    Returns
    -------
    identifier : str
        Unique item identifier
    """

    IDENTIFIER = ""

    # {database}/{uri}_{channel}
    database = item.get("database", None)
    if database is not None:
        IDENTIFIER += f"{database}/"
    IDENTIFIER += item['uri']
    channel = item.get("channel", None)
    if channel is not None:
        IDENTIFIER += f"_{channel:d}"

    return IDENTIFIER


# This function is used in custom.py
def get_annotated(current_file):
    """Get part of the file that is annotated.

    Parameters
    ----------
    current_file : `dict`
        File generated by a `pyannote.database` protocol.

    Returns
    -------
    annotated : `pyannote.core.Timeline`
        Part of the file that is annotated. Defaults to
        `current_file["annotated"]`. When it does not exist, try to use the
        full audio extent. When that fails, use "annotation" extent.
    """

    # if protocol provides 'annotated' key, use it
    if "annotated" in current_file:
        annotated = current_file["annotated"]
        return annotated

    # if it does not, but does provide 'audio' key
    # try and use wav duration

    if "duration" in current_file:
        try:
            duration = current_file["duration"]
        except ImportError:
            pass
        else:
            annotated = Timeline([Segment(0, duration)])
            msg = '"annotated" was approximated by [0, audio duration].'
            warnings.warn(msg)
            return annotated

    extent = current_file["annotation"].get_timeline().extent()
    annotated = Timeline([extent])

    msg = (
        '"annotated" was approximated by "annotation" extent. '
        'Please provide "annotated" directly, or at the very '
        'least, use a "duration" preprocessor.'
    )
    warnings.warn(msg)

    return annotated


def get_label_identifier(label, current_file):
    """Return unique label identifier

    Parameters
    ----------
    label : str
        Database-internal label
    current_file
        Yielded by pyannote.database protocols

    Returns
    -------
    unique_label : str
        Global label
    """

    # TODO. when the "true" name of a person is used,
    # do not preprend database name.
    database = current_file["database"]
    return database + "|" + label


def load_rttm(file_rttm):
    """Load RTTM file

    Parameter
    ---------
    file_rttm : `str`
        Path to RTTM file.

    Returns
    -------
    annotations : `dict`
        Speaker diarization as a {uri: pyannote.core.Annotation} dictionary.
    """

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
    data = pd.read_csv(
        file_rttm,
        names=names,
        dtype=dtype,
        delim_whitespace=True,
        keep_default_na=False,
    )

    annotations = dict()
    for uri, turns in data.groupby("uri"):
        annotation = Annotation(uri=uri)
        for i, turn in turns.iterrows():
            segment = Segment(turn.start, turn.start + turn.duration)
            annotation[segment, i] = turn.speaker
        annotations[uri] = annotation

    return annotations


class RTTMLoader(object):
    """RTTM loader for use as pyannote.database preprocessor

    Parameters
    ----------
    train : `Path`, optional
        Path to RTTM file for training set
    development : `Path`, optional
        Path to RTTM file for development set
    test : `Path`, optional
        Path to RTTM file for test set
    """

    def __init__(self, train=None, development=None, test=None):
        super().__init__()
        # preload everything in memory
        self.hypotheses_ = {}
        if train is not None:
            self.hypotheses_["train"] = load_rttm(train)
        if development is not None:
            self.hypotheses_["development"] = load_rttm(development)
        if test is not None:
            self.hypotheses_["test"] = load_rttm(test)

    def __call__(self, current_file):
        """Return RTTM content for current file

        Parameter
        ---------
        current_file : `dict`
            Current file as provided by a `pyannote.database.Protocol`

        Returns
        -------
        annotation : `pyannote.core.Annotation`
            Annotation
        """

        uri = current_file["uri"]
        found = []
        for subset, hypotheses in self.hypotheses_.items():
            if uri in hypotheses:
                found.append(hypotheses[uri])

        if len(found) == 1:
            return found[0]
        elif len(found) == 0:
            msg = f'Could not find any hypothesis for "{uri}".'
            raise ValueError(msg)
        else:
            msg = f'Found {len(found)} hypotheses for "{uri}".'
            raise ValueError(msg)


def load_mdtm(file_mdtm):
    """Load MDTM file

    Parameter
    ---------
    file_mdtm : `str`
        Path to MDTM file.

    Returns
    -------
    annotations : `dict`
        Speaker diarization as a {uri: pyannote.core.Annotation} dictionary.
    """

    names = ["uri", "NA1", "start", "duration", "NA2", "NA3", "NA4", "speaker"]
    dtype = {"uri": str, "start": float, "duration": float, "speaker": str}
    data = pd.read_csv(
        file_mdtm,
        names=names,
        dtype=dtype,
        delim_whitespace=True,
        keep_default_na=False,
    )

    annotations = dict()
    for uri, turns in data.groupby("uri"):
        annotation = Annotation(uri=uri)
        for i, turn in turns.iterrows():
            segment = Segment(turn.start, turn.start + turn.duration)
            annotation[segment, i] = turn.speaker
        annotations[uri] = annotation

    return annotations


def load_uem(file_uem):
    """Load UEM file

    Parameter
    ---------
    file_uem : `str`
        Path to UEM file.

    Returns
    -------
    timelines : `dict`
        Evaluation map as a {uri: pyannote.core.Timeline} dictionary.
    """

    names = ["uri", "NA1", "start", "end"]
    dtype = {"uri": str, "start": float, "end": float}
    data = pd.read_csv(file_uem, names=names, dtype=dtype, delim_whitespace=True)

    timelines = dict()
    for uri, parts in data.groupby("uri"):
        segments = [Segment(part.start, part.end) for i, part in parts.iterrows()]
        timelines[uri] = Timeline(segments=segments, uri=uri)

    return timelines


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


def load_mapping(mapping_txt):
    """Load mapping file

    Parameter
    ---------
    mapping_txt : `str`
        Path to mapping file

    Returns
    -------
    mapping : `dict`
        {1st field: 2nd field} dictionary
    """

    with open(mapping_txt, mode="r") as fp:
        lines = fp.readlines()

    mapping = dict()
    for line in lines:
        key, value, *left = line.strip().split()
        mapping[key] = value

    return mapping


class LabelMapper(object):
    """Label mapper for use as pyannote.database preprocessor

    Parameters
    ----------
    mapping : `dict`
        Mapping dictionary as used in `Annotation.rename_labels()`.
    keep_missing : `bool`, optional
        In case a label has no mapping, a `ValueError` will be raised.
        Set "keep_missing" to True to keep those labels unchanged instead.

    Usage
    -----
    >>> mapping = {'Hadrien': 'MAL', 'Marvin': 'MAL',
    ...            'Wassim': 'CHI', 'Herve': 'GOD'}
    >>> preprocessors = {'annotation': LabelMapper(mapping=mapping)}
    >>> protocol = get_protocol('AMI.SpeakerDiarization.MixHeadset',
                                preprocessors=preprocessors)

    """

    def __init__(self, mapping, keep_missing=False):
        self.mapping = mapping
        self.keep_missing = keep_missing

    def __call__(self, current_file):

        if not self.keep_missing:
            missing = set(current_file["annotation"].labels()) - set(self.mapping)
            if missing and not self.keep_missing:
                label = missing.pop()
                msg = (
                    f'No mapping found for label "{label}". Set "keep_missing" '
                    f"to True to keep labels with no mapping."
                )
                raise ValueError(msg)

        return current_file["annotation"].rename_labels(mapping=self.mapping)
