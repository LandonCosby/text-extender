# Text Extender: Plan

A Windows background app: type a shortcut such as `;addr`, press a hotkey, and the shortcut is replaced by its full message.

**Decisions so far**
- **Trigger:** type the shortcut, then press the hotkey (configurable, default `Ctrl+Space`).
- **Tech:** Python, with `pynput` for system-wide key listening and typing, and `tkinter` for the window.
- **Interface:** a system-tray icon (`pystray`) plus a settings window.
- **Speed:** a delay between typed characters. 0 means instant, which pastes through the clipboard.

---

## Step 1: Project setup ✅
- [x] Create the layout:
  ```
  text-extender/
  ├── main.py              # starts the app
  ├── extender/
  │   ├── config.py        # load/save snippets and settings
  │   ├── buffer.py        # remembers recently typed characters
  │   ├── matcher.py       # finds which shortcut was just typed
  │   ├── clipboard.py     # reads/writes the Windows clipboard (for instant paste)
  │   ├── expander.py      # erases the shortcut and types/pastes the message
  │   ├── listener.py      # global keyboard listening and the hotkey
  │   ├── settings_window.py
  │   └── tray.py
  ├── tests/
  ├── requirements.txt     # pynput, pystray, Pillow, pytest
  ├── .gitignore
  └── README.md
  ```
- [x] **Downloads:** installed `pynput` 1.8.2, `pystray` 0.19.5 and `Pillow` 12.3.0 (`Pillow` is what `pystray` uses to draw the tray icon). `pytest` was already installed.

## Step 2: Storing snippets and settings (`config.py`) ✅
- [x] One JSON file in `%APPDATA%\TextExtender\config.json`, outside the project folder. Snippets can hold personal details (addresses, phone numbers), so they should never end up in a git repo.
  ```json
  {
    "hotkey": "<ctrl>+<space>",
    "char_delay_ms": 0,
    "snippets": { ";addr": "123 Example St\nSpringfield", ";sig": "Best,\nYour Name" }
  }
  ```
- [x] Defaults when the file is missing, and a backup copy if the file is damaged. The damaged file is renamed to `config.damaged-<date-time>.json`, so nothing is lost.
- [x] Validation: shortcuts must be unique and have no spaces, the message can't be empty, and the delay must be between 0 and 200 ms. Shortcuts are at most 30 characters. The hotkey must be one `pynput` recognises, with a modifier plus another key, so it can't fire while you type.
- [x] Atomic save: write a temp file and then rename it, so a crash can't corrupt the config.
- [x] Add / edit / rename / delete snippet helpers for the settings window. Each change is checked first, so a failed change leaves everything as it was.

## Step 3: Remembering what was typed (`buffer.py`) ✅
- [x] Keep the last 50 typed characters.
- [x] Backspace removes the last character.
- [x] Clear the buffer on Enter, Tab, Esc, arrow keys, Home/End, Page Up/Down, F-keys and Ctrl/Alt shortcuts (Ctrl+V, Ctrl+Z and so on). After any of those, the "just typed" text might not be next to the cursor any more. Keys that don't touch the text (Shift, Caps Lock, Delete, volume and media keys) are ignored, and AltGr characters such as € count as typing.
- [x] `clear()` is ready for mouse clicks and window switches. Connecting those happens in step 6.

## Step 4: Finding the shortcut (`matcher.py`) ✅
- [x] When the hotkey is pressed, find the **longest** shortcut that the buffer ends with. That way `;addr2` wins over `;addr`.
- [x] No match returns nothing, so nothing happens. A tray notification for "no match" can come with step 8.
- [x] Matching is case-sensitive, and the shortcut must stand on its own: right after a space or line break, or the first thing typed since the cursor moved. `thanks brb` expands `brb`; `thanksbrb` doesn't.

## Step 5: Doing the expansion (`expander.py`, `clipboard.py`) ✅
- [x] Wait for the hotkey's keys (Ctrl and so on) to be released first, so the text isn't typed as Ctrl+letters. If they're still held after 1 second, release them.
- [x] Press Backspace once per character of the shortcut to erase it.
- [x] Output the message:
  - **Delay 0:** copy it to the clipboard, press Ctrl+V, then restore whatever was on the clipboard before. Uses the Windows clipboard functions directly, so no extra download. Only plain text can be put back; if the clipboard holds an image or files, or another program has it busy, the message is typed quickly instead so nothing is lost. (Copied *formatted* text comes back as plain text.)
  - **Delay > 0:** type it character by character with that pause between each.
  - Handle new lines (Enter), tabs (Tab) and non-English characters.
- [x] `is_typing` is on while an expansion runs, and only one runs at a time. Running it on a background thread is part of step 6.

