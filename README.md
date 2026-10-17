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

## Tests

```
python -m pytest tests
```

## Where snippets are stored

`%APPDATA%\TextExtender\config.json`, outside this folder, so personal snippets are never committed to git.
