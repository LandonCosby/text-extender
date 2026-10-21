"""Placeholders in messages: {date}, {time}, {clipboard} and {cursor}."""

from extender.placeholders import Filled, fill, windows_date, windows_time


def filled(message, clipboard="copied text"):
    return fill(message, clipboard_text=lambda: clipboard, date=lambda: "21/10/2026", now=lambda: "14:05")


def test_message_without_placeholders_is_unchanged():
    assert filled("Hello there") == Filled("Hello there", 0)


def test_date_time_and_clipboard_are_filled_in():
    assert filled("On {date} at {time}: {clipboard}").text == "On 21/10/2026 at 14:05: copied text"


def test_a_placeholder_can_be_used_more_than_once():
    assert filled("{date} / {date}").text == "21/10/2026 / 21/10/2026"


def test_empty_clipboard_gives_nothing():
    assert filled("[{clipboard}]", clipboard="").text == "[]"
    assert filled("[{clipboard}]", clipboard=None).text == "[]"


def test_sources_are_only_asked_for_when_used():
    asked = []
    fill("Hello", clipboard_text=lambda: asked.append("clipboard"), date=lambda: asked.append("date"),
         now=lambda: asked.append("time"))
    assert asked == []


def test_cursor_gives_how_far_back_to_move():
    assert filled("Dear {cursor},\nThanks") == Filled("Dear ,\nThanks", 8)


def test_cursor_counts_a_windows_line_break_once():
    assert filled("{cursor}a\r\nb").cursor_back == 3


def test_cursor_at_the_end_needs_no_moving():
    assert filled("Hello{cursor}") == Filled("Hello", 0)


def test_only_the_first_cursor_counts():
    assert filled("a{cursor}b{cursor}c") == Filled("abc", 2)


def test_cursor_counts_filled_in_placeholders_after_it():
    assert filled("{cursor} {time}") == Filled(" 14:05", 6)


def test_placeholder_text_from_the_clipboard_is_left_alone():
    assert filled("{clipboard}!", clipboard="{cursor}{date}") == Filled("{cursor}{date}!", 0)


def test_other_braces_are_kept():
    assert filled("{name} and {{date}}").text == "{name} and {21/10/2026}"


def test_real_date_and_time_give_something():
    assert windows_date().strip()
    assert windows_time().strip()
