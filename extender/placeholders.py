"""Placeholders in messages, filled in when a snippet expands.

- {date}: today's date, in the short format set in Windows (e.g. 21/10/2026)
- {time}: the time now, in Windows' short format (e.g. 14:05)
- {clipboard}: the text on the clipboard (nothing if it holds no text)
- {cursor}: where the cursor is left afterwards, instead of at the end. Only the
  first one counts; any others are removed.

Anything else in braces is left as it is, so messages can still contain braces.
"""

import ctypes
import re
import sys
import time
from typing import NamedTuple

PLACEHOLDERS = ("{date}", "{time}", "{clipboard}", "{cursor}")
CURSOR = "{cursor}"
PATTERN = re.compile("(" + "|".join(re.escape(p) for p in PLACEHOLDERS) + ")")

LOCALE_USER_DEFAULT = 0x0400
DATE_SHORTDATE = 0x1
TIME_NOSECONDS = 0x2


class Filled(NamedTuple):
    text: str
    cursor_back: int  # how many characters from the end the cursor should go back


def windows_date():
    if sys.platform == "win32":
        buffer = ctypes.create_unicode_buffer(80)
        if ctypes.windll.kernel32.GetDateFormatW(LOCALE_USER_DEFAULT, DATE_SHORTDATE, None, None, buffer, 80):
            return buffer.value
    return time.strftime("%x")


def windows_time():
    if sys.platform == "win32":
        buffer = ctypes.create_unicode_buffer(80)
        if ctypes.windll.kernel32.GetTimeFormatW(LOCALE_USER_DEFAULT, TIME_NOSECONDS, None, None, buffer, 80):
            return buffer.value
    return time.strftime("%H:%M")


def fill(message, clipboard_text=lambda: "", date=windows_date, now=windows_time):
    """The message with its placeholders filled in. Each source is only asked for if
    its placeholder is used, so the clipboard isn't touched unless it's needed."""
    sources = {"{date}": date, "{time}": now, "{clipboard}": clipboard_text}
    values = {}
    parts, cursor_at = [], None
    # One pass, so placeholder-like text that comes *from* the clipboard stays as it is.
    for piece in PATTERN.split(message):
        if piece == CURSOR:
            if cursor_at is None:
                cursor_at = len(parts)
        elif piece in sources:
            if piece not in values:
                values[piece] = sources[piece]() or ""
            parts.append(values[piece])
        else:
            parts.append(piece)
    text = "".join(parts)
    if cursor_at is None:
        return Filled(text, 0)
    after = "".join(parts[cursor_at:])
    # Line breaks become one Enter each when typed or pasted, so count \r\n once.
    return Filled(text, len(after.replace("\r\n", "\n").replace("\r", "\n")))
