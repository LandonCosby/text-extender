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
python main.py
```

It opens the settings window, where you can add, edit and delete snippets, change the hotkey and set the typing speed. Changes are saved and used straight away. Closing the window quits.

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

- `char_delay_ms`: 0 pastes instantly; 1–200 types one character at a time with that many milliseconds between.
- A shortcut must come after a space or a new line (`hi ;te` works, `hi;te` doesn't).
- It can't type into programs running as administrator; Windows blocks that.

## Tests

```
python -m pytest tests
```

## Where snippets are stored

`%APPDATA%\TextExtender\config.json`, outside this folder, so personal snippets are never committed to git.
