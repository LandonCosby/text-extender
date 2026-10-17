"""The typed-text buffer (plan step 3), fed with real pynput key objects."""

import threading

import pytest
from pynput.keyboard import Key, KeyCode

from extender.buffer import MAX_LENGTH, TypedBuffer
from extender.config import MAX_SHORTCUT_LENGTH


def type_text(buffer, text):
    for ch in text:
        buffer.key_pressed(Key.space if ch == " " else KeyCode.from_char(ch))


@pytest.fixture
def buffer():
    return TypedBuffer()


def test_starts_empty(buffer):
    assert buffer.text == ""


def test_typing_adds_characters(buffer):
    type_text(buffer, ";addr")
    assert buffer.text == ";addr"


def test_space_is_kept(buffer):
    type_text(buffer, "hi ;sig")
    assert buffer.text == "hi ;sig"


def test_capitals_and_symbols_are_kept(buffer):
    # Shift itself is ignored; the shifted character arrives as its own key.
    buffer.key_pressed(Key.shift)
    type_text(buffer, "A!@#;X")
    assert buffer.text == "A!@#;X"


def test_non_english_characters_are_kept(buffer):
    type_text(buffer, "café;ñ日")
    assert buffer.text == "café;ñ日"


def test_backspace_removes_the_last_character(buffer):
    type_text(buffer, ";addx")
    buffer.key_pressed(Key.backspace)
    type_text(buffer, "r")
    assert buffer.text == ";addr"


def test_backspace_on_empty_buffer_does_nothing(buffer):
    buffer.key_pressed(Key.backspace)
    assert buffer.text == ""


def test_keeps_only_the_most_recent_characters(buffer):
    type_text(buffer, "x" * 100 + ";end")
    assert len(buffer.text) == MAX_LENGTH
    assert buffer.text.endswith(";end")


def test_room_for_the_longest_allowed_shortcut():
    assert MAX_LENGTH > MAX_SHORTCUT_LENGTH


@pytest.mark.parametrize("key", [
    Key.enter, Key.tab, Key.esc,
    Key.left, Key.right, Key.up, Key.down,
    Key.home, Key.end, Key.page_up, Key.page_down,
    Key.f1, Key.f5, Key.menu,
])
def test_keys_that_can_move_the_cursor_clear_the_buffer(buffer, key):
    type_text(buffer, ";addr")
    buffer.key_pressed(key)
    assert buffer.text == ""


@pytest.mark.parametrize("key", [
    Key.shift, Key.shift_r, Key.ctrl_l, Key.alt_l, Key.cmd,
    Key.caps_lock, Key.num_lock, Key.insert, Key.delete,
    Key.media_volume_up, Key.media_play_pause,
])
def test_keys_that_dont_change_the_text_are_ignored(buffer, key):
    type_text(buffer, ";addr")
    buffer.key_pressed(key)
    assert buffer.text == ";addr"


@pytest.mark.parametrize("ctrl, alt", [(True, False), (False, True)])
def test_ctrl_or_alt_shortcuts_clear_the_buffer(buffer, ctrl, alt):
    # Ctrl+V, Ctrl+Z, Alt+letter and so on change the text in ways we can't follow.
    type_text(buffer, ";addr")
    buffer.key_pressed(KeyCode.from_char("v"), ctrl=ctrl, alt=alt)
    assert buffer.text == ""


def test_ctrl_backspace_clears_the_buffer(buffer):
    type_text(buffer, "word ;addr")
    buffer.key_pressed(Key.backspace, ctrl=True)  # deletes a whole word
    assert buffer.text == ""


def test_altgr_characters_count_as_typing(buffer):
    # On Windows, AltGr arrives as Ctrl + Alt with a normal character, e.g. €.
    type_text(buffer, "price")
    buffer.key_pressed(KeyCode.from_char("€"), ctrl=True, alt=True)
    assert buffer.text == "price€"


def test_keys_without_a_character_clear_the_buffer(buffer):
    type_text(buffer, ";addr")
    buffer.key_pressed(KeyCode.from_vk(0x0C))  # a key pynput has no name or character for
    assert buffer.text == ""


def test_control_characters_clear_the_buffer(buffer):
    type_text(buffer, ";addr")
    buffer.key_pressed(KeyCode.from_char("\x16"))  # what Ctrl+V can look like on Windows
    assert buffer.text == ""


def test_clear(buffer):
    type_text(buffer, ";addr")
    buffer.clear()
    assert buffer.text == ""


def test_safe_to_use_from_several_threads(buffer):
    def typist():
        for _ in range(2000):
            buffer.add("a")
            buffer.backspace()

    threads = [threading.Thread(target=typist) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert buffer.text == ""
