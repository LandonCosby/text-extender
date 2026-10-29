r"""Starting Text Extender when you sign in to Windows (plan step 11).

Windows runs every command listed under HKEY_CURRENT_USER\...\CurrentVersion\Run at
sign-in, so turning this on adds a "TextExtender" entry there and turning it off removes
it. It's your own user's list, so no administrator rights are needed, and it shows up
(and can be switched off) in Task Manager's Startup apps.

The entry itself is the setting, not the config file: if you switch it off in Task
Manager, the settings window shows it as off too.
"""

import sys
from pathlib import Path

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "TextExtender"


def launch_command():
    """The command that starts this copy of the app: the .exe itself when packaged,
    otherwise pythonw (no terminal window) running main.py."""
    if getattr(sys, "frozen", False):  # set by PyInstaller
        return f'"{sys.executable}"'
    python = Path(sys.executable)
    pythonw = python.with_name("pythonw.exe")
    main = Path(__file__).resolve().parent.parent / "main.py"
    return f'"{pythonw if pythonw.exists() else python}" "{main}"'


class StartWithWindows:
    def __init__(self, key_path=RUN_KEY, name=VALUE_NAME):
        """key_path can point somewhere harmless in tests."""
        self.key_path = key_path
        self.name = name

    def is_enabled(self):
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.key_path) as key:
                winreg.QueryValueEx(key, self.name)
            return True
        except FileNotFoundError:
            return False

    def enable(self):
        """Add (or update) the entry. Raises OSError if Windows refuses."""
        import winreg
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, self.key_path) as key:
            winreg.SetValueEx(key, self.name, 0, winreg.REG_SZ, launch_command())

    def disable(self):
        """Remove the entry, if it's there. Raises OSError if Windows refuses."""
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.key_path, 0, winreg.KEY_SET_VALUE) as key:
                winreg.DeleteValue(key, self.name)
        except FileNotFoundError:
            pass
