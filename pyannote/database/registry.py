#!/usr/bin/env python
# encoding: utf-8

# The MIT License (MIT)

# Copyright (c) 2022- CNRS
# Copyright (c) 2022- Université Paul Sabatier

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
# Alexis PLAQUET 
# Hervé BREDIN - http://herve.niderb.fr
# Alexis PLAQUET

from enum import Enum
import os
from pathlib import Path
from typing import Dict, List, Optional, Set, Text, Tuple, Type, Union
import warnings

from pyannote.database.protocol.protocol import Preprocessors, Protocol
from .custom import create_protocol, get_init, get_custom_protocol_class_name
from .database import Database
import yaml

# import sys
# from pkg_resources import iter_entry_points


class OverrideType(Enum):
    OVERRIDE = 0  # replace existing
    WARN_OVERRIDE = 1  # warn when replacing existing data, do it, and continue.
    WARN_KEEP = 2  # warn when trying to replace existing data. Dont override it.
    KEEP = 3  # never replace existing data


# To ease the understanding of future me, all comments inside Registry codebase
# assume the existence of the following database.yml files.

# ======================================
# Content of /path/to/first/database.yml
# ======================================
# Databases:
#     DatabaseA: 
#         - relative/path/A/trn/{uri}.wav
#         - relative/path/A/dev/{uri}.wav
#         - relative/path/A/tst/{uri}.wav
#     DatabaseB: /absolute/path/B/{uri}.wav
#
# Protocols:
#     DatabaseA:
#         SpeakerDiarization:
#             ProtocolA:
#                 train:
#                     uri: relative/path/A/trn.lst
#                 development:
#                     uri: relative/path/A/dev.lst
#                 test:
#                     uri: relative/path/A/tst.lst
#             ProtocolB:
#                 ...
#     DatabaseB:
#         SpeakerDiarization:
#             Protocol:
#                 ...
#     X:
#         SpeakerDiarization:
#             A_and_B:
#                 train: ...
#                 development: ...
#                 test: ...

# ======================================
# Content of /path/to/second/database.yml
# ======================================
# Databases:
#     DatabaseC: /absolute/path/C/{uri}.wav
#     DatabaseB: /absolute/path/B/{uri}.wav
# Protocols:
#     DatabaseB:
#         SpeakerDiarization:
#             Protocol:
#                ...
#     DatabaseC:
#         SpeakerDiarization:
#             Protocol:
#                 ...    


