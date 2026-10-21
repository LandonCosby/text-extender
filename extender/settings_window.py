"""The window for managing snippets, the hotkey, the typing speed and the theme (plan step 7).

Every change is saved straight away through the on_change callback (which writes the
config file and hands the new settings to the running listener). If a change isn't
allowed, or saving fails, the reason is shown at the bottom of the window and nothing
changes.
"""

import copy
import tkinter as tk
from tkinter import messagebox, ttk

from . import theme
from .config import MAX_CHAR_DELAY_MS, THEMES, ConfigError
from .expander import MIN_TYPING_DELAY_MS
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
    """How fast messages appear. Delays under MIN_TYPING_DELAY_MS are typed at that
    speed anyway (apps can't keep up with faster), so that's what's shown."""
    if delay_ms == 0:
        return "Instant (paste)"
    return f"{max(delay_ms, MIN_TYPING_DELAY_MS)} ms per character"


class SettingsWindow:
    def __init__(self, master, config, on_change, on_capture_start=lambda: None,
                 on_capture_end=lambda: None, confirm=None, on_quit=None):
        """on_change(new_config) saves and applies settings; it may raise ConfigError
        or OSError. The capture callbacks pause and resume the global listener while
        a new hotkey is recorded. confirm(title, question) -> bool asks the user.
        on_quit, if given, adds a "Quit Text Extender" button that ends the app."""
        self.master = master
        self.config = copy.deepcopy(config)
        self.on_change = on_change
        self.on_capture_start = on_capture_start
        self.on_capture_end = on_capture_end
        self.on_quit = on_quit
        self.confirm = confirm or (lambda title, question: messagebox.askyesno(title, question, parent=master))
        self.editing = None  # shortcut of the snippet in the form, or None for a new one
        self.capturing = False
        self._held = set()
        self._bindings = []
        self._speed_job = None
        self._preview_job = None
        self._status_error = False

        master.title("Text Extender – Settings")
        master.minsize(680, 700)
        self.palette = theme.apply(master, self.config.theme)
        self._build()
        theme.style_text(self.message_text, self.palette)
        self.refresh_list()
        self.new_snippet()

    # Layout

    def _build(self):
        outer = ttk.Frame(self.master, padding=(20, 16, 20, 14))
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(1, weight=1)

        header = ttk.Frame(outer)
        header.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        ttk.Label(header, text="Text Extender", style="Title.TLabel").pack(anchor="w")
        ttk.Label(header, text="Type a shortcut, then press the hotkey to swap it for its message.",
                  style="Subtitle.TLabel").pack(anchor="w")

        # Snippet list
        list_card = self._card(outer, row=1)
        list_card.rowconfigure(1, weight=1)
        ttk.Label(list_card, text="Snippets", style="CardTitle.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Button(list_card, text="+ New snippet", command=self.new_snippet).grid(row=0, column=1, sticky="e")
        list_frame = ttk.Frame(list_card, style="Inner.TFrame")
        list_frame.grid(row=1, column=0, columnspan=2, sticky="nsew", pady=(8, 0))
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)
        self.tree = ttk.Treeview(list_frame, columns=("shortcut", "message"), show="headings",
                                 selectmode="browse", height=6)
        self.tree.heading("shortcut", text="SHORTCUT", anchor="w")
        self.tree.heading("message", text="MESSAGE", anchor="w")
        self.tree.column("shortcut", width=150, stretch=False)
        self.tree.column("message", width=420)
        self.tree.grid(row=0, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(list_frame, orient="vertical", command=self.tree.yview)
        scroll.grid(row=0, column=1, sticky="ns", padx=(4, 0))
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.bind("<<TreeviewSelect>>", lambda e: self.load_selected())

        # Snippet form
        form = self._card(outer, row=2)
        self.form_title = ttk.Label(form, text="New snippet", style="CardTitle.TLabel")
        self.form_title.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 8))
        ttk.Label(form, text="Shortcut", style="Field.TLabel").grid(row=1, column=0, sticky="w", padx=(0, 12))
        self.shortcut_var = tk.StringVar()
        self.shortcut_entry = ttk.Entry(form, textvariable=self.shortcut_var, width=24)
        self.shortcut_entry.grid(row=1, column=1, sticky="w", pady=(0, 8))
        ttk.Label(form, text="Message", style="Field.TLabel").grid(row=2, column=0, sticky="nw", padx=(0, 12), pady=(6, 0))
        self.message_text = tk.Text(form, height=4, wrap="word", font=theme.FONT, undo=True)
        self.message_text.grid(row=2, column=1, sticky="ew")
        buttons = ttk.Frame(form, style="Inner.TFrame")
        buttons.grid(row=3, column=1, sticky="e", pady=(10, 0))
        self.delete_button = ttk.Button(buttons, text="Delete", command=self.delete_snippet)
        self.delete_button.pack(side="left", padx=(0, 8))
        ttk.Button(buttons, text="Save snippet", style="Accent.TButton", command=self.save_snippet).pack(side="left")

        # Settings
        settings = self._card(outer, row=3)
        ttk.Label(settings, text="Settings", style="CardTitle.TLabel").grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 8))
        ttk.Label(settings, text="Hotkey", style="Card.TLabel").grid(row=1, column=0, sticky="w", padx=(0, 16))
        self.hotkey_label = ttk.Label(settings, style="Value.TLabel")
        self.hotkey_label.grid(row=1, column=1, sticky="w")
        self.hotkey_button = ttk.Button(settings, text="Change…", command=self.start_hotkey_capture)
        self.hotkey_button.grid(row=1, column=2, sticky="e")

        ttk.Label(settings, text="Typing speed", style="Card.TLabel").grid(row=2, column=0, sticky="w", pady=(12, 0))
        speed_row = ttk.Frame(settings, style="Inner.TFrame")
        speed_row.grid(row=2, column=1, sticky="ew", pady=(12, 0))
        speed_row.columnconfigure(0, weight=1)
        # Given its starting value up front: set() would call speed_moved and save.
        self.speed_scale = ttk.Scale(speed_row, from_=0, to=MAX_CHAR_DELAY_MS, orient="horizontal",
                                     value=self.config.char_delay_ms, command=lambda v: self.speed_moved())
        self.speed_scale.grid(row=0, column=0, sticky="ew")
        self.speed_label = ttk.Label(speed_row, width=20, style="Muted.TLabel", anchor="e")
        self.speed_label.grid(row=0, column=1, sticky="e", padx=(12, 12))
        ttk.Button(settings, text="Preview", command=self.preview_speed).grid(row=2, column=2, sticky="e", pady=(12, 0))
        self.preview_label = ttk.Label(settings, style="Muted.TLabel")
        self.preview_label.grid(row=3, column=1, columnspan=2, sticky="w", pady=(4, 0))

        ttk.Label(settings, text="Appearance", style="Card.TLabel").grid(row=4, column=0, sticky="w", pady=(10, 0))
        switch = ttk.Frame(settings, style="Inner.TFrame")
        switch.grid(row=4, column=1, sticky="w", pady=(10, 0))
        self.theme_var = tk.StringVar(value=self.config.theme)
        self.theme_buttons = {}
        for name in THEMES:
            button = ttk.Radiobutton(switch, text=name.capitalize(), value=name, variable=self.theme_var,
                                     style="Segment.Toolbutton", command=self.theme_chosen)
            button.pack(side="left")
            self.theme_buttons[name] = button

        bottom = ttk.Frame(outer)
        bottom.grid(row=4, column=0, sticky="ew", pady=(12, 0))
        bottom.columnconfigure(0, weight=1)
        self.status = ttk.Label(bottom, text="")
        self.status.grid(row=0, column=0, sticky="w")
        self.quit_button = None
        if self.on_quit is not None:
            # Closing the window keeps the app running in the tray; this ends it.
            self.quit_button = ttk.Button(bottom, text="Quit Text Extender", command=self.quit_app)
            self.quit_button.grid(row=0, column=1, sticky="e")
        self._show_settings()

    def _card(self, parent, row):
        """A bordered panel in the given row of the window, with its second column stretching."""
        card = ttk.Frame(parent, style="Card.TFrame", padding=(16, 12))
        card.grid(row=row, column=0, sticky="nsew", pady=(0, 12) if row < 3 else 0)
        card.columnconfigure(1, weight=1)
        return card

    def apply_theme(self):
        """Colour the window for the current theme (ttk styles, plus the bits they miss)."""
        self.palette = theme.apply(self.master, self.config.theme)
        theme.style_text(self.message_text, self.palette)
        self.show_status(self.status.cget("text"), error=self._status_error)

    def theme_chosen(self):
        name = self.theme_var.get()
        if name == self.config.theme:
            return True
        new = copy.deepcopy(self.config)
        new.theme = name
        if not self.commit(new, f"Switched to {name} mode."):
            self.theme_var.set(self.config.theme)
            return False
        self.apply_theme()
        return True

    def _show_settings(self):
        self.hotkey_label.configure(text=describe_hotkey(self.config.hotkey))
        self.speed_label.configure(text=describe_speed(self.speed_value()))

    def quit_app(self):
        """End the whole app (not just this window). Settings are already saved."""
        if self.capturing:
            self.stop_hotkey_capture()
        self.on_quit()

    def show_status(self, text, error=False):
        self._status_error = error
        self.status.configure(text=text, foreground=self.palette["error" if error else "success"])

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
        self.form_title.configure(text="New snippet")
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
        self.form_title.configure(text=f"Edit {shortcut}")
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
        self.form_title.configure(text=f"Edit {shortcut}")
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
        """The slider's delay. Anything between Instant and the slowest-needed gap snaps
        up to MIN_TYPING_DELAY_MS, the fastest that apps reliably keep up with."""
        delay = int(round(float(self.speed_scale.get())))
        return 0 if delay == 0 else max(delay, MIN_TYPING_DELAY_MS)

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
