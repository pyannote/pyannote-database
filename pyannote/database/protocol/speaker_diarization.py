#!/usr/bin/env python
# encoding: utf-8

# The MIT License (MIT)

# Copyright (c) 2016-2019 CNRS

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

from tqdm import tqdm

from typing import Iterator
from typing import Optional
from typing import Dict
from typing import Any
from ..types import Subset
from ..types import Progress
from .protocol import Protocol
from .protocol import ProtocolFile
from ..util import get_annotated


class SpeakerDiarizationProtocol(Protocol):
    """Speaker diarization protocol

    Parameters
    ----------
    preprocessors : dict
        When provided, each protocol file (dictionary) are preprocessed, such
        that file[key] = preprocessor(file). In case 'preprocessor' is not
        callable, it should be a string containing placeholder for file keys
        (e.g. {'audio': '/path/to/{uri}.wav'})
    """

    def trn_iter(self) -> Iterator[Dict[str, Any]]:
        raise NotImplementedError(
            'Custom speaker diarization protocol should implement "trn_iter".')

    def dev_iter(self) -> Iterator[Dict[str, Any]]:
        raise NotImplementedError(
            'Custom speaker diarization protocol should implement "dev_iter".')

    def tst_iter(self) -> Iterator[Dict[str, Any]]:
        raise NotImplementedError(
            'Custom speaker diarization protocol should implement "tst_iter".')

    def train(self, progress: Optional[Progress] = None) -> Iterator[ProtocolFile]:
        """Iterate over the training set

        Parameters
        ----------
        progress : dict, optional
            When provided, displays a tqdm progress bar with these parameters

        Yields
        ------
        file : ProtocolFile
        """

        generator = self.trn_iter()

        if progress is not None:
            if 'total' not in progress:
                progress['total'] = getattr(self.trn_iter, 'n_items', None)
            generator = tqdm(generator, **progress)

        for file in generator:
            yield self.preprocess(file)

    def development(self, progress: Optional[Progress] = None) -> Iterator[ProtocolFile]:
        """Iterate over the development set

        Parameters
        ----------
        progress : dict, optional
            When provided, displays a tqdm progress bar with these parameters

        Yields
        ------
        file : ProtocolFile
        """

        generator = self.dev_iter()

        if progress is not None:
            if 'total' not in progress:
                progress['total'] = getattr(self.dev_iter, 'n_items', None)
            generator = tqdm(generator, **progress)

        for file in generator:
            yield self.preprocess(file)

    def test(self, progress: Optional[Progress] = None) -> Iterator[ProtocolFile]:
        """Iterate over the test set

        Parameters
        ----------
        progress : dict, optional
            When provided, displays a tqdm progress bar with these parameters

        Yields
        ------
        file : ProtocolFile
        """

        generator = self.tst_iter()

        if progress is not None:
            if 'total' not in progress:
                progress['total'] = getattr(self.tst_iter, 'n_items', None)
            generator = tqdm(generator, **progress)

        for file in generator:
            yield self.preprocess(file)

    def stats(self, subset: Subset) -> dict:
        """Obtain global statistics on a given subset

        Parameters
        ----------
        subset : {'train', 'development', 'test'}

        Returns
        -------
        stats : dict
            Dictionary with the followings keys:
            * annotated: float
              total duration (in seconds) of the parts that were manually annotated
            * annotation: float
              total duration (in seconds) of actual (speech) annotations
            * n_files: int
              number of files in the subset
            * labels: dict
              maps speakers with their total speech duration (in seconds)
        """

        annotated_duration = 0.
        annotation_duration = 0.
        n_files = 0
        labels = {}

        lower_bound = False

        for item in getattr(self, subset)():

            annotated = get_annotated(item)
            annotated_duration += annotated.duration()

            # increment 'annotation' total duration
            annotation = item['annotation']
            annotation_duration += annotation.get_timeline().duration()

            for label, duration in annotation.chart():
                if label not in labels:
                    labels[label] = 0.
                labels[label] += duration
            n_files += 1

        stats = {'annotated': annotated_duration,
                 'annotation': annotation_duration,
                 'n_files': n_files,
                 'labels': labels}

        return stats