class Registry:
    """Stores the data from one (or multiple !) database.yml files.
    

    Usage
    -----

    >>> from pyannote.database import registry
    >>> registry.load_database("/path/to/first/database.yml")
    >>> registry.load_database("/path/to/second/database.yml")
    
    """

    def __init__(self) -> None:

        # Mapping of database.yml paths to their config in a dictionary
        # Example after loading both database.yml:
        #   {"/path/to/first/database.yml": ????,
        #    "/path/to/second/database.yml": ???}

        self.configs: Dict[Path, Dict] = dict()


        # Content of the "Database" root item (= where to find file content)
        # Example after loading both database.yml:
        #   {???: ???}
        self.sources: Dict[Text, List[Text]] = dict()

        # Mapping of database names to a type that inherits from Database
        self.databases: Dict[Text, Type] = dict()
        # Example after loading both database.yml:
        #   {???: ???}

        # Mapping of tasks name to the set of databases that support this task
        # Example after loading both database.yml:
        #   {???: ???}
        self.tasks: Dict[Text, Set[Text]] = dict()

        # self.load_entry_points()

    # def load_entry_points(self):

    #     # load databases from entry points
    #     for o in iter_entry_points(group="pyannote.database.databases", name=None):

    #         database_name = o.name

    #         DatabaseClass = o.load()
    #         self.databases[database_name] = DatabaseClass

    #         database = DatabaseClass()

    #         for task in database.get_tasks():
    #             if task not in self.tasks:
    #                 self.tasks[task] = set()
    #             self.tasks[task].add(database_name)

    #         setattr(sys.modules[__name__], database_name, DatabaseClass)

    #     # TODO: update self.configs
    #     # TODO: update self.sources


    def load_databases(
        self,
        *paths: Union[Text, Path],
        allow_override: OverrideType = OverrideType.WARN_KEEP,
    ):
        """Load all database yaml files passed as parameter into this config.

        Parameters
        ----------
        allow_override : OverrideType, optional
            How to treat duplicates protocols between multiple yml files.
            Files will be treated in the order they're passed.
            If overriding, last yml to define a protocol will set it.
            If not, first yml to define a protocol will be set it.
            By default, all override attemps will result in a warning, by default OverrideType.WARN_OVERRIDES
        """

        for path in paths:
            fullpath = get_database_yml(path)  # only expands ~ to full path

            with open(fullpath, "r") as fp:
                config = yaml.load(fp, Loader=yaml.SafeLoader)

            self.configs[fullpath] = config
            self._process_config(fullpath, allow_override=allow_override)

        self._reload_meta_protocols()


    def get_databases(self, task=None) -> List[Text]:
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
            return sorted(self.databases)

        return sorted(self.tasks.get(task, []))

    def get_database(self, database_name, **kwargs) -> Database:
        """Get database by name

        Parameters
        ----------
        database_name : str
            Database name.

        Returns
        -------
        database : Database
            Database instance
        """

        try:
            database = self.databases[database_name]

        except KeyError:

            if database_name == "X":
                msg = (
                    "Could not find any meta-protocol. Please refer to "
                    "pyannote.database documentation to learn how to define them: "
                    "https://github.com/pyannote/pyannote-database"
                )
            else:
                msg = (
                    'Could not find any protocol for "{name}" database. Please '
                    "refer to pyannote.database documentation to learn how to "
                    "define them: https://github.com/pyannote/pyannote-database"
                )
                msg = msg.format(name=database_name)
            raise ValueError(msg)

        return database(**kwargs)

    def get_protocol(self, name, preprocessors: Optional[Preprocessors] = None) -> Protocol:
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

        database_name, task_name, protocol_name = name.split(".")
        database = self.get_database(database_name)
        protocol = database.get_protocol(
            task_name, protocol_name, preprocessors=preprocessors
        )
        protocol.name = name
        return protocol


    def get_tasks(self) -> List[Text]:
        """Get the list of tasks

        Returns
        -------
        List[Text]
            List of all task names.
        """
        return sorted(self.tasks)


    def _process_database(
        self,
        db_name,
        db_entries: dict,
        database_yml: Union[Text, Path] = None,
        allow_override: OverrideType = OverrideType.WARN_KEEP,
    ):
        """Loads all protocols from this database to this Registry.

        Parameters
        ----------
        db_name : _type_
            Name of the database
        db_entries : dict
            Dict of all entries under this database (this should be tasks)
        database_yml : Union[Text, Path], optional
            Path to the database.yml file. Not required for X protocols, by default None
        """

        db_name = str(db_name)

        # maps tuple (task,protocol) to the custom protocol class
        protocols: Dict[Tuple[Text, Text], Type] = dict()

        for task_name, task_entries in db_entries.items():
            for protocol, protocol_entries in task_entries.items():
                protocol = str(protocol)
                CustomProtocol = create_protocol(
                    db_name, task_name, protocol, protocol_entries, database_yml
                )
                if CustomProtocol is None:
                    continue

                protocols[(task_name, protocol)] = CustomProtocol

                # update TASKS dictionary
                if task_name not in self.tasks:
                    self.tasks[task_name] = set()
                self.tasks[task_name].add(db_name)

        # If needed, merge old protocols dict with the new one (according to current override rules)
        if db_name in self.databases:
            old_protocols = self.databases[db_name]._protocols
            _merge_protocols_inplace(protocols, old_protocols, allow_override, db_name, database_yml)

        # create database class on-the-fly
        protocol_list = [
            (task, p_name, p_type) for (task, p_name), p_type in protocols.items()
        ]
        self.databases[db_name] = type(
            db_name,
            (Database,),
            {"__init__": get_init(protocol_list), "_protocols": protocols},
        )

    def _process_config(
        self,
        database_yml: Union[Text, Path],
        config: dict = None,
        allow_override: OverrideType = OverrideType.WARN_KEEP,
    ):
        """Register all protocols (but meta protocols) and all file sources defined in configuration file.

        Parameters
        ----------
        database_yml : Union[Text, Path]
            Path to the database.yml
        config : dict, optional
            Dictionary containing all data parsed from the database.yml file.
            Loads the config from self.configs if left to None, by default None
        """

        database_yml = Path(database_yml)
        if config is None:
            config = self.configs[database_yml]

        databases = config.get("Protocols", dict())

        # make sure meta-protocols are processed last (relies on the fact that
        # dicts are iterated in insertion order since Python 3.6)
        x = databases.pop("X", None)
        if x is not None:
            databases["X"] = x
            # TODO: add postprocessing reloading X protocol

        for db_name, db_entries in databases.items():
            self._process_database(
                db_name, db_entries, database_yml, allow_override=allow_override
            )

        # process sources
        # TODO: decide how to handle source overriding
        for db_name, value in config.get("Databases", dict()).items():
            if not isinstance(value, list):
                value = [value]

            path_list: List[str] = list()
            for p in value:
                path = Path(p)
                if not path.is_absolute():
                    path = database_yml.parent / path
                path_list.append(str(path))
            self.sources[str(db_name)] = path_list

    def _reload_meta_protocols(self):
        """Reloads all meta protocols from all database.yml files loaded."""

        # TODO: decide how to handle X protocol overriding.

        self.databases.pop("X", None)

        for db_yml, config in self.configs.items():
            databases = config.get("Protocols", dict())
            if "X" in databases:
                self._process_database("X", databases["X"], db_yml, allow_override=OverrideType.WARN_OVERRIDE)



