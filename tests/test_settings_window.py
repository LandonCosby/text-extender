"""The settings window (plan step 7).

The real window is created (hidden) and driven by calling its buttons and handlers.
Saving goes to a recorder instead of the config file.
"""

import json
from types import SimpleNamespace

import pytest

tk = pytest.importorskip("tkinter")

from extender.config import Config, ConfigError
from extender.settings_window import (
    SettingsWindow,
    count,
    describe_hotkey,
    describe_speed,
    hotkey_from_keys,
    hotkey_warning,
    matches_search,
    message_preview,
    PREVIEW_TEXT,
)


class Recorder:
    """Stands in for saving: remembers each config, or fails if told to."""

    def __init__(self):
        self.saved = []
        self.fail_with = None

    def __call__(self, config):
        if self.fail_with:
            raise self.fail_with
        self.saved.append(config)


@pytest.fixture
def recorder():
    return Recorder()


class FakeStartup:
    """Stands in for the Windows startup list."""

    def __init__(self, enabled=False, fail=False):
        self.enabled = enabled
        self.fail = fail

    def is_enabled(self):
        return self.enabled

    def enable(self):
        if self.fail:
            raise PermissionError(13, "Access is denied")
        self.enabled = True

    def disable(self):
        if self.fail:
            raise PermissionError(13, "Access is denied")
        self.enabled = False


@pytest.fixture
def make_window(root, recorder):
    def make(config=None, answer=True, startup=None, file_path=""):
        events = []
        window = SettingsWindow(
            root,
            config or Config(snippets={";sig": "Best,\nYour Name", ";addr": "123 Example St"}),
            on_change=recorder,
            on_capture_start=lambda: events.append("paused"),
            on_capture_end=lambda: events.append("resumed"),
            confirm=lambda title, question: (events.append(("asked", question)), answer)[1],
            startup=startup or FakeStartup(),
            ask_open_path=lambda: str(file_path),
            ask_save_path=lambda: str(file_path),
        )
        window.events = events
        return window
    return make


def key(keysym):
    return SimpleNamespace(keysym=keysym)


def fill_form(window, shortcut, message):
    window.shortcut_var.set(shortcut)
    window.message_text.delete("1.0", "end")
    window.message_text.insert("1.0", message)


def select(window, shortcut):
    window.tree.selection_set(shortcut)
    window.load_selected()


def listed(window):
    return [window.tree.item(i, "values") for i in window.tree.get_children()]


# Small helpers

@pytest.mark.parametrize("modifiers, keysym, expected", [
    ({"ctrl"}, "space", "<ctrl>+<space>"),
    ({"alt", "ctrl"}, "e", "<ctrl>+<alt>+e"),
    ({"shift", "ctrl"}, "E", "<ctrl>+<shift>+e"),  # Shift gives a capital; the key is still e
    ({"cmd"}, "F5", "<cmd>+<f5>"),
    ({"ctrl"}, "semicolon", "<ctrl>+;"),
    ({"ctrl", "shift"}, "exclam", "<ctrl>+<shift>+1"),
    ({"ctrl"}, "Next", "<ctrl>+<page_down>"),
])
def test_hotkey_from_keys(modifiers, keysym, expected):
    assert hotkey_from_keys(modifiers, keysym) == expected


@pytest.mark.parametrize("keysym", ["Caps_Lock", "Print", "Num_Lock", "F25", "odiaeresis"])
def test_unusable_keys_give_none(keysym):
    assert hotkey_from_keys({"ctrl"}, keysym) is None


@pytest.mark.parametrize("hotkey, text", [
    ("<ctrl>+<space>", "Ctrl+Space"),
    ("<ctrl>+<alt>+e", "Ctrl+Alt+E"),
    ("<cmd>+<f12>", "Win+F12"),
    ("<ctrl>+<page_up>", "Ctrl+Page Up"),
])
def test_describe_hotkey(hotkey, text):
    assert describe_hotkey(hotkey) == text


def test_hotkey_warnings():
    assert "Copy" in hotkey_warning("<ctrl>+c")
    assert "Switch windows" in hotkey_warning("<alt>+<tab>")
    assert "AltGr" in hotkey_warning("<ctrl>+<alt>+e")
    assert hotkey_warning("<ctrl>+<space>") is None
    assert hotkey_warning("<ctrl>+<alt>+<f2>") is None


