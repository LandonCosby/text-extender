"""Start the text extender.

Opens the settings window, with the keyboard listener running in the background.
Closing the window quits (the tray icon in plan step 8 will keep it running instead).
"""

import ctypes
import sys
import tkinter as tk

from extender import config
from extender.listener import TextExtender
from extender.settings_window import SettingsWindow, describe_hotkey

EXAMPLE_SNIPPETS = {";te": "Text Extender is working!"}


def sharp_on_high_dpi_screens():
    """Without this, Windows stretches tkinter windows on scaled displays and they look blurry."""
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError, OSError):
        pass


def main():
    path = config.default_path()
    settings = config.load(path)
    if not path.exists():
        # First run: save an example so there's something to try straight away.
        settings.snippets = dict(EXAMPLE_SNIPPETS)
        config.save(settings, path)

    app = TextExtender(settings)
    app.on_no_match = lambda: print("  (hotkey pressed, but no shortcut was just typed)")
    app.start()
    print(f"Text Extender is running. Hotkey: {describe_hotkey(settings.hotkey)}. "
          f"Settings file: {path}")
    print("Close the settings window (or press Ctrl+C here) to quit.")

    def apply(new_settings):
        config.save(new_settings, path)
        app.set_config(new_settings)

    sharp_on_high_dpi_screens()
    root = tk.Tk()
    SettingsWindow(root, settings, on_change=apply, on_capture_start=app.pause, on_capture_end=app.resume)

    def keep_ctrl_c_working():
        # tkinter only lets Python notice Ctrl+C between events, so wake it regularly.
        root.after(250, keep_ctrl_c_working)

    keep_ctrl_c_working()
    try:
        root.mainloop()
    except KeyboardInterrupt:
        root.destroy()
    finally:
        app.stop()
    print("Stopped.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