## Step 6: Keyboard listening and the hotkey (`listener.py`) ✅
- [x] A `pynput` keyboard listener that feeds typed characters into the buffer.
- [x] Clear the buffer on mouse clicks (a `pynput` mouse listener) and when the active window changes.
- [x] Hotkey detection from the configured combination. Changing it in settings takes effect straight away, without a restart.
  - [x] The hotkey is spotted in pynput's Windows event filter from raw key codes and **blocked**, so it never reaches the app you're typing in, and never reaches the buffer (so Ctrl+Space can't clear it before matching).
  - [x] The modifiers must match exactly: Ctrl+Shift+Space doesn't count as Ctrl+Space. Left and right Ctrl/Alt/Shift both work.
  - [x] Alt or Win hotkeys tap an unused key afterwards, so Windows doesn't open the menu bar or Start menu.
  - [x] Each expansion runs on a background thread, with the listener telling the expander which modifiers are held.
  - [x] Keys the app presses itself (marked injected by Windows) are ignored, and the buffer is cleared after each expansion.
- [x] Pause/resume support for the tray menu.
- [x] `python main.py` runs it in the terminal until Ctrl+C. On first run it saves an example snippet, `;te`.
- [x] The hotkey must have exactly one key besides the modifiers (added to the step 2 rules).

## Step 7: Settings window (`settings_window.py`, tkinter) ✅
- [x] **Snippets list** showing each shortcut and the start of its message (`↵…` marks more lines).
- [x] **Add / Edit / Delete** with a form: one-line shortcut, multi-line message. Renaming keeps the snippet's place; deleting asks first.
- [x] **Hotkey:** a "Change…" button that records the next key combination you press (Esc cancels), and warns about common clashes (Ctrl+C, Ctrl+V, Alt+Tab and so on, plus Ctrl+Alt+letter, which can clash with AltGr characters). The background listener is paused while recording, so even the current hotkey can be pressed.
- [x] **Speed:** a slider from Instant to Slow (0–200 ms per character) with a preview line that types out a sentence at that speed. Saved a moment after the slider stops moving.
- [x] Save straight to the config, and show errors in the window. Every change is checked first; if it isn't allowed or saving fails, the reason appears at the bottom and nothing changes.
- [x] `python main.py` opens the window with the listener running; closing it quits (until step 8's tray icon). Sharp on high-DPI screens.

## Step 8: Tray icon (`tray.py`) ✅
- [x] Menu: **Open settings** (also a double-click on the icon), **Pause / Resume**, **Quit**.
- [x] Run `tkinter` on the main thread and the tray icon on its own thread, and make sure Quit stops everything cleanly. Menu clicks are queued and handled on the main thread.
- [x] Closing the settings window keeps the app running in the tray. A **Quit Text Extender** button in the window ends the app.
- [x] The icon greys out while paused, and its tooltip shows the hotkey (or "paused"). Recording a hotkey doesn't undo a pause chosen from the tray.
- [x] Only one copy can run at a time (two would type every message twice). Starting it again opens the running copy's settings window.
- [x] Starting the app opens the settings window.
- [x] Tray clicks keep working even if handling one fails, Quit always ends the app, and errors from every part of the app go to `textextender.log` (needed under `pythonw`, which has no terminal).
- [ ] Not done: a notification when the hotkey finds no shortcut. It would pop up every time you pressed the hotkey by accident, so it was left out.

## Step 9: Tests (`tests/`, pytest)
- [x] Config: defaults, saving and reloading, rejecting bad input, recovering from a damaged file (done with step 2).
- [x] Buffer: typing, backspace, clearing on navigation keys (done with step 3).
- [x] Matcher: longest match, no match, shortcuts that are prefixes of others (done with step 4).
- [x] Expander: with a fake keyboard, check the right number of backspaces, the typed text, newlines, the delay, and the clipboard being restored (done with step 5, plus one test on the real Windows clipboard that puts it back afterwards).
- [x] Hotkey parsing and validation, and the listener with simulated key events (done with step 6).

## Step 10: Trying it in real apps
- [ ] Notepad, a browser text box, Word, a chat app.
- [ ] Edge cases:
  - shortcuts typed with Shift
  - very long messages
  - pressing the hotkey with nothing typed
  - apps running as administrator. Windows blocks a normal program from typing into those; note it in the README.

## Step 11: Starting with Windows (optional)
- [ ] A "Start with Windows" checkbox in settings that adds a shortcut to the Startup folder.
- [ ] Later, optionally, package it as a single `.exe` with PyInstaller (another download).

---

**Suggested order:** steps 1–5 with their tests first, so the core works from the command line. Then step 6 for a working app with a config file. Then steps 7–8 for the window and tray, and finish with 10–11.
