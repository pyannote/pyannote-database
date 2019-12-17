#!/usr/bin/env python
# encoding: utf-8

# The MIT License (MIT)

# Copyright (c) 2016 CNRS

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
from typing import Any
from typing import Dict
from typing import Iterator
from typing import Text
from ..types import RawPreprocessor
from ..types import Preprocessors
from ..types import FileValue
from ..types import FileKey
from ..types import RegularFile


class ProtocolFile(collections.abc.MutableMapping):
    """Dictionary with lazy values

    This is a dict-like data structure where some values may depend on other
    values, and are only computed if/when requested. Once computed, they are
    cached and never recomputed again.

    Parameters
    ----------
    ready : dict
        Regular dictionary with precomputed values
    lazy : dict
        Dictionary describing how lazy value needs to be computed.
        Values are callable expecting a dictionary as input and returning the
        computed value.
    """

    def __init__(self, ready: RegularFile,
                       lazy: Preprocessors):
        self._store : RegularFile = dict(ready)
        self.lazy : Preprocessors = dict(lazy)

    def __abs__(self) -> RegularFile:
        return dict(self._store)

    def __getitem__(self, key: FileKey) -> FileValue:

        if key in self.lazy:

            # TODO. add an option to **NOT** update existing keys

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

        return self._store[key]

    def __setitem__(self, key: FileKey,
                          value: FileValue) -> None:

        if key in self.lazy:
            del self.lazy[key]

        self._store[key] = value

    def __delitem__(self, key: FileKey) -> None:

        if key in self.lazy:
            del self.lazy[key]

        del self._store[key]

    def __iter__(self) -> Iterator[FileKey]:

        for key in self._store:
            yield key

        for key in self.lazy:
            if key in self._store:
                continue
            yield key

    def __len__(self) -> int:
        return len(set(self._store) | set(self.lazy))


class Protocol:
    """Base protocol

    This class should be inherited from, not used directly.

    Parameters
    ----------
    preprocessors : dict
        When provided, each protocol file (dictionary) are preprocessed, such
        that file[key] = preprocessor(file). In case 'preprocessor' is not
        callable, it should be a string containing placeholder for file keys
        (e.g. {'audio': '/path/to/{uri}.wav'})
    """

    def __init__(self, preprocessors: Dict[FileKey, RawPreprocessor] = {},
                       **kwargs):

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

        self.progress = False
        if 'progress' in kwargs:
            msg = f"'progress' keyword argument has been deprecated."
            warnings.warn(msg, DeprecationWarning)

    def preprocess(self, current_file: dict) -> ProtocolFile:
        return ProtocolFile(current_file, self.preprocessors)

    def __str__(self) -> str:
        return self.__doc__
