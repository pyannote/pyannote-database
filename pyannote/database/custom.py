#!/usr/bin/env python
# encoding: utf-8

# The MIT License (MIT)

# Copyright (c) 2019 CNRS

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

from . import protocol as Protocol
from .database import Database
from .util import load_lst, load_uem, load_mdtm, load_rttm
import functools
from pathlib import Path
import yaml
import pandas as pd


from . import DATABASES, TASKS



def subset_iter(database_name, file_lst=None, file_rttm=None, file_uem=None):
    """This function will become a xxx_iter method of a protocol.

    Parameters
    ----------
    database_name : `str`
        Database name.
    file_lst : `Path`, optional
        Path to file with a list of URIs of the database.
    file_rttm : `Path`, optional
        Path to RTTM (or MDTM) file.
    file_uem : `Path`, optional
        Path to UEM file.

    Yields
    ------
    current_file : `dict`
        Dictionary that provides information about a file.
        This must include (at the very least) 'uri' and 'database' keys.
    """

    annotations, annotated, uris = dict(), dict(), list()

    # load annotations
    if file_rttm is not None:

        if file_rttm.suffix == '.rttm':
            annotations = load_rttm(file_rttm)
        elif file_rttm.suffix == '.mdtm':
            annotations = load_mdtm(file_mdtm)
        else:
            msg = f'Unsupported format in {file_rttm}: please use RTTM.'
            raise ValueError(msg)

    # load annotated
    if file_uem is not None:
        annotated = load_uem(file_uem)

    # load list of files
    if file_lst is not None:
        uris = load_lst(file_lst)

    # check URIs list consistency

    # if file_lst is provided, make sure other files don't contain extra URIs
    if len(uris) > 0:

        if not set(annotations).issubset(set(uris)):
            msg = f'{file_rttm} contains URIs that are not in {file_lst}.'
            raise ValueError(msg)

        if not set(annotated).issubset(set(uris)):
            msg = f'{file_rttm} contains URIs that are not in {file_lst}.'
            raise ValueError(msg)

    # if file_uem is provided, make sure file_rttm doesn't contain extra URIs
    elif len(annotated) > 0:
        uris = sorted(annotated)
        if not set(annotations).issubset(set(uris)):
            msg = f'{file_rttm} contains URIs that are not in {file_uem}.'
            raise ValueError(msg)

    # if file_rttm is the only file provided, use its list of URIs
    elif len(annotations) > 0:
        uris = sorted(annotations)

    # complain if we weren't able to get any list of URIs
    if len(uris) == 0:
        msg = f'Empty protocol'
        raise ValueError(msg)

    # loop on all URIs
    for uri in uris:

        # initialize current file with the mandatory keys
        current_file = {'database': database_name,
                        'uri': uri}

        # add 'annotation' if/when available
        if uri in annotations:
            current_file['annotation'] = annotations[uri]

        # add 'annotated' if/when available
        if uri in annotated:
            current_file['annotated'] = annotated[uri]

        yield current_file


def add_custom_protocols(custom_yml=None):
    """Update pyannote.database.{DATABASES, TASKS} with custom protocols

    Parameters
    ----------
    custom_yml : `Path`, optional
        path to YAML file with description of the database and its protocols

    Returns
    -------
    pyannote.database.DATABASES
    pyannote.database.TASKS
    """

    if custom_yml is None:
        custom_yml = Path('~/.pyannote/custom.yml').expanduser()

    try:
        with open(custom_yml, 'r') as fp:
            custom_config = yaml.load(fp)

    except FileNotFoundError:
        custom_config = dict()

    # for each database
    for database_name, dbtasks in custom_config.items():

        # this list is meant to contain one class per protocol
        register = []

        # for each type of task
        for task_name, protocols in dbtasks.items():

            # update TASKS dictionary
            if task_name not in TASKS:
                TASKS[task_name] = set()
            TASKS[task_name].add(database_name)

            # only speaker diarization TASKS are supported for now...
            if task_name != 'SpeakerDiarization':
                msg = ('Only speaker diarization protocols are supported for now.')
                raise ValueError(msg)

            # get protocol base class (here: SpeakerDiarizationProtocol)
            protocol_base_class = getattr(Protocol, f'{task_name}Protocol')

            # annoying mapping...
            SUBSET = {'train': 'trn', 'development': 'dev', 'test': 'tst'}

            # for each protocol
            for protocol_name, subsets in protocols.items():

                # this dictionary is meant to contain "trn_iter", "dev_iter", and "tst_iter" methods
                protocol_methods = {}

                # for each subset
                for subset, sub in SUBSET.items():

                    # if protocols.yml does not provide a file for this subset,
                    # skip it
                    if subset not in subsets:
                        continue

                    paths = subsets[subset]
                    file_rttm, file_lst, file_uem = None, None, None
                    if 'annotation' in paths:
                        file_rttm = Path(paths['annotation'])
                    if 'uris' in paths:
                        file_lst = Path(paths['uris'])
                    if 'annotated' in paths:
                        file_uem = Path(paths['annotated'])

                    # define xxx_iter method
                    protocol_methods[f'{sub}_iter'] = functools.partial(
                        subset_iter, database_name, file_rttm=file_rttm,
                        file_lst=file_lst, file_uem=file_uem)

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
        DATABASES[database_name] = type(database_name, (Database,),
                                        {'__init__': db_init})

    return DATABASES, TASKS
