"""Start the text extender.

For now it runs in this terminal (the tray icon and settings window come in plan
steps 7 and 8). Snippets and settings are edited in the config file it prints.
Press Ctrl+C here to quit.
"""

import sys

from extender import config
from extender.listener import TextExtender

EXAMPLE_SNIPPETS = {";te": "Text Extender is working!"}


def describe_hotkey(hotkey):
    """'<ctrl>+<space>' -> 'Ctrl+Space'."""
    return "+".join(part.strip("<>").capitalize() for part in hotkey.split("+"))


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

    print("Text Extender is running.")
    print(f"  Hotkey: {describe_hotkey(settings.hotkey)}")
    delay = "instant (paste)" if settings.char_delay_ms == 0 else f"{settings.char_delay_ms} ms per character"
    print(f"  Typing speed: {delay}")
    print(f"  Snippets ({len(settings.snippets)}): {', '.join(settings.snippets) or 'none yet'}")
    print(f"  Settings file: {path}")
    print("Type a shortcut, then press the hotkey. Press Ctrl+C here to quit.")
    try:
        while app.is_running():
            app.join(timeout=0.5)  # short waits, so Ctrl+C is noticed
    except KeyboardInterrupt:
        pass
    finally:
        app.stop()
    print("Stopped.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
