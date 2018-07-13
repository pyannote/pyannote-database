#!/usr/bin/env python
# encoding: utf-8

# The MIT License (MIT)

# Copyright (c) 2018 CNRS

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


class CollectionProtocol(Protocol):
    """Collection

    Parameters
    ----------
    preprocessors : dict or (key, preprocessor) iterable
        When provided, each protocol item (dictionary) are preprocessed, such
        that item[key] = preprocessor(item). In case 'preprocessor' is not
        callable, it should be a string containing placeholder for item keys
        (e.g. {'audio': '/path/to/{uri}.wav'})
    progress : boolean, optional
        Show iteration progress. Defaults to False.

    Usage
    -----
    >>> collection = get_protocol('YOUR_PROTOCOL_GOES_HERE')
    >>> for current_file in collection.files():
    ...    # do something with current_file
    ...    pass

    """

    def files_iter(self):
        raise NotImplementedError(
            'Custom collection protocol should implement "files_iter".')

    def files(self):
        """Iterate over the collection

        Yields
        ------
        current_file : dict
            ['database'] (`str`) unique database identifier
            ['uri'] (`str`) unique resource identifier
        """

        generator = self.files_iter()

        if self.progress:
            generator = tqdm(
                generator, desc='Files',
                total=getattr(self.trn_iter, 'n_items', None))

        for item in generator:
            yield self.preprocess(item)

    def stats(self):
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
