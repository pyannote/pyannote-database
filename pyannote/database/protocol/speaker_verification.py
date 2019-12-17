#!/usr/bin/env python
# encoding: utf-8

# The MIT License (MIT)

# Copyright (c) 2017-2019 CNRS

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

from typing import Dict, Any
from typing_extensions import TypedDict
from ..protocol import ProtocolFile

Trial = TypedDict(
    'Trial', {'reference': bool,
              'file1': Dict[str, Any],
              'file2': Dict[str, Any]})

ProtocolTrial = TypedDict(
    'ProtocolTrial', {'reference': bool,
                      'file1': ProtocolFile,
                      'file2': ProtocolFile})


from tqdm import tqdm
from typing import Iterator
from typing import Progress
from ..types import Trial
from ..types import ProtocolTrial


from .speaker_diarization import SpeakerDiarizationProtocol

class SpeakerVerificationProtocol(SpeakerDiarizationProtocol):
    """Speaker verification protocol

    Parameters
    ----------
    preprocessors : dict
        When provided, each protocol file (dictionary) are preprocessed, such
        that file[key] = preprocessor(file). In case 'preprocessor' is not
        callable, it should be a string containing placeholder for file keys
        (e.g. {'audio': '/path/to/{uri}.wav'})
    """

    def trn_try_iter(self) -> Iterator[Trial]:
        for trial in []:
            yield trial

    def train_trial(self, progress: Optional[Progress] = None) -> Iterator[ProtocolTrial]:
        """Iterate over the trials of the train set

        Each trial is yielded as a dictionary with the following keys:

        ['reference'] (`boolean`)
            Groundtruth: True for a target trial, False for a non-target trial.

        ['file{1|2}'] (`dict`)
            Both parts of the trial are provided as dictionaries with the
            following keys (as well as keys added by preprocessors):

            ['uri'] (`str`)
                Unique file identifier.

            ['try_with'] (`pyannote.core.{Segment|Timeline}`), optional
                Part(s) of the file to use in the trial. Default is to use the
                whole file.
        """

        generator = self.trn_try_iter()

        if progress is not None:
            if 'total' not in progress:
                progress['total'] = getattr(self.trn_try_iter, 'n_items', None)
            generator = tqdm(generator, **progress)

        for current_trial in generator:
            current_trial['file1'] = self.preprocess(current_trial['file1'])
            current_trial['file2'] = self.preprocess(current_trial['file2'])
            yield current_trial

    def dev_try_iter(self) -> Iterator[Trial]:
        for trial in []:
            yield trial

    def development_trial(self, progress: Optional[Progress] = None) -> Iterator[ProtocolTrial]:
        """Iterate over the trials of the development set

        Each trial is yielded as a dictionary with the following keys:

        [`reference`] (`boolean`)
            Groundtruth: True for a target trial, False for a non-target trial.

        [`file{1|2}`] (`dict`)
            Both parts of the trial are provided as dictionaries with the
            following keys (as well as keys added by preprocessors):

            [`uri`] (`str`)
                Unique file identifier.

            [`try_with`] (`pyannote.core.{Segment|Timeline}`), optional
                Part(s) of the file to use in the trial. Default is to use the
                whole file.

        """

        generator = self.dev_try_iter()

        if progress is not None:
            if 'total' not in progress:
                progress['total'] = getattr(self.dev_try_iter, 'n_items', None)
            generator = tqdm(generator, **progress)

        for current_trial in generator:
            current_trial['file1'] = self.preprocess(current_trial['file1'])
            current_trial['file2'] = self.preprocess(current_trial['file2'])
            yield current_trial

    def tst_try_iter(self) -> Iterator[Trial]:
        for trial in []:
            yield trial

    def test_trial(self, progress: Optional[Progress] = None) -> Iterator[ProtocolTrial]:
        """Iterate over the trials of the test set

        Each trial is yielded as a dictionary with the following keys:

        [`reference`] (`boolean`)
            Groundtruth: True for a target trial, False for a non-target trial.

        [`file{1|2}`] (`dict`)
            Both parts of the trial are provided as dictionaries with the
            following keys (as well as keys added by preprocessors):

            [`uri`] (`str`)
                Unique file identifier.

            [`try_with`] (`pyannote.core.{Segment|Timeline}`), optional
                Part(s) of the file to use in the trial. Default is to use the
                whole file.

        """

        generator = self.tst_try_iter()

        if progress is not None:
            if 'total' not in progress:
                progress['total'] = getattr(self.tst_try_iter, 'n_items', None)
            generator = tqdm(generator, **progress)

        for current_trial in generator:
            current_trial['file1'] = self.preprocess(current_trial['file1'])
            current_trial['file2'] = self.preprocess(current_trial['file2'])
            yield current_trial
