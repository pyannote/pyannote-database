from pathlib import Path
from typing import Text
from pyannote.database.protocol.protocol import ProtocolFile
from .registry import registry as global_registry
from .registry import Registry


class FileFinder:
    """Database file finder. Retrieve content files from URIs.

    Parameters
    ----------
    registry : str, optional
        Registry to use to get where to find the database files.
        If not set, defaults to pyannote.database's global registry.

    Configuration file
    ------------------
    Here are a few examples of what is expected in the configuration file.

    # support for multiple databases
    database1: /path/to/database1/{uri}.wav
    database2: /path/to/database2/{uri}.wav

    # files are spread over multiple directory
    database3:
      - /path/to/database3/1/{uri}.wav
      - /path/to/database3/2/{uri}.wav

    # supports * (and **) globbing
    database4: /path/to/database4/*/{uri}.wav

    See also
    --------
    pathlib.Path.glob
    """

    def __init__(self, registry: Registry = None):
        super().__init__()
        self.registry = registry if registry is not None else global_registry

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

        # read
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
            msg = f'Could not find file "{uri}" in the following location(s):'
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
