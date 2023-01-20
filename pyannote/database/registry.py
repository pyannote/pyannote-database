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
# Hervé BREDIN - http://herve.niderb.fr
# Alexis PLAQUET

from enum import Enum
import os
from pathlib import Path
from typing import Dict, List, Optional, Text, Tuple, Type, Union
import warnings

from pyannote.database.protocol.protocol import Preprocessors, Protocol
from .custom import create_protocol, get_init
from .database import Database
import yaml

# controls what to do in case of protocol name conflict
class LoadingMode(Enum):
    OVERRIDE = 0  # override existing protocol
    KEEP = 1      # keep existing protocol
    ERROR = 2     # raise an error 

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
    """Database and experimental protocols registry

    Usage
    -----
    >>> from pyannote.database import registry
    >>> registry.load_database("/path/to/first/database.yml")
    >>> registry.load_database("/path/to/second/database.yml")
    """

    def __init__(self) -> None:

        # Mapping of database.yml paths to their config in a dictionary
        # Example after loading both database.yml:
        #   {"/path/to/first/database.yml": {
        #           "Databases":{
        #               "DatabaseA": ["relative/path/A/trn/{uri}.wav", "relative/path/A/dev/{uri}.wav", relative/path/A/tst/{uri}.wav]
        #               "DatabaseB": "/absolute/path/B/{uri}.wav" 
        #           },
        #           "Protocols":{
        #               "DatabaseA":{
        #                   "SpeakerDiarization": {
        #                       "ProtocolA": {
        #                           "train": {"uri": "relative/path/A/trn.lst"},
        #                           "development": {"uri": "relative/path/A/dev.lst"},
        #                           "test": {"uri"; "relative/path/A/tst.lst"}
        #                       }
        #                   }
        #               },
        #               "DatabaseB":{"SpeakerDiarization":{"Protocol": {...}}},
        #               "X":{"SpeakerDiarization":{"A_and_B":{...}}}
        #           }
        #       },
        #    "/path/to/second/database.yml": {
        #           "Databases":{
        #               "DatabaseC": /absolute/path/C/{uri}.wav
        #               "DatabaseB": "/absolute/path/B/{uri}.wav" 
        #           },
        #           "Protocols":{
        #               "DatabaseB":{"SpeakerDiarization": {"Protocol": {...}}},
        #               "DatabaseC":{...}
        #           }
        #       }
        #   }
        self.configs: Dict[Path, Dict] = dict()


        # Content of the "Database" root item (= where to find file content)
        # Example after loading both database.yml:
        #   {
        #   "DatabaseA": [
        #       "/path/to/first/relative/path/A/trn/{uri}.wav",
        #       "/path/to/first/relative/path/A/dev/{uri}.wav",
        #       /path/to/first/relative/path/A/tst/{uri}.wav
        #       ],
        #   "DatabaseB": ["/absolute/path/B/{uri}.wav"],
        #   "DatabaseC": ["/absolute/path/C/{uri}.wav"]
        #   }
        self.sources: Dict[Text, List[Text]] = dict()

        # Mapping of database names to a type that inherits from Database
        # Example after loading both database.yml:
        #   {"DatabaseA": pyannote.database.registry.DatabaseA,
        #    "DatabaseB": pyannote.database.registry.DatabaseB,
        #    "DatabaseC": pyannote.database.registry.DatabaseC,
        #    "X": pyannote.database.registry.X}
        self.databases: Dict[Text, Type] = dict()

    def load_database(
        self,
        path: Union[Text, Path],
        mode: LoadingMode = LoadingMode.OVERRIDE,
    ):
        """Load YAML configuration file into the registry

        Parameters
        ----------
        path : str or Path
            Path to YAML configuration file. 
        mode : LoadingMode, optional
            Controls how to handle conflicts in protocol names.
            Defaults to overriding the existing protocol.

        Usage
        -----
        >>> from pyannote.database import registry
        >>> registry.load_database("/path/to/database.yml")
        """

        # TODO: turn relative path to absolute
        path = Path(path).expanduser()
        with open(path, "r") as fp:
            config = yaml.load(fp, Loader=yaml.SafeLoader)
        self.configs[path] = config
        self._process_config(path, mode=mode)
        self._reload_meta_protocols()

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

        Parameters
        ----------
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

    def _process_database(
        self,
        db_name,
        db_entries: dict,
        database_yml: Union[Text, Path] = None,
        mode: LoadingMode = LoadingMode.OVERRIDE,
    ):
        """Load all protocols from this database into the registry.

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

        # If needed, merge old protocols dict with the new one (according to current override rules)
        if db_name in self.databases:
            old_protocols = self.databases[db_name]._protocols
            _merge_protocols_inplace(protocols, old_protocols, mode, db_name, database_yml)

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
        mode: LoadingMode = LoadingMode.KEEP,
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
                db_name, db_entries, database_yml, mode=mode
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
                self._process_database("X", databases["X"], db_yml, mode=LoadingMode.OVERRIDE)



def _env_config_paths() -> List[Path]:
    """Parse PYANNOTE_DATABASE_CONFIG environment variable
    
    PYANNOTE_DATABASE_CONFIG may contain multiple paths separation by ";".

    Returns
    -------
    paths : list of Path
        List of all YAML database file defined in PYANNOTE_DATABASE_CONF
    """

    content = os.environ.get("PYANNOTE_DATABASE_CONFIG", "")

    paths = []
    for path in content.split(";"):
        path = Path(path).expanduser()
        if path.is_file():
            paths.append(path)
    return paths

def _find_default_ymls() -> List[Path]:
    """Get paths to default YAML configuration files

    * $HOME/.pyannote/database.yml 
    * $CWD/database.yml
    * PYANNOTE_DATABASE_CONFIG environment variable

    Returns
    -------
    paths : list of Path
        List of existing default YAML configuration files
    """

    paths: List[Path] = []

    home_db_yml = Path("~/.pyannote/database.yml").expanduser()
    if home_db_yml.is_file():
        paths.append(home_db_yml)
    
    cwd_db_yml = Path.cwd() / "database.yml"
    if cwd_db_yml.is_file():
        paths.append(cwd_db_yml)
    
    paths += _env_config_paths()

    return paths

def _merge_protocols_inplace(
    new_protocols: Dict[Tuple[Text, Text], Type], 
    old_protocols: Dict[Tuple[Text, Text], Type], 
    mode: LoadingMode, 
    db_name: str, 
    database_yml: str):
    """Merge new and old protocols inplace into the passed new_protocol.

    Warning, merging order might be counterintuitive : "KEEP" strategy keeps element from the OLD protocol
    and MODIFIES the new protocol.

    TODO: make it intuitive :)

    Parameters
    ----------
    new_protocols : Dict[Tuple[Text, Text], Type]
        New protocol dict
        Maps (task,protocol) tuples to custom protocol classes
    old_protocols : Dict[Tuple[Text, Text], Type]
        Old protocols dict
        Maps (task,protocol) tuples to custom protocol classes.
    mode : LoadingMode
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
            realname = f"{db_name}.{t_name}.{p_name}"

            # raise an error
            if mode == LoadingMode.ERROR:
                raise RuntimeError(
                    f"Cannot load {realname} protocol from '{database_yml}' as it already exists.")

            # keep the new protocol
            elif mode == LoadingMode.OVERRIDE:
                warnings.warn(f"Replacing existing {realname} protocol by the one defined in '{database_yml}'.")
                pass
            
            # keep the old protocol
            elif mode == LoadingMode.KEEP:
                warnings.warn(
                    f"Skipping {realname} protocol defined in '{database_yml}' as it already exists."
                )
                new_protocols[p_id] = old_p

        # no conflit : keep the previously defined protocol
        else:
            new_protocols[p_id] = old_p

# initialize the registry singleton
registry = Registry()

# load all database yaml files found at startup
for yml in _find_default_ymls():
    registry.load_database(yml)