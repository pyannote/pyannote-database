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

"""

import sys
from pkg_resources import iter_entry_points

from .database import Database
from .database import PyannoteDatabaseException

DATABASES = dict()
TASKS = dict()

for o in iter_entry_points(group='pyannote.database.databases', name=None):

    database_name = o.name

    DatabaseClass = o.load()
    DATABASES[database_name] = DatabaseClass

    database = DatabaseClass()

    for task in database.get_tasks():
        if task not in TASKS:
            TASKS[task] = set()
        TASKS[task].add(database_name)

    setattr(sys.modules[__name__], database_name, DatabaseClass)


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

    if task is None:
        return sorted(DATABASES)

    return sorted(TASKS.get(task, []))


def get_database(database_name, preprocessors={}, **kwargs):
    """Get database by name

    Parameters
    ----------
    name : str
        Database name.
    preprocessors : dict or (key, preprocessor) iterable
        When provided, each protocol item (dictionary) are preprocessed, such
        that item[key] = preprocessor(item). In case 'preprocessor' is not
        callable, it should be a string containing placeholder for item keys
        (e.g. {'audio': '/path/to/{uri}.wav'})

    Returns
    -------
    database : Database
        Database instance
    """
    try:
        database = DATABASES[database_name]
    except KeyError as e:

        if database_name == 'X':
            msg = ('Could not find any "meta-protocol". '
                   'Edit file "~/.pyannote/meta.yml" to define them.')
        else:
            msg = ('Could not find any "{name}" database. '
                   'Did you install the corresponding pyannote.database plugin?')
            msg = msg.format(name=database_name)
        raise ValueError(msg)

    return database(preprocessors=preprocessors, **kwargs)

def get_protocol(name, preprocessors={}, progress=False, **kwargs):
    """Get protocol by full name

    name : str
        Protocol full name (e.g. "Etape.SpeakerDiarization.TV")
    preprocessors : dict or (key, preprocessor) iterable
        When provided, each protocol item (dictionary) are preprocessed, such
        that item[key] = preprocessor(item). In case 'preprocessor' is not
        callable, it should be a string containing placeholder for item keys
        (e.g. {'audio': '/path/to/{uri}.wav'})
    progress : bool, optional
        Defaults to False.

    Returns
    -------
    protocol : Protocol
        Protocol instance
    """

    database_name, task_name, protocol_name = name.split('.')
    database = get_database(database_name,
                            preprocessors=preprocessors,
                            **kwargs)
    protocol = database.get_protocol(task_name, protocol_name,
                                     progress=progress)
    return protocol


def get_tasks():
    """List of tasks"""
    return sorted(TASKS)


from .util import FileFinder
from .util import get_annotated
from .util import get_unique_identifier
from .util import get_label_identifier

# import meta-protocol database X
from . import meta
database = meta.X()
try:
    tasks = database.get_tasks()
    for task in tasks:
        if task not in TASKS:
            TASKS[task] = set()
        TASKS[task].add('X')
    DATABASES['X'] = meta.X
    setattr(sys.modules[__name__], 'X', meta.X)
except PyannoteDatabaseException as e:
    pass

from ._version import get_versions
__version__ = get_versions()['version']
del get_versions
