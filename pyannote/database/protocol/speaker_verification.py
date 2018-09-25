#!/usr/bin/env python
# encoding: utf-8

# The MIT License (MIT)

# Copyright (c) 2017-2018 CNRS

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


from .speaker_diarization import SpeakerDiarizationProtocol


class SpeakerVerificationProtocol(SpeakerDiarizationProtocol):
    """Speaker verification protocol

    Parameters
    ----------
    preprocessors : dict or (key, preprocessor) iterable
        When provided, each protocol item (dictionary) are preprocessed, such
        that item[key] = preprocessor(item).
    """

    def trn_try_iter(self):
        for trial in []:
            yield trial

    def train_trial(self):
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

        if self.progress:
            generator = tqdm(
                generator, desc='Trial (train set)',
                total=getattr(self.trn_try_iter, 'n_items', None))

        for current_trial in generator:
            current_trial['file1'] = self.preprocess(current_trial['file1'])
            current_trial['file2'] = self.preprocess(current_trial['file2'])
            yield current_trial

    def dev_try_iter(self):
        for trial in []:
            yield trial

    def development_trial(self):
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

        if self.progress:
            generator = tqdm(
                generator, desc='Trial (development set)',
                total=getattr(self.dev_try_iter, 'n_items', None))

        for current_trial in generator:
            current_trial['file1'] = self.preprocess(current_trial['file1'])
            current_trial['file2'] = self.preprocess(current_trial['file2'])
            yield current_trial

    def tst_try_iter(self):
        for trial in []:
            yield trial

    def test_trial(self):
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

        if self.progress:
            generator = tqdm(
                generator, desc='Trial (test set)',
                total=getattr(self.tst_try_iter, 'n_items', None))

        for current_trial in generator:
            current_trial['file1'] = self.preprocess(current_trial['file1'])
            current_trial['file2'] = self.preprocess(current_trial['file2'])
            yield current_trial
