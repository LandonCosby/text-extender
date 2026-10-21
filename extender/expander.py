"""Erases the typed shortcut and outputs the full message (plan step 5).

An expansion:
1. waits for you to let go of the hotkey (Ctrl and so on), so the message isn't typed
   as Ctrl+letters;
2. presses Backspace once for each character of the shortcut;
3. outputs the message:
   - with a typing delay of 0, it pastes: the message goes on the clipboard, Ctrl+V is
     pressed, and the clipboard's old text is put back. If the clipboard holds
     something other than text (an image, files) or can't be used, the message is
     typed quickly instead, so nothing on the clipboard is lost;
   - with a delay, it's typed one character at a time with that pause between each.
   Line breaks are typed as Enter and tabs as Tab. Placeholders such as {date} are
   filled in first (see placeholders.py), and {cursor} moves the cursor back to its
   spot afterwards.

Expansions are meant to run on a background thread (the listener in step 6 does that).
While one runs, is_typing is True so the listener can ignore the keys it presses.
"""

import sys
import threading
import time

from pynput.keyboard import Controller, Key, KeyCode

from .clipboard import ClipboardError, WindowsClipboard
from .placeholders import fill

VK_V = KeyCode.from_vk(0x56)  # the V key itself; a typed letter 'v' wouldn't trigger Ctrl+V


def default_keyboard():
    if sys.platform == "win32":
        from .keyboard import WindowsKeyboard
        return WindowsKeyboard()
    return Controller()


MODIFIER_WAIT = 1.0  # longest to wait for the hotkey to be released, in seconds
MODIFIER_POLL = 0.01
PASTE_SETTLE = 0.15  # time for the app to read the clipboard before it's put back
# Real apps need time to keep up with simulated keys (measured in Windows 11 Notepad):
# typed faster than this, characters go missing or get swapped, and Ctrl+V straight
# after the Backspaces can arrive as a plain 'v'.
MIN_TYPING_DELAY_MS = 25  # slowest-needed gap between typed characters
KEY_PAUSE = 0.03  # after the Backspaces, and around Ctrl+V


def normalise_line_breaks(text):
    """Turn \\r\\n and \\r into \\n."""
    return text.replace("\r\n", "\n").replace("\r", "\n")


class Expander:
    def __init__(self, keyboard=None, clipboard=None, held_modifiers=lambda: (),
                 sleep=time.sleep, clock=time.monotonic):
        """keyboard and clipboard can be swapped for fakes in tests. held_modifiers
        returns the modifier keys being held down right now (the listener knows)."""
        self.keyboard = keyboard if keyboard is not None else default_keyboard()
        self._clipboard = clipboard
        self.held_modifiers = held_modifiers
        self.sleep = sleep
        self.clock = clock
        self._typing = threading.Event()
        self._one_at_a_time = threading.Lock()

    @property
    def clipboard(self):
        # Created when first needed, so the expander also works where it can't be used.
        if self._clipboard is None:
            self._clipboard = WindowsClipboard()
        return self._clipboard

    @property
    def is_typing(self):
        return self._typing.is_set()

    def expand(self, match, char_delay_ms, typed_after="", key_after=None):
        """Replace match.shortcut, just typed, with match.message.

        For automatic expansion: typed_after is the space or punctuation typed after
        the shortcut, which is erased too and put back after the message. key_after
        (Enter or Tab) was kept from the app, and is pressed after the message."""
        with self._one_at_a_time:
            self._typing.set()
            try:
                self.wait_for_modifiers()
                filled = fill(match.message, clipboard_text=self.clipboard_text)
                for _ in match.shortcut + typed_after:
                    self.keyboard.tap(Key.backspace)
                self.sleep(KEY_PAUSE)
                text = filled.text + typed_after
                if char_delay_ms == 0:
                    self.paste(text)
                else:
                    self.type_text(text, char_delay_ms / 1000)
                if key_after is not None:
                    self.keyboard.tap(key_after)
                    self.sleep(KEY_PAUSE)
                if filled.cursor_back:
                    self.move_left(filled.cursor_back + len(typed_after) + (key_after is not None))
            finally:
                self._typing.clear()

    def clipboard_text(self):
        """The clipboard's text for {clipboard}, or "" if it holds none."""
        try:
            contents = self.clipboard.read()
        except ClipboardError:
            return ""
        return contents.text if contents.kind == "text" else ""

    def move_left(self, count):
        """Press Left `count` times, for {cursor}."""
        for _ in range(count):
            self.keyboard.tap(Key.left)
            self.sleep(MIN_TYPING_DELAY_MS / 1000)

    def wait_for_modifiers(self):
        """Wait until the hotkey's modifiers are let go. If they're still held after
        MODIFIER_WAIT seconds, release them ourselves so typing comes out right."""
        deadline = self.clock() + MODIFIER_WAIT
        while self.held_modifiers():
            if self.clock() >= deadline:
                for key in list(self.held_modifiers()):
                    self.keyboard.release(key)
                return
            self.sleep(MODIFIER_POLL)

    def paste(self, message):
        try:
            saved = self.clipboard.read()
        except ClipboardError:
            saved = None
        if saved is None or saved.kind == "other":
            self.type_text(message, 0)  # don't lose an image or files on the clipboard
            return
        try:
            # Windows programs expect line breaks on the clipboard as \r\n.
            self.clipboard.write_text(normalise_line_breaks(message).replace("\n", "\r\n"))
        except ClipboardError:
            self.type_text(message, 0)
            return
        self.keyboard.press(Key.ctrl)
        self.sleep(KEY_PAUSE)
        self.keyboard.tap(VK_V)
        self.sleep(KEY_PAUSE)
        self.keyboard.release(Key.ctrl)
        self.sleep(PASTE_SETTLE)
        try:
            self.clipboard.restore(saved)
        except ClipboardError:
            pass  # the message was pasted; the old text just couldn't be put back

    def type_text(self, message, pause):
        """Type the message one character at a time, waiting `pause` seconds after each
        (never less than MIN_TYPING_DELAY_MS, so the app keeps up)."""
        pause = max(pause, MIN_TYPING_DELAY_MS / 1000)
        for ch in normalise_line_breaks(message):
            if ch == "\n":
                self.keyboard.tap(Key.enter)
            elif ch == "\t":
                self.keyboard.tap(Key.tab)
            else:
                self.keyboard.type(ch)
            self.sleep(pause)
