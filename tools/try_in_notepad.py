"""Try real expansions in Notepad (plan step 10).

Opens Notepad on a scratch file, and for each case types some text, has the app expand
it (real Backspaces, real paste or typing, real clipboard), saves, and checks what
Notepad actually contains.

    python tools/try_in_notepad.py

It takes over the keyboard for about 30 seconds: don't type or click while it runs.
Before every keystroke it checks that Notepad's scratch file is the active window and
stops straight away if not, so it can't type into anything else.

The one thing it can't do is press the real hotkey: Windows marks key presses made by
programs as "injected", and the app deliberately ignores those. So it starts from the
moment after the hotkey; pressing Ctrl+Space yourself is on the manual checklist.
"""

import ctypes
import subprocess
import sys
import tempfile
import time
from ctypes import wintypes
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pynput.keyboard import Key, KeyCode  # noqa: E402

from extender.clipboard import WindowsClipboard  # noqa: E402
from extender.keyboard import WindowsKeyboard  # noqa: E402
from extender.config import Config  # noqa: E402
from extender.expander import MIN_TYPING_DELAY_MS  # noqa: E402
from extender.listener import TextExtender  # noqa: E402

user32 = ctypes.WinDLL("user32", use_last_error=True)
WM_CLOSE = 0x0010
FILE_NAME = "text-extender-check.txt"
# Shortcut keys by key code: a typed letter wouldn't trigger Ctrl+A and so on.
VK_A, VK_S, VK_W = KeyCode.from_vk(0x41), KeyCode.from_vk(0x53), KeyCode.from_vk(0x57)

LONG = ("This is a long message to check that big snippets come through whole. " * 30).strip()
SNIPPETS = {
    ";sig": "Best,\nYour Name",
    ";addr": "123 Example St\nSpringfield\nExampleland",
    ";uni": "café — naïve — 日本語 — 👍",
    ";tab": "Name:\tYour Name\nPhone:\t555-0100",
    ";long": LONG,
}

# (name, typed text, typing delay in ms, what Notepad should contain afterwards)
CASES = [
    ("paste, two lines", "Hello ;sig", 0, "Hello Best,\nYour Name"),
    ("type, three lines", ";addr", 5, "123 Example St\nSpringfield\nExampleland"),
    ("paste, special characters", ";uni", 0, "café — naïve — 日本語 — 👍"),
    ("type, special characters", ";uni", 5, "café — naïve — 日本語 — 👍"),
    ("type, tabs", ";tab", 5, "Name:\tYour Name\nPhone:\t555-0100"),
    ("paste, long message", "Note: ;long", 0, "Note: " + LONG),
    ("no matching shortcut", "nothing here", 0, "nothing here"),
    ("shortcut not after a space", "word;sig", 0, "word;sig"),
    ("hotkey with nothing typed", "", 0, ""),
]


class NotNotepad(RuntimeError):
    """The active window isn't the scratch file in Notepad."""


def window_title(hwnd):
    buffer = ctypes.create_unicode_buffer(512)
    user32.GetWindowTextW(hwnd, buffer, 512)
    return buffer.value


def find_window(text, timeout=10):
    """The top-level window whose title contains `text`."""
    found = []
    callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def check(hwnd, _):
        if user32.IsWindowVisible(hwnd) and text in window_title(hwnd):
            found.append(hwnd)
        return True

    callback = callback_type(check)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        found.clear()
        user32.EnumWindows(callback, 0)
        if found:
            return found[0]
        time.sleep(0.2)
    return None


def ensure_notepad_active():
    title = window_title(user32.GetForegroundWindow())
    if FILE_NAME not in title:
        raise NotNotepad(f"The active window is '{title}', not Notepad's scratch file. Stopped.")


