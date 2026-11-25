"""Exercise real terminal input, which Textual's headless pilot bypasses."""

import os
import select
import subprocess
import sys
import time

import pytest

pytest.importorskip("textual")
pytest.importorskip("termios")

import pty

from typer.testing import CliRunner

from pyannote.database.cli import app
from pyannote.database.tui import DatabaseBrowser


@pytest.mark.parametrize("option, expected", [([], True), (["--no-mouse"], False)])
def test_browse_mouse_option(tmp_path, monkeypatch, option, expected):
    path = tmp_path / "database.yml"
    path.write_text("Protocols: {}\n")
    calls = []
    monkeypatch.setattr(
        DatabaseBrowser, "run", lambda self, **kwargs: calls.append(kwargs)
    )
    result = CliRunner().invoke(app, ["browse", *option, str(path)])
    assert result.exit_code == 0, result.output
    assert calls == [{"mouse": expected}]


def test_binary_mouse_report_does_not_crash_terminal_input(tmp_path):
    path = tmp_path / "database.yml"
    path.write_text("Protocols: {}\n")
    master, slave = pty.openpty()
    process = subprocess.Popen(
        [
            sys.executable,
            "-c",
            "from pyannote.database.cli import app; app()",
            "browse",
            str(path),
        ],
        stdin=slave,
        stdout=slave,
        stderr=slave,
    )
    os.close(slave)
    output = bytearray()

    def wait_for(predicate, timeout=8):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if select.select([master], [], [], 0.05)[0]:
                try:
                    output.extend(os.read(master, 65536))
                except OSError:
                    break
            if predicate():
                return
        assert predicate(), output[-4000:].decode("utf-8", errors="replace")

    try:
        wait_for(lambda: b"pyannote database browser" in output)
        # X10 mouse encoding: ESC [ M, button, x+32, y+32. Byte 0x80 at
        # position 4 is a valid binary coordinate but invalid standalone UTF-8.
        os.write(master, b"\x1b[M \x80!")
        wait_for(lambda: b"Terminal compatibility" in output)
        assert process.poll() is None
        # A queued legacy report must not bring the restarted decoder down either.
        os.write(master, b"\x1b[M \x81!")
        time.sleep(0.15)
        os.write(master, b"c")
        wait_for(lambda: b"Checkbox order:" in output)
        os.write(master, b"q")
        wait_for(lambda: process.poll() is not None)
        assert process.returncode == 0
        assert b"UnicodeDecodeError" not in output
    finally:
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=5)
        os.close(master)
