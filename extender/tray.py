"""The system-tray icon and its menu (plan step 8).

The app lives in the tray: the settings window can be opened and closed without
stopping it. The tray menu has Open settings (also a double-click on the icon),
Pause / Resume and Quit.

tkinter has to run on the main thread, while pystray runs the icon on its own thread.
So menu clicks don't touch the window directly: they put a request on a queue, which
the main thread checks every POLL_MS milliseconds.
"""

import ctypes
import logging
import queue
import sys

from PIL import Image, ImageDraw

from . import config as config_store
from .settings_window import SettingsWindow, describe_hotkey

log = logging.getLogger(__name__)

POLL_MS = 100
ACTIVE_COLOUR = (43, 108, 176)
PAUSED_COLOUR = (140, 140, 150)


def make_icon_image(paused=False, size=64):
    """A rounded square with a 'T' and three dots (text, extended). Grey when paused.
    Drawn four times bigger, then shrunk, for smooth edges."""
    big = size * 4
    image = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    colour = PAUSED_COLOUR if paused else ACTIVE_COLOUR
    draw.rounded_rectangle((8, 8, big - 8, big - 8), radius=big // 5, fill=colour)
    white = (255, 255, 255)
    # The T
    draw.rectangle((big * 0.22, big * 0.22, big * 0.62, big * 0.32), fill=white)
    draw.rectangle((big * 0.37, big * 0.22, big * 0.47, big * 0.72), fill=white)
    # The dots
    r = big * 0.05
    for i in range(3):
        cx, cy = big * (0.56 + i * 0.13), big * 0.70
        draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=white)
    return image.resize((size, size), Image.LANCZOS)


class SingleInstance:
    """Stops a second copy of the app from running at the same time (both would expand
    every shortcut, typing the message twice). Uses a named Windows mutex."""

    ERROR_ALREADY_EXISTS = 183

    def __init__(self, name="Local\\TextExtender"):
        self.handle = None
        if sys.platform != "win32":
            self.acquired = True
            return
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateMutexW.restype = ctypes.c_void_p
        self.handle = kernel32.CreateMutexW(None, False, name)
        self.acquired = bool(self.handle) and ctypes.get_last_error() != self.ERROR_ALREADY_EXISTS

    def release(self):
        if self.handle:
            ctypes.WinDLL("kernel32").CloseHandle(ctypes.c_void_p(self.handle))
            self.handle = None


class OpenSettingsSignal:
    """Lets a second launch of the app ask the copy already running to open its
    settings window. Uses a named Windows event."""

    WAIT_OBJECT_0 = 0

    def __init__(self, name="Local\\TextExtender-OpenSettings"):
        self.name = name
        self.handle = None
        if sys.platform == "win32":
            self.kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            self.kernel32.CreateEventW.restype = ctypes.c_void_p
            self.kernel32.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
            self.kernel32.SetEvent.argtypes = [ctypes.c_void_p]
            self.kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
            # Auto-reset: each signal is seen once.
            self.handle = self.kernel32.CreateEventW(None, False, False, name)

    def send(self):
        """Ask the running copy to open settings. Returns whether that worked."""
        return bool(self.handle) and bool(self.kernel32.SetEvent(self.handle))

    def received(self):
        """Whether a request arrived since the last check (doesn't wait)."""
        return bool(self.handle) and self.kernel32.WaitForSingleObject(self.handle, 0) == self.WAIT_OBJECT_0

    def close(self):
        if self.handle:
            self.kernel32.CloseHandle(self.handle)
            self.handle = None


