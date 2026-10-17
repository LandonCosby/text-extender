"""The window for managing snippets, the hotkey and the typing speed (plan step 7).

Every change is saved straight away through the on_change callback (which writes the
config file and hands the new settings to the running listener). If a change isn't
allowed, or saving fails, the reason is shown at the bottom of the window and nothing
changes.
"""

import copy
import tkinter as tk
from tkinter import messagebox, ttk

from .config import MAX_CHAR_DELAY_MS, ConfigError
from .listener import parse_hotkey

PREVIEW_TEXT = "The quick brown fox jumps over the lazy dog."
SPEED_SAVE_DELAY_MS = 400  # wait for the slider to settle before saving
MESSAGE_PREVIEW_LENGTH = 48

# Hotkey recording: tkinter key names -> pynput hotkey parts.
MODIFIER_KEYSYMS = {
    "Control_L": "ctrl", "Control_R": "ctrl",
    "Alt_L": "alt", "Alt_R": "alt",
    "Shift_L": "shift", "Shift_R": "shift",
    "Win_L": "cmd", "Win_R": "cmd", "Super_L": "cmd", "Super_R": "cmd",
}
MODIFIER_ORDER = ["ctrl", "alt", "shift", "cmd"]
NAMED_KEYS = {
    "space": "<space>", "Return": "<enter>", "Tab": "<tab>", "BackSpace": "<backspace>",
    "Delete": "<delete>", "Insert": "<insert>", "Home": "<home>", "End": "<end>",
    "Prior": "<page_up>", "Next": "<page_down>",
    "Up": "<up>", "Down": "<down>", "Left": "<left>", "Right": "<right>",
}
PUNCTUATION_KEYS = {
    "semicolon": ";", "comma": ",", "period": ".", "slash": "/", "backslash": "\\",
    "minus": "-", "equal": "=", "bracketleft": "[", "bracketright": "]",
    "apostrophe": "'", "grave": "`",
    # With Shift held, Windows reports the shifted symbol (US layout): use the key itself.
    "exclam": "1", "at": "2", "numbersign": "3", "dollar": "4", "percent": "5",
    "asciicircum": "6", "ampersand": "7", "asterisk": "8", "parenleft": "9", "parenright": "0",
    "colon": ";", "less": ",", "greater": ".", "question": "/", "bar": "\\",
    "underscore": "-", "plus": "=", "braceleft": "[", "braceright": "]",
    "quotedbl": "'", "asciitilde": "`",
}

# Hotkeys that would take over something you probably use.
COMMON_SHORTCUTS = {
    "<ctrl>+c": "Copy", "<ctrl>+v": "Paste", "<ctrl>+x": "Cut", "<ctrl>+z": "Undo",
    "<ctrl>+y": "Redo", "<ctrl>+a": "Select all", "<ctrl>+s": "Save", "<ctrl>+f": "Find",
    "<ctrl>+p": "Print", "<ctrl>+w": "Close tab", "<ctrl>+t": "New tab", "<ctrl>+n": "New window",
    "<ctrl>+o": "Open", "<ctrl>+<tab>": "Next tab", "<ctrl>+<backspace>": "Delete word",
    "<alt>+<tab>": "Switch windows", "<alt>+<f4>": "Close window",
    "<ctrl>+<shift>+<esc>": "Task Manager", "<cmd>+d": "Show desktop", "<cmd>+e": "File Explorer",
    "<cmd>+r": "Run", "<cmd>+l": "Lock", "<cmd>+v": "Clipboard history",
}


def hotkey_from_keys(modifiers, keysym):
    """Build a pynput hotkey ('<ctrl>+<alt>+e') from held modifier names and the
    tkinter name of the other key. None if that key can't be used."""
    if len(keysym) == 1 and keysym.isalnum():
        key = keysym.lower()
    elif keysym in NAMED_KEYS:
        key = NAMED_KEYS[keysym]
    elif keysym in PUNCTUATION_KEYS:
        key = PUNCTUATION_KEYS[keysym]
    elif keysym.startswith("F") and keysym[1:].isdigit() and 1 <= int(keysym[1:]) <= 24:
        key = f"<f{int(keysym[1:])}>"
    else:
        return None
    parts = [f"<{m}>" for m in MODIFIER_ORDER if m in modifiers]
    return "+".join(parts + [key])


