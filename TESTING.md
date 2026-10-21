# Testing in real apps (plan step 10)

## 1. Automatic check in Notepad

```
python tools/try_in_notepad.py
```

It opens Notepad on a scratch file and runs real expansions there: pasting and typing, line breaks, tabs, special characters and emoji, a long message, cases that shouldn't expand, and putting your clipboard back. **Don't type or click for about 30 seconds while it runs.** It stops by itself if anything other than its Notepad file becomes the active window.

It can't press the real hotkey (Windows marks key presses made by programs, and the app ignores those), so the checklist below covers that.

## 2. By hand

Start the app (`pythonw main.py`). Add these snippets in the settings window if they aren't there yet:

| Shortcut | Message |
|---|---|
| `;te` | `Text Extender is working!` |
| `;addr` | three lines, e.g. `123 Example St` / `Springfield` / `Exampleland` |
| `;Sig` | `Best,` / `Your Name` (note the capital S) |

Tick each one off, and note anything that goes wrong.

**The hotkey**
- [ ] In Notepad, type `;te` and press **Ctrl+Space**: it becomes "Text Extender is working!".
- [ ] In VS Code (where Ctrl+Space normally opens suggestions), type `;te` and press Ctrl+Space: it expands, and **no suggestion list appears**, because the hotkey is kept from the app.
- [ ] Press Ctrl+Space with nothing typed: nothing happens.
- [ ] Type `hello;te` (no space) and press Ctrl+Space: nothing happens.

**Different apps**
- [ ] A browser text box (e.g. a search box or a message field): `;te` and `;addr` expand; `;addr` gives three lines.
- [ ] Word or another word processor: `;addr` gives three separate lines.
- [ ] A chat app (Teams, Discord, Slack…): `;te` expands. Note: in many chat apps Enter *sends* the message, so a multi-line snippet may send early when typed rather than pasted.

**Typing**
- [ ] `;Sig`, typed with Shift for the capital S, expands.
- [ ] Set the speed slider to about 100 ms, expand `;addr`: it types out visibly, letter by letter, with nothing missing.
- [ ] Back on **Instant (paste)**: copy some text first, expand `;te`, then paste with Ctrl+V somewhere: your copied text comes back, not the snippet.
- [ ] Take a screenshot with Win+Shift+S (so the clipboard holds an image), expand `;te`, then paste: the screenshot is still on the clipboard.

**Automatic expansion and placeholders** (tick *Also expand without the hotkey* first)
- [ ] In Notepad, type `;te,`: it becomes "Text Extender is working!," without pressing the hotkey.
- [ ] In a chat app, type `;te` and press Enter: the message is sent with the full text, not `;te`.
- [ ] In a browser form, type `;te` and press Tab: it expands, then moves to the next box.
- [ ] Add `;dear` = `Dear {cursor},` and expand it in Notepad and Word: the cursor ends up after "Dear ".
- [ ] Add `;now` = `{date} {time}`: it gives today's date and time in your usual format.
- [ ] Add `;cb` = `[{clipboard}]`: with text copied it gives that text in brackets; with a screenshot copied it gives `[]` and the screenshot is still on the clipboard.

**Settings and tray**
- [ ] Change the hotkey to Ctrl+Alt+F2 in settings: it works straight away; Ctrl+Space no longer expands.
- [ ] Pause from the tray: the icon goes grey and nothing expands. Resume: it works again.
- [ ] Close the settings window: expansions still work. Run `python main.py` again: the settings window comes back.

**Known limit**
- [ ] Open Notepad **as administrator** (right-click → Run as administrator) and try `;te`: it doesn't expand. That's expected; Windows blocks normal programs from typing into administrator programs.

If anything fails, the app's log (`textextender.log`, next to the settings file) may show why.
