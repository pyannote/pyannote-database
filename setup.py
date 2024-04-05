#!/usr/bin/env python
# encoding: utf-8

# The MIT License (MIT)

# Copyright (c) 2016-2020 CNRS

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

import versioneer
from setuptools import setup, find_packages

setup(
    # package
    namespace_packages=["pyannote"],
    packages=find_packages(),
    install_requires=[
        "pyannote.core >= 4.1",
        "pyYAML >= 3.12",
        "pandas >= 0.19",
        "typer >= 0.12.1",
        "typing_extensions >= 3.7.4;python_version < '3.8'",
    ],
    entry_points={
        "console_scripts": [
            "pyannote-database=pyannote.database.cli:main",
        ],
        "pyannote.database.loader": [
            ".rttm = pyannote.database.loader:RTTMLoader",
            ".uem = pyannote.database.loader:UEMLoader",
            ".ctm = pyannote.database.loader:CTMLoader",
            ".map = pyannote.database.loader:MAPLoader",
            ".lab = pyannote.database.loader:LABLoader",
            ".stm = pyannote.database.loader:STMLoader",
        ],
    },
    # versioneer
    version=versioneer.get_version(),
    cmdclass=versioneer.get_cmdclass(),
    # PyPI
    name="pyannote.database",
    description=("Interface to multimedia databases and experimental protocols"),
    author="Hervé Bredin",
    author_email="bredin@limsi.fr",
    url="http://pyannote.github.io/",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: MIT License",
        "Natural Language :: English",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Scientific/Engineering",
    ],
    extras_require={
        "testing": ["pytest", "flake8==3.7.9"],
        "doc": [
            "matplotlib >= 2.0.0",
            "Sphinx == 2.2.2",
            "ipython == 7.16.3",
            "sphinx_rtd_theme == 0.4.3",
        ],
    },
)
