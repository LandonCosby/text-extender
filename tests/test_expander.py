"""Erasing the shortcut and outputting the message (plan step 5).

Uses a fake keyboard that records key presses and a fake clipboard, so nothing is
really typed. One test at the end uses the real Windows clipboard, carefully.
"""

import sys

import pytest
from pynput.keyboard import Key

from extender.clipboard import ClipboardContents, ClipboardError
from extender.expander import MODIFIER_WAIT, PASTE_SETTLE, Expander
from extender.matcher import Match


class FakeKeyboard:
    def __init__(self, on_key=None):
        self.events = []
        self.on_key = on_key  # called on every key, to look at state mid-expansion

    def _record(self, action, key):
        self.events.append((action, key))
        if self.on_key:
            self.on_key()

    def press(self, key):
        self._record("press", key)

    def release(self, key):
        self._record("release", key)

    def tap(self, key):
        self._record("tap", key)

    def type(self, text):
        self._record("type", text)

    def typed(self):
        """What would appear on screen from type/tap events."""
        out = []
        for action, key in self.events:
            if action == "type":
                out.append(key)
            elif action == "tap" and key == Key.enter:
                out.append("\n")
            elif action == "tap" and key == Key.tab:
                out.append("\t")
        return "".join(out)


class FakeClipboard:
    def __init__(self, contents=ClipboardContents("text", "old clipboard text"), fail=None):
        self.contents = contents
        self.fail = fail  # "read" or "write" to simulate another program holding it
        self.writes = []

    def read(self):
        if self.fail == "read":
            raise ClipboardError("busy")
        return self.contents

    def write_text(self, text):
        if self.fail == "write":
            raise ClipboardError("busy")
        self.writes.append(text)
        self.contents = ClipboardContents("text", text)

    def restore(self, contents):
        self.contents = contents


class FakeTime:
    def __init__(self):
        self.now = 0.0
        self.sleeps = []

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds

    def clock(self):
        return self.now


def make(clipboard=None, held=lambda: (), on_key=None):
    keyboard = FakeKeyboard(on_key)
    clock = FakeTime()
    expander = Expander(keyboard=keyboard, clipboard=clipboard or FakeClipboard(),
                        held_modifiers=held, sleep=clock.sleep, clock=clock.clock)
    return expander, keyboard, clock


def backspaces(keyboard):
    return sum(1 for e in keyboard.events if e == ("tap", Key.backspace))


ADDR = Match(";addr", "123 Example St\nSpringfield")


# Erasing the shortcut

@pytest.mark.parametrize("shortcut", [";a", ";addr", ";café", "→"])
def test_one_backspace_per_shortcut_character(shortcut):
    expander, keyboard, _ = make()
    expander.expand(Match(shortcut, "x"), char_delay_ms=10)
    assert backspaces(keyboard) == len(shortcut)


def test_backspaces_come_before_the_message():
    expander, keyboard, _ = make()
    expander.expand(ADDR, char_delay_ms=10)
    first_typed = next(i for i, e in enumerate(keyboard.events) if e[0] == "type")
    assert all(e == ("tap", Key.backspace) for e in keyboard.events[:5])
    assert first_typed == 5


# Typing with a delay

def test_typed_message_comes_out_right():
    expander, keyboard, _ = make()
    expander.expand(ADDR, char_delay_ms=10)
    assert keyboard.typed() == "123 Example St\nSpringfield"


def test_line_breaks_are_typed_as_enter_and_tabs_as_tab():
    expander, keyboard, _ = make()
    expander.expand(Match(";x", "a\r\nb\rc\nd\te"), char_delay_ms=10)
    assert ("tap", Key.enter) in keyboard.events
    assert ("tap", Key.tab) in keyboard.events
    assert keyboard.typed() == "a\nb\nc\nd\te"  # \r\n and \r become one Enter each


def test_waits_the_delay_after_every_character():
    expander, _, clock = make()
    expander.expand(Match(";x", "abc\nd"), char_delay_ms=40)
    assert clock.sleeps == [0.04] * 5


def test_non_english_text_is_typed():
    expander, keyboard, _ = make()
    expander.expand(Match(";x", "café 日本語 👍"), char_delay_ms=5)
    assert keyboard.typed() == "café 日本語 👍"


def test_typing_does_not_touch_the_clipboard():
    clipboard = FakeClipboard()
    expander, _, _ = make(clipboard)
    expander.expand(ADDR, char_delay_ms=10)
    assert clipboard.writes == []


# Pasting instantly