def test_message_preview():
    assert message_preview("Hello") == "Hello"
    assert message_preview("Best,\nYour Name") == "Best, ↵…"
    long = "x" * 100
    assert message_preview(long) == "x" * 48 + "…"


def test_describe_speed():
    assert describe_speed(0) == "Instant (paste)"
    assert describe_speed(40) == "40 ms per character"
    assert describe_speed(1) == "25 ms per character"  # typed at the safe minimum anyway


# The snippet list

def test_lists_snippets_in_order(make_window):
    window = make_window()
    assert listed(window) == [(";sig", "Best, ↵…"), (";addr", "123 Example St")]


def test_opening_the_window_saves_nothing(make_window, recorder, root):
    make_window(Config(char_delay_ms=30))
    root.update()
    root.after(500)  # longer than the slider's save delay
    root.update()
    assert recorder.saved == []


def test_shows_the_current_settings(make_window):
    window = make_window(Config(hotkey="<ctrl>+<alt>+<f2>", char_delay_ms=30))
    assert window.hotkey_label.cget("text") == "Ctrl+Alt+F2"
    assert window.speed_value() == 30
    assert window.speed_label.cget("text") == "30 ms per character"


def test_selecting_a_snippet_loads_it_into_the_form(make_window):
    window = make_window()
    select(window, ";sig")
    assert window.form_values() == (";sig", "Best,\nYour Name")


# Adding, editing, deleting

def test_add_a_snippet(make_window, recorder):
    window = make_window()
    window.new_snippet()
    fill_form(window, ";hi", "Hello there!\nSecond line")
    assert window.save_snippet()
    assert recorder.saved[-1].snippets[";hi"] == "Hello there!\nSecond line"
    assert (";hi", "Hello there! ↵…") in listed(window)
    assert window.tree.selection() == (";hi",)
    assert "Saved ;hi" in window.status.cget("text")


def test_spaces_around_the_shortcut_are_trimmed(make_window, recorder):
    window = make_window()
    fill_form(window, "  ;hi  ", "Hello")
    window.save_snippet()
    assert ";hi" in recorder.saved[-1].snippets


def test_duplicate_shortcut_is_refused(make_window, recorder):
    window = make_window()
    window.new_snippet()
    fill_form(window, ";sig", "Another")
    assert not window.save_snippet()
    assert recorder.saved == []
    assert "already" in window.status.cget("text")


@pytest.mark.parametrize("shortcut, message, problem", [
    ("", "Hello", "empty"),
    ("two words", "Hello", "spaces"),
    (";hi", "   ", "empty"),
])
def test_bad_snippets_are_refused_with_a_reason(make_window, recorder, shortcut, message, problem):
    window = make_window()
    fill_form(window, shortcut, message)
    assert not window.save_snippet()
    assert recorder.saved == []
    assert problem in window.status.cget("text")


def test_edit_a_snippet(make_window, recorder):
    window = make_window()
    select(window, ";addr")
    fill_form(window, ";addr", "456 New Rd")
    window.save_snippet()
    assert recorder.saved[-1].snippets[";addr"] == "456 New Rd"


def test_rename_a_snippet_keeps_its_place(make_window, recorder):
    window = make_window()
    select(window, ";sig")
    fill_form(window, ";signature", "Best,\nYour Name")
    window.save_snippet()
    assert list(recorder.saved[-1].snippets) == [";signature", ";addr"]
    assert [row[0] for row in listed(window)] == [";signature", ";addr"]


def test_delete_a_snippet_after_confirming(make_window, recorder):
    window = make_window(answer=True)
    select(window, ";sig")
    assert window.delete_snippet()
    assert ("asked", "Delete the snippet ;sig?") in window.events
    assert list(recorder.saved[-1].snippets) == [";addr"]
    assert [row[0] for row in listed(window)] == [";addr"]
    assert window.form_values() == ("", "")


def test_delete_can_be_cancelled(make_window, recorder):
    window = make_window(answer=False)
    select(window, ";sig")
    assert not window.delete_snippet()
    assert recorder.saved == []


