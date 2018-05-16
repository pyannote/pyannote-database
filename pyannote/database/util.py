#!/usr/bin/env python
# encoding: utf-8

# The MIT License (MIT)

# Copyright (c) 2016-2017 CNRS

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
import os.path
import warnings
import itertools
from glob import glob
from pyannote.core import Segment, Timeline


class PyannoteDatabaseException(Exception):
    pass


class FileFinder(object):
    """Database file finder

    Parameters
    ----------
    config_yml : str, optional
        Path to database configuration file in YAML format.
        See "Configuration file" sections for examples.
        Defaults to '~/.pyannote/db.yml'.

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
            config_yml = '~/.pyannote/db.yml'
        config_yml = os.path.expanduser(config_yml)

        with open(config_yml, 'r') as fp:
            self.config = yaml.load(fp)

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

            found_files = self._find(self.config, **current_file_)
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

    # if protocol provides 'annotated' key, use it
    if 'annotated' in current_file:
        annotated = current_file['annotated']
        return annotated

    # if it does not, but does provide 'audio' key
    # try and use wav duration

    if 'audio' in current_file:
        try:
            from pyannote.audio.features.utils import get_audio_duration
            duration = get_audio_duration(current_file)
        except ImportError as e:
            pass
        else:
            warnings.warn('"annotated" was approximated by "audio" duration.')
            annotated = Timeline([Segment(0, duration)])
            return annotated

    warnings.warn('"annotated" was approximated by "annotation" extent.')
    extent = current_file['annotation'].get_timeline().extent()
    annotated = Timeline([extent])
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