def describe_hotkey(hotkey):
    """'<ctrl>+<space>' -> 'Ctrl+Space', '<cmd>+e' -> 'Win+E'."""
    names = {"cmd": "Win", "page_up": "Page Up", "page_down": "Page Down", "esc": "Esc"}
    parts = []
    for part in hotkey.split("+"):
        name = part.strip("<>")
        parts.append(names.get(name, name.upper() if len(name) <= 3 and name[:1] == "f" else name.capitalize()))
    return "+".join(parts)


def hotkey_warning(hotkey):
    """A warning if the hotkey clashes with something common, else None."""
    if hotkey in COMMON_SHORTCUTS:
        return f"{describe_hotkey(hotkey)} is usually {COMMON_SHORTCUTS[hotkey]}. Use it anyway?"
    parts = hotkey.split("+")
    if "<ctrl>" in parts and "<alt>" in parts and len(parts[-1]) == 1:
        return (f"On some keyboards, Ctrl+Alt+{parts[-1].upper()} types a special character "
                "(AltGr). Use it anyway?")
    return None


def message_preview(message):
    """One line for the snippet list: the first line, shortened, with ↵ if there's more."""
    lines = message.splitlines() or [""]
    text = lines[0]
    if len(text) > MESSAGE_PREVIEW_LENGTH:
        text = text[:MESSAGE_PREVIEW_LENGTH].rstrip() + "…"
    if len(lines) > 1:
        text += " ↵…"
    return text


def describe_speed(delay_ms):
    return "Instant (paste)" if delay_ms == 0 else f"{delay_ms} ms per character"


