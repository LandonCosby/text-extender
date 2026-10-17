"""Checks that the project and its dependencies are set up (plan step 1)."""

import importlib

import pytest

MODULES = ["config", "buffer", "matcher", "expander", "listener", "settings_window", "tray"]


@pytest.mark.parametrize("name", MODULES)
def test_extender_modules_import(name):
    importlib.import_module(f"extender.{name}")


@pytest.mark.parametrize("package", ["pynput", "pystray", "PIL", "tkinter"])
def test_dependencies_are_installed(package):
    importlib.import_module(package)


def test_main_runs():
    import main
    assert main.main() == 0
