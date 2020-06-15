#!/usr/bin/env python
# encoding: utf-8

# The MIT License (MIT)

# Copyright (c) 2020 CNRS

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

import os
from pathlib import Path
from typing import Text
from typing import Union


def get_database_yml(database_yml: Union[Text, Path] = None) -> Path:
    """Find location of pyannote.database configuration file

    Parameter
    ---------
    database_yml : Path, optional
        Force using this file.

    Returns
    -------
    path : Path
        Path to 'database.yml'

    Raises
    ------
    FileNotFoundError when the configuration file could not be found.
    """

    # when database_yml is provided, use it
    if database_yml is not None:
        database_yml = Path(database_yml).expanduser()
        # does the provided file exist?
        if not database_yml.is_file():
            msg = f"File '{database_yml}' does not exist."
            raise FileNotFoundError(msg)

        return database_yml

    # is there a file named "database.yml" in current working directory?
    if (Path.cwd() / "database.yml").is_file():
        database_yml = Path.cwd() / "database.yml"

    # does PYANNOTE_DATABASE_CONFIG environment variable links to an existing file?
    elif os.environ.get("PYANNOTE_DATABASE_CONFIG") is not None:
        database_yml = Path(os.environ.get("PYANNOTE_DATABASE_CONFIG")).expanduser()
        if not database_yml.is_file():
            msg = (
                f'"PYANNOTE_DATABASE_CONFIG" links to a file that does not'
                f'exist: "{database_yml}".'
            )
            raise FileNotFoundError(msg)

    # does default "~/.pyannote/database.yml" file exist?
    else:
        database_yml = Path("~/.pyannote/database.yml").expanduser()

        # if it does not, let the user know that nothing worked and in which
        # locations "database.yml" was looked for.
        if not database_yml.is_file():
            msg = (
                f'"pyannote.database" relies on a YAML configuration file but '
                f"could not find any. Here are the locations that were "
                f'looked for: {Path.cwd() / "database.yml"}, {database_yml}'
            )
            if os.environ.get("PYANNOTE_DATABASE_CONFIG") is not None:
                database_yml = Path(
                    os.environ.get("PYANNOTE_DATABASE_CONFIG")
                ).expanduser()
                msg += (
                    f", and {database_yml} (given by "
                    f"PYANNOTE_DATABASE_CONFIG environment variable)."
                )
            else:
                msg += "."
            raise FileNotFoundError(msg)

    return database_yml
