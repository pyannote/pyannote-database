"""Keep keyboard navigation alive when a terminal sends non-UTF-8 input."""

from textual.drivers.linux_driver import LinuxDriver


class CompatibleLinuxDriver(LinuxDriver):
    """Recover from legacy binary mouse packets in Textual's UTF-8 input reader.

    Some terminals send X10 mouse coordinates as raw bytes even after SGR mouse
    reporting is requested. Textual's reader cannot decode coordinates >= 128.
    Restart its input parser and disable mouse reporting, preserving normal UTF-8
    decoding and all keyboard controls. This also handles already-queued packets.
    The superclass still reports exceptions unrelated to input decoding normally.
    """

    def run_input_thread(self) -> None:
        notified = False
        while not self.exit_event.is_set():
            try:
                return super().run_input_thread()
            except UnicodeDecodeError:
                if self.exit_event.is_set():
                    return
                if self._mouse:
                    self._disable_mouse_support()
                    self.flush()
                    self._mouse = False
                if not notified:
                    notified = True
                    self._app.call_later(
                        self._app.notify,
                        "Your terminal sent non-UTF-8 input. Mouse reporting is disabled; "
                        "use arrows, Tab, Space, and 1/2/3. You can also start with --no-mouse.",
                        title="Terminal compatibility",
                        severity="warning",
                        timeout=15,
                    )
