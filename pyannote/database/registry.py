from enum import Enum
import os
from pathlib import Path
from typing import Dict, List, Optional, Set, Text, Tuple, Type, Union

from .custom import create_protocol, get_init, get_custom_protocol_class_name
from .database import Database
import yaml


class OverrideType(Enum):
    OVERRIDE = 0  # replace existing
    INFO_OVERRIDE = 1  # inform when replacing existing data, do it, and continue.
    WARN_KEEP = 2  # warn when trying to replace existing data. Dont override it.
    KEEP = 3  # never replace existing data


class Registry:
    """Stores the data from one (or multiple !) database.yml files."""

    def __init__(self) -> None:
        # Mapping of database.yml paths to their config in a dictionary
        self.configs: Dict[Path, Dict] = dict()

        # Content of the "Database" root item (=where to find file content)
        self.sources: Dict[Text, List[Text]] = dict()

        # Mapping of database names to a type that inherits from Database
        self.databases: Dict[Text, Type] = dict()

        # Mapping of tasks name to the set of databases that support this task
        self.tasks: Dict[Text, Set[Text]] = dict()

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
                self._process_database("X", databases["X"], None)



# registry singleton
registry = Registry()



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

    Raises
    ------
    Warning
        Raised if OverrideType is WARN_KEEP and a protocol is defined both in new_protocols and new_protocols
    """

    # for all previously defined protocol (in old_protocols)
    for p_id, old_p in old_protocols.items():
        # if this protocol is redefined
        if p_id in new_protocols:
            t_name, p_name = p_id
            realname = get_custom_protocol_class_name(
                db_name, t_name, p_name
            )

            # Either overriding the protocol is allowed (OVERRIDE or INFO_OVERRIDES) ...
            if allow_override == OverrideType.OVERRIDE or allow_override == OverrideType.INFO_OVERRIDE:
                if allow_override == OverrideType.INFO_OVERRIDE:
                    print(f"Overriding protocol {realname}, the new definition is from {database_yml}.")
                continue    # keep the protocol in new_protocol
            # ... or it isnt : (KEEP or WARN_OVERRIDES)
            else:
                if allow_override == OverrideType.WARN_KEEP:
                    raise Warning(
                        f"Couldn't override already loaded protocol {realname} in {database_yml}. Allow or ignore overrides to get rid of this message."
                    )
                # keep the previously defined protocol : replace the new protocol with the old one
                new_protocols[p_id] = old_p

        # no conflit : keep the previously defined protocol
        else:
            new_protocols[p_id] = old_p