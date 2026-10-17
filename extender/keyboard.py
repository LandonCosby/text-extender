"""Pressing keys and typing text on Windows, for the expander.

pynput's own typing turned out to be unreliable in real apps (found in plan step 10):
capitals are typed by faking Shift around each letter, which apps sometimes drop, and an
emoji is sent as two separate halves. So this module talks to Windows' SendInput
directly, the way the on-screen keyboard does:

- text is sent as Unicode characters, so no Shift faking is needed, and both halves of
  an emoji go in a single call so they arrive together;
- keys (Backspace, Enter, Tab, Ctrl, V for paste) are sent by their Windows key code.

It has the same tap / press / release / type methods the expander uses on pynput's
Controller, and accepts the same pynput Key and KeyCode objects.
"""

import ctypes
from ctypes import wintypes

from pynput.keyboard import Key, KeyCode

INPUT_KEYBOARD = 1
KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004

# Keys that Windows expects marked as "extended" (on the arrow/navigation block).
EXTENDED_VKS = {0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27, 0x28, 0x2D, 0x2E, 0xA3, 0xA5, 0x5B, 0x5C}

ULONG_PTR = ctypes.c_size_t


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD), ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR)]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG), ("mouseData", wintypes.DWORD),
                ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR)]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [("uMsg", wintypes.DWORD), ("wParamL", wintypes.WORD), ("wParamH", wintypes.WORD)]


class _INPUTUNION(ctypes.Union):
    _fields_ = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT), ("hi", HARDWAREINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("u", _INPUTUNION)]


def vk_of(key):
    """The Windows key code for a pynput Key or KeyCode (None for a plain character)."""
    if isinstance(key, Key):
        return key.value.vk
    if isinstance(key, KeyCode):
        return key.vk
    return None


def key_event(vk, up=False):
    flags = (KEYEVENTF_KEYUP if up else 0) | (KEYEVENTF_EXTENDEDKEY if vk in EXTENDED_VKS else 0)
    return INPUT(type=INPUT_KEYBOARD, u=_INPUTUNION(ki=KEYBDINPUT(wVk=vk, wScan=0, dwFlags=flags)))


def unicode_events(char):
    """Key down and up for each UTF-16 half of `char` (an emoji has two halves)."""
    data = char.encode("utf-16-le")
    units = [int.from_bytes(data[i:i + 2], "little") for i in range(0, len(data), 2)]
    events = []
    for unit in units:
        for up in (False, True):
            flags = KEYEVENTF_UNICODE | (KEYEVENTF_KEYUP if up else 0)
            events.append(INPUT(type=INPUT_KEYBOARD, u=_INPUTUNION(ki=KEYBDINPUT(wVk=0, wScan=unit, dwFlags=flags))))
    return events


class WindowsKeyboard:
    def __init__(self, send=None):
        """send(list of INPUT) delivers the events; replaceable in tests."""
        if send is None:
            user32 = ctypes.WinDLL("user32", use_last_error=True)
            user32.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int]
            user32.SendInput.restype = wintypes.UINT

            def send(events):
                array = (INPUT * len(events))(*events)
                user32.SendInput(len(events), array, ctypes.sizeof(INPUT))
        self.send = send

    def _events(self, key, up):
        vk = vk_of(key)
        if vk is not None:
            return [key_event(vk, up)]
        char = key.char if isinstance(key, KeyCode) else key
        events = unicode_events(char)
        return [e for i, e in enumerate(events) if (i % 2 == 1) == up]

    def press(self, key):
        self.send(self._events(key, up=False))

    def release(self, key):
        self.send(self._events(key, up=True))

    def tap(self, key):
        self.send(self._events(key, up=False) + self._events(key, up=True))

    def type(self, text):
        """Type text as Unicode characters, each one sent in a single call."""
        for char in text:
            self.send(unicode_events(char))
