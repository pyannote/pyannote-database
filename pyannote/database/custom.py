#!/usr/bin/env python
# encoding: utf-8

# The MIT License (MIT)

# Copyright (c) 2019-2020 CNRS

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
# Pavel KORSHUNOV - https://www.idiap.ch/~pkorshunov/
# Paul LERNER

"""Custom protocols

Protocols:
  MyDatabase:
    Collection:
      MyProtocol:
        train:
          uris: xxx.lst
          annotation: xxx.rttm
          annotated: xxx.uem
"""

from pathlib import Path

from . import protocol as Protocol
from .database import Database
from pyannote.database import ProtocolFile
import yaml
from typing import Text, Dict, Callable, Any
import functools

from . import DATABASES, TASKS

import pkg_resources

LOADERS = {
    ep.name: ep
    for ep in pkg_resources.iter_entry_points(group="pyannote.database.loader")
}


def Template(template: Text, database_yml: Path) -> Callable[[ProtocolFile], Any]:
    """

    Parameters
    ----------
    template : str
        Path format template with "@" prefix (e.g. "@/path/to/{uri}.csv")
    database_yml : Path
        Path to database.yml configuration file.

    Returns
    -------
    load : callable

    """

    path = Path(template[1:])
    if path.suffix not in LOADERS:
        msg = f"No loader for files with '{path.suffix}' suffix"
        raise ValueError(msg)

    Loader = LOADERS[path.suffix].load()

    def load(current_file: ProtocolFile):
        path = resolve_path(Path(template.format(**abs(current_file))), database_yml)

        # check if file exists
        if not path.is_file():
            msg = f"No such file or directory: '{path}' (via '{template}' template)."
            raise FileNotFoundError(msg)

        loader = Loader(path)
        return loader(current_file)

    return load


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
    return [l.strip() for l in lines]


def resolve_path(path: Text, database_yml: Path) -> Path:
    """Resolve path

    Parameters
    ----------
    path : `str`
        Path. Can be either absolute, relative to current working directory, or
        relative to `config.yml`.
    database_yml : `Path`
        Path to pyannote.database configuration file in YAML format.

    Returns
    -------
    resolved_path: `Path`
        Resolved path.
    """

    path = Path(path).expanduser()

    if path.is_file():
        return path

    else:
        relative_path = database_yml.parent / path
        if relative_path.is_file():
            return relative_path

    msg = f'Could not find file "{path}".'
    raise FileNotFoundError(msg)


def meta_subset_iter(
    meta_database: Text,
    meta_task: Text,
    meta_protocol: Text,
    meta_subset: Text,
    subset_entries: Dict,
    database_yml: Path,
):
    """Meta-protocol method that iterates over a subset

    Parameters
    ----------
    meta_database : str
        "X"
    meta_task : str
        Task name (e.g. SpeakerDiarization, SpeakerVerification)
    meta_protocol : str
        Protocol name (e.g. MyProtocol)
    meta_subset : {"train", "development", "test"}
        Subset
    subset_entries : dict
        Subset entries.
            Etape.SpeakerDiarization.TV: [train]
            REPERE.SpeakerDiarization.Phase1: [train, development]
            REPERE.SpeakerDiarization.Phase2: [train, development]
    """

    # this is imported here to avoid circular imports
    from . import get_protocol

    for protocol, subsets in subset_entries.items():
        partial_protocol = get_protocol(protocol)

        for subset in subsets:
            # TODO. get rid of this ugly mapping in favor of "train" -> "train_iter"
            subset_short = {"train": "trn", "development": "dev", "test": "tst"}[subset]
            method_name = f"{subset_short}_iter"
            for file in getattr(partial_protocol, method_name)():
                yield file