def test_delete_needs_a_selected_snippet(make_window, recorder):
    window = make_window()
    window.new_snippet()
    assert not window.delete_snippet()


def test_failed_save_changes_nothing(make_window, recorder):
    recorder.fail_with = OSError("Disk is full")
    window = make_window()
    fill_form(window, ";hi", "Hello")
    assert not window.save_snippet()
    assert ";hi" not in window.config.snippets
    assert ";hi" not in [row[0] for row in listed(window)]
    assert "Disk is full" in window.status.cget("text")


# Recording a new hotkey

def test_changing_the_hotkey(make_window, recorder):
    window = make_window()
    window.start_hotkey_capture()
    assert window.events == ["paused"]  # so the current hotkey reaches the window
    assert "Press the new hotkey" in window.hotkey_label.cget("text")
    window.capture_key_press(key("Control_L"))
    window.capture_key_press(key("Alt_L"))
    window.capture_key_press(key("F2"))
    assert recorder.saved[-1].hotkey == "<ctrl>+<alt>+<f2>"
    assert window.hotkey_label.cget("text") == "Ctrl+Alt+F2"
    assert "resumed" in window.events
    assert not window.capturing


def test_escape_cancels_recording(make_window, recorder):
    window = make_window()
    window.start_hotkey_capture()
    window.capture_key_press(key("Escape"))
    assert recorder.saved == []
    assert window.events == ["paused", "resumed"]
    assert window.hotkey_label.cget("text") == "Ctrl+Space"


def test_releasing_a_modifier_forgets_it(make_window, recorder):
    window = make_window()
    window.start_hotkey_capture()
    window.capture_key_press(key("Shift_L"))
    window.capture_key_release(key("Shift_L"))
    window.capture_key_press(key("Control_L"))
    window.capture_key_press(key("F3"))
    assert recorder.saved[-1].hotkey == "<ctrl>+<f3>"


def test_a_key_without_a_modifier_is_refused_and_recording_continues(make_window, recorder):
    window = make_window()
    window.start_hotkey_capture()
    window.capture_key_press(key("e"))
    assert recorder.saved == []
    assert window.capturing
    assert "Ctrl, Alt, Shift or Win" in window.status.cget("text")
    window.capture_key_press(key("Control_L"))
    window.capture_key_press(key("F4"))
    assert recorder.saved[-1].hotkey == "<ctrl>+<f4>"


def test_an_unusable_key_is_refused_and_recording_continues(make_window, recorder):
    window = make_window()
    window.start_hotkey_capture()
    window.capture_key_press(key("Control_L"))
    window.capture_key_press(key("Caps_Lock"))
    assert window.capturing
    assert "can't be used" in window.status.cget("text")


def test_clashing_hotkey_asks_first_and_can_be_declined(make_window, recorder):
    window = make_window(answer=False)
    window.start_hotkey_capture()
    window.capture_key_press(key("Control_L"))
    window.capture_key_press(key("c"))
    assert any(e[0] == "asked" and "Copy" in e[1] for e in window.events if isinstance(e, tuple))
    assert recorder.saved == []
    assert window.hotkey_label.cget("text") == "Ctrl+Space"


def test_clashing_hotkey_can_be_accepted(make_window, recorder):
    window = make_window(answer=True)
    window.start_hotkey_capture()
    window.capture_key_press(key("Control_L"))
    window.capture_key_press(key("c"))
    assert recorder.saved[-1].hotkey == "<ctrl>+c"


# Quitting

def test_no_quit_button_unless_quitting_is_possible(make_window):
    assert make_window().quit_button is None


def test_quit_button_ends_the_app(root, recorder):
    quits = []
    window = SettingsWindow(root, Config(), on_change=recorder, on_quit=lambda: quits.append(True))
    assert window.quit_button.cget("text") == "Quit Text Extender"
    window.quit_button.invoke()
    assert quits == [True]
    assert recorder.saved == []  # nothing to save: changes were already saved


def test_quitting_while_recording_a_hotkey_resumes_the_listener_first(root, recorder):
    events = []
    window = SettingsWindow(root, Config(), on_change=recorder,
                            on_capture_start=lambda: events.append("paused"),
                            on_capture_end=lambda: events.append("resumed"),
                            on_quit=lambda: events.append("quit"))
    window.start_hotkey_capture()
    window.quit_app()
    assert events == ["paused", "resumed", "quit"]


