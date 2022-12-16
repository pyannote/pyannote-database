#!/usr/bin/env python
# encoding: utf-8

# The MIT License (MIT)

# Copyright (c) 2016- CNRS

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
# Alexis PLAQUET

"""pyannote.database"""

import warnings

from typing import Optional

from .registry import registry, OverrideType

from .database import Database

from .protocol.protocol import Protocol
from .protocol.protocol import ProtocolFile
from .protocol.protocol import Subset
from .protocol.protocol import Preprocessors

from .file_finder import FileFinder
from .util import get_annotated
from .util import get_unique_identifier
from .util import get_label_identifier

from ._version import get_versions


__version__ = get_versions()["version"]
del get_versions


def get_databases(task=None):
    """Get list of databases

    Parameters
    ----------
    task : str, optional
        Only returns databases providing protocols for this task.
        Defaults to returning every database.

    Returns
    -------
    databases : list
        List of database, sorted in alphabetical order

    """
    warnings.warn("get_databases is deprecated, use registry.get_databases instead.", DeprecationWarning)
    return registry.get_databases(task=task)


def get_database(database_name, **kwargs):
    """Get database by name

    Parameters
    ----------
    name : str
        Database name.

    Returns
    -------
    database : Database
        Database instance
    """
    warnings.warn("get_database is deprecated, use registry.get_database instead.", DeprecationWarning)
    return registry.get_database(database, **kwargs)


def get_protocol(name, preprocessors: Optional[Preprocessors] = None) -> Protocol:
    """Get protocol by full name

    name : str
        Protocol full name (e.g. "Etape.SpeakerDiarization.TV")
    preprocessors : dict or (key, preprocessor) iterable
        When provided, each protocol item (dictionary) are preprocessed, such
        that item[key] = preprocessor(item). In case 'preprocessor' is not
        callable, it should be a string containing placeholder for item keys
        (e.g. {'audio': '/path/to/{uri}.wav'})

    Returns
    -------
    protocol : Protocol
        Protocol instance
    """
    warnings.warn("get_protocol is deprecated, use registry.get_protocol instead.", DeprecationWarning)
    return registry.get_protocol(name, preprocessors=preprocessors)


def get_tasks():
    """List of tasks"""
    warnings.warn("get_tasks is deprecated, use registry.get_tasks instead.", DeprecationWarning)
    return registry.get_tasks()


__all__ = [
    "registry",
    "OverrideType",
    "Database",
    "get_databases",
    "get_database",
    "get_tasks",
    "Protocol",
    "get_protocol",
    "ProtocolFile",
    "Subset",
    "FileFinder",
    "get_annotated",
    "get_unique_identifier",
    "get_label_identifier",
]
