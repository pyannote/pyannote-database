#!/usr/bin/env python
# encoding: utf-8

# The MIT License (MIT)

# Copyright (c) 2018-2019 CNRS

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


from typing import Iterator
from typing import Dict
from typing import Any
from typing import Optional
from tqdm import tqdm
from .protocol import Protocol
from .protocol import ProtocolFile


class CollectionProtocol(Protocol):
    """Collection

    Parameters
    ----------
    preprocessors : dict
        When provided, each protocol file (dictionary) are preprocessed, such
        that file[key] = preprocessor(file). In case 'preprocessor' is not
        callable, it should be a string containing placeholder for file keys
        (e.g. {'audio': '/path/to/{uri}.wav'})
    """

    def files_iter(self) -> Iterator[Dict[str, Any]]:
        raise NotImplementedError(
            'Custom collection protocol should implement "files_iter".')

    def files(self, progress: Optional[Dict[str, Any]] = None) -> Iterator[ProtocolFile]:
        """Iterate over the collection

        Parameters
        ----------
        progress : dict, optional
            When provided, displays a tqdm progress bar with these parameters

        Yields
        ------
        file : ProtocolFile
        """
        
        generator = self.files_iter()

        if progress is not None:
            if 'total' not in progress:
                progress['total'] = getattr(self.files_iter, 'n_items', None)
            generator = tqdm(generator, **progress)

        for file in generator:
            yield self.preprocess(file)

    def stats(self) -> dict:
        """Collection statistics

        Returns
        -------
        stats : dict
            ['n_files'] (`int`) number of files in collection
        """

        n_files = 0
        for current_file in self.files():
            n_files += 1

        return {'n_files': n_files}
