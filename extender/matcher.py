"""Finds which shortcut, if any, was just typed (plan step 4).

When the hotkey is pressed, the text just before the cursor (from the buffer) is
checked against every snippet's shortcut. The longest shortcut it ends with wins,
so with both ';addr' and ';addr2' saved, typing ';addr2' expands ';addr2'.

Matching is exact (case-sensitive), and the shortcut has to stand on its own: it must
come right after a space or a line break, or be the first thing typed since the cursor
last moved (Enter, arrow keys and mouse clicks clear the buffer, so that covers the
start of a new line). So 'thanksbrb' does not expand 'brb', but 'thanks brb' does.
"""

from typing import NamedTuple, Optional


class Match(NamedTuple):
    shortcut: str  # what was typed, and so what has to be erased
    message: str  # what replaces it


def stands_alone(typed, shortcut):
    """Whether the shortcut at the end of the typed text has a space, a line break, or
    nothing before it."""
    before = typed[:-len(shortcut)]
    return before == "" or before[-1] in " \t\r\n"


def find_match(typed, snippets) -> Optional[Match]:
    """The snippet whose shortcut the typed text ends with (the longest, if several
    do), or None if none of them match."""
    best = None
    for shortcut, message in snippets.items():
        if (shortcut and typed.endswith(shortcut) and stands_alone(typed, shortcut)
                and (best is None or len(shortcut) > len(best.shortcut))):
            best = Match(shortcut, message)
    return best


def could_continue(typed, snippets):
    """Whether the end of the typed text could be the start of a shortcut (or a whole
    one). Automatic expansion waits then: with ';a' and ';a.b' saved, the '.' after
    ';a' may be part of ';a.b'."""
    for shortcut in snippets:
        for length in range(1, len(shortcut) + 1):
            start = shortcut[:length]
            if typed.endswith(start) and stands_alone(typed, start):
                return True
    return False
