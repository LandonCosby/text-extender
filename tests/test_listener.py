"""Keyboard listening and the hotkey (plan step 6), with simulated key events.

handle_raw gets raw Windows key codes (as from the low-level hook) and on_press gets
pynput keys (as after pynput translates them), just like the real listener sends.
"""

import sys

import pytest
from pynput.keyboard import Key, KeyCode

from extender.config import Config, ConfigError
from extender.listener import (
    MENU_MASK_KEY,
    WM_KEYDOWN,
    WM_KEYUP,
    WM_SYSKEYDOWN,
    ParsedHotkey,
    TextExtender,
    parse_hotkey,
)
from extender.matcher import Match

VK_LCTRL, VK_LSHIFT, VK_LALT, VK_SPACE = 0xA2, 0xA0, 0xA4, 0x20
VK_RETURN, VK_TAB = 0x0D, 0x09
VK = {"e": 0x45, "f2": 0x71}


class FakeKeyboard:
    def __init__(self):
        self.taps = []

    def tap(self, key):
        self.taps.append(key)


class FakeExpander:
    def __init__(self):
        self.is_typing = False
        self.keyboard = FakeKeyboard()
        self.expanded = []

    def expand(self, match, char_delay_ms, **ending):
        self.expanded.append((match, char_delay_ms, ending) if ending else (match, char_delay_ms))


class Window:
    def __init__(self):
        self.current = 1

    def __call__(self):
        return self.current


@pytest.fixture
def app():
    config = Config(snippets={";sig": "Best,\nYour Name", ";addr": "123 Example St"}, char_delay_ms=15)
    window = Window()
    extender = TextExtender(config, expander=FakeExpander(), window=window,
                            run_in_background=lambda job: job(), sleep=lambda s: None)
    extender.test_window = window
    return extender


def type_text(app, text):
    for ch in text:
        app.on_press(Key.space if ch == " " else KeyCode.from_char(ch))


def key_down(app, vk, injected=False, msg=WM_KEYDOWN):
    return app.handle_raw(msg, vk, injected)


def key_up(app, vk, injected=False):
    return app.handle_raw(WM_KEYUP, vk, injected)


def press_hotkey(app, modifiers=(VK_LCTRL,), vk=VK_SPACE):
    """Hold the modifiers, press the key, let go. Returns whether the key was blocked."""
    for m in modifiers:
        key_down(app, m)
    blocked_down = key_down(app, vk)
    blocked_up = key_up(app, vk)
    for m in modifiers:
        key_up(app, m)
    return blocked_down, blocked_up


# Parsing hotkeys

@pytest.mark.parametrize("text, expected", [
    ("<ctrl>+<space>", ParsedHotkey(frozenset({"ctrl"}), VK_SPACE)),
    ("<ctrl>+<alt>+<f2>", ParsedHotkey(frozenset({"ctrl", "alt"}), VK["f2"])),
    ("<shift>+<cmd>+<space>", ParsedHotkey(frozenset({"shift", "cmd"}), VK_SPACE)),
])
def test_parse_hotkey(text, expected):
    assert parse_hotkey(text) == expected


@pytest.mark.skipif(sys.platform != "win32", reason="looks up the key on the Windows keyboard layout")
def test_parse_hotkey_with_a_letter():
    assert parse_hotkey("<ctrl>+<alt>+e") == ParsedHotkey(frozenset({"ctrl", "alt"}), VK["e"])


def test_parse_hotkey_rejects_bad_hotkeys():
    with pytest.raises(ConfigError):
        parse_hotkey("e")


# Typing fills the buffer

def test_typing_fills_the_buffer(app):
    type_text(app, "hi ;sig")
    assert app.buffer.text == "hi ;sig"


# The hotkey

def test_hotkey_expands_the_shortcut(app):
    type_text(app, "thanks ;sig")
    press_hotkey(app)
    assert app.expander.expanded == [(Match(";sig", "Best,\nYour Name"), 15)]


def test_hotkey_is_blocked_from_reaching_apps(app):
    type_text(app, ";sig")
    assert press_hotkey(app) == (True, True)  # both the press and the release of Space


