#!/usr/bin/env python
# encoding: utf-8

# The MIT License (MIT)

# Copyright (c) 2016-2019 CNRS

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

import os
import yaml
from pathlib import Path
import warnings
import itertools
import pandas as pd
from glob import glob
from pyannote.core import Segment, Timeline, Annotation



class PyannoteDatabaseException(Exception):
    pass


class FileFinder(object):
    """Database file finder

    Parameters
    ----------
    config_yml : str, optional
        Path to database configuration file in YAML format.
        See "Configuration file" sections for examples.
        Defaults to the content of PYANNOTE_DATABASE_CONFIG environment
        variable if defined and to "~/.pyannote/database.yml" otherwise.

    Configuration file
    ------------------
    Here are a few examples of what is expected in the configuration file.

    # all files are in the same directory
    /path/to/files/{uri}.wav

    # support for {database} placeholder
    /path/to/{database}/files/{uri}.wav

    # support for multiple databases
    database1: /path/to/files/{uri}.wav
    database2: /path/to/other/files/{uri}.wav

    # files are spread over multiple directory
    database3:
      - /path/to/files/1/{uri}.wav
      - /path/to/files/2/{uri}.wav

    # supports * globbing
    database4: /path/to/files/*/{uri}.wav

    See also
    --------
    glob
    """

    def __init__(self, config_yml=None):
        super(FileFinder, self).__init__()

        if config_yml is None:
            config_yml = os.environ.get("PYANNOTE_DATABASE_CONFIG",
                                        "~/.pyannote/database.yml")
        config_yml = Path(config_yml).expanduser()

        try:
            with open(config_yml, 'r') as fp:
                config = yaml.load(fp, Loader=yaml.SafeLoader)

        except FileNotFoundError:
            config = dict()

        self.config = config.get('Databases', dict())


    def _find(self, config, uri=None, database=None, **kwargs):

        found = []

        # list of path templates
        if isinstance(config, list):

            for path_template in config:
                path = path_template.format(uri=uri, database=database,
                                            **kwargs)
                found_ = glob(path)
                found.extend(found_)

        # database-indexed dictionary
        elif isinstance(config, dict):

            # if database identifier is not provided
            # or does not exist in configuration file
            # look into all databases...
            if database is None or database not in config:
                databases = list(config)
            # if database identifier is provided AND exists
            # only look into this very database
            else:
                databases = [database]

            # iteratively look into selected databases
            for database in databases:
                found_ = self._find(config[database], uri=uri,
                                    database=database, **kwargs)
                found.extend(found_)

        else:
            path_template = config
            path = path_template.format(uri=uri, database=database, **kwargs)
            found_ = glob(path)
            found.extend(found_)

        return found

    @classmethod
    def protocol_file_iter(cls, protocol, extra_keys=None):
        """Iterate over all files in `protocol`

        Parameters
        ----------
        protocol : Protocol
        extra_keys : list, optional
            Extra keys to consider (e.g. 'audio'). By default, only 'uri',
            'channel', and 'database' keys are considered.
        """

        # remember `progress` attribute
        progress = protocol.progress

        methods = []
        for suffix in ['', '_enrolment', '_trial']:
            for subset in ['development', 'test', 'train']:
                methods.append(f'{subset}{suffix}')

        yielded_uris = set()

        for method in methods:

            if not hasattr(protocol, method):
                continue

            try:
                protocol.progress = False
                file_generator = getattr(protocol, method)()
                first_file = next(file_generator)
            except NotImplementedError as e:
                continue
            except StopIteration as e:
                continue

            protocol.progress = True
            file_generator = getattr(protocol, method)()

            for current_file in file_generator:

                # skip "files" that do not contain a "uri" entry.
                # this happens for speaker verification trials that contain
                # two nested files "file1" and "file2"
                # see https://github.com/pyannote/pyannote-db-voxceleb/issues/4
                if 'uri' not in current_file:
                    continue

                for current_file_ in cls.current_file_iter(
                    current_file, extra_keys=extra_keys):

                    # corner case when the same file is yielded several times
                    uri = get_unique_identifier(current_file_)
                    if uri in yielded_uris:
                        continue

                    yield current_file_

                    yielded_uris.add(uri)

        # revert `progress` attribute
        protocol.progess = progress

    @classmethod
    def current_file_iter(cls, current_file, extra_keys=None,
                          return_status=False):
        """Iterate over all files in `current_file`

        When `current_file` refers to only one file, yield it and return.
        When `current_file` refers to a list of file (i.e. 'uri', 'channel', or
        'database' is a list, yield each file separately.

        Parameters
        ----------
        extra_keys : list, optional
            Extra keys to consider (e.g. 'audio'). By default, only 'uri',
            'channel', and 'database' keys are considered.
        return_status : bool, optional
            Set to True to yield a boolean indicating if the original
            `current_file` was a multi-file. Defaults to False.

        Examples
        --------
        >>> current_file = {
        ...     'uri': 'my_uri',
        ...     'database': 'my_database'}
        >>> for file in FileFinder.current_file_iter(current_file):
        ...     print(file['uri'], file['database'])
        my_uri my_database

        >>> current_file = {
        ...     'uri': ['my_uri1', 'my_uri2', 'my_uri3'],
        ...     'database': 'my_database'}
        >>> for file in FileFinder.current_file_iter(current_file):
        ...     print(file['uri'], file['database'])
        my_uri1 my_database
        my_uri2 my_database
        my_uri3 my_database

        """
        keys = ['uri', 'channel', 'database']
        if extra_keys is not None:
            keys += extra_keys

        # value of each key, in order
        values = [current_file.get(k, None) for k in keys]

        # True if at least one value is a list
        status = False

        # make sure 'list' values (if any) all share the same length
        for v, value in enumerate(values):
            if isinstance(value, list):
                # set (hopefully) common length when first encountering a list
                if not status:
                    first = v
                    n = len(value)
                # otherwise, check if subsequent lists have the same length
                else:
                    try:
                        assert len(value) == n
                    except AssertionError as e:
                        msg = 'length mismatch ({0}: {1:d} vs. {2}: {3:d})'

                        raise ValueError(msg.format(first, n, v, len(value)))

                # at least one value is a list
                status = True

        # if no value is a list, return current_file, unmodified
        if not status:
            yield (current_file, status) if return_status else current_file
            return

        # otherwise, make sure one can iterate on all values
        # by replacing those that are not lists by their infinite repetition
        for k, value in enumerate(list(values)):
            if not isinstance(value, list):
                values[k] = itertools.repeat(value)

        i = dict(current_file)
        for value in zip(*values):
            for k, v in enumerate(value):
                i[keys[k]] = v
            yield (i, status) if return_status else i

    def __call__(self, current_file):
        """Find files

        Parameters
        ----------
        current_file : pyannote.database dict
            Dictionary as generated by pyannote.database plugins.

        Returns
        -------
        path : str (or list of str)
            When `current_file` refers to only one file, returns it.
            When `current_file` refers to a list of file (i.e. 'uri',
            'channel', or 'database' is a list), returns a list of files.

        """

        found = []
        for current_file_, status in self.current_file_iter(
            current_file, return_status=True):

            found_files = self._find(self.config, **abs(current_file_))
            n_found_files = len(found_files)

            if n_found_files == 1:
                found.append(found_files[0])

            elif n_found_files == 0:
                uri = current_file_['uri']
                msg = 'Could not find file "{uri}".'
                raise ValueError(msg.format(uri=uri))

            else:
                uri = current_file_['uri']
                msg = 'Found {n} matches for file "{uri}"'
                raise ValueError(msg.format(uri=uri, n=n_found_files))

        if status:
            return found
        else:
            return found[0]

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
    database = item.get('database', None)
    if database is not None:
        IDENTIFIER += "{database}/"
    IDENTIFIER += "{uri}"
    channel = item.get('channel', None)
    if channel is not None:
        IDENTIFIER += "_{channel:d}"

    return IDENTIFIER.format(**item)


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
    if 'annotated' in current_file:
        annotated = current_file['annotated']
        return annotated

    # if it does not, but does provide 'audio' key
    # try and use wav duration

    if 'duration' in current_file:
        try:
            duration = current_file['duration']
        except ImportError as e:
            pass
        else:
            annotated = Timeline([Segment(0, duration)])
            msg = f'"annotated" was approximated by [0, audio duration].'
            warnings.warn(msg)
            return annotated

    extent = current_file['annotation'].get_timeline().extent()
    annotated = Timeline([extent])

    msg = (f'"annotated" was approximated by "annotation" extent. '
           f'Please provide "annotated" directly, or at the very '
           f'least, use a "duration" preprocessor.')
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
    database = current_file['database']
    return database + '|' + label


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

    names = ['NA1', 'uri', 'NA2', 'start', 'duration',
             'NA3', 'NA4', 'speaker', 'NA5', 'NA6']
    dtype = {'uri': str, 'start': float, 'duration': float, 'speaker': str}
    data = pd.read_csv(file_rttm, names=names, dtype=dtype,
                       delim_whitespace=True,
                       keep_default_na=False)

    annotations = dict()
    for uri, turns in data.groupby('uri'):
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
            self.hypotheses_['train'] = load_rttm(train)
        if development is not None:
            self.hypotheses_['development'] = load_rttm(development)
        if test is not None:
            self.hypotheses_['test'] = load_rttm(test)

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

        uri = current_file['uri']
        found = []
        for subset, hypotheses in self.hypotheses_.items():
            if uri in hypotheses:
                found.append(hypotheses[uri])

        if len(found) == 1:
            return found[0]
        elif len(found) == 0:
            msg = (
                f'Could not find any hypothesis for "{uri}".'
            )
            raise ValueError(msg)
        else:
            msg = (
                f'Found {len(found)} hypotheses for "{uri}".'
            )
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

    names = ['uri', 'NA1', 'start', 'duration', 'NA2', 'NA3', 'NA4', 'speaker']
    dtype = {'uri': str, 'start': float, 'duration': float, 'speaker': str}
    data = pd.read_csv(file_mdtm, names=names, dtype=dtype,
                       delim_whitespace=True,
                       keep_default_na=False)

    annotations = dict()
    for uri, turns in data.groupby('uri'):
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

    names = ['uri', 'NA1', 'start', 'end']
    dtype = {'uri': str, 'start': float, 'end': float}
    data = pd.read_csv(file_uem, names=names, dtype=dtype,
                       delim_whitespace=True)

    timelines = dict()
    for uri, parts in data.groupby('uri'):
        segments = [Segment(part.start, part.end)
                    for i, part in parts.iterrows()]
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

    with open(file_lst, mode='r') as fp:
        lines = fp.readlines()
    return [l.strip() for l in lines]


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

    with open(mapping_txt, mode='r') as fp:
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
            missing = set(current_file['annotation'].labels()) - set(self.mapping)
            if missing and not self.keep_missing:
                label = missing.pop()
                msg = (
                    f'No mapping found for label "{label}". Set "keep_missing" '
                    f'to True to keep labels with no mapping.'
                )
                raise ValueError(msg)

        return current_file['annotation'].rename_labels(mapping=self.mapping)