def subset_iter(
    database: Text,
    task: Text,
    protocol: Text,
    subset: Text,
    entries: Dict,
    database_yml: Path,
):
    """

    Parameters
    ----------
    database : str
        Database name (e.g. MyDatabase)
    task : str
        Task name (e.g. SpeakerDiarization, SpeakerVerification)
    protocol : str
        Protocol name (e.g. MyProtocol)
    subset : {"train", "development", "test"}
        Subset
    entries : dict
        Subset entries.


    """

    if "uri" not in entries:
        msg = f"Missing mandatory 'uri' entry in {database}.{task}.{protocol}.{subset}"
        raise ValueError(msg)

    uris = load_lst(resolve_path(Path(entries["uri"]), database_yml))

    lazy_loader = dict()

    for key, value in entries.items():

        if key == "uri":
            continue

        if value.startswith("@"):
            lazy_loader[key] = Template(value, database_yml)

        else:

            path = resolve_path(Path(value), database_yml)

            # check if file exists
            if not path.is_file():
                msg = f"No such file or directory: '{path}'"
                raise FileNotFoundError(msg)

            # check if loader exists
            if path.suffix not in LOADERS:
                msg = f"No loader for file with '{path.suffix}' suffix"
                raise TypeError(msg)

            # load custom loader class
            Loader = LOADERS[path.suffix].load()

            # TODO: As it is right now, every call to "subset_iter" also calls "Loader(path)".
            # However, calling "Loader(path)" might be time consuming so we should probably cache it:            # following better behavior
            # Current behavior:
            #   for _ in protocol.train(): pass   # first call is slow (compute Loader(path))
            #   for _ in protocol.train(): pass   # subsequent calls are equally slow (compute Loader(path))
            # Proposed behavior:
            #   for _ in protocol.train(): pass   # first call is slow (compute and cache Loader(path))
            #   for _ in protocol.train(): pass   # subsequent calls are fast (use cached Loader(path))
            lazy_loader[key] = Loader(path)

    for uri in uris:
        yield ProtocolFile(
            {"uri": uri, "database": database, "subset": subset}, lazy=lazy_loader
        )


def get_init(protocols):
    def init(self, preprocessors={}):
        super(self.__class__, self).__init__(preprocessors=preprocessors)
        for protocol in protocols:
            self.register_protocol(*protocol)

    return init


def new_speaker_diarization_protocol(
    database: Text,
    task: Text,
    protocol: Text,
    protocol_entries: Dict,
    database_yml: Path,
) -> type:
    """Create new protocol class

    Parameters
    ----------
    database : str
    task : str
    protocol : str
    protocol_entries : dict

    Returns
    -------
    CustomProtocol : type
    """

    base_class = getattr(Protocol, f"{task}Protocol")

    methods = dict()
    for subset, subset_entries in protocol_entries.items():

        # TODO. get rid of this ugly mapping in favor of "train" -> "train_iter"
        subset_short = {"train": "trn", "development": "dev", "test": "tst"}[subset]
        method_name = f"{subset_short}_iter"

        if database == "X":
            methods[method_name] = functools.partial(
                meta_subset_iter,
                database,
                task,
                protocol,
                subset,
                subset_entries,
                database_yml,
            )
        else:
            methods[method_name] = functools.partial(
                subset_iter,
                database,
                task,
                protocol,
                subset,
                subset_entries,
                database_yml,
            )

    return type(protocol, (base_class,), methods)


def add_custom_protocols():
    """
    """

    from .config import get_database_yml

    try:
        database_yml = get_database_yml()
        with open(database_yml, "r") as fp:
            config = yaml.load(fp, Loader=yaml.SafeLoader)

    except FileNotFoundError:
        config = dict()

    databases = config.get("Protocols", dict())

    # make sure meta-protocols are processed last (relies on the fact that
    # dicts are iterated in insertion order since Python 3.6)
    x = databases.pop("X", None)
    if x is not None:
        databases["X"] = x

    protocols = dict()

    for database, database_entries in databases.items():
        database = str(database)
        protocols[database] = []
        for task, task_entries in database_entries.items():

            # update TASKS dictionary
            if task not in TASKS:
                TASKS[task] = set()
            TASKS[task].add(database)

            # only speaker diarization TASKS are supported for now...
            if task != "SpeakerDiarization":
                msg = "Only speaker diarization protocols are supported for now."
                raise ValueError(msg)

            for protocol, protocol_entries in task_entries.items():
                protocol = str(protocol)
                CustomProtocol = new_speaker_diarization_protocol(
                    database, task, protocol, protocol_entries, database_yml
                )
                protocols[database].append((task, protocol, CustomProtocol))

        # create database class on-the-fly
        DATABASES[database] = type(
            database, (Database,), {"__init__": get_init(protocols[database])}
        )

    return DATABASES, TASKS
