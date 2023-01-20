#!/usr/bin/env python
# encoding: utf-8

# The MIT License (MIT)

# Copyright (c) 2016- CNRS

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
# Alexis PLAQUET

import warnings
from pathlib import Path
from typing import Text
from pyannote.database.protocol.protocol import ProtocolFile
from .registry import registry as global_registry
from .registry import Registry


class FileFinder:
    """Database file finder. 
    
    Retrieve media files by URI.

    Parameters
    ----------
    registry : Registry, optional
        Database registry. Defaults to `pyannote.database.registry`.
    """

    def __init__(
        self, 
        registry: Registry = None,
        database_yml: Text = None):
        super().__init__()
        if registry is None:
            if database_yml is None:
                registry = global_registry
            else:
                warnings.warn("Passing `database.yml` to `FileFinder` is deprecated in favor of `registry`.")
                registry = Registry()
                registry.load_database(database_yml)
        self.registry = registry

    def __call__(self, current_file: ProtocolFile) -> Path:
        """Look for current file

        Parameter
        ---------
        current_file : ProtocolFile
            Protocol file.

        Returns
        -------
        path : Path
            Path to file.

        Raises
        ------
        FileNotFoundError when the file could not be found or when more than one
        matching file were found.
        """

        uri = current_file["uri"]
        database = current_file["database"]

        path_templates = self.registry.sources[database]
        if isinstance(path_templates, Text):
            path_templates = [path_templates]

        searched = []
        found = []

        for path_template in path_templates:
            path = Path(path_template.format(uri=uri, database=database))
            searched.append(path)

            # paths with "*" or "**" patterns are split into two parts,
            # - the root part (from the root up to the first occurrence of *)
            # - the pattern part (from the first occurrence of * to the end)
            #   which is looked for (inside root) using Path.glob
            # Example with path = '/path/to/**/*/file.wav'
            #   root = '/path/to'
            #   pattern = '**/*/file.wav'

            if "*" in str(path):
                parts = path.parent.parts
                for p, part in enumerate(parts):
                    if "*" in part:
                        break

                root = path.parents[len(parts) - p]
                pattern = str(path.relative_to(root))
                found_ = root.glob(pattern)
                found.extend(found_)

            # a path without "*" patterns is supposed to be an actual file
            elif path.is_file():
                found.append(path)

        if len(found) == 1:
            return found[0]

        if len(found) == 0:
            msg = f'Could not find file "{uri}" in any of the following location(s):'
            for path in searched:
                msg += f"\n - {path}"
            raise FileNotFoundError(msg)

        if len(found) > 1:
            msg = (
                f'Looked for file "{uri}" and found more than one '
                f"({len(found)}) matching locations: "
            )
            for path in found:
                msg += f"\n - {path}"
            raise FileNotFoundError(msg)