class SettingsWindow:
    def __init__(self, master, config, on_change, on_capture_start=lambda: None,
                 on_capture_end=lambda: None, confirm=None):
        """on_change(new_config) saves and applies settings; it may raise ConfigError
        or OSError. The capture callbacks pause and resume the global listener while
        a new hotkey is recorded. confirm(title, question) -> bool asks the user."""
        self.master = master
        self.config = copy.deepcopy(config)
        self.on_change = on_change
        self.on_capture_start = on_capture_start
        self.on_capture_end = on_capture_end
        self.confirm = confirm or (lambda title, question: messagebox.askyesno(title, question, parent=master))
        self.editing = None  # shortcut of the snippet in the form, or None for a new one
        self.capturing = False
        self._held = set()
        self._bindings = []
        self._speed_job = None
        self._preview_job = None

        master.title("Text Extender – Settings")
        master.minsize(640, 520)
        self._build()
        self.refresh_list()
        self.new_snippet()

    # Layout

    def _build(self):
        outer = ttk.Frame(self.master, padding=12)
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(1, weight=1)

        ttk.Label(outer, text="Snippets", font=("Segoe UI", 11, "bold")).grid(row=0, column=0, sticky="w")
        list_frame = ttk.Frame(outer)
        list_frame.grid(row=1, column=0, sticky="nsew", pady=(4, 8))
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)
        self.tree = ttk.Treeview(list_frame, columns=("shortcut", "message"), show="headings",
                                 selectmode="browse", height=8)
        self.tree.heading("shortcut", text="Shortcut")
        self.tree.heading("message", text="Message")
        self.tree.column("shortcut", width=140, stretch=False)
        self.tree.column("message", width=420)
        self.tree.grid(row=0, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(list_frame, orient="vertical", command=self.tree.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.bind("<<TreeviewSelect>>", lambda e: self.load_selected())

        form = ttk.LabelFrame(outer, text="Snippet", padding=8)
        form.grid(row=2, column=0, sticky="ew")
        form.columnconfigure(1, weight=1)
        ttk.Label(form, text="Shortcut").grid(row=0, column=0, sticky="w")
        self.shortcut_var = tk.StringVar()
        self.shortcut_entry = ttk.Entry(form, textvariable=self.shortcut_var, width=24)
        self.shortcut_entry.grid(row=0, column=1, sticky="w", pady=2)
        ttk.Label(form, text="Message").grid(row=1, column=0, sticky="nw")
        self.message_text = tk.Text(form, height=5, wrap="word", font=("Segoe UI", 10), undo=True)
        self.message_text.grid(row=1, column=1, sticky="ew", pady=2)
        buttons = ttk.Frame(form)
        buttons.grid(row=2, column=1, sticky="e", pady=(4, 0))
        ttk.Button(buttons, text="New", command=self.new_snippet).pack(side="left", padx=2)
        self.delete_button = ttk.Button(buttons, text="Delete", command=self.delete_snippet)
        self.delete_button.pack(side="left", padx=2)
        ttk.Button(buttons, text="Save snippet", command=self.save_snippet).pack(side="left", padx=2)

        settings = ttk.LabelFrame(outer, text="Settings", padding=8)
        settings.grid(row=3, column=0, sticky="ew", pady=(8, 0))
        settings.columnconfigure(1, weight=1)
        ttk.Label(settings, text="Hotkey").grid(row=0, column=0, sticky="w")
        self.hotkey_label = ttk.Label(settings, font=("Segoe UI", 10, "bold"))
        self.hotkey_label.grid(row=0, column=1, sticky="w")
        self.hotkey_button = ttk.Button(settings, text="Change…", command=self.start_hotkey_capture)
        self.hotkey_button.grid(row=0, column=2, sticky="e")

        ttk.Label(settings, text="Typing speed").grid(row=1, column=0, sticky="w", pady=(8, 0))
        self.speed_label = ttk.Label(settings, width=22)
        self.speed_label.grid(row=1, column=2, sticky="e", pady=(8, 0))
        # Given its starting value up front: set() would call speed_moved and save.
        self.speed_scale = ttk.Scale(settings, from_=0, to=MAX_CHAR_DELAY_MS, orient="horizontal",
                                     value=self.config.char_delay_ms, command=lambda v: self.speed_moved())
        self.speed_scale.grid(row=1, column=1, sticky="ew", padx=8, pady=(8, 0))
        ttk.Button(settings, text="Preview", command=self.preview_speed).grid(row=2, column=2, sticky="e", pady=(4, 0))
        self.preview_label = ttk.Label(settings, foreground="#555")
        self.preview_label.grid(row=2, column=0, columnspan=2, sticky="w", pady=(4, 0))

        self.status = ttk.Label(outer, text="")
        self.status.grid(row=4, column=0, sticky="w", pady=(8, 0))
        self._show_settings()

    def _show_settings(self):
        self.hotkey_label.configure(text=describe_hotkey(self.config.hotkey))
        self.speed_label.configure(text=describe_speed(self.speed_value()))

    def show_status(self, text, error=False):
        self.status.configure(text=text, foreground="#b00020" if error else "#1b6e20")

    # Saving

    def commit(self, new_config, success):
        """Save new settings. Returns whether it worked; on failure nothing changes."""
        try:
            new_config.validate()
            self.on_change(new_config)
        except (ConfigError, OSError) as e:
            self.show_status(str(e), error=True)
            return False
        self.config = new_config
        self.show_status(success)
        return True

    # Snippets

    def refresh_list(self):
        self.tree.delete(*self.tree.get_children())
        for shortcut, message in self.config.snippets.items():
            self.tree.insert("", "end", iid=shortcut, values=(shortcut, message_preview(message)))

    def new_snippet(self):
        self.editing = None
        self.tree.selection_set(())
        self.shortcut_var.set("")
        self.message_text.delete("1.0", "end")
        self.delete_button.state(["disabled"])
        self.shortcut_entry.focus_set()

    def load_selected(self):
        selected = self.tree.selection()
        if not selected:
            return
        shortcut = selected[0]
        self.editing = shortcut
        self.shortcut_var.set(shortcut)
        self.message_text.delete("1.0", "end")
        self.message_text.insert("1.0", self.config.snippets[shortcut])
        self.delete_button.state(["!disabled"])

    def form_values(self):
        return self.shortcut_var.get().strip(), self.message_text.get("1.0", "end-1c")

    def save_snippet(self):
        shortcut, message = self.form_values()
        new = copy.deepcopy(self.config)
        try:
            if self.editing is None:
                new.add_snippet(shortcut, message)
            else:
                new.update_snippet(self.editing, shortcut, message)
        except ConfigError as e:
            self.show_status(str(e), error=True)
            return False
        if not self.commit(new, f"Saved {shortcut}."):
            return False
        self.refresh_list()
        self.tree.selection_set(shortcut)
        self.tree.see(shortcut)
        self.editing = shortcut
        self.delete_button.state(["!disabled"])
        return True

    def delete_snippet(self):
        if self.editing is None:
            return False
        shortcut = self.editing
        if not self.confirm("Delete snippet", f"Delete the snippet {shortcut}?"):
            return False
        new = copy.deepcopy(self.config)
        new.remove_snippet(shortcut)
        if not self.commit(new, f"Deleted {shortcut}."):
            return False
        self.refresh_list()
        self.new_snippet()
        return True

    # Hotkey

    def start_hotkey_capture(self):
        if self.capturing:
            return
        self.capturing = True
        self._held = set()
        self.on_capture_start()  # pause the listener, so the current hotkey reaches us
        self.hotkey_label.configure(text="Press the new hotkey… (Esc to cancel)")
        self.hotkey_button.state(["disabled"])
        self._bindings = [
            ("<KeyPress>", self.master.bind("<KeyPress>", self.capture_key_press, add=True)),
            ("<KeyRelease>", self.master.bind("<KeyRelease>", self.capture_key_release, add=True)),
        ]
        self.master.focus_force()

    def stop_hotkey_capture(self):
        if not self.capturing:
            return
        self.capturing = False
        for sequence, funcid in self._bindings:
            self.master.unbind(sequence, funcid)
        self._bindings = []
        self.hotkey_button.state(["!disabled"])
        self._show_settings()
        self.on_capture_end()

    def capture_key_release(self, event):
        self._held.discard(MODIFIER_KEYSYMS.get(event.keysym))

    def capture_key_press(self, event):
        """Record keys until a non-modifier key is pressed. Returns 'break' so the key
        doesn't also type into a box in the window."""
        if event.keysym == "Escape":
            self.stop_hotkey_capture()
            self.show_status("Hotkey unchanged.")
            return "break"
        if event.keysym in MODIFIER_KEYSYMS:
            self._held.add(MODIFIER_KEYSYMS[event.keysym])
            return "break"
        hotkey = hotkey_from_keys(self._held, event.keysym)
        if hotkey is None:
            self.show_status(f"The key '{event.keysym}' can't be used in a hotkey. Try another.", error=True)
            return "break"
        try:
            parse_hotkey(hotkey)
        except (ConfigError, ValueError) as e:
            self.show_status(f"{describe_hotkey(hotkey)}: {e} Try again.", error=True)
            return "break"
        self.stop_hotkey_capture()
        warning = hotkey_warning(hotkey)
        if warning and not self.confirm("Hotkey clash", warning):
            self.show_status("Hotkey unchanged.")
            return "break"
        new = copy.deepcopy(self.config)
        new.hotkey = hotkey
        self.commit(new, f"Hotkey is now {describe_hotkey(hotkey)}.")
        self._show_settings()
        return "break"

    # Typing speed

    def speed_value(self):
        return int(round(float(self.speed_scale.get())))

    def speed_moved(self):
        self.speed_label.configure(text=describe_speed(self.speed_value()))
        if self._speed_job is not None:
            self.master.after_cancel(self._speed_job)
        self._speed_job = self.master.after(SPEED_SAVE_DELAY_MS, self.save_speed)

    def save_speed(self):
        self._speed_job = None
        delay = self.speed_value()
        if delay == self.config.char_delay_ms:
            return True
        new = copy.deepcopy(self.config)
        new.char_delay_ms = delay
        return self.commit(new, f"Typing speed is now {describe_speed(delay).lower()}.")

    def preview_speed(self):
        """Show how fast messages will appear, typed into the preview line."""
        if self._preview_job is not None:
            self.master.after_cancel(self._preview_job)
            self._preview_job = None
        delay = self.speed_value()
        if delay == 0:
            self.preview_label.configure(text=PREVIEW_TEXT)
            return

        def step(shown):
            self.preview_label.configure(text=PREVIEW_TEXT[:shown])
            if shown < len(PREVIEW_TEXT):
                self._preview_job = self.master.after(delay, step, shown + 1)
            else:
                self._preview_job = None

        step(0)
