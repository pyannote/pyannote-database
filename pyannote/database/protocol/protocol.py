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

"""
#########
Protocols
#########




"""


import warnings


class Protocol(object):
    """Base protocol

    This class should be inherited from, not used directly.

    Parameters
    ----------
    preprocessors : dict
        When provided, each protocol item (dictionary) are preprocessed, such
        that item[key] = preprocessor(item). In case 'preprocessor' is not
        callable, it should be a string containing placeholder for item keys
        (e.g. {'audio': '/path/to/{uri}.wav'})
    """

    def __init__(self, preprocessors={}, progress=False, **kwargs):
        super(Protocol, self).__init__()

        self.preprocessors = dict()
        for key, preprocessor in preprocessors.items():

            if callable(preprocessor):
                self.preprocessors[key] = preprocessor

            # when `preprocessor` is not callable, it should be a string
            # containing placeholder for item key (e.g. '/path/to/{uri}.wav')
            elif isinstance(preprocessor, str):
                preprocessor_copy = str(preprocessor)
                def func(current_file):
                    return preprocessor_copy.format(**current_file)
                self.preprocessors[key] = func

            else:
                msg = f'"{key}" preprocessor is neither a callable nor a string.'
                raise ValueError(msg)

        self.progress = progress

    def preprocess(self, current_file):

        for key, preprocessor in self.preprocessors.items():

            # warn the user that preprocessors modify an existing key
            if key in current_file:
                msg = 'Key "{key}" may have been modified by preprocessors.'
                warnings.warn(msg.format(key=key))

            current_file[key] = preprocessor(current_file)

        return current_file

    def __str__(self):
        return self.__doc__