def _env_config_paths() -> List[Path]:
    """Retrieve yaml database files to be loaded from the PYANNOTE_DATABASE_CONFIG environment variable.
    In case it contains multiple files, the paths must be separated by semicolons (;) in the environment variable.

    Returns
    -------
    List[Path]
        List of all yaml database file paths found in $PYANNOTE_DATABASE_CONFIG
    """

    valid_paths = []

    env_config_paths = os.environ.get("PYANNOTE_DATABASE_CONFIG", "")
    splitted = env_config_paths.split(";")
    for path in splitted:
        path = Path(path).expanduser()
        if path.is_file():
            valid_paths.append(path)
    return valid_paths

def _find_default_ymls() -> List[Path]:
    """Retrieve all possible yaml databases at startup.
    The order is '~/.pyannote/database.yml' -> './database.yml" -> $PYANNOTE_DATABASE_CONFIG.

    Returns
    -------
    List[Path]
        List of all yaml database file path to load at startup
    """

    valid_paths: List[Path] = []

    home_db_yml = Path("~/.pyannote/database.yml").expanduser()
    if home_db_yml.is_file():
        valid_paths.append(home_db_yml)
    
    cwd_db_yml = Path.cwd() / "database.yml"
    if cwd_db_yml.is_file():
        valid_paths.append(home_db_yml)
    
    valid_paths += _env_config_paths()

    return valid_paths

