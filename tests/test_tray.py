"""The tray icon and running in the background (plan step 8).

Uses a fake tray icon and a fake listener; the settings window is real (hidden).
"""

import threading
import uuid

import pytest

from extender import config as config_store
from extender.config import Config
from extender.tray import OpenSettingsSignal, SingleInstance, TrayApp, make_icon_image


class FakeExtender:
    def __init__(self, config):
        self.config = config
        self.paused = False
        self.stopped = False

    def pause(self):
        self.paused = True

    def resume(self):
        self.paused = False

    def set_config(self, config):
        self.config = config

    def stop(self):
        self.stopped = True


class FakeIcon:
    def __init__(self, name, image, title, menu):
        self.icon, self.title, self.menu = image, title, menu
        self.notifications = []
        self.detached = self.stopped = False
        self.menu_updates = 0

    def notify(self, message, title=None):
        self.notifications.append(message)

    def update_menu(self):
        self.menu_updates += 1

    def run_detached(self):
        self.detached = True

    def stop(self):
        self.stopped = True


@pytest.fixture
def make_tray(root, tmp_path):
    def make(config=None):
        extender = FakeExtender(config or Config(snippets={";sig": "Best,\nYour Name"}))
        quits = []
        tray = TrayApp(root, extender, config_path=tmp_path / "config.json",
                       icon_factory=FakeIcon, on_quit=lambda: (quits.append(True), root.quit()))
        tray.quits = quits
        return tray
    return make


def menu_texts(tray):
    """The menu's item names, leaving out the separator line."""
    import pystray
    return [item.text for item in tray.icon.menu.items if item is not pystray.Menu.SEPARATOR]


def click(tray, text):
    """Click a tray menu item the way pystray would (from its own thread)."""
    item = next(i for i in tray.icon.menu.items if i.text == text)
    item(tray.icon)


# The icon picture

def test_icon_image_size_and_transparency():
    image = make_icon_image(size=64)
    assert image.size == (64, 64)
    assert image.mode == "RGBA"
    assert image.getpixel((0, 0))[3] == 0  # transparent corner


def test_paused_icon_is_grey():
    active, paused = make_icon_image(), make_icon_image(paused=True)
    r, g, b, _ = active.getpixel((10, 32))
    assert b > r + 50  # blue
    r, g, b, _ = paused.getpixel((10, 32))
    assert abs(r - b) < 20  # grey


# Only one copy

def test_second_copy_is_refused_until_the_first_ends():
    name = f"Local\\TextExtenderTest-{uuid.uuid4()}"  # not the real app's name
    first = SingleInstance(name)
    second = SingleInstance(name)
    try:
        assert first.acquired
        assert not second.acquired
    finally:
        second.release()
        first.release()
    third = SingleInstance(name)
    assert third.acquired
    third.release()


# Tooltip and menu

def test_tooltip_shows_the_hotkey(make_tray):
    tray = make_tray(Config(hotkey="<ctrl>+<alt>+<f2>"))
    assert tray.icon.title == "Text Extender (Ctrl+Alt+F2)"


def test_menu_items(make_tray):
    tray = make_tray()
    assert menu_texts(tray) == ["Open settings", "Pause", "Quit"]
    assert tray.icon.menu.items[0].default  # double-clicking the icon opens settings


def test_menu_clicks_are_queued_for_the_main_thread(make_tray):
    tray = make_tray()
    click(tray, "Open settings")
    assert tray.settings_window is None  # nothing happens on pystray's thread
    tray.handle_requests()
    assert tray.settings_window is not None


def test_requests_from_another_thread(make_tray):
    tray = make_tray()
    t = threading.Thread(target=lambda: tray.request("toggle_pause"))
    t.start()
    t.join()
    tray.handle_requests()
    assert tray.extender.paused


# Settings window

def test_open_settings(make_tray):
    tray = make_tray()
    tray.open_settings()
    window = tray.settings_window
    assert window is not None
    assert window.master.winfo_exists()
    assert ";sig" in window.config.snippets


def test_opening_twice_reuses_the_window(make_tray):
    tray = make_tray()
    tray.open_settings()
    first = tray.settings_window
    tray.open_settings()
    assert tray.settings_window is first


def test_closing_the_window_keeps_the_app_running(make_tray):
    tray = make_tray()
    tray.open_settings()
    top = tray.settings_window.master
    tray.close_settings()
    assert tray.settings_window is None
    assert not top.winfo_exists()
    assert not tray.extender.stopped
    assert tray.quits == []


def test_settings_changes_are_saved_and_applied(make_tray, tmp_path):
    tray = make_tray()
    new = Config(hotkey="<ctrl>+<alt>+<f2>", snippets={";hi": "Hello"})
    tray.apply_settings(new)
    assert config_store.load(tmp_path / "config.json") == new
    assert tray.extender.config is new
    assert tray.icon.title == "Text Extender (Ctrl+Alt+F2)"


def test_saving_from_the_window_reaches_the_listener(make_tray, tmp_path):
    tray = make_tray()
    tray.open_settings()
    window = tray.settings_window
    window.new_snippet()
    window.shortcut_var.set(";hi")
    window.message_text.insert("1.0", "Hello")
    assert window.save_snippet()
    assert tray.extender.config.snippets[";hi"] == "Hello"
    assert config_store.load(tmp_path / "config.json").snippets[";hi"] == "Hello"


# Pause / Resume

