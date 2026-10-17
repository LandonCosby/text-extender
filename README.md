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

It runs in the terminal until you press Ctrl+C there. To try it, open any text box (Notepad, a browser), type `;te`, and press **Ctrl+Space**.

Until the settings window exists, add snippets by editing the settings file it prints (then restart it):

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
