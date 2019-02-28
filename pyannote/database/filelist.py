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

from pyannote.core import Segment, Timeline, Annotation
from .database import Database
from . import protocol as Protocol
import functools
from pathlib import Path
import yaml
import pandas as pd


def subset_iter(database_name, path_mdtm=None, path_uem=None):
    """This function will become a xxx_iter method of a protocol.

    Parameters
    ----------
    database_name : `str`
        Database name.
    path_mdtm : `Path`, optional
        Path to MDTM file.
    path_uem : `Path`, optional
        Path to UEM file.

    Yields
    ------
    current_file : `dict`
        Dictionary that provides information about a file.
        This includes (at least) a 'uri' key and a 'database' keys.

    """

    names = ['uri', 'NA1', 'start', 'duration', 'NA2', 'NA3', 'NA4', 'label']
    annotations = pd.read_table(path_mdtm, names=names, delim_whitespace=True)

    names = ['uri', 'NA1', 'start', 'end']
    annotated = pd.read_table(path_uem, names=names, delim_whitespace=True).groupby('uri')

    for uri, turns in annotations.groupby('uri'):
        reference = Annotation(uri=uri)
        for turn_id, row in turns.iterrows():
            segment = Segment(row.start, row.start + row.duration)
            label = row.label
            reference[segment, turn_id] = label

        uem = Timeline(uri=uri)
        for _, row in annotated.get_group(uri).iterrows():
            segment = Segment(row.start, row.end)
            uem.add(segment)

        yield {'uri': uri,
               'database': database_name,
               'annotation': reference,
               'annotated': uem}


def add_filelist_databases(databases={}, tasks={}, config_path=None):
    """

    :param databases: This dictionary cotains one database class per entry.
    Thus method will updated it by parsing entries in ~/.pyannote/protocols.yml or a provided config
    :param tasks: The dictionary of tasks and associated databases
    :param config_path: path to YAML file with description of the database and its protocols
    :return: updated databases dictionary
    """

    if config_path is None or not Path(config_path).exists():
        # load databases from config file in ~/.pyannote/protocols.yml
        config_path = '~/.pyannote/protocols.yml'
    ymlpath = Path(config_path).expanduser()
    with open(ymlpath, 'r') as fp:
        protocols_description = yaml.load(fp)

    # for each database
    for database_name, dbtasks in protocols_description.items():

        # this list is meant to contain one class per protocol
        register = []

        # for each type of task
        for task_name, protocols in dbtasks.items():

            # update tasks dictionary
            if task_name not in tasks:
                tasks[task_name] = set()
            tasks[task_name].add(database_name)

            # only speaker diarization tasks are supported for now...
            if task_name != 'SpeakerDiarization':
                msg = ('Only speaker diarization protocols are supported for now.')
                raise ValueError(msg)

            # get protocol base class (here: SpeakerDiarizationProtocol)
            protocol_base_class = getattr(Protocol,
                                          f'{task_name}Protocol')

            # annoying mapping...
            SUBSET = {'train': 'trn', 'development': 'dev', 'test': 'tst'}

            # for each protocol
            for protocol_name, subsets in protocols.items():

                # this dictionary is meant to contain "trn_iter", "dev_iter", and "tst_iter" methods
                protocol_methods = {}

                # for each subset
                for subset, sub in SUBSET.items():

                    # if protocols.yml does not provide a file for this subset, skip it
                    if subset not in subsets:
                        continue

                    # define xxx_iter method
                    protocol_methods[f'{sub}_iter'] = functools.partial(
                        subset_iter,
                        database_name,
                        path_mdtm=subsets[subset].get('annotation', None),
                        path_uem=subsets[subset].get('annotated', None))

            # create protocol class on-the-fly
            protocol = type(protocol_name, (protocol_base_class,), protocol_methods)

            # keep track of this protocol -- database.__init__ needs to register it later...
            register.append((task_name, protocol_name, protocol))

        # define Database.__init__ method
        def db_init(self, preprocessors={}):
            super(self.__class__, self).__init__(preprocessors=preprocessors)
            for protocol in register:
                self.register_protocol(*protocol)

        # create database class on-the-fly
        databases[database_name] = type(database_name, (Database,), {'__init__': db_init})

    return databases, tasks

