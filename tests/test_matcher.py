"""Finding the shortcut that was just typed (plan step 4)."""

import pytest
from pynput.keyboard import KeyCode

from extender.buffer import TypedBuffer
from extender.matcher import Match, find_match

SNIPPETS = {
    ";addr": "123 Example St\nSpringfield",
    ";addr2": "456 Second Ave",
    ";sig": "Best,\nYour Name",
    "brb": "be right back",
}


def test_finds_the_shortcut_at_the_end():
    assert find_match("hello ;sig", SNIPPETS) == Match(";sig", "Best,\nYour Name")


def test_whole_typed_text_can_be_the_shortcut():
    assert find_match(";sig", SNIPPETS) == Match(";sig", "Best,\nYour Name")


def test_longest_shortcut_wins_when_one_is_a_prefix_of_another():
    assert find_match("my ;addr2", SNIPPETS).shortcut == ";addr2"
    assert find_match("my ;addr", SNIPPETS).shortcut == ";addr"


def test_longest_wins_whatever_order_the_snippets_were_saved_in():
    reversed_order = dict(reversed(list(SNIPPETS.items())))
    assert find_match("my ;addr2", reversed_order).shortcut == ";addr2"


def test_longest_wins_when_one_shortcut_ends_another():
    snippets = {"ty": "thank you", ";ty": "Thank you very much!"}
    assert find_match("ok ;ty", snippets).shortcut == ";ty"
    assert find_match("ok ty", snippets).shortcut == "ty"


@pytest.mark.parametrize("typed", [
    "",
    "nothing here",
    ";sig ",       # space typed after the shortcut
    ";si",         # not finished
    ";sigs",       # typed past it
    ";SIG",        # different case
    ";addr is",    # shortcut isn't at the end
])
def test_no_match(typed):
    assert find_match(typed, SNIPPETS) is None


def test_no_snippets_means_no_match():
    assert find_match(";sig", {}) is None


def test_matching_is_case_sensitive():
    snippets = {";Sig": "Formal", ";sig": "casual"}
    assert find_match(";Sig", snippets).message == "Formal"
    assert find_match(";sig", snippets).message == "casual"


@pytest.mark.parametrize("typed", ["thanksbrb", "ok.brb", "(brb", "x;sig"])
def test_shortcut_straight_after_other_characters_does_not_match(typed):
    assert find_match(typed, SNIPPETS) is None


@pytest.mark.parametrize("typed", ["thanks brb", "brb", "line one\nbrb", "line one\r\nbrb", "col\tbrb"])
def test_shortcut_after_a_space_line_break_or_at_the_start_matches(typed):
    assert find_match(typed, SNIPPETS) == Match("brb", "be right back")


def test_needing_a_space_picks_the_right_one_of_overlapping_shortcuts():
    snippets = {"ty": "thank you", ";ty": "Thank you very much!"}
    assert find_match("ok ;ty", snippets).shortcut == ";ty"  # "ty" follows ";", so only ";ty" counts
    assert find_match("ok;ty", snippets) is None  # neither stands alone


def test_non_english_shortcuts():
    snippets = {";café": "Café Example, 1 Rue de Paris", "→": "arrow"}
    assert find_match("meet at ;café", snippets).message == "Café Example, 1 Rue de Paris"
    assert find_match("go →", snippets).message == "arrow"


def test_works_with_the_typed_text_buffer():
    buffer = TypedBuffer()
    for ch in "see you ;addr2":
        buffer.add(ch)
    assert find_match(buffer.text, SNIPPETS).shortcut == ";addr2"
    buffer.key_pressed(KeyCode.from_char("x"))
    assert find_match(buffer.text, SNIPPETS) is None
