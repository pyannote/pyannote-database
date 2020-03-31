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

from typing import Text
from pathlib import Path
from . import protocol as Protocol
from .database import Database
from .util import load_lst, load_uem, load_mdtm, load_rttm, load_mapping
import functools
import yaml
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

    annotations, annotateds, uris = dict(), dict(), list()

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
        annotateds = load_uem(file_uem)

    # load list of files
    if file_lst is not None:
        uris = load_lst(file_lst)

    # when file_lst is provided, use this list of uris
    if len(uris) > 0:
        pass

    # when file_uem is provided, use this list of uris
    elif len(annotateds) > 0:
        uris = sorted(annotateds)

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

        # add 'annotated' when UEM file is provided
        # defaults to empty Timeline because of
        # github.com/pyannote/pyannote-database/pull/13#discussion_r261564520)
        if file_uem is not None:
            current_file['annotated'] = annotateds.get(uri, Timeline(uri=uri))

        # add 'annotation' when RTTM file is provided
        # defaults to empty Annotation for the same reason as above
        if file_rttm is not None:
            annotation = annotations.get(uri, Annotation(uri=uri))
            # crop 'annotation' to 'annotated' extent if needed
            annotated = current_file.get('annotated')
            if annotated and not annotated.covers(annotation.get_timeline()):
                annotation = annotation.crop(annotated)
            current_file['annotation'] = annotation
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


def add_custom_protocols():
    """Update pyannote.database.{DATABASES|TASKS} with custom & meta protocols

    Returns
    -------
    pyannote.database.DATABASES
    pyannote.database.TASKS
    """

    from .config import get_database_yml

    try:
        database_yml = get_database_yml()
        with open(database_yml, 'r') as fp:
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

                protocol_name = str(protocol_name)

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
                            file_rttm = resolve_path(paths['annotation'], database_yml)
                        if 'uris' in paths:
                            file_lst = resolve_path(paths['uris'], database_yml)
                        if 'annotated' in paths:
                            file_uem = resolve_path(paths['annotated'], database_yml)
                        if 'domain' in paths:
                            domain_txt = resolve_path(paths['domain'], database_yml)

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
