"""Loading, saving and validating snippets and settings (plan step 2).

Every test uses a temporary folder, so the real config in %APPDATA% is never touched.
"""

import json

import pytest

from extender import config as cfg
from extender.config import Config, ConfigError


@pytest.fixture
def path(tmp_path):
    return tmp_path / "TextExtender" / "config.json"


def damaged_backups(path):
    return list(path.parent.glob("config.damaged-*.json"))


# Where it's stored

def test_default_path_is_in_appdata(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    assert cfg.default_path() == tmp_path / "TextExtender" / "config.json"


def test_load_and_save_use_the_default_path(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    cfg.save(Config(snippets={";hi": "Hello!"}))
    assert (tmp_path / "TextExtender" / "config.json").exists()
    assert cfg.load().snippets == {";hi": "Hello!"}


# Loading

def test_missing_file_gives_defaults(path):
    config = cfg.load(path)
    assert config == Config()
    assert config.hotkey == "<ctrl>+<space>"
    assert config.char_delay_ms == 0
    assert config.snippets == {}
    assert config.theme == "light"
    assert not path.exists()  # nothing is written until something is saved


def test_save_then_load_gives_the_same_config(path):
    original = Config(hotkey="<ctrl>+<alt>+e", char_delay_ms=25, theme="dark",
                      snippets={";addr": "123 Example St\nSpringfield", ";sig": "Best,\nYour Name"})
    cfg.save(original, path)
    assert cfg.load(path) == original


def test_line_breaks_and_non_english_text_survive(path):
    message = "Line one\nLine two\n\tindented — café, naïve, 日本語, 👍"
    cfg.save(Config(snippets={";x": message}), path)
    assert cfg.load(path).snippets[";x"] == message
    assert "café" in path.read_text(encoding="utf-8")  # stored readably, not as \u escapes


def test_snippet_order_is_kept(path):
    snippets = {";c": "3", ";a": "1", ";b": "2"}
    cfg.save(Config(snippets=snippets), path)
    assert list(cfg.load(path).snippets) == [";c", ";a", ";b"]


def test_missing_settings_are_filled_with_defaults(path):
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"snippets": {";hi": "Hello"}}), encoding="utf-8")
    config = cfg.load(path)
    assert config.hotkey == cfg.DEFAULT_HOTKEY
    assert config.char_delay_ms == cfg.DEFAULT_CHAR_DELAY_MS
    assert config.snippets == {";hi": "Hello"}
    assert config.theme == cfg.DEFAULT_THEME


def test_unknown_theme_falls_back_to_light_and_keeps_the_rest(path):
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"theme": "purple", "snippets": {";hi": "Hello"}}), encoding="utf-8")
    config = cfg.load(path)
    assert config.theme == "light"
    assert config.snippets == {";hi": "Hello"}
    assert damaged_backups(path) == []


@pytest.mark.parametrize("contents", [
    "{ not json",
    "",
    "[1, 2, 3]",
    json.dumps({"char_delay_ms": 9999}),
    json.dumps({"hotkey": "<nonsense>"}),
    json.dumps({"snippets": {"has space": "x"}}),
    json.dumps({"snippets": ["not", "a", "dict"]}),
])
def test_damaged_file_is_backed_up_and_defaults_are_used(path, contents):
    path.parent.mkdir(parents=True)
    path.write_text(contents, encoding="utf-8")
    assert cfg.load(path) == Config()
    assert not path.exists()
    backups = damaged_backups(path)
    assert len(backups) == 1
    assert backups[0].read_text(encoding="utf-8") == contents  # nothing lost


def test_backups_never_overwrite_each_other(path):
    path.parent.mkdir(parents=True)
    for contents in ("first damaged", "second damaged", "third damaged"):
        path.write_text(contents, encoding="utf-8")
        cfg.load(path)
    kept = sorted(p.read_text(encoding="utf-8") for p in path.parent.glob("config.damaged-*.json"))
    assert kept == ["first damaged", "second damaged", "third damaged"]


# Saving

def test_save_creates_the_folder(path):
    assert not path.parent.exists()
    cfg.save(Config(), path)
    assert path.exists()


def test_save_leaves_no_temporary_files(path):
    cfg.save(Config(snippets={";a": "1"}), path)
    cfg.save(Config(snippets={";a": "2"}), path)
    assert [p.name for p in path.parent.iterdir()] == ["config.json"]


