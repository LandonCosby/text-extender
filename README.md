# Text Extender

A Windows background app for typing long text quickly: type a shortcut such as `;addr`, press the hotkey (default `Ctrl+Space`), and the shortcut is replaced by its full message.

- Store shortcuts and their messages
- Change the hotkey
- Change how fast the message is typed (or paste it instantly)

**Status:** in progress. See [PLAN.md](PLAN.md) for the steps.

## Setup

```
python -m pip install -r requirements.txt
```

## Run

```
pythonw main.py
```

(`pythonw` starts it without a terminal window; `python main.py` works too.)

It runs in the **system tray** (the blue "T…" icon; on Windows 11 it may be under the `^` arrow). Right-click it for:
- **Open settings** (or double-click the icon): add, edit and delete snippets, change the hotkey and set the typing speed. Changes are saved and used straight away. Closing the window keeps the app running; the **Quit Text Extender** button at the bottom ends it.
- **Pause / Resume**: the icon turns grey while paused.
- **Quit**

Starting it opens the settings window. Only one copy runs at a time: starting it again while it's running just brings up the running copy's settings window.

If something goes wrong, errors are written to `textextender.log` next to the settings file.

To try it, open any text box (Notepad, a browser), type `;te`, and press **Ctrl+Space**.

The settings are stored as JSON, which you can also edit by hand while the app is closed:

```json
{
  "hotkey": "<ctrl>+<space>",
  "char_delay_ms": 0,
  "snippets": {
    ";te": "Text Extender is working!",
    ";sig": "Best,\nYour Name"
  }
}
```

- `char_delay_ms`: 0 pastes instantly; 1–200 types one character at a time with that many milliseconds between (never faster than 25 ms, which is about as fast as apps reliably keep up with).
- A shortcut must come after a space or a new line (`hi ;te` works, `hi;te` doesn't).
- It can't type into programs running as administrator; Windows blocks that.

## Tests

```
python -m pytest tests
```

To try it in real Notepad (it takes over the keyboard for about 30 seconds), and for a by-hand checklist for other apps, see [TESTING.md](TESTING.md).

## Where snippets are stored

`%APPDATA%\TextExtender\config.json`, outside this folder, so personal snippets are never committed to git.
