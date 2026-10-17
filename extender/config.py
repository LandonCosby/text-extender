r"""Loading and saving snippets and settings (plan step 2).

Stored as JSON in %APPDATA%\TextExtender\config.json, outside the project folder,
because snippets can contain personal details:

    {
      "hotkey": "<ctrl>+<space>",
      "char_delay_ms": 0,
      "snippets": {";addr": "123 Example St\nSpringfield"}
    }
"""

import json
import os
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from pynput.keyboard import HotKey, Key

DEFAULT_HOTKEY = "<ctrl>+<space>"
DEFAULT_CHAR_DELAY_MS = 0  # 0 pastes the message instantly
MAX_CHAR_DELAY_MS = 200
MAX_SHORTCUT_LENGTH = 30  # must fit in the typed-text buffer (plan step 3)

MODIFIERS = {
    Key.ctrl, Key.ctrl_l, Key.ctrl_r,
    Key.alt, Key.alt_l, Key.alt_r, Key.alt_gr,
    Key.shift, Key.shift_l, Key.shift_r,
    Key.cmd, Key.cmd_l, Key.cmd_r,
}


class ConfigError(ValueError):
    """A setting or snippet that isn't allowed. The message is shown to the user."""


@dataclass
class Config:
    hotkey: str = DEFAULT_HOTKEY
    char_delay_ms: int = DEFAULT_CHAR_DELAY_MS
    snippets: dict = field(default_factory=dict)  # shortcut -> message

    def validate(self):
        """Raise ConfigError if anything isn't allowed."""
        validate_hotkey(self.hotkey)
        validate_char_delay(self.char_delay_ms)
        if not isinstance(self.snippets, dict):
            raise ConfigError("Snippets must be a list of shortcuts and messages.")
        for shortcut, message in self.snippets.items():
            validate_shortcut(shortcut)
            validate_message(message)

    # Snippet editing, used by the settings window. Each change is checked first,
    # so a failed change leaves the snippets as they were.

    def add_snippet(self, shortcut, message):
        validate_shortcut(shortcut)
        validate_message(message)
        if shortcut in self.snippets:
            raise ConfigError(f"There's already a snippet for '{shortcut}'.")
        self.snippets[shortcut] = message

    def update_snippet(self, old_shortcut, new_shortcut, message):
        if old_shortcut not in self.snippets:
            raise ConfigError(f"There's no snippet for '{old_shortcut}'.")
        validate_shortcut(new_shortcut)
        validate_message(message)
        if new_shortcut != old_shortcut and new_shortcut in self.snippets:
            raise ConfigError(f"There's already a snippet for '{new_shortcut}'.")
        # Rebuild the dict so a renamed snippet keeps its place in the list.
        self.snippets = {
            (new_shortcut if s == old_shortcut else s): (message if s == old_shortcut else m)
            for s, m in self.snippets.items()
        }

    def remove_snippet(self, shortcut):
        if shortcut not in self.snippets:
            raise ConfigError(f"There's no snippet for '{shortcut}'.")
        del self.snippets[shortcut]


def validate_hotkey(hotkey):
    """A hotkey is pynput text such as '<ctrl>+<space>' or '<ctrl>+<alt>+e': at least
    one modifier plus one other key, so it can't fire during normal typing."""
    if not isinstance(hotkey, str) or not hotkey.strip():
        raise ConfigError("The hotkey can't be empty.")
    try:
        keys = HotKey.parse(hotkey)
    except ValueError:
        raise ConfigError(f"'{hotkey}' isn't a hotkey I recognise.") from None
    if not any(k in MODIFIERS for k in keys):
        raise ConfigError("The hotkey needs Ctrl, Alt, Shift or Win, so it can't fire while you type.")
    others = [k for k in keys if k not in MODIFIERS]
    if not others:
        raise ConfigError("The hotkey needs a key besides Ctrl, Alt, Shift or Win.")
    if len(others) > 1:
        raise ConfigError("The hotkey can only have one key besides Ctrl, Alt, Shift or Win.")


def validate_char_delay(delay):
    if isinstance(delay, bool) or not isinstance(delay, int):
        raise ConfigError("The typing delay must be a whole number of milliseconds.")
    if not 0 <= delay <= MAX_CHAR_DELAY_MS:
        raise ConfigError(f"The typing delay must be between 0 and {MAX_CHAR_DELAY_MS} ms.")


def validate_shortcut(shortcut):
    if not isinstance(shortcut, str) or not shortcut:
        raise ConfigError("The shortcut can't be empty.")
    if any(ch.isspace() for ch in shortcut):
        raise ConfigError("The shortcut can't contain spaces or line breaks.")
    if len(shortcut) > MAX_SHORTCUT_LENGTH:
        raise ConfigError(f"The shortcut can be at most {MAX_SHORTCUT_LENGTH} characters.")


def validate_message(message):
    if not isinstance(message, str) or not message.strip():
        raise ConfigError("The message can't be empty.")


def default_path():
    """%APPDATA%\\TextExtender\\config.json (the home folder if APPDATA isn't set)."""
    base = os.environ.get("APPDATA") or str(Path.home())
    return Path(base) / "TextExtender" / "config.json"


def load(path=None):
    """Load the config. A missing file gives the defaults. A damaged file (not JSON,
    or with settings that aren't allowed) is moved aside as a backup, and the
    defaults are used, so the app always starts."""
    path = Path(path) if path else default_path()
    if not path.exists():
        return Config()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ConfigError("The config file should hold a JSON object.")
        config = Config(
            hotkey=data.get("hotkey", DEFAULT_HOTKEY),
            char_delay_ms=data.get("char_delay_ms", DEFAULT_CHAR_DELAY_MS),
            snippets=dict(data.get("snippets", {})),
        )
        config.validate()
        return config
    except (ValueError, TypeError):  # bad JSON (ValueError) or ConfigError
        backup_damaged(path)
        return Config()


def backup_damaged(path):
    """Rename a damaged config to config.damaged-<date-time>.json, next to it,
    adding a number if a backup from the same second already exists."""
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = path.with_name(f"{path.stem}.damaged-{stamp}{path.suffix}")
    number = 1
    while backup.exists():
        number += 1
        backup = path.with_name(f"{path.stem}.damaged-{stamp}-{number}{path.suffix}")
    path.replace(backup)
    return backup


def save(config, path=None):
    """Check the config, then write it. It's written to a temporary file that then
    replaces the real one, so a crash part-way through can't leave it half-written."""
    config.validate()
    path = Path(path) if path else default_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {"hotkey": config.hotkey, "char_delay_ms": config.char_delay_ms, "snippets": config.snippets}
    fd, temp = tempfile.mkstemp(dir=path.parent, prefix=".config-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(temp, path)
    except BaseException:
        os.unlink(temp)
        raise
