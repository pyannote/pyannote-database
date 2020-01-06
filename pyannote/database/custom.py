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


import os
from . import protocol as Protocol
from .database import Database
from .util import load_lst, load_uem, load_mdtm, load_rttm, load_mapping
import functools
from pathlib import Path
import yaml
import pandas as pd
from pyannote.core import Annotation, Timeline


from . import DATABASES, TASKS


# annoying mapping...
SUBSET_MAPPING = {'train': 'trn', 'development': 'dev', 'test': 'tst'}


def meta_subset_iter(config):
    """This function will become a xxx_iter method of a meta-protocol


    `config` comes from this part of ~/.pyannote/database.yml
    (marked with arrows below)

    ~~~~ ~/.pyannote/database.yml ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Protocols:
      X:
        SpeakerDiarization:
          ExtendedETAPE:
            train:
    -->       Etape.SpeakerDiarization.TV: [train]
    -->       REPERE.SpeakerDiarization.Phase1: [train, development]
    -->       REPERE.SpeakerDiarization.Phase2: [train, development]
            development:
              Etape.SpeakerDiarization.TV: [development]
            test:
              Etape.SpeakerDiarization.TV: [train]
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Parameters
    ----------
    config: `dict`
        {protocol_name: list of subsets} dictionary.

    Yields
    ------
    current_file : `dict`
        Dictionary that provide information about a file.
        This must include (at the very least) 'uri' and 'database' keys.
    """

    from . import get_protocol


    # loop on all protocols
    for protocol_name, subsets in config.items():

        protocol = get_protocol(protocol_name)

        # loop on requested subsets of current protocol
        for subset in subsets:

            # loop on all files of current subset
            xxx_iter = getattr(protocol, f'{SUBSET_MAPPING[subset]}_iter')
            for current_file in xxx_iter():
                yield current_file


def subset_iter(database_name, file_lst=None, file_rttm=None,
                file_uem=None, domain_txt=None):
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
    domain_txt : `Path`, optional
        Path to domain mapping file.

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
            annotations = load_mdtm(file_rttm)
        else:
            msg = f'Unsupported format in {file_rttm}: please use RTTM.'
            raise ValueError(msg)

    # load annotated
    if file_uem is not None:
        annotated = load_uem(file_uem)

    # load list of files
    if file_lst is not None:
        uris = load_lst(file_lst)

    # when file_lst is provided, use this list of uris
    if len(uris) > 0:
        pass

    # when file_uem is provided, use this list of uris
    elif len(annotated) > 0:
        uris = sorted(annotated)

    # if file_rttm is the only file provided, use its list of URIs
    elif len(annotations) > 0:
        uris = sorted(annotations)

    # complain if we weren't able to get any list of URIs
    if not uris:
        msg = f'Empty protocol'
        raise ValueError(msg)

    # load domain mapping
    if domain_txt is not None:
        domains = load_mapping(domain_txt)

    # loop on all URIs
    for uri in uris:

        # initialize current file with the mandatory keys
        current_file = {'database': database_name, 'uri': uri}

        # add 'annotation' when RTTM file is provided
        # defaults to empty Annotation because of
        # github.com/pyannote/pyannote-database/pull/13#discussion_r261564520)
        if file_rttm is not None:
            current_file['annotation'] = annotations.get(
                uri, Annotation(uri=uri))

        # add 'annotated' when UEM file is provided
        # defaults to empty Timeline for the same reason as above
        if file_uem is not None:
            current_file['annotated'] = annotated.get(uri, Timeline(uri=uri))

        # add 'domain' when domain mapping is provided
        if domain_txt is not None:
            current_file['domain'] = domains[uri]

        yield current_file


def get_init(register):

    def init(self, preprocessors={}):
        super(self.__class__, self).__init__(preprocessors=preprocessors)
        for protocol in register:
            self.register_protocol(*protocol)

    return init


def add_custom_protocols(config_yml=None):
    """Update pyannote.database.{DATABASES|TASKS} with custom & meta protocols

    Parameters
    ----------
    config_yml : `str`, optional
        Path to pyannote.database configuration file in YAML format.
        Defaults to the content of PYANNOTE_DATABASE_CONFIG environment
        variable if defined and to "~/.pyannote/database.yml" otherwise.
        Path to YAML file with description of the database and its protocols.

    Returns
    -------
    pyannote.database.DATABASES
    pyannote.database.TASKS
    """

    if config_yml is None:
        config_yml = os.environ.get("PYANNOTE_DATABASE_CONFIG",
                                    "~/.pyannote/database.yml")
    config_yml = Path(config_yml).expanduser()

    try:
        with open(config_yml, 'r') as fp:
            config = yaml.load(fp, Loader=yaml.SafeLoader)

    except FileNotFoundError:
        config = dict()

    databases = config.get('Protocols', dict())

    # make sure meta-protocols are processed last (relies on the fact that
    # dicts are iterated in insertion order since Python 3.6)
    x = databases.pop('X', None)
    if x is not None:
        databases['X'] = x

    # for each database
    for database_name, tasks in databases.items():

        database_name = str(database_name)

        # this list is meant to contain one class per protocol
        register = []

        # for each type of task
        for task_name, protocols in tasks.items():

            # update TASKS dictionary
            if task_name not in TASKS:
                TASKS[task_name] = set()
            TASKS[task_name].add(database_name)

            # only speaker diarization TASKS are supported for now...
            if task_name != 'SpeakerDiarization':
                msg = (
                    'Only speaker diarization protocols are supported for now.'
                )
                raise ValueError(msg)

            # get protocol base class (here: SpeakerDiarizationProtocol)
            protocol_base_class = getattr(Protocol, f'{task_name}Protocol')

            # for each protocol
            for protocol_name, subsets in protocols.items():

                # this dictionary is meant to contain "trn_iter", "dev_iter", and "tst_iter" methods
                protocol_methods = {}

                # for each subset
                for subset, sub in SUBSET_MAPPING.items():

                    # if database.yml does not provide a file for this subset,
                    # skip it
                    if subset not in subsets:
                        continue

                    # special treatment for meta-protocols
                    if database_name == 'X':

                        protocol_methods[f'{sub}_iter'] = functools.partial(
                            meta_subset_iter, subsets[subset])

                    else:

                        paths = subsets[subset]
                        file_rttm, file_lst, file_uem, domain_txt = \
                            None, None, None, None
                        if 'annotation' in paths:
                            file_rttm = Path(paths['annotation'])
                        if 'uris' in paths:
                            file_lst = Path(paths['uris'])
                        if 'annotated' in paths:
                            file_uem = Path(paths['annotated'])
                        if 'domain' in paths:
                            domain_txt = Path(paths['domain'])

                        # define xxx_iter method
                        protocol_methods[f'{sub}_iter'] = functools.partial(
                            subset_iter, database_name, file_rttm=file_rttm,
                            file_lst=file_lst, file_uem=file_uem,
                            domain_txt=domain_txt)

                # create protocol class on-the-fly
                protocol = type(protocol_name, (protocol_base_class,),
                                protocol_methods)

                # keep track of this protocol -- database.__init__ needs to
                # register it later...
                register.append((task_name, protocol_name, protocol))

        # define Database.__init__ method

        # create database class on-the-fly
        DATABASES[database_name] = type(database_name, (Database,),
                                        {'__init__': get_init(register)})

    return DATABASES, TASKS
