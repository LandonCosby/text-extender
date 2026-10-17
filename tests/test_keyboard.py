"""Typing through Windows' SendInput (extender/keyboard.py), checked without sending
anything: the events are captured instead."""

from pynput.keyboard import Key, KeyCode

from extender.keyboard import (
    KEYEVENTF_EXTENDEDKEY,
    KEYEVENTF_KEYUP,
    KEYEVENTF_UNICODE,
    WindowsKeyboard,
)


def capture():
    calls = []
    keyboard = WindowsKeyboard(send=lambda events: calls.append(
        [(e.u.ki.wVk, e.u.ki.wScan, e.u.ki.dwFlags) for e in events]))
    return keyboard, calls


def test_letters_are_sent_as_unicode_with_no_shift():
    keyboard, calls = capture()
    keyboard.type("Sa")
    assert calls == [
        [(0, ord("S"), KEYEVENTF_UNICODE), (0, ord("S"), KEYEVENTF_UNICODE | KEYEVENTF_KEYUP)],
        [(0, ord("a"), KEYEVENTF_UNICODE), (0, ord("a"), KEYEVENTF_UNICODE | KEYEVENTF_KEYUP)],
    ]


def test_an_emoji_is_sent_whole_in_one_call():
    keyboard, calls = capture()
    keyboard.type("👍")
    assert len(calls) == 1  # both halves together
    units = [scan for _, scan, flags in calls[0] if not flags & KEYEVENTF_KEYUP]
    assert units == [0xD83D, 0xDC4D]  # the two UTF-16 halves of 👍


def test_keys_are_sent_by_key_code():
    keyboard, calls = capture()
    keyboard.tap(Key.backspace)
    assert calls == [[(0x08, 0, 0), (0x08, 0, KEYEVENTF_KEYUP)]]


def test_ctrl_v_uses_the_v_key_code():
    keyboard, calls = capture()
    keyboard.press(Key.ctrl)
    keyboard.tap(KeyCode.from_vk(0x56))
    keyboard.release(Key.ctrl)
    assert calls == [[(0x11, 0, 0)], [(0x56, 0, 0), (0x56, 0, KEYEVENTF_KEYUP)], [(0x11, 0, KEYEVENTF_KEYUP)]]


def test_navigation_keys_are_marked_extended():
    keyboard, calls = capture()
    keyboard.tap(Key.delete)
    assert all(flags & KEYEVENTF_EXTENDEDKEY for _, _, flags in calls[0])


def test_enter_and_tab():
    keyboard, calls = capture()
    keyboard.tap(Key.enter)
    keyboard.tap(Key.tab)
    assert [c[0][0] for c in calls] == [0x0D, 0x09]
