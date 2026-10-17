import os
import sys

import pytest

# Let tests import the extender package from the project folder.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture(scope="session")
def tk_app():
    """tkinter, started once for the whole test run: starting it again and again in one
    process occasionally fails on Windows ("Can't find a usable tk.tcl")."""
    tk = pytest.importorskip("tkinter")
    try:
        app = tk.Tk()
    except tk.TclError as e:
        pytest.skip(f"tkinter couldn't start: {e}")
    app.withdraw()
    yield app
    app.destroy()


@pytest.fixture
def root(tk_app):
    """A fresh, hidden window for each test."""
    import tkinter as tk
    window = tk.Toplevel(tk_app)
    window.withdraw()
    # tkinter normally just prints errors raised in event handlers; make them fail the test.
    errors = []
    tk_app.report_callback_exception = lambda kind, error, tb: errors.append(error)
    yield window
    if window.winfo_exists():
        window.update()  # run anything still waiting, such as handlers triggered while building
        window.destroy()
    assert errors == [], f"error in a tkinter handler: {errors[0]!r}"
