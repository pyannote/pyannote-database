#!/usr/bin/env python
# encoding: utf-8

# The MIT License (MIT)

# Copyright (c) 2016-2017 CNRS

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


from .protocol import Protocol
from tqdm import tqdm
from ..util import get_annotated


class SpeakerDiarizationProtocol(Protocol):
    """Speaker diarization protocol

    Parameters
    ----------
    preprocessors : dict or (key, preprocessor) iterable
        When provided, each protocol item (dictionary) are preprocessed, such
        that item[key] = preprocessor(item). In case 'preprocessor' is not
        callable, it should be a string containing placeholder for item keys
        (e.g. {'audio': '/path/to/{uri}.wav'})
    """

    def trn_iter(self):
        raise NotImplementedError(
            'Custom speaker diarization protocol should implement "trn_iter".')

    def dev_iter(self):
        raise NotImplementedError(
            'Custom speaker diarization protocol should implement "dev_iter".')

    def tst_iter(self):
        raise NotImplementedError(
            'Custom speaker diarization protocol should implement "tst_iter".')

    def train(self):
        """Iterate over the training set

This will yield dictionaries with the followings keys:

* database: str
  unique database identifier
* uri: str
  uniform (or unique) resource identifier
* annotated: pyannote.core.Timeline
  parts of the resource that were manually annotated
* annotation: pyannote.core.Annotation
  actual annotations

as well as keys coming from the provided preprocessors.

Usage
-----
>>> for item in protocol.train():
...     uri = item['uri']
...     annotated = item['annotated']
...     annotation = item['annotation']
        """

        generator = self.trn_iter()

        if self.progress:
            generator = tqdm(
                generator, desc='Training set',
                total=getattr(self.trn_iter, 'n_items', None))

        for item in generator:
            yield self.preprocess(item)

    def development(self):
        """Iterate over the development set

This will yield dictionaries with the followings keys:

* database: str
  unique database identifier
* uri: str
  uniform (or unique) resource identifier
* annotated: pyannote.core.Timeline, optional
  parts of the resource that were manually annotated
* annotation: pyannote.core.Annotation
  actual annotations

as well as keys coming from the provided preprocessors.

Usage
-----
>>> for item in protocol.development():
...     uri = item['uri']
...     annotated = item['annotated']
...     annotation = item['annotation']
        """

        generator = self.dev_iter()
        if self.progress:
            generator = tqdm(
                generator, desc='Development set',
                total=getattr(self.dev_iter, 'n_items', None))

        for item in generator:
            yield self.preprocess(item)

    def test(self):
        """Iterate over the test set

This will yield dictionaries with the followings keys:

* database: str
  unique database identifier
* uri: str
  uniform (or unique) resource identifier
* annotated: pyannote.core.Timeline, optional
  parts of the resource that were manually annotated
* annotation: pyannote.core.Annotation
  actual annotations

as well as keys coming from the provided preprocessors.

Usage
-----
>>> for item in protocol.test():
...     uri = item['uri']
...     annotated = item['annotated']
...     annotation = item['annotation']
        """

        generator = self.tst_iter()
        if self.progress:
            generator = tqdm(
                generator, desc='Test set',
                total=getattr(self.tst_iter, 'n_items', None))

        for item in generator:
            yield self.preprocess(item)

    def stats(self, subset):
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
