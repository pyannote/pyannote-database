from pathlib import Path
from typing import Dict, List, Set, Text, Union
from .custom import create_protocol, get_init
from .database import Database
from .config import get_database_yml
import yaml


class PyannoteDbConfig:
    """Stores the data from one (or multiple !) database.yml files."""

    def __init__(self) -> None:
        # Mapping of database.yml paths to their config in a dictionary
        self.configs: Dict[Path, Dict] = dict()

        # Content of the "Database" root item (=where to find file content)
        self.sources = dict()

        self.databases = dict()
        self.tasks: Dict[Text, Set[Text]] = dict()

    def load_databases(self, *paths: Union[Text, Path]):
        for path in paths:
            fullpath = get_database_yml(path)  # only expands ~ to full path

            if fullpath in self.configs:
                raise Warning(f"Tried to load {path} multiple times")
                continue

            with open(fullpath, "r") as fp:
                config = yaml.load(fp, Loader=yaml.SafeLoader)

            self.configs[fullpath] = config
        
        self._reload_meta_protocols()

    def _process_database(
        self, db_name, db_entries: dict, database_yml: Union[Text, Path] = None
    ):
        # adds everything in this database to the PyannoteDbConfig
        # database_yml not required for X meta protocols ;)

        db_name = str(db_name)
        protocols = []

        for task_name, task_entries in db_entries.items():
            for protocol, protocol_entries in task_entries.items():
                protocol = str(protocol)
                CustomProtocol = create_protocol(
                    db_name, task_name, protocol, protocol_entries, database_yml
                )
                if CustomProtocol is None:
                    continue

                protocols.append((task_name, protocol, CustomProtocol))

                # update TASKS dictionary
                if task_name not in self.tasks:
                    self.tasks[task_name] = set()
                self.tasks[task_name].add(db_name)

        # create database class on-the-fly
        # if database was already defined, get its existing protocols and add the new ones
        if db_name in self.databases:
            protocols += self.databases[db_name]._protocols
        self.databases[db_name] = type(
            db_name,
            (Database,),
            {"__init__": get_init(protocols), "_protocols": protocols},
        )

    def _process_config(self, database_yml: Union[Text, Path], config: dict):
        """Register databases, tasks, and protocols defined in configuration file"""
        database_yml = Path(database_yml)

        databases = config.get("Protocols", dict())

        # make sure meta-protocols are processed last (relies on the fact that
        # dicts are iterated in insertion order since Python 3.6)
        x = databases.pop("X", None)
        if x is not None:
            databases["X"] = x
            # TODO: add postprocessing reloading X protocol

        for db_name, db_entries in databases.items():
            self._process_database(db_name, db_entries, database_yml)

        # process sources
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
        """Reloads all meta protocols from all database.yml files loaded.
        """

        for db_yml, config in self.configs.items():
            databases = config.get("Protocols", dict())
            if "X" in databases:
                self._process_database("X", databases["X"], None)
                