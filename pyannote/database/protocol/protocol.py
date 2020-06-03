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

"""
#########
Protocols
#########

"""

import warnings
import collections
import threading
import itertools
from typing import Union, Dict, Iterator


class ProtocolFile(collections.abc.MutableMapping):
    """Protocol file with lazy preprocessors

    This is a dict-like data structure where some values may depend on other
    values, and are only computed if/when requested. Once computed, they are
    cached and never recomputed again.

    Parameters
    ----------
    precomputed : dict
        Regular dictionary with precomputed values
    lazy : dict, optional
        Dictionary describing how lazy value needs to be computed.
        Values are callable expecting a dictionary as input and returning the
        computed value.

    """

    def __init__(self, precomputed, lazy=None):
        self._store = dict(precomputed)
        if lazy is None:
            lazy = dict()
        self.lazy = dict(lazy)
        self.lock_ = threading.RLock()

        # this is needed to avoid infinite recursion
        # when a key is both in precomputed and lazy.
        # keys with evaluating_ > 0 are currently being evaluated
        # and therefore should be taken from precomputed
        self.evaluating_ = collections.Counter()

    def __abs__(self):
        with self.lock_:
            return dict(self._store)

    def __getitem__(self, key):
        with self.lock_:

            if key in self.lazy and self.evaluating_[key] == 0:

                # mark lazy key as being evaluated
                self.evaluating_.update([key])

                # apply preprocessor once and remove it
                value = self.lazy[key](self)
                del self.lazy[key]

                # warn the user when a precomputed key is modified
                if key in self._store:
                    msg = 'Existing key "{key}" may have been modified.'
                    warnings.warn(msg.format(key=key))

                # store the output of the lazy computation
                # so that it is available for future access
                self._store[key] = value

                # lazy evaluation is finished for key
                self.evaluating_.subtract([key])

            return self._store[key]

    def __setitem__(self, key, value):
        with self.lock_:

            if key in self.lazy:
                del self.lazy[key]

            self._store[key] = value

    def __delitem__(self, key):
        with self.lock_:

            if key in self.lazy:
                del self.lazy[key]

            del self._store[key]

    def __iter__(self):
        with self.lock_:

            for key in self._store:
                yield key

            for key in self.lazy:
                if key in self._store:
                    continue
                yield key

    def __len__(self):
        with self.lock_:

            return len(set(self._store) | set(self.lazy))

    def files(self) -> Iterator["ProtocolFile"]:
        """Iterate over all files

        When `current_file` refers to only one file,
            yield it and return.
        When `current_file` refers to a list of file (i.e. 'uri' is a list),
            yield each file separately.

        Examples
        --------
        >>> current_file = ProtocolFile({
        ...     'uri': 'my_uri',
        ...     'database': 'my_database'})
        >>> for file in current_file.files():
        ...     print(file['uri'], file['database'])
        my_uri my_database

        >>> current_file = {
        ...     'uri': ['my_uri1', 'my_uri2', 'my_uri3'],
        ...     'database': 'my_database'}
        >>> for file in current_file.files():
        ...     print(file['uri'], file['database'])
        my_uri1 my_database
        my_uri2 my_database
        my_uri3 my_database

        """

        uris = self["uri"]
        if not isinstance(uris, list):
            yield self
            return

        n_uris = len(uris)

        # iterate over precomputed keys and make sure

        precomputed = {"uri": uris}
        for key, value in abs(self).items():

            if key == "uri":
                continue

            if not isinstance(value, list):
                precomputed[key] = itertools.repeat(value)

            else:
                if len(value) != n_uris:
                    msg = (
                        f'Mismatch between number of "uris" ({n_uris}) '
                        f'and number of "{key}" ({len(value)}).'
                    )
                    raise ValueError(msg)
                precomputed[key] = value

        keys = list(precomputed.keys())
        for values in zip(*precomputed.values()):
            precomputed_one = dict(zip(keys, values))
            yield ProtocolFile(precomputed_one, self.lazy)


class Protocol:
    """Base protocol

    This class should be inherited from, not used directly.

    Parameters
    ----------
    preprocessors : dict
        When provided, each protocol item (dictionary) are preprocessed, such
        that item[key] = preprocessor(item). In case 'preprocessor' is not
        callable, it should be a string containing placeholder for item keys
        (e.g. {'audio': '/path/to/{uri}.wav'})
    """

    def __init__(self, preprocessors={}, progress=False, **kwargs):
        super(Protocol, self).__init__()

        self.preprocessors = dict()
        for key, preprocessor in preprocessors.items():

            if callable(preprocessor):
                self.preprocessors[key] = preprocessor

            # when `preprocessor` is not callable, it should be a string
            # containing placeholder for item key (e.g. '/path/to/{uri}.wav')
            elif isinstance(preprocessor, str):
                preprocessor_copy = str(preprocessor)

                def func(current_file):
                    return preprocessor_copy.format(**current_file)

                self.preprocessors[key] = func

            else:
                msg = f'"{key}" preprocessor is neither a callable nor a string.'
                raise ValueError(msg)

        self.progress = progress

    def preprocess(self, current_file: Union[Dict, ProtocolFile]) -> ProtocolFile:
        return ProtocolFile(current_file, lazy=self.preprocessors)

    def __str__(self):
        return self.__doc__

    def files(self) -> Iterator[ProtocolFile]:
        """Iterate over all files in `protocol`"""

        # imported here to avoid circular imports
        from pyannote.database.util import get_unique_identifier

        # remember `progress` attribute
        progress = self.progress

        methods = []
        for suffix in ["", "_enrolment", "_trial"]:
            for subset in ["development", "test", "train"]:
                methods.append(f"{subset}{suffix}")

        yielded_uris = set()

        for method in methods:

            if not hasattr(self, method):
                continue

            try:
                self.progress = False
                file_generator = getattr(self, method)()
                first_file = next(file_generator)
            except NotImplementedError as e:
                continue
            except StopIteration as e:
                continue

            self.progress = True
            file_generator = getattr(self, method)()

            for current_file in file_generator:

                # skip "files" that do not contain a "uri" entry.
                # this happens for speaker verification trials that contain
                # two nested files "file1" and "file2"
                # see https://github.com/pyannote/pyannote-db-voxceleb/issues/4
                if "uri" not in current_file:
                    continue

                for current_file_ in current_file.files():

                    # corner case when the same file is yielded several times
                    uri = get_unique_identifier(current_file_)
                    if uri in yielded_uris:
                        continue

                    yield current_file_

                    yielded_uris.add(uri)

        # revert `progress` attribute
        self.progess = progress
