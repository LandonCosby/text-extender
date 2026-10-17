"""The error log, used when running without a terminal (pythonw)."""

import logging
import sys
import threading

import pytest

from extender import logs


@pytest.fixture
def log_file(tmp_path, monkeypatch):
    # setup() changes process-wide hooks and logging; put them all back afterwards.
    monkeypatch.setattr(sys, "excepthook", sys.excepthook)
    monkeypatch.setattr(threading, "excepthook", threading.excepthook)
    root = logging.getLogger()
    handlers, level = list(root.handlers), root.level
    path = logs.setup(tmp_path / "TextExtender")
    yield path
    for handler in root.handlers:
        if handler not in handlers:
            handler.close()
            root.removeHandler(handler)
    root.setLevel(level)


def read(path):
    for handler in logging.getLogger().handlers:
        handler.flush()
    return path.read_text(encoding="utf-8")


def test_log_file_is_next_to_the_settings(log_file, tmp_path):
    assert log_file == tmp_path / "TextExtender" / "textextender.log"


def test_messages_are_written(log_file):
    logging.getLogger("test").error("something went wrong")
    assert "something went wrong" in read(log_file)


def test_errors_in_threads_are_written(log_file):
    def broken():
        raise ValueError("thread failed")

    t = threading.Thread(target=broken)
    t.start()
    t.join()
    assert "thread failed" in read(log_file)


def test_errors_in_tkinter_handlers_are_written(log_file, root):
    tk_app = root.master
    previous = tk_app.report_callback_exception
    try:
        logs.log_tkinter_errors(tk_app)
        root.after(0, lambda: 1 / 0)
        root.update()
    finally:
        tk_app.report_callback_exception = previous
    assert "ZeroDivisionError" in read(log_file)
