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


from .protocol import Protocol


class SpeakerDiarizationProtocol(Protocol):

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

* uri: str
  uniform (or unique) resource identifier
* annotated: pyannote.core.Timeline
  parts of the resource that were manually annotated
* annotation: pyannote.core.Annotation
  actual annotations
* medium: dict
  dictionary of path to medium file (e.g. {'wav': '/path/to/file.wav'})

Usage
-----
>>> for item in protocol.train():
...     uri = item['uri']
...     annotated = item['annotated']
...     annotation = item['annotation']
        """
        for item in self.trn_iter():
            if 'medium' not in item:
                item['medium'] = {}
            for medium, template in self.medium_template.items():
                item['medium'][medium] = template.format(**item)
            yield item

    def development(self):
        """Iterate over the development set

This will yield dictionaries with the followings keys:

* uri: str
  uniform (or unique) resource identifier
* annotated: pyannote.core.Timeline
  parts of the resource that were manually annotated
* annotation: pyannote.core.Annotation
  actual annotations
* medium: dict
  dictionary of path to medium file (e.g. {'wav': '/path/to/file.wav'})

Usage
-----
>>> for item in protocol.development():
...     uri = item['uri']
...     annotated = item['annotated']
...     annotation = item['annotation']
        """
        for item in self.dev_iter():
            if 'medium' not in item:
                item['medium'] = {}
            for medium, template in self.medium_template.items():
                item['medium'][medium] = template.format(**item)
            yield item

    def test(self):
        """Iterate over the test set

This will yield dictionaries with the followings keys:

* uri: str
  uniform (or unique) resource identifier
* annotated: pyannote.core.Timeline
  parts of the resource that were manually annotated
* annotation: pyannote.core.Annotation
  actual annotations
* medium: dict
  dictionary of path to medium file (e.g. {'wav': '/path/to/file.wav'})

Usage
-----
>>> for item in protocol.test():
...     uri = item['uri']
...     annotated = item['annotated']
...     annotation = item['annotation']
        """
        for item in self.tst_iter():
            if 'medium' not in item:
                item['medium'] = {}
            for medium, template in self.medium_template.items():
                item['medium'][medium] = template.format(**item)
            yield item

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
    * speakers: dict
      maps speakers with their total speech duration (in seconds)
        """

        annotated = 0.
        annotation = 0.
        n_files = 0
        speakers = {}

        for item in getattr(self, subset)():
            annotated += item['annotated'].duration()
            annotation += item['annotation'].get_timeline().duration()
            for speaker, duration in item['annotation'].chart():
                if speaker not in speakers:
                    speakers[speaker] = 0.
                speakers[speaker] += duration
            n_files += 1

        return {'annotated': annotated,
                'annotation': annotation,
                'n_files': n_files,
                'speakers': speakers}
