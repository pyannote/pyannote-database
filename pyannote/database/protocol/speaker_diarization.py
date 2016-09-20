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

* uri: str
  uniform (or unique) resource identifier
* annotated: pyannote.core.Timeline
  parts of the resource that were manually annotated
* annotation: pyannote.core.Annotation
  actual annotations

Usage
-----
>>> for item in protocol.train():
...     uri = item['uri']
...     annotated = item['annotated']
...     annotation = item['annotation']
        """
        return self.trn_iter()

    def development(self):
        """Iterate over the development set

* uri: str
  uniform (or unique) resource identifier
* annotated: pyannote.core.Timeline
  parts of the resource that were manually annotated
* annotation: pyannote.core.Annotation
  actual annotations

Usage
-----
>>> for item in protocol.development():
...     uri = item['uri']
...     annotated = item['annotated']
...     annotation = item['annotation']
        """
        return self.dev_iter()

    def test(self):
        """Iterate over the test set

* uri: str
  uniform (or unique) resource identifier
* annotated: pyannote.core.Timeline
  parts of the resource that were manually annotated
* annotation: pyannote.core.Annotation
  actual annotations

Usage
-----
>>> for item in protocol.test():
...     uri = item['uri']
...     annotated = item['annotated']
...     annotation = item['annotation']
        """
        return self.tst_iter()
