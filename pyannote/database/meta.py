#!/usr/bin/env python
# encoding: utf-8

# The MIT License (MIT)

# Copyright (c) 2017 CNRS

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


import yaml
import os.path
import itertools
from pyannote.database import Database
from pyannote.database import get_protocol
from pyannote.database.protocol import SpeakerDiarizationProtocol


ITER = {'train': 'trn_iter',
        'development': 'dev_iter',
        'test': 'tst_iter'}


def get_subset_iter(subset_config):

    def subset_iter(self):
        # loop on every protocol part of the meta-protocol
        for protocol_name, details in subset_config.items():
            protocol = get_protocol(protocol_name)
            # loop on requested subsets of current protocol
            for subset in details['subset']:
                subset_iter = getattr(protocol, ITER[subset])
                # loop on all files of current subset
                for current_file in subset_iter():
                    yield current_file

    # now that the method has been built, return it
    # it will become one of protocol.{trn, dev, tst}_iter methods

    return subset_iter


class X(Database):
    """Database used to define meta-protocols"""

    def __init__(self, preprocessors={}, **kwargs):
        """Parse ~/.pyannote/meta.yml and register corresponding protocols

Here is a valid ~/.pyannote.meta.yml
---
MyMetaProtocol:
  task: SpeakerDiarization
  subset:
    train:
      Etape.SpeakerDiarization.TV:
        subset: [train]
      REPERE.SpeakerDiarization.Phase1:
        subset: [train, development]
      REPERE.SpeakerDiarization.Phase2:
        subset: [train, development]
    development:
      Etape.SpeakerDiarization.TV:
        subset: [development]
    test:
      Etape.SpeakerDiarization.TV:
        subset: [test]
---
        """

        super(X, self).__init__(preprocessors=preprocessors,
                                           **kwargs)

        meta_yml = os.path.expanduser('~/.pyannote/meta.yml')
        try:
            with open(meta_yml, 'r') as fp:
                meta = yaml.load(fp)
        except FileNotFoundError as e:
            return

        # loop on meta-protocols
        for protocol_name, protocol_config in meta.items():
            # in the above example, protocol_name is 'MyMetaProtocol'
            # and protocol_config is what's come next

            # in the above example, task_name is 'SpeakerDiarization'
            # FIXME this is the only supported task, for now...
            task_name = protocol_config['task']
            if task_name != 'SpeakerDiarization':
                raise NotImplementedError('')

            # define (empty) speaker diarization protocol
            class MetaProtocol(SpeakerDiarizationProtocol):
                pass

            # loop on meta-protocol subsets. in the above example, those would
            # be train, development, and test
            for subset, subset_config in protocol_config['subset'].items():
                # define {trn, dev, tst}_iter methods
                setattr(MetaProtocol, ITER[subset],
                        get_subset_iter(subset_config))

            # register the current meta-protocol
            self.register_protocol(task_name, protocol_name, MetaProtocol)