# Typing speed

def test_moving_the_slider_saves_the_speed(make_window, recorder):
    window = make_window()
    window.speed_scale.set(42)
    window.speed_moved()
    assert window.speed_label.cget("text") == "42 ms per character"
    window.save_speed()  # normally runs a moment after the slider stops
    assert recorder.saved[-1].char_delay_ms == 42


def test_slider_snaps_up_to_the_fastest_safe_speed(make_window, recorder):
    window = make_window()
    window.speed_scale.set(5)
    window.speed_moved()
    assert window.speed_label.cget("text") == "25 ms per character"
    window.save_speed()
    assert recorder.saved[-1].char_delay_ms == 25


def test_unchanged_speed_is_not_saved_again(make_window, recorder):
    window = make_window()
    window.save_speed()
    assert recorder.saved == []


def test_preview_shows_the_text_instantly_at_zero(make_window):
    window = make_window(Config(char_delay_ms=0))
    window.preview_speed()
    assert window.preview_label.cget("text") == PREVIEW_TEXT


def test_preview_types_the_text_out(make_window, root):
    window = make_window(Config(char_delay_ms=1))
    window.preview_speed()
    assert window.preview_label.cget("text") == ""  # starts empty
    for _ in range(400):
        root.update()
        if window.preview_label.cget("text") == PREVIEW_TEXT:
            break
        root.after(2)
    assert window.preview_label.cget("text") == PREVIEW_TEXT


# Appearance

def test_starts_in_the_saved_theme(make_window):
    window = make_window(Config(theme="dark"))
    assert window.theme_var.get() == "dark"
    assert window.message_text.cget("background") == window.palette["field"]


def test_switching_to_dark_mode_saves_and_recolours(make_window, recorder):
    window = make_window()
    light_field = window.message_text.cget("background")
    window.theme_buttons["dark"].invoke()
    assert recorder.saved[-1].theme == "dark"
    assert window.message_text.cget("background") != light_field
    assert "dark mode" in window.status.cget("text")


def test_failed_theme_save_keeps_the_old_theme(make_window, recorder):
    recorder.fail_with = OSError("Disk is full")
    window = make_window()
    window.theme_buttons["dark"].invoke()
    assert window.theme_var.get() == "light"
    assert window.config.theme == "light"



# Searching

def test_matches_search():
    assert matches_search("", ";sig", "Best")
    assert matches_search("SIG", ";sig", "Best")
    assert matches_search("best", ";sig", "Best,\nYour Name")
    assert not matches_search("zzz", ";sig", "Best")


def test_search_filters_the_list(make_window):
    window = make_window()
    window.search_var.set("example")
    assert [row[0] for row in listed(window)] == [";addr"]
    window.search_var.set("")
    assert [row[0] for row in listed(window)] == [";sig", ";addr"]


def test_search_with_no_results_says_so(make_window):
    window = make_window()
    window.search_var.set("zzz")
    assert listed(window) == []
    assert window.no_results.winfo_manager() == "place"
    window.search_var.set("")
    assert window.no_results.winfo_manager() == ""


def test_search_keeps_unsaved_changes_in_the_form(make_window):
    window = make_window()
    select(window, ";sig")
    fill_form(window, ";sig", "Changed but not saved")
    window.search_var.set("sig")
    window.master.update()
    assert window.form_values() == (";sig", "Changed but not saved")


def test_saving_a_snippet_the_search_hides_clears_the_search(make_window):
    window = make_window()
    window.search_var.set("example")
    window.new_snippet()
    fill_form(window, ";hi", "Hello")
    assert window.save_snippet()
    assert window.search_var.get() == ""
    assert window.tree.selection() == (";hi",)


def test_search_hint_hides_while_there_is_text(make_window):
    window = make_window()
    assert window.search_hint.winfo_manager() == "place"
    window.search_var.set("x")
    assert window.search_hint.winfo_manager() == ""


# Automatic expansion

def test_auto_expand_checkbox_saves_the_setting(make_window, recorder):
    window = make_window()
    assert window.auto_var.get() is False
    window.auto_check.invoke()
    assert recorder.saved[-1].auto_expand is True
    window.auto_check.invoke()
    assert recorder.saved[-1].auto_expand is False