class TrayApp:
    """Runs the tray icon, opens the settings window on request, and applies changes
    to the running listener (`extender`)."""

    def __init__(self, root, extender, config_path=None, icon_factory=None, on_quit=None,
                 open_signal=None):
        """root is a hidden tkinter window that settings windows are opened from.
        icon_factory(name, image, title, menu) makes the tray icon (pystray.Icon unless
        replaced in tests). on_quit ends the program (stops tkinter's loop).
        open_signal, if given, is checked for "open settings" requests from a second
        launch of the app."""
        self.root = root
        self.extender = extender
        self.config_path = config_path
        self.on_quit = on_quit or root.quit
        self.open_signal = open_signal
        self.requests = queue.Queue()
        self.settings_window = None
        self._paused_before_capture = False
        self._quitting = False
        self.icon = (icon_factory or self._pystray_icon)(
            "TextExtender", make_icon_image(), self.tooltip(), self._menu())

    # The icon

    @staticmethod
    def _pystray_icon(name, image, title, menu):
        import pystray
        return pystray.Icon(name, image, title, menu)

    def _menu(self):
        import pystray
        item = pystray.MenuItem
        return pystray.Menu(
            item("Open settings", lambda icon, it: self.request("open"), default=True),
            item(lambda it: "Resume" if self.extender.paused else "Pause",
                 lambda icon, it: self.request("toggle_pause")),
            pystray.Menu.SEPARATOR,
            item("Quit", lambda icon, it: self.request("quit")),
        )

    def tooltip(self):
        state = "paused" if self.extender.paused else describe_hotkey(self.extender.config.hotkey)
        return f"Text Extender ({state})"

    def refresh_icon(self):
        self.icon.icon = make_icon_image(paused=self.extender.paused)
        self.icon.title = self.tooltip()
        self.icon.update_menu()

    def notify(self, message):
        try:
            self.icon.notify(message, "Text Extender")
        except Exception:
            pass  # notifications are a nicety; never let them stop the app

    # Requests from the tray menu (any thread) -> handled on the main thread

    def request(self, name):
        self.requests.put(name)

    def handle_requests(self):
        """Run waiting requests. Called regularly on the main thread. A request that
        fails is logged and skipped, so it can't stop the ones after it."""
        actions = {"open": self.open_settings, "toggle_pause": self.toggle_pause, "quit": self.quit}
        while True:
            try:
                name = self.requests.get_nowait()
            except queue.Empty:
                return
            try:
                actions[name]()
            except Exception:
                log.exception("Tray request %r failed", name)

    def _poll(self):
        # Always check again later, even if handling went wrong; otherwise one error
        # would leave every later tray click waiting forever.
        try:
            if self.open_signal is not None and self.open_signal.received():
                self.request("open")  # the app was started again
            self.handle_requests()
        finally:
            if not self._quitting:
                self.root.after(POLL_MS, self._poll)

    # Actions

    def open_settings(self):
        import tkinter as tk
        if self.settings_window is not None and not self.settings_window.master.winfo_exists():
            self.settings_window = None  # destroyed some other way; open a fresh one
        if self.settings_window is not None:
            top = self.settings_window.master
            top.deiconify()
            top.lift()
            top.focus_force()
            return
        top = tk.Toplevel(self.root)
        self.settings_window = SettingsWindow(
            top, self.extender.config, on_change=self.apply_settings,
            on_capture_start=self._capture_started, on_capture_end=self._capture_ended,
            # Queued like the tray's Quit, so the window isn't destroyed from inside
            # its own button's click handler.
            on_quit=lambda: self.request("quit"))
        top.protocol("WM_DELETE_WINDOW", self.close_settings)
        top.lift()
        top.focus_force()

    def close_settings(self):
        """Closing the window just hides it from view; the app keeps running in the tray."""
        if self.settings_window is not None:
            window, self.settings_window = self.settings_window, None
            if window.capturing:
                window.stop_hotkey_capture()
            window.master.destroy()

    def apply_settings(self, new_config):
        config_store.save(new_config, self.config_path)
        self.extender.set_config(new_config)
        self.refresh_icon()  # the tooltip shows the hotkey

    def _capture_started(self):
        # Recording a hotkey pauses the listener; afterwards, only resume it if it
        # wasn't already paused from the tray.
        self._paused_before_capture = self.extender.paused
        self.extender.pause()

    def _capture_ended(self):
        if not self._paused_before_capture:
            self.extender.resume()

    def toggle_pause(self):
        if self.extender.paused:
            self.extender.resume()
        else:
            self.extender.pause()
        self.refresh_icon()

    def quit(self):
        """Stop everything. Each part is stopped even if an earlier one fails, so Quit
        always ends the app."""
        self._quitting = True
        for step in (self.close_settings, self.extender.stop, self.icon.stop):
            try:
                step()
            except Exception:
                log.exception("Problem while quitting")
        self.on_quit()

    # Running

    def run(self, show_settings=True):
        """Show the icon and run until Quit. Blocks; call from the main thread.
        With show_settings the settings window opens straight away; otherwise a
        notification says the app is running in the tray."""
        self.icon.run_detached()
        if show_settings:
            self.open_settings()
        else:
            self.notify(f"Running in the tray. Type a shortcut, then press "
                        f"{describe_hotkey(self.extender.config.hotkey)}.")
        # Start checking for requests once the loop is running: a Quit handled before
        # mainloop() starts would be lost, because starting the loop resets its quit flag.
        self.root.after(0, self._poll)
        self.root.mainloop()
