"""Starting with Windows (plan step 11).

Uses a throwaway registry key under HKEY_CURRENT_USER instead of the real Run list,
so the real startup setting is never touched.
"""

import sys
import uuid

import pytest

from extender import startup

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="needs the Windows registry")


@pytest.fixture
def entry():
    import winreg
    key_path = rf"Software\TextExtenderTest-{uuid.uuid4().hex}"
    yield startup.StartWithWindows(key_path=key_path, name="TextExtender")
    try:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, key_path)
    except FileNotFoundError:
        pass


def read_value(entry):
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, entry.key_path) as key:
        return winreg.QueryValueEx(key, entry.name)[0]


def test_off_until_enabled(entry):
    assert not entry.is_enabled()


def test_enable_adds_the_launch_command(entry):
    entry.enable()
    assert entry.is_enabled()
    assert read_value(entry) == startup.launch_command()


def test_disable_removes_it(entry):
    entry.enable()
    entry.disable()
    assert not entry.is_enabled()


def test_disabling_when_already_off_is_fine(entry):
    entry.disable()
    assert not entry.is_enabled()


def test_launch_command_runs_main_without_a_terminal(monkeypatch):
    monkeypatch.delattr(sys, "frozen", raising=False)
    command = startup.launch_command()
    assert command.endswith('main.py"')
    assert "python" in command.lower()


def test_launch_command_for_the_exe_is_the_exe_itself(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", r"C:\Apps\TextExtender.exe")
    assert startup.launch_command() == r'"C:\Apps\TextExtender.exe"'
