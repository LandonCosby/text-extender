"""Remembers the characters typed most recently (plan step 3).

The buffer is the app's guess at the text just before the cursor. When the hotkey is
pressed, the matcher checks whether that text ends with a shortcut.

The rule when unsure: clear the buffer. A missed expansion is harmless, but trusting a
stale buffer would erase the wrong characters. So anything that might move the cursor
or change the text in an unknown way (arrow keys, Enter, Ctrl shortcuts, mouse clicks,
switching windows) clears it.
"""

import threading

from pynput.keyboard import Key, KeyCode

MAX_LENGTH = 50  # longer than any shortcut (config.MAX_SHORTCUT_LENGTH is 30)

# Keys that never change the text or move the cursor.
IGNORED_KEYS = {
    Key.shift, Key.shift_l, Key.shift_r,
    Key.ctrl, Key.ctrl_l, Key.ctrl_r,
    Key.alt, Key.alt_l, Key.alt_r, Key.alt_gr,
    Key.cmd, Key.cmd_l, Key.cmd_r,
    Key.caps_lock, Key.num_lock, Key.scroll_lock,
    Key.insert, Key.print_screen, Key.pause,
    Key.media_play_pause, Key.media_stop, Key.media_previous, Key.media_next,
    Key.media_volume_mute, Key.media_volume_down, Key.media_volume_up,
    # Delete removes the character after the cursor, so the text before it is unchanged.
    Key.delete,
}


class TypedBuffer:
    """The last few characters typed. Safe to use from the listener thread and the
    expansion thread at the same time."""

    def __init__(self, max_length=MAX_LENGTH):
        self.max_length = max_length
        self._text = ""
        self._lock = threading.Lock()

    @property
    def text(self):
        with self._lock:
            return self._text

    def add(self, characters):
        with self._lock:
            self._text = (self._text + characters)[-self.max_length:]

    def backspace(self):
        with self._lock:
            self._text = self._text[:-1]

    def clear(self):
        """For anything that may have moved the cursor: a mouse click, switching
        windows, or after an expansion has been typed."""
        with self._lock:
            self._text = ""

    def key_pressed(self, key, ctrl=False, alt=False):
        """Update the buffer for one key press from pynput.

        ctrl and alt say whether those were held. On Windows, AltGr (used for
        characters such as € on many keyboards) shows up as Ctrl and Alt together
        with a normal character, so that still counts as typing.
        """
        if key in IGNORED_KEYS:
            return
        char = key.char if isinstance(key, KeyCode) else None
        printable = char is not None and char.isprintable()
        if ctrl or alt:
            if ctrl and alt and printable:
                self.add(char)  # AltGr character
            else:
                self.clear()  # a shortcut such as Ctrl+V or Ctrl+Z: text changed unpredictably
            return
        if key == Key.backspace:
            self.backspace()
        elif key == Key.space:
            self.add(" ")
        elif printable:
            self.add(char)
        else:
            # Enter, Tab, Esc, arrows, Home/End, Page Up/Down, F-keys, the menu key,
            # and keys pynput can't name: the cursor may have moved.
            self.clear()
