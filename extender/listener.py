"""Listens to the keyboard system-wide and watches for the hotkey (plan step 6).

How a key press travels:
- Windows hands every key to `pynput`'s low-level hook, which calls our *filter*
  (handle_raw) with the raw key code. The filter keeps track of which modifiers
  (Ctrl, Alt, Shift, Win) are held and spots the hotkey. The hotkey is *blocked*, so it
  never reaches the app you're typing in, and never reaches the buffer either.
- Everything else carries on to on_press, where pynput has turned the key code into a
  character for your keyboard layout, and the buffer is updated.

When the hotkey is pressed, a background thread finds the shortcut just typed and has
the expander replace it. Keys the app presses itself (marked "injected" by Windows) are
ignored, and the buffer is cleared on mouse clicks and when you switch windows.
"""

import ctypes
import sys
import threading
import time
from typing import NamedTuple

from pynput import keyboard, mouse
from pynput.keyboard import HotKey, Key, KeyCode

from .buffer import TypedBuffer
from .config import validate_hotkey
from .expander import Expander
from .matcher import find_match

WM_KEYDOWN, WM_KEYUP, WM_SYSKEYDOWN, WM_SYSKEYUP = 0x0100, 0x0101, 0x0104, 0x0105
LLKHF_INJECTED, LLKHF_LOWER_IL_INJECTED = 0x10, 0x02

# Windows key codes for the modifiers (generic, left and right versions).
MODIFIER_VKS = {
    0x10: "shift", 0xA0: "shift", 0xA1: "shift",
    0x11: "ctrl", 0xA2: "ctrl", 0xA3: "ctrl",
    0x12: "alt", 0xA4: "alt", 0xA5: "alt",
    0x5B: "cmd", 0x5C: "cmd",
}
MODIFIER_KEYS = {"shift": Key.shift, "ctrl": Key.ctrl, "alt": Key.alt, "cmd": Key.cmd}
PYNPUT_MODIFIERS = {
    Key.shift: "shift", Key.shift_l: "shift", Key.shift_r: "shift",
    Key.ctrl: "ctrl", Key.ctrl_l: "ctrl", Key.ctrl_r: "ctrl",
    Key.alt: "alt", Key.alt_l: "alt", Key.alt_r: "alt", Key.alt_gr: "alt",
    Key.cmd: "cmd", Key.cmd_l: "cmd", Key.cmd_r: "cmd",
}

# Pressing and releasing Alt or Win on its own opens the menu bar or Start menu. After a
# blocked Alt/Win hotkey, tapping this unused key code makes Windows see something
# pressed in between, so nothing opens (AutoHotkey does the same).
MENU_MASK_KEY = KeyCode.from_vk(0xE8)

MATCH_SETTLE = 0.02  # let pending key presses reach the buffer before matching


class ParsedHotkey(NamedTuple):
    modifiers: frozenset  # names: "ctrl", "alt", "shift", "cmd"
    vk: int  # Windows key code of the other key


def vk_for_char(char):
    """The Windows key code that types `char` on the current keyboard layout."""
    if sys.platform != "win32":
        raise ValueError("Character hotkeys need Windows.")
    result = ctypes.WinDLL("user32").VkKeyScanW(ctypes.c_wchar(char))
    if result == -1:
        raise ValueError(f"No key types '{char}' on this keyboard layout.")
    return result & 0xFF


def parse_hotkey(text):
    """'<ctrl>+<space>' -> ParsedHotkey({'ctrl'}, 0x20). Raises ValueError (as a
    ConfigError) if the hotkey isn't allowed."""
    validate_hotkey(text)
    modifiers, vk = set(), None
    for key in HotKey.parse(text):
        if key in PYNPUT_MODIFIERS:
            modifiers.add(PYNPUT_MODIFIERS[key])
        elif isinstance(key, Key):
            vk = key.value.vk
        elif key.vk is not None:
            vk = key.vk
        else:
            vk = vk_for_char(key.char)
    return ParsedHotkey(frozenset(modifiers), vk)


def foreground_window():
    """An id for the window you're typing in (0 if unknown)."""
    if sys.platform != "win32":
        return 0
    return ctypes.WinDLL("user32").GetForegroundWindow() or 0


def start_background(job):
    threading.Thread(target=job, daemon=True).start()