def test_hotkey_is_blocked_even_with_no_match(app):
    type_text(app, "nothing")
    assert press_hotkey(app) == (True, True)
    assert app.expander.expanded == []


def test_no_match_calls_the_callback_and_keeps_the_buffer(app):
    calls = []
    app.on_no_match = lambda: calls.append(True)
    type_text(app, "nothing")
    press_hotkey(app)
    assert calls == [True]
    assert app.buffer.text == "nothing"


def test_buffer_is_cleared_after_expanding(app):
    type_text(app, ";sig")
    press_hotkey(app)
    assert app.buffer.text == ""


def test_modifiers_are_not_blocked(app):
    assert key_down(app, VK_LCTRL) is False
    assert key_up(app, VK_LCTRL) is False


def test_space_without_ctrl_is_just_typing(app):
    type_text(app, ";sig")
    assert key_down(app, VK_SPACE) is False
    assert app.expander.expanded == []


def test_extra_modifiers_dont_count_as_the_hotkey(app):
    type_text(app, ";sig")
    blocked, _ = press_hotkey(app, modifiers=(VK_LCTRL, VK_LSHIFT))
    assert blocked is False
    assert app.expander.expanded == []


def test_right_ctrl_works_too(app):
    type_text(app, ";sig")
    press_hotkey(app, modifiers=(0xA3,))
    assert len(app.expander.expanded) == 1


def test_alt_hotkey_taps_the_menu_mask_key(app):
    app.set_config(Config(hotkey="<ctrl>+<alt>+<f2>", snippets=app.config.snippets))
    type_text(app, ";sig")
    press_hotkey(app, modifiers=(VK_LCTRL, VK_LALT), vk=VK["f2"])
    assert app.expander.keyboard.taps == [MENU_MASK_KEY]
    assert len(app.expander.expanded) == 1


def test_ctrl_hotkey_needs_no_menu_mask(app):
    type_text(app, ";sig")
    press_hotkey(app)
    assert app.expander.keyboard.taps == []


def test_alt_hotkeys_arrive_as_system_key_messages(app):
    app.set_config(Config(hotkey="<alt>+<f2>", snippets=app.config.snippets))
    type_text(app, ";sig")
    key_down(app, VK_LALT, msg=WM_SYSKEYDOWN)
    assert key_down(app, VK["f2"], msg=WM_SYSKEYDOWN) is True
    assert len(app.expander.expanded) == 1


# Changing settings

def test_changed_hotkey_works_straight_away(app):
    app.set_config(Config(hotkey="<ctrl>+<alt>+<f2>", snippets=app.config.snippets))
    type_text(app, ";sig")
    blocked, _ = press_hotkey(app)  # the old Ctrl+Space
    assert blocked is False
    press_hotkey(app, modifiers=(VK_LCTRL, VK_LALT), vk=VK["f2"])
    assert len(app.expander.expanded) == 1


def test_bad_hotkey_is_refused_and_the_old_one_kept(app):
    with pytest.raises(ConfigError):
        app.set_config(Config(hotkey="<nonsense>"))
    assert app.hotkey == parse_hotkey("<ctrl>+<space>")


def test_changed_snippets_and_speed_are_used(app):
    app.set_config(Config(snippets={";new": "Fresh"}, char_delay_ms=0))
    type_text(app, ";new")
    press_hotkey(app)
    assert app.expander.expanded == [(Match(";new", "Fresh"), 0)]


# Ignoring things

def test_keys_the_app_types_itself_are_ignored(app):
    type_text(app, ";s")
    app.on_press(KeyCode.from_char("x"), injected=True)
    assert key_down(app, VK_LCTRL, injected=True) is False
    assert app.held == set()
    assert app.buffer.text == ";s"


def test_keys_are_ignored_while_expanding(app):
    app.expander.is_typing = True
    type_text(app, ";sig")
    assert app.buffer.text == ""
    assert press_hotkey(app)[0] is False


def test_paused_ignores_typing_and_the_hotkey(app):
    app.pause()
    type_text(app, ";sig")
    assert app.buffer.text == ""
    assert press_hotkey(app)[0] is False
    app.resume()
    type_text(app, ";sig")
    press_hotkey(app)
    assert len(app.expander.expanded) == 1


# Clearing the buffer

