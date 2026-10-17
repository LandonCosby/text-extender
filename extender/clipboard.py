"""Reading and writing the Windows clipboard, for pasting messages instantly (plan step 5).

Uses the Windows clipboard functions directly through ctypes, so no extra download is
needed. Only plain text can be saved and put back: if the clipboard holds an image or
copied files, the expander types the message instead, so those aren't lost.
"""

import ctypes
import sys
import time
from ctypes import wintypes
from typing import NamedTuple, Optional

CF_UNICODETEXT = 13
GMEM_MOVEABLE = 0x0002
OPEN_ATTEMPTS = 20  # another app may have the clipboard open for a moment
OPEN_RETRY_PAUSE = 0.01


class ClipboardError(OSError):
    """The clipboard couldn't be read or written."""


class ClipboardContents(NamedTuple):
    kind: str  # "empty", "text", or "other" (an image, files and so on)
    text: Optional[str] = None


class WindowsClipboard:
    def __init__(self):
        if sys.platform != "win32":
            raise ClipboardError("The clipboard is only supported on Windows.")
        self.user32 = ctypes.WinDLL("user32", use_last_error=True)
        self.kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        u, k = self.user32, self.kernel32
        u.OpenClipboard.argtypes, u.OpenClipboard.restype = [wintypes.HWND], wintypes.BOOL
        u.CloseClipboard.restype = wintypes.BOOL
        u.EmptyClipboard.restype = wintypes.BOOL
        u.CountClipboardFormats.restype = ctypes.c_int
        u.IsClipboardFormatAvailable.argtypes, u.IsClipboardFormatAvailable.restype = [wintypes.UINT], wintypes.BOOL
        u.GetClipboardData.argtypes, u.GetClipboardData.restype = [wintypes.UINT], wintypes.HANDLE
        u.SetClipboardData.argtypes, u.SetClipboardData.restype = [wintypes.UINT, wintypes.HANDLE], wintypes.HANDLE
        k.GlobalAlloc.argtypes, k.GlobalAlloc.restype = [wintypes.UINT, ctypes.c_size_t], wintypes.HGLOBAL
        k.GlobalLock.argtypes, k.GlobalLock.restype = [wintypes.HGLOBAL], wintypes.LPVOID
        k.GlobalUnlock.argtypes, k.GlobalUnlock.restype = [wintypes.HGLOBAL], wintypes.BOOL
        k.GlobalFree.argtypes, k.GlobalFree.restype = [wintypes.HGLOBAL], wintypes.HGLOBAL

    def _open(self):
        for _ in range(OPEN_ATTEMPTS):
            if self.user32.OpenClipboard(None):
                return
            time.sleep(OPEN_RETRY_PAUSE)
        raise ClipboardError("Another program is using the clipboard.")

    def read(self):
        """What's on the clipboard now."""
        self._open()
        try:
            if self.user32.CountClipboardFormats() == 0:
                return ClipboardContents("empty")
            if not self.user32.IsClipboardFormatAvailable(CF_UNICODETEXT):
                return ClipboardContents("other")
            handle = self.user32.GetClipboardData(CF_UNICODETEXT)
            if not handle:
                raise ClipboardError("Couldn't read the clipboard.")
            pointer = self.kernel32.GlobalLock(handle)
            if not pointer:
                raise ClipboardError("Couldn't read the clipboard.")
            try:
                return ClipboardContents("text", ctypes.wstring_at(pointer))
            finally:
                self.kernel32.GlobalUnlock(handle)
        finally:
            self.user32.CloseClipboard()

    def write_text(self, text):
        """Replace the clipboard with plain text."""
        data = ctypes.create_unicode_buffer(text)
        size = ctypes.sizeof(data)
        self._open()
        try:
            self.user32.EmptyClipboard()
            handle = self.kernel32.GlobalAlloc(GMEM_MOVEABLE, size)
            if not handle:
                raise ClipboardError("Not enough memory for the clipboard.")
            pointer = self.kernel32.GlobalLock(handle)
            ctypes.memmove(pointer, data, size)
            self.kernel32.GlobalUnlock(handle)
            if not self.user32.SetClipboardData(CF_UNICODETEXT, handle):
                self.kernel32.GlobalFree(handle)  # Windows only owns it once this succeeds
                raise ClipboardError("Couldn't write to the clipboard.")
        finally:
            self.user32.CloseClipboard()

    def clear(self):
        self._open()
        try:
            self.user32.EmptyClipboard()
        finally:
            self.user32.CloseClipboard()

    def restore(self, contents):
        """Put back what read() returned earlier (text or empty)."""
        if contents.kind == "text":
            self.write_text(contents.text)
        elif contents.kind == "empty":
            self.clear()