def test_pause_and_resume(make_tray):
    tray = make_tray()
    active_image = tray.icon.icon
    tray.toggle_pause()
    assert tray.extender.paused
    assert menu_texts(tray) == ["Open settings", "Resume", "Quit"]
    assert tray.icon.title == "Text Extender (paused)"
    assert tray.icon.icon.tobytes() != active_image.tobytes()  # greyed out
    tray.toggle_pause()
    assert not tray.extender.paused
    assert menu_texts(tray)[1] == "Pause"


def test_recording_a_hotkey_pauses_then_resumes(make_tray):
    tray = make_tray()
    tray.open_settings()
    tray.settings_window.start_hotkey_capture()
    assert tray.extender.paused
    tray.settings_window.stop_hotkey_capture()
    assert not tray.extender.paused


def test_recording_a_hotkey_keeps_a_tray_pause(make_tray):
    tray = make_tray()
    tray.toggle_pause()
    tray.open_settings()
    tray.settings_window.start_hotkey_capture()
    tray.settings_window.stop_hotkey_capture()
    assert tray.extender.paused  # still paused, as chosen from the tray


def test_closing_the_window_while_recording_resumes(make_tray):
    tray = make_tray()
    tray.open_settings()
    tray.settings_window.start_hotkey_capture()
    tray.close_settings()
    assert not tray.extender.paused


# Staying responsive when something goes wrong

def test_a_failing_request_doesnt_stop_the_next_ones(make_tray, caplog):
    tray = make_tray()

    def broken():
        raise RuntimeError("settings window broke")

    tray.open_settings = broken
    tray.request("open")
    tray.request("toggle_pause")
    tray.handle_requests()
    assert tray.extender.paused  # the request after the failure still ran
    assert "settings window broke" in caplog.text


def test_polling_continues_after_an_error(make_tray, root):
    tray = make_tray()
    scheduled = []
    tray.root = type("FakeRoot", (), {"after": lambda self, ms, fn: scheduled.append(fn)})()
    tray.handle_requests = lambda: (_ for _ in ()).throw(RuntimeError("boom"))
    with pytest.raises(RuntimeError):
        tray._poll()
    assert scheduled == [tray._poll]  # still checks again later


def test_reopening_after_the_window_was_destroyed_some_other_way(make_tray):
    tray = make_tray()
    tray.open_settings()
    tray.settings_window.master.destroy()  # not through close_settings
    tray.open_settings()
    assert tray.settings_window.master.winfo_exists()


def test_quit_still_ends_the_app_if_a_step_fails(make_tray):
    tray = make_tray()

    def broken_stop():
        raise RuntimeError("listener wouldn't stop")

    tray.extender.stop = broken_stop
    tray.quit()
    assert tray.icon.stopped
    assert tray.quits == [True]


def test_no_more_polling_after_quit(make_tray):
    tray = make_tray()
    scheduled = []
    tray.root = type("FakeRoot", (), {"after": lambda self, ms, fn: scheduled.append(fn), "quit": lambda self: None})()
    tray.on_quit = lambda: None
    tray.request("quit")
    tray._poll()
    assert scheduled == []


# Quitting and running

def test_quit_button_in_settings_ends_the_app(make_tray):
    tray = make_tray()
    tray.open_settings()
    tray.settings_window.quit_button.invoke()
    assert tray.quits == []  # queued, so the window isn't destroyed mid-click
    tray.handle_requests()
    assert tray.quits == [True]
    assert tray.extender.stopped
    assert tray.icon.stopped
    assert tray.settings_window is None


def test_quit_stops_everything(make_tray):
    tray = make_tray()
    tray.open_settings()
    tray.quit()
    assert tray.settings_window is None
    assert tray.extender.stopped
    assert tray.icon.stopped
    assert tray.quits == [True]


def test_starting_shows_the_icon_and_opens_settings(make_tray):
    tray = make_tray()
    opened = []
    real_open = tray.open_settings
    tray.open_settings = lambda: (opened.append(True), real_open())
    tray.request("quit")  # so run() returns straight away
    tray.run()
    assert tray.icon.detached
    assert opened == [True]
    assert tray.icon.notifications == []
    assert tray.quits == [True]


def test_quiet_start_shows_a_notification_instead(make_tray):
    tray = make_tray()
    tray.request("quit")
    tray.run(show_settings=False)
    assert tray.settings_window is None
    assert "Ctrl+Space" in tray.icon.notifications[0]


# Starting it again while it's running

@pytest.fixture
def signal_name():
    return f"Local\\TextExtenderTest-{uuid.uuid4()}"  # not the real app's name


def test_a_second_launch_can_signal_the_running_copy(signal_name):
    running, second = OpenSettingsSignal(signal_name), OpenSettingsSignal(signal_name)
    try:
        assert not running.received()
        assert second.send()
        assert running.received()
        assert not running.received()  # each signal is seen once
    finally:
        second.close()
        running.close()


def test_signal_from_a_second_launch_opens_settings(make_tray, signal_name):
    tray = make_tray()
    running = OpenSettingsSignal(signal_name)
    second = OpenSettingsSignal(signal_name)
    tray.open_signal = running
    try:
        tray._poll()
        assert tray.settings_window is None  # nothing asked yet
        second.send()
        tray._poll()
        assert tray.settings_window is not None
    finally:
        tray._quitting = True  # stop _poll rescheduling itself after the test
        second.close()
        running.close()