def test_mouse_click_clears_the_buffer(app):
    type_text(app, ";sig")
    app.on_click(10, 10, "left", pressed=True)
    assert app.buffer.text == ""


def test_mouse_release_alone_does_nothing(app):
    type_text(app, ";sig")
    app.on_click(10, 10, "left", pressed=False)
    assert app.buffer.text == ";sig"


def test_switching_windows_clears_the_buffer(app):
    type_text(app, ";si")
    app.test_window.current = 2
    type_text(app, "g")
    assert app.buffer.text == "g"


def test_switching_windows_before_the_hotkey_means_no_match(app):
    type_text(app, ";sig")
    app.test_window.current = 2  # e.g. Alt+Tab, then the hotkey in another window
    press_hotkey(app)
    assert app.expander.expanded == []


def test_ctrl_shortcuts_clear_the_buffer(app):
    type_text(app, ";sig")
    key_down(app, VK_LCTRL)
    app.on_press(KeyCode.from_char("z"))  # Ctrl+Z
    key_up(app, VK_LCTRL)
    assert app.buffer.text == ""


# Held modifiers, for the expander

def test_held_modifiers_are_tracked(app):
    key_down(app, VK_LCTRL)
    key_down(app, VK_LSHIFT)
    assert app.held_modifier_keys() == {Key.ctrl, Key.shift}
    key_up(app, VK_LCTRL)
    assert app.held_modifier_keys() == {Key.shift}


# The real listeners

@pytest.mark.skipif(sys.platform != "win32", reason="Windows keyboard hooks")
def test_real_listeners_start_and_stop():
    extender = TextExtender(Config())
    extender.start()
    assert extender.is_running()
    extender.stop()
    extender.join(timeout=2)
    assert not extender.is_running()


# Automatic expansion

SIG = Match(";sig", "Best,\nYour Name")


@pytest.fixture
def auto(app):
    app.config.auto_expand = True
    return app


def test_auto_expand_is_off_by_default(app):
    type_text(app, ";sig ")
    assert app.expander.expanded == []


@pytest.mark.parametrize("ending", [" ", ",", ".", "!", "?", ")"])
def test_space_or_punctuation_expands_and_is_kept(auto, ending):
    type_text(auto, "thanks ;sig" + ending)
    assert auto.expander.expanded == [(SIG, 15, {"typed_after": ending})]
    assert auto.buffer.text == ""


@pytest.mark.parametrize("vk, key", [(VK_RETURN, Key.enter), (VK_TAB, Key.tab)])
def test_enter_or_tab_is_held_back_and_pressed_after(auto, vk, key):
    type_text(auto, ";sig")
    assert key_down(auto, vk) is True
    assert key_up(auto, vk) is True
    assert auto.expander.expanded == [(SIG, 15, {"key_after": key})]


def test_enter_without_a_shortcut_goes_through(auto):
    type_text(auto, "hello")
    assert key_down(auto, VK_RETURN) is False
    assert key_up(auto, VK_RETURN) is False
    assert auto.expander.expanded == []


def test_shift_enter_is_left_alone(auto):
    type_text(auto, ";sig")
    key_down(auto, VK_LSHIFT)
    assert key_down(auto, VK_RETURN) is False


def test_letters_and_digits_dont_end_a_shortcut(auto):
    type_text(auto, ";sigx ;sig2 ;sig_")
    assert auto.expander.expanded == []


def test_shortcut_inside_a_word_does_not_expand(auto):
    type_text(auto, "x;sig ")
    assert auto.expander.expanded == []


def test_waits_when_a_longer_shortcut_could_follow(auto):
    auto.config.snippets = {";a": "short", ";a.b": "longer"}
    type_text(auto, ";a.b ")
    assert auto.expander.expanded == [(Match(";a.b", "longer"), 15, {"typed_after": " "})]


def test_paused_does_not_auto_expand(auto):
    auto.pause()
    type_text(auto, ";sig ")
    assert key_down(auto, VK_RETURN) is False
    assert auto.expander.expanded == []


def test_hotkey_still_works_with_auto_expand_on(auto):
    type_text(auto, ";sig")
    press_hotkey(auto)
    assert auto.expander.expanded == [(SIG, 15)]
