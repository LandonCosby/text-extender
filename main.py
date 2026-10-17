"""Start the text extender.

Starting it opens the settings window. It keeps running in the system tray: closing the
window doesn't stop it, and right-clicking the icon gives Open settings, Pause / Resume
and Quit. Starting it again while it's running just opens the settings window of the
copy already running. Use `pythonw main.py` to start it without a terminal window.
"""

import ctypes
import logging
import sys
import tkinter as tk
from tkinter import messagebox

from extender import config, logs
from extender.listener import TextExtender
from extender.tray import OpenSettingsSignal, SingleInstance, TrayApp

EXAMPLE_SNIPPETS = {";te": "Text Extender is working!"}


def sharp_on_high_dpi_screens():
    """Without this, Windows stretches tkinter windows on scaled displays and they look blurry."""
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError, OSError):
        pass


def main():
    instance = SingleInstance()
    open_signal = OpenSettingsSignal()
    if not instance.acquired:
        # Already running: ask that copy to show its settings window instead.
        if not open_signal.send():
            root = tk.Tk()
            root.withdraw()
            messagebox.showinfo("Text Extender", "Text Extender is already running. Look for its icon in the system tray.")
            root.destroy()
        open_signal.close()
        instance.release()
        return 0

    path = config.default_path()
    logs.setup(path.parent)
    logging.info("Starting (settings: %s)", path)
    settings = config.load(path)
    first_run = not path.exists()
    if first_run:
        # Save an example so there's something to try straight away.
        settings.snippets = dict(EXAMPLE_SNIPPETS)
        config.save(settings, path)

    extender = TextExtender(settings)
    extender.start()

    sharp_on_high_dpi_screens()
    root = tk.Tk()
    root.withdraw()  # hidden: only the settings window (opened from the tray) is shown
    logs.log_tkinter_errors(root)

    def keep_ctrl_c_working():
        # tkinter only lets Python notice Ctrl+C between events, so wake it regularly.
        root.after(250, keep_ctrl_c_working)

    keep_ctrl_c_working()
    tray = TrayApp(root, extender, config_path=path, open_signal=open_signal)
    try:
        tray.run(show_settings=True)
    except KeyboardInterrupt:
        tray.quit()
    finally:
        extender.stop()
        root.destroy()
        open_signal.close()
        instance.release()
        logging.info("Stopped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