def get_database_yml(database_yml: Union[Text, Path] = None) -> Path:
    """Find location of pyannote.database configuration file

    Parameter
    ---------
    database_yml : Path, optional
        Force using this file.

    Returns
    -------
    path : Path
        Path to 'database.yml'

    Raises
    ------
    FileNotFoundError when the configuration file could not be found.
    """

    # when database_yml is provided, use it
    if database_yml is not None:
        database_yml = Path(database_yml).expanduser()
        # does the provided file exist?
        if not database_yml.is_file():
            msg = f"File '{database_yml}' does not exist."
            raise FileNotFoundError(msg)

        return database_yml

    # is there a file named "database.yml" in current working directory?
    if (Path.cwd() / "database.yml").is_file():
        database_yml = Path.cwd() / "database.yml"

    # does PYANNOTE_DATABASE_CONFIG environment variable links to an existing file?
    elif os.environ.get("PYANNOTE_DATABASE_CONFIG") is not None:
        database_yml = Path(os.environ.get("PYANNOTE_DATABASE_CONFIG")).expanduser()
        if not database_yml.is_file():
            msg = (
                f'"PYANNOTE_DATABASE_CONFIG" links to a file that does not'
                f'exist: "{database_yml}".'
            )
            raise FileNotFoundError(msg)

    # does default "~/.pyannote/database.yml" file exist?
    else:
        database_yml = Path("~/.pyannote/database.yml").expanduser()

        # if it does not, let the user know that nothing worked and in which
        # locations "database.yml" was looked for.
        if not database_yml.is_file():
            msg = (
                f'"pyannote.database" relies on a YAML configuration file but '
                f"could not find any. Here are the locations that were "
                f'looked for: {Path.cwd() / "database.yml"}, {database_yml}'
            )
            if os.environ.get("PYANNOTE_DATABASE_CONFIG") is not None:
                database_yml = Path(
                    os.environ.get("PYANNOTE_DATABASE_CONFIG")
                ).expanduser()
                msg += (
                    f", and {database_yml} (given by "
                    f"PYANNOTE_DATABASE_CONFIG environment variable)."
                )
            else:
                msg += "."
            raise FileNotFoundError(msg)

    return database_yml


def _merge_protocols_inplace(new_protocols: Dict[Tuple[Text, Text], Type], old_protocols: Dict[Tuple[Text, Text], Type], allow_override:OverrideType, db_name, database_yml:str):
    """Merge new and old protocols inplace into the passed new_protocol.
    Warning, merging order might be counterintuitive : "KEEP" strategy keeps element from the OLD protocol
    and MODIFIES the new protocol.

    Parameters
    ----------
    new_protocols : Dict[Tuple[Text, Text], Type]
        New protocol dict
        Maps (task,protocol) tuples to custom protocol classes
    old_protocols : Dict[Tuple[Text, Text], Type]
        Old protocols dict
        Maps (task,protocol) tuples to custom protocol classes.
    allow_override : OverrideType
        How to handle override
    db_name : _type_
        Name of the database (for logging/warning purposes)
    database_yml : str
        Path of the database.yml file (for logging/warning purposes)
    """

    # for all previously defined protocol (in old_protocols)
    for p_id, old_p in old_protocols.items():
        # if this protocol is redefined
        if p_id in new_protocols:
            t_name, p_name = p_id
            realname = get_custom_protocol_class_name(
                db_name, t_name, p_name
            )

            # Either overriding the protocol is allowed (OVERRIDE or WARN_OVERRIDES) ...
            if allow_override == OverrideType.OVERRIDE or allow_override == OverrideType.WARN_OVERRIDE:
                if allow_override == OverrideType.WARN_OVERRIDE:
                    warnings.warn(f"Overriding protocol {realname}, the new definition is from {database_yml}.")
                # do nothing : keep the protocol in new_protocol
                continue
            # ... or it isnt : (KEEP or WARN_OVERRIDES)
            else:
                if allow_override == OverrideType.WARN_KEEP:
                    warnings.warn(
                        f"Couldn't override already loaded protocol {realname}, redefined in {database_yml}. Allow or ignore overrides to get rid of this message."
                    )
                # keep the previously defined protocol : replace the new protocol with the old one
                new_protocols[p_id] = old_p

        # no conflit : keep the previously defined protocol
        else:
            new_protocols[p_id] = old_p




# initialize the registry singleton
registry = Registry()

# load all database yaml files found at startup
registry.load_databases(*_find_default_ymls(), allow_override=OverrideType.WARN_OVERRIDE)