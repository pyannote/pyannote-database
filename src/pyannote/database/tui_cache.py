"""Best-effort, bounded-age disk cache for browser statistics."""

import hashlib
import json
import os
import tempfile
import time
from pathlib import Path


class StatisticsCache:
    """Invalidate on YAML changes; annotation changes require refresh or expiry."""

    MAX_AGE = 24 * 60 * 60

    def __init__(self, registry, directory=None):
        self.directory = Path(
            directory
            or Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
            / "pyannote-database"
            / "statistics"
        )
        digest = hashlib.sha256(b"statistics-v4")
        for path in sorted(registry.configs):
            digest.update(str(path).encode())
            digest.update(path.read_bytes())
        self.prefix = digest.hexdigest()

    def path(self, name):
        key = hashlib.sha256(f"{self.prefix}:{name}".encode()).hexdigest()
        return self.directory / f"{key}.json"

    def get(self, name):
        try:
            path = self.path(name)
            if time.time() - path.stat().st_mtime > self.MAX_AGE:
                return None
            summaries = json.loads(path.read_text())
            for stats in summaries.values():
                for key in (
                    "speakers",
                    "conversation_durations",
                    "conversation_speakers",
                ):
                    stats[key] = {int(k): v for k, v in stats[key].items()}
            return summaries
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            return None

    def put(self, name, summaries):
        if any(
            stats.get("error") or stats.get("errors") for stats in summaries.values()
        ):
            return
        temporary = None
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                mode="w", dir=self.directory, delete=False
            ) as stream:
                temporary = Path(stream.name)
                json.dump(summaries, stream)
            temporary.replace(self.path(name))
        except OSError:
            pass
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