def test_failed_auto_expand_save_unticks_the_box(make_window, recorder):
    recorder.fail_with = OSError("Disk is full")
    window = make_window()
    window.auto_check.invoke()
    assert window.auto_var.get() is False
    assert window.config.auto_expand is False


# Importing and exporting snippets

def write_snippets(path, snippets):
    path.write_text(json.dumps({"snippets": snippets}), encoding="utf-8")


def test_count():
    assert count(1, "snippet") == "1 snippet"
    assert count(0, "snippet") == "0 snippets"
    assert count(3, "snippet") == "3 snippets"


def test_export_writes_every_snippet(make_window, tmp_path):
    file = tmp_path / "out.json"
    window = make_window(file_path=file)
    assert window.export_snippets()
    assert json.loads(file.read_text(encoding="utf-8")) == {
        "snippets": {";sig": "Best,\nYour Name", ";addr": "123 Example St"}}
    assert "Exported 2 snippets to out.json" in window.status.cget("text")


def test_export_with_no_snippets_says_so(make_window, tmp_path):
    window = make_window(Config(), file_path=tmp_path / "out.json")
    assert not window.export_snippets()
    assert not (tmp_path / "out.json").exists()
    assert "no snippets" in window.status.cget("text")


def test_cancelling_export_or_import_does_nothing(make_window, recorder):
    window = make_window(file_path="")
    assert not window.export_snippets()
    assert not window.import_snippets()
    assert recorder.saved == []


def test_import_adds_new_snippets(make_window, recorder, tmp_path):
    file = tmp_path / "in.json"
    write_snippets(file, {";hi": "Hello", ";sig": "Best,\nYour Name"})
    window = make_window(file_path=file)
    assert window.import_snippets()
    assert recorder.saved[-1].snippets[";hi"] == "Hello"
    assert (";hi", "Hello") in listed(window)
    assert window.events == []  # nothing clashed, so nothing to ask
    assert "Imported 1 new snippet." in window.status.cget("text")


@pytest.mark.parametrize("answer, expected", [(True, "theirs"), (False, "Best,\nYour Name")])
def test_import_asks_before_replacing_a_different_message(make_window, recorder, tmp_path, answer, expected):
    file = tmp_path / "in.json"
    write_snippets(file, {";sig": "theirs", ";hi": "Hello"})
    window = make_window(answer=answer, file_path=file)
    assert window.import_snippets()
    assert window.events[0][0] == "asked"
    assert "1 shortcut in the file already exists" in window.events[0][1]
    assert recorder.saved[-1].snippets[";sig"] == expected


def test_import_with_nothing_new_saves_nothing(make_window, recorder, tmp_path):
    file = tmp_path / "in.json"
    write_snippets(file, {";addr": "123 Example St"})
    window = make_window(file_path=file)
    assert window.import_snippets()
    assert recorder.saved == []
    assert "Nothing to import" in window.status.cget("text")


def test_import_of_a_bad_file_changes_nothing(make_window, recorder, tmp_path):
    file = tmp_path / "in.json"
    file.write_text("not json", encoding="utf-8")
    window = make_window(file_path=file)
    assert not window.import_snippets()
    assert recorder.saved == []
    assert "valid JSON" in window.status.cget("text")


# Starting with Windows

def test_startup_box_shows_the_current_state(make_window):
    assert make_window(startup=FakeStartup(enabled=True)).startup_var.get()
    assert not make_window(startup=FakeStartup(enabled=False)).startup_var.get()


def test_ticking_the_startup_box_turns_it_on_and_off(make_window):
    startup = FakeStartup()
    window = make_window(startup=startup)
    window.startup_var.set(True)
    assert window.startup_toggled()
    assert startup.enabled
    window.startup_var.set(False)
    assert window.startup_toggled()
    assert not startup.enabled
    assert "won't start" in window.status.cget("text")


def test_startup_box_goes_back_if_windows_refuses(make_window):
    window = make_window(startup=FakeStartup(fail=True))
    window.startup_var.set(True)
    assert not window.startup_toggled()
    assert not window.startup_var.get()
    assert "Access is denied" in window.status.cget("text")