class NotepadCheck:
    def __init__(self, folder):
        self.path = Path(folder) / FILE_NAME
        self.keyboard = WindowsKeyboard()  # the same typing the app uses
        self.clipboard = WindowsClipboard()

    def shortcut(self, *keys):
        ensure_notepad_active()
        for key in keys[:-1]:
            self.keyboard.press(key)
        self.keyboard.tap(keys[-1])
        for key in reversed(keys[:-1]):
            self.keyboard.release(key)

    def clear(self):
        self.shortcut(Key.ctrl, VK_A)
        ensure_notepad_active()
        self.keyboard.tap(Key.delete)

    def save_and_read(self):
        before = self.path.stat().st_mtime_ns
        self.shortcut(Key.ctrl, VK_S)
        deadline = time.monotonic() + 5
        while self.path.stat().st_mtime_ns == before and time.monotonic() < deadline:
            time.sleep(0.05)
        time.sleep(0.2)
        text = self.path.read_text(encoding="utf-8-sig")
        return text.replace("\r\n", "\n")

    def run_case(self, app, typed, delay):
        self.clear()  # always counts as a change, so the save below rewrites the file
        app.set_config(Config(snippets=SNIPPETS, char_delay_ms=delay))
        app.buffer.clear()
        for ch in typed:
            ensure_notepad_active()
            self.keyboard.type(ch)
            time.sleep(MIN_TYPING_DELAY_MS / 1000)  # typed any faster, Notepad drops characters
            # The app ignores keys typed by programs, so tell it what was "typed".
            app.on_press(Key.space if ch == " " else KeyCode.from_char(ch))
        time.sleep(0.1)
        ensure_notepad_active()
        app.hotkey_pressed()  # what pressing Ctrl+Space would do from here
        time.sleep(0.3)
        return self.save_and_read()


def main():
    if sys.platform != "win32":
        print("This check needs Windows.")
        return 1
    folder = tempfile.mkdtemp(prefix="text-extender-check-")
    check = NotepadCheck(folder)
    check.path.write_text("", encoding="utf-8")

    saved_clipboard = check.clipboard.read()
    clipboard_note = None
    if saved_clipboard.kind == "other":
        clipboard_note = "Your clipboard holds an image or files, so it was left alone (paste cases typed instead)."
    else:
        check.clipboard.write_text("ORIGINAL CLIPBOARD")

    print("Opening Notepad. Don't type or click until it's finished (about 30 seconds)...")
    subprocess.Popen(["notepad.exe", str(check.path)])
    hwnd = find_window(FILE_NAME)
    if hwnd is None:
        print("Notepad didn't open.")
        return 1
    user32.SetForegroundWindow(hwnd)
    time.sleep(1.0)

    app = TextExtender(Config(snippets=SNIPPETS), run_in_background=lambda job: job())
    results = []
    try:
        for name, typed, delay, expected in CASES:
            got = check.run_case(app, typed, delay)
            results.append((name, got == expected, expected, got))
        clipboard_ok = (check.clipboard.read().text == "ORIGINAL CLIPBOARD") if clipboard_note is None else None
    except NotNotepad as e:
        print(f"\n{e}")
        return 1
    finally:
        # Close the scratch tab or window, then put the clipboard back.
        try:
            if FILE_NAME in window_title(user32.GetForegroundWindow()):
                check.shortcut(Key.ctrl, VK_W)  # closes just this tab in Windows 11 Notepad
                time.sleep(0.5)
            leftover = find_window(FILE_NAME, timeout=1)
            if leftover:
                user32.PostMessageW(leftover, WM_CLOSE, 0, 0)
        except NotNotepad:
            pass
        if saved_clipboard.kind != "other":
            check.clipboard.restore(saved_clipboard)

    print()
    for name, ok, expected, got in results:
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")
        if not ok:
            print(f"        expected: {expected!r}\n        got:      {got!r}")
    if clipboard_note:
        print(f"  NOTE  {clipboard_note}")
    else:
        print(f"  {'PASS' if clipboard_ok else 'FAIL'}  clipboard put back after pasting")
    passed = sum(ok for _, ok, _, _ in results) + bool(clipboard_ok)
    total = len(results) + (clipboard_note is None)
    print(f"\n{passed}/{total} passed")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
