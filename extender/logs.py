"""Writing errors to a log file.

Started with pythonw there's no terminal, so errors would otherwise vanish. Everything
goes to textextender.log next to the settings file: errors from any thread, from
tkinter's event handlers, and from pystray. Snippet text is never logged.
"""

import logging
import sys
import threading
import traceback
from logging.handlers import RotatingFileHandler

LOG_NAME = "textextender.log"
MAX_BYTES = 200_000  # then it starts a new file, keeping one old one


def setup(folder):
    """Send log messages and uncaught errors to folder/textextender.log. Returns its path."""
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / LOG_NAME
    handler = RotatingFileHandler(path, maxBytes=MAX_BYTES, backupCount=1, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root = logging.getLogger()
    root.addHandler(handler)
    root.setLevel(logging.INFO)

    def log_uncaught(kind, error, tb):
        logging.getLogger("uncaught").error("".join(traceback.format_exception(kind, error, tb)))

    sys.excepthook = log_uncaught
    threading.excepthook = lambda args: log_uncaught(args.exc_type, args.exc_value, args.exc_traceback)
    return path


def log_tkinter_errors(tk_root):
    """tkinter normally prints errors in event handlers to the terminal; log them too."""
    def report(kind, error, tb):
        logging.getLogger("tkinter").error("".join(traceback.format_exception(kind, error, tb)))
    tk_root.report_callback_exception = report
