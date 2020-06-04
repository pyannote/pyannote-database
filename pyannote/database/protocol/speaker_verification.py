#!/usr/bin/env python
# encoding: utf-8

# The MIT License (MIT)

# Copyright (c) 2017-2020 CNRS

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


from typing import Dict, Iterator
from .speaker_diarization import SpeakerDiarizationProtocol
from .protocol import Subset
from .protocol import LEGACY_SUBSET_MAPPING


class SpeakerVerificationProtocol(SpeakerDiarizationProtocol):
    """A protocol for speaker verification experiments

    TODO: write docstring following SpeakerDiarizationProtocol 
    docstring template. below is what used to be part of the 
    docstring of xxxx_trial methods.

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

    def subset_trial_helper(self, subset: Subset) -> Iterator[Dict]:

        try:
            trials = getattr(self, f"{subset}_trial_iter")()
        except (AttributeError, NotImplementedError) as e:
            # previous pyannote.database versions used `trn_try_iter` instead
            # of `train_trial_iter`, `dev_try_iter` instead of
            # `development_trial_iter`, and `tst_try_iter` instead of
            # `test_iter`. therefore, we use the legacy version when it is
            # available (and the new one is not).
            subset_legacy = LEGACY_SUBSET_MAPPING[subset]
            try:
                trials = getattr(self, f"{subset_legacy}_try_iter")()
            except AttributeError as e:
                msg = f"{subset}_trial_iter is not implemented."
                raise AttributeError(msg)

        for trial in trials:
            trial["file1"] = self.preprocess(trial["file1"])
            trial["file2"] = self.preprocess(trial["file2"])
            yield trial

    def train_trial_iter(self) -> Iterator[Dict]:
        """Iterate over trials in the train subset"""
        raise NotImplementedError()

    def development_trial_iter(self) -> Iterator[Dict]:
        """Iterate over trials in the development subset"""
        raise NotImplementedError()

    def test_trial_iter(self) -> Iterator[Dict]:
        """Iterate over trials in the test subset"""
        raise NotImplementedError()

    def train_trial(self) -> Iterator[Dict]:
        return self.subset_trial_helper("train")

    def development_trial(self) -> Iterator[Dict]:
        return self.subset_trial_helper("development")

    def test_trial(self) -> Iterator[Dict]:
        return self.subset_trial_helper("test")