def ctrl_v_pressed(keyboard):
    events = keyboard.events
    i = events.index(("press", Key.ctrl))
    return events[i:i + 3] == [("press", Key.ctrl), ("tap", "v"), ("release", Key.ctrl)]


def test_delay_zero_pastes_with_ctrl_v():
    clipboard = FakeClipboard()
    expander, keyboard, _ = make(clipboard)
    expander.expand(ADDR, char_delay_ms=0)
    assert ctrl_v_pressed(keyboard)
    assert keyboard.typed() == ""  # nothing typed character by character
    assert backspaces(keyboard) == len(";addr")


def test_paste_uses_windows_line_breaks():
    clipboard = FakeClipboard()
    expander, _, _ = make(clipboard)
    expander.expand(Match(";x", "a\nb\r\nc"), char_delay_ms=0)
    assert clipboard.writes == ["a\r\nb\r\nc"]


def test_old_clipboard_text_is_put_back_after_pasting():
    clipboard = FakeClipboard(ClipboardContents("text", "something I copied"))
    expander, _, clock = make(clipboard)
    expander.expand(ADDR, char_delay_ms=0)
    assert clipboard.contents == ClipboardContents("text", "something I copied")
    assert PASTE_SETTLE in clock.sleeps  # gave the app time to paste first


def test_empty_clipboard_is_left_empty():
    clipboard = FakeClipboard(ClipboardContents("empty"))
    expander, _, _ = make(clipboard)
    expander.expand(ADDR, char_delay_ms=0)
    assert clipboard.contents == ClipboardContents("empty")


def test_image_on_the_clipboard_is_kept_by_typing_instead():
    clipboard = FakeClipboard(ClipboardContents("other"))
    expander, keyboard, clock = make(clipboard)
    expander.expand(ADDR, char_delay_ms=0)
    assert clipboard.writes == []
    assert clipboard.contents == ClipboardContents("other")
    assert keyboard.typed() == ADDR.message
    assert clock.sleeps == []  # typed with no delay


@pytest.mark.parametrize("fail", ["read", "write"])
def test_busy_clipboard_falls_back_to_typing(fail):
    expander, keyboard, _ = make(FakeClipboard(fail=fail))
    expander.expand(ADDR, char_delay_ms=0)
    assert keyboard.typed() == ADDR.message


# Waiting for the hotkey to be released

def test_waits_for_modifiers_to_be_released_before_any_key():
    held = {"count": 0}

    def held_modifiers():
        held["count"] += 1
        return {Key.ctrl} if held["count"] <= 5 else set()

    expander, keyboard, clock = make(held=held_modifiers)
    expander.expand(ADDR, char_delay_ms=10)
    assert clock.sleeps[:5] == [0.01] * 5  # polled while Ctrl was down
    assert ("release", Key.ctrl) not in keyboard.events  # it was let go, not forced
    assert keyboard.typed() == ADDR.message


def test_releases_stuck_modifiers_after_a_second():
    expander, keyboard, clock = make(held=lambda: {Key.ctrl, Key.shift})
    expander.expand(ADDR, char_delay_ms=10)
    assert clock.now >= MODIFIER_WAIT
    released = {key for action, key in keyboard.events if action == "release"}
    assert released == {Key.ctrl, Key.shift}
    assert keyboard.typed() == ADDR.message


# While it types

def test_is_typing_only_while_expanding():
    seen = []
    expander, _, _ = make(on_key=lambda: seen.append(expander.is_typing))
    assert not expander.is_typing
    expander.expand(ADDR, char_delay_ms=10)
    assert seen and all(seen)
    assert not expander.is_typing


def test_is_typing_resets_even_if_typing_fails():
    def boom():
        raise RuntimeError("keyboard unplugged")

    expander, _, _ = make(on_key=boom)
    with pytest.raises(RuntimeError):
        expander.expand(ADDR, char_delay_ms=10)
    assert not expander.is_typing


# The real Windows clipboard

@pytest.mark.skipif(sys.platform != "win32", reason="Windows clipboard")
def test_real_clipboard_round_trip():
    from extender.clipboard import WindowsClipboard

    clipboard = WindowsClipboard()
    saved = clipboard.read()
    if saved.kind == "other":
        pytest.skip("the clipboard holds an image or files; not touching it")
    try:
        clipboard.write_text("Text Extender test ✓ café\r\nline 2")
        assert clipboard.read() == ClipboardContents("text", "Text Extender test ✓ café\r\nline 2")
        clipboard.clear()
        assert clipboard.read().kind == "empty"
    finally:
        clipboard.restore(saved)
    assert clipboard.read() == saved