class TextExtender:
    """Joins the buffer, matcher and expander to the keyboard and mouse.

    The pieces that touch the real system (expander, window lookup, starting threads,
    waiting) can be replaced, so the logic can be tested with simulated key presses.
    """

    def __init__(self, config, expander=None, buffer=None, window=foreground_window,
                 run_in_background=start_background, sleep=time.sleep):
        self.config = config
        self.hotkey = parse_hotkey(config.hotkey)
        self.buffer = buffer if buffer is not None else TypedBuffer()
        self.held = set()  # names of the modifiers physically held right now
        self.expander = expander if expander is not None else Expander(held_modifiers=self.held_modifier_keys)
        self.window = window
        self.run_in_background = run_in_background
        self.sleep = sleep
        self.paused = False
        self.on_no_match = None  # optional callback, e.g. a tray notification (step 8)
        self._blocked_vk = None  # the hotkey's key, so its release is blocked too
        self._last_window = None
        self._keyboard_listener = None
        self._mouse_listener = None

    # Settings

    def set_config(self, config):
        """Use new settings straight away, including a changed hotkey."""
        hotkey = parse_hotkey(config.hotkey)
        self.config, self.hotkey = config, hotkey

    def pause(self):
        self.paused = True
        self.buffer.clear()

    def resume(self):
        self.buffer.clear()
        self.paused = False

    def held_modifier_keys(self):
        """The held modifiers as pynput keys, for the expander to wait on."""
        return {MODIFIER_KEYS[name] for name in self.held.copy()}  # copy: the hook thread changes it

    # Key events

    def handle_raw(self, msg, vk, injected):
        """Every key event, before it reaches any app. Returns True if it should be
        blocked (the hotkey)."""
        if injected:
            return False
        down = msg in (WM_KEYDOWN, WM_SYSKEYDOWN)
        up = msg in (WM_KEYUP, WM_SYSKEYUP)
        name = MODIFIER_VKS.get(vk)
        if name:
            if down:
                self.held.add(name)
            elif up:
                self.held.discard(name)
            return False
        if up and vk == self._blocked_vk:
            self._blocked_vk = None
            return True
        if (down and not self.paused and not self.expander.is_typing
                and vk == self.hotkey.vk and self.held == set(self.hotkey.modifiers)):
            self._blocked_vk = vk
            self.hotkey_pressed()
            return True
        return False

    def on_press(self, key, injected=False):
        """A key press that wasn't blocked, with pynput's character for it."""
        if injected or self.paused or self.expander.is_typing:
            return
        self._check_window()
        ctrl = "ctrl" in self.held or "cmd" in self.held
        self.buffer.key_pressed(key, ctrl=ctrl, alt="alt" in self.held)

    def on_click(self, x, y, button, pressed):
        if pressed:
            self.buffer.clear()  # the cursor may have moved

    def _check_window(self):
        window = self.window()
        if window != self._last_window:
            self.buffer.clear()
            self._last_window = window

    # The hotkey

    def hotkey_pressed(self):
        # Called from inside Windows' keyboard hook, which must return quickly, so the
        # real work happens on a background thread.
        needs_mask = bool(self.hotkey.modifiers & {"alt", "cmd"})
        self.run_in_background(lambda: self._expand_typed(needs_mask))

    def _expand_typed(self, needs_mask):
        if needs_mask:
            self.expander.keyboard.tap(MENU_MASK_KEY)
        self.sleep(MATCH_SETTLE)
        self._check_window()
        match = find_match(self.buffer.text, self.config.snippets)
        if match is None:
            if self.on_no_match:
                self.on_no_match()
            return
        try:
            self.expander.expand(match, self.config.char_delay_ms)
        finally:
            self.buffer.clear()

    # Starting and stopping the real listeners

    def _event_filter(self, msg, data):
        injected = bool(data.flags & (LLKHF_INJECTED | LLKHF_LOWER_IL_INJECTED))
        if self.handle_raw(msg, data.vkCode, injected):
            self._keyboard_listener.suppress_event()

    def start(self):
        self._keyboard_listener = keyboard.Listener(on_press=self.on_press, win32_event_filter=self._event_filter)
        self._mouse_listener = mouse.Listener(on_click=self.on_click)
        self._keyboard_listener.start()
        self._mouse_listener.start()
        self._keyboard_listener.wait()
        self._mouse_listener.wait()

    def stop(self):
        for listener in (self._keyboard_listener, self._mouse_listener):
            if listener is not None:
                listener.stop()

    def is_running(self):
        return self._keyboard_listener is not None and self._keyboard_listener.is_alive()

    def join(self, timeout=None):
        """Wait until stopped (or timeout seconds)."""
        if self._keyboard_listener is not None:
            self._keyboard_listener.join(timeout)