def test_save_refuses_a_bad_config_and_keeps_the_old_file(path):
    cfg.save(Config(snippets={";a": "1"}), path)
    with pytest.raises(ConfigError):
        cfg.save(Config(char_delay_ms=-5), path)
    assert cfg.load(path).snippets == {";a": "1"}


# Settings rules

@pytest.mark.parametrize("hotkey", ["<ctrl>+<space>", "<ctrl>+<alt>+e", "<shift>+<f2>", "<cmd>+j"])
def test_accepts_hotkeys_with_a_modifier_and_a_key(hotkey):
    cfg.validate_hotkey(hotkey)


@pytest.mark.parametrize("hotkey, problem", [
    ("", "empty"),
    ("<ctrl>+<nonsense>", "recognise"),
    ("e", "Ctrl, Alt, Shift or Win"),  # would fire while typing
    ("<space>", "Ctrl, Alt, Shift or Win"),
    ("<ctrl>+<alt>", "a key besides"),
    ("<ctrl>+a+b", "only have one key"),
])
def test_rejects_bad_hotkeys(hotkey, problem):
    with pytest.raises(ConfigError, match=problem):
        cfg.validate_hotkey(hotkey)


@pytest.mark.parametrize("delay", [0, 1, 50, cfg.MAX_CHAR_DELAY_MS])
def test_accepts_delays_in_range(delay):
    cfg.validate_char_delay(delay)


@pytest.mark.parametrize("delay", [-1, cfg.MAX_CHAR_DELAY_MS + 1, 2.5, "10", None, True])
def test_rejects_bad_delays(delay):
    with pytest.raises(ConfigError):
        cfg.validate_char_delay(delay)


@pytest.mark.parametrize("shortcut", ["", "two words", "tab\there", "line\nbreak",
                                      "x" * (cfg.MAX_SHORTCUT_LENGTH + 1), None])
def test_rejects_bad_shortcuts(shortcut):
    with pytest.raises(ConfigError):
        cfg.validate_shortcut(shortcut)


@pytest.mark.parametrize("message", ["", "   ", "\n\n", None])
def test_rejects_empty_messages(message):
    with pytest.raises(ConfigError):
        cfg.validate_message(message)


# Editing snippets

def test_add_snippet():
    config = Config()
    config.add_snippet(";hi", "Hello!")
    assert config.snippets == {";hi": "Hello!"}


def test_add_snippet_refuses_a_duplicate_shortcut():
    config = Config(snippets={";hi": "Hello!"})
    with pytest.raises(ConfigError, match="already"):
        config.add_snippet(";hi", "Hi again")
    assert config.snippets == {";hi": "Hello!"}


def test_update_snippet_changes_the_message():
    config = Config(snippets={";hi": "Hello!"})
    config.update_snippet(";hi", ";hi", "Hi there!")
    assert config.snippets == {";hi": "Hi there!"}


def test_renaming_a_snippet_keeps_its_place():
    config = Config(snippets={";a": "1", ";b": "2", ";c": "3"})
    config.update_snippet(";b", ";bee", "two")
    assert list(config.snippets.items()) == [(";a", "1"), (";bee", "two"), (";c", "3")]


def test_renaming_onto_an_existing_shortcut_is_refused():
    config = Config(snippets={";a": "1", ";b": "2"})
    with pytest.raises(ConfigError, match="already"):
        config.update_snippet(";a", ";b", "x")
    assert config.snippets == {";a": "1", ";b": "2"}


def test_a_bad_edit_changes_nothing():
    config = Config(snippets={";a": "1"})
    with pytest.raises(ConfigError):
        config.update_snippet(";a", ";a", "   ")
    assert config.snippets == {";a": "1"}


def test_remove_snippet():
    config = Config(snippets={";a": "1", ";b": "2"})
    config.remove_snippet(";a")
    assert config.snippets == {";b": "2"}


@pytest.mark.parametrize("action", [
    lambda c: c.remove_snippet(";missing"),
    lambda c: c.update_snippet(";missing", ";x", "y"),
])
def test_editing_a_missing_snippet_is_refused(action):
    with pytest.raises(ConfigError, match="no snippet"):
        action(Config())


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_accepts_known_themes(theme):
    cfg.validate_theme(theme)


@pytest.mark.parametrize("theme", ["", "Dark", "blue", None])
def test_rejects_unknown_themes(theme):
    with pytest.raises(ConfigError):
        cfg.validate_theme(theme)
