"""Light and dark looks for the settings window.

Built on tkinter's own "clam" theme, which lets every colour be changed, so nothing
extra needs installing. ttk styles are shared by every window in the app; plain tk
widgets (such as the message box, a tk.Text) aren't reached by them and are coloured
with style_text().
"""

import ctypes
from tkinter import font as tkfont, ttk

THEMES = ("light", "dark")

PALETTES = {
    "light": {
        "bg": "#f3f4f6", "card": "#ffffff", "border": "#e3e5ea",
        "text": "#1f2328", "muted": "#6b7280", "disabled": "#a8adb7",
        "accent": "#2563eb", "accent_hover": "#1d4ed8", "accent_pressed": "#1e40af", "accent_text": "#ffffff",
        "button": "#ffffff", "button_hover": "#f1f3f6", "button_pressed": "#e6e9ee",
        "field": "#ffffff", "field_border": "#d0d4db",
        "select": "#dbe7fe", "trough": "#e3e5ea", "scroll": "#c9cdd4", "scroll_hover": "#aeb3bc",
        "error": "#c62828", "success": "#1b7a3a",
    },
    "dark": {
        "bg": "#16171b", "card": "#1f2126", "border": "#2e3138",
        "text": "#e6e7ea", "muted": "#9aa0aa", "disabled": "#5c616b",
        "accent": "#3b7bf0", "accent_hover": "#5590f5", "accent_pressed": "#2f68d6", "accent_text": "#ffffff",
        "button": "#2a2d34", "button_hover": "#33373f", "button_pressed": "#3b4049",
        "field": "#17181c", "field_border": "#3a3e47",
        "select": "#28395c", "trough": "#33373f", "scroll": "#3d414a", "scroll_hover": "#4d525c",
        "error": "#ff6b6b", "success": "#5cc98a",
    },
}

FONT = ("Segoe UI", 10)
SEMIBOLD = ("Segoe UI Semibold", 10)


def apply(window, name):
    """Style ttk widgets for the named theme and colour the window itself. Returns the
    palette, for colouring plain tk widgets and status text."""
    p = PALETTES[name]
    style = ttk.Style(window)
    style.theme_use("clam")

    style.configure(".", background=p["bg"], foreground=p["text"], font=FONT,
                    bordercolor=p["border"], lightcolor=p["bg"], darkcolor=p["bg"],
                    troughcolor=p["trough"], focuscolor=p["accent"], arrowcolor=p["muted"],
                    selectbackground=p["select"], selectforeground=p["text"],
                    fieldbackground=p["field"], insertcolor=p["text"])

    # Frames and text
    style.configure("TFrame", background=p["bg"])
    style.configure("Card.TFrame", background=p["card"], relief="solid", borderwidth=1,
                    bordercolor=p["border"], lightcolor=p["border"], darkcolor=p["border"])
    style.configure("Inner.TFrame", background=p["card"])
    style.configure("TLabel", background=p["bg"], foreground=p["text"])
    style.configure("Title.TLabel", font=("Segoe UI Semibold", 16))
    style.configure("Subtitle.TLabel", foreground=p["muted"])
    style.configure("Card.TLabel", background=p["card"])
    style.configure("CardTitle.TLabel", background=p["card"], font=("Segoe UI Semibold", 11))
    style.configure("Field.TLabel", background=p["card"], foreground=p["muted"], font=("Segoe UI", 9))
    style.configure("Value.TLabel", background=p["card"], font=SEMIBOLD)
    style.configure("Muted.TLabel", background=p["card"], foreground=p["muted"])

    # Buttons: plain ones are quiet, Accent ones are the main action.
    button_states = dict(
        background=[("disabled", p["card"]), ("pressed", p["button_pressed"]), ("active", p["button_hover"])],
        lightcolor=[("disabled", p["card"]), ("pressed", p["button_pressed"]), ("active", p["button_hover"])],
        darkcolor=[("disabled", p["card"]), ("pressed", p["button_pressed"]), ("active", p["button_hover"])],
        foreground=[("disabled", p["disabled"])],
        bordercolor=[("focus", p["accent"])],
    )
    style.configure("TButton", padding=(14, 5), background=p["button"], foreground=p["text"],
                    bordercolor=p["field_border"], lightcolor=p["button"], darkcolor=p["button"],
                    focuscolor=p["button"], relief="raised")  # raised draws the outline in clam
    style.map("TButton", **button_states)
    style.configure("Accent.TButton", background=p["accent"], foreground=p["accent_text"],
                    bordercolor=p["accent"], lightcolor=p["accent"], darkcolor=p["accent"],
                    focuscolor=p["accent"], font=SEMIBOLD)
    accent_bg = [("pressed", p["accent_pressed"]), ("active", p["accent_hover"])]
    style.map("Accent.TButton", background=accent_bg, lightcolor=accent_bg, darkcolor=accent_bg,
              bordercolor=[("focus", p["text"])])

    # Two-way switch (radio buttons drawn as joined buttons)
    style.configure("Segment.Toolbutton", padding=(16, 5), background=p["button"], foreground=p["muted"],
                    bordercolor=p["field_border"], lightcolor=p["button"], darkcolor=p["button"],
                    focuscolor=p["button"], relief="raised", anchor="center")
    segment_bg = [("selected", p["accent"]), ("active", p["button_hover"])]
    style.map("Segment.Toolbutton", background=segment_bg, lightcolor=segment_bg, darkcolor=segment_bg,
              foreground=[("selected", p["accent_text"])],
              bordercolor=[("selected", p["accent"]), ("focus", p["accent"])],
              relief=[("selected", "raised"), ("pressed", "raised")])

    # Text boxes
    style.configure("TEntry", padding=(8, 5), fieldbackground=p["field"], foreground=p["text"],
                    bordercolor=p["field_border"], lightcolor=p["field"], darkcolor=p["field"],
                    insertcolor=p["text"], selectbackground=p["select"], selectforeground=p["text"])
    style.map("TEntry", bordercolor=[("focus", p["accent"])], lightcolor=[("focus", p["accent"])])

    # Snippet list: no outer border (it sits on a card), roomy rows, quiet headings.
    row_height = tkfont.Font(window, font=FONT).metrics("linespace") + 12
    style.layout("Treeview", [("Treeview.treearea", {"sticky": "nswe"})])
    style.configure("Treeview", background=p["card"], fieldbackground=p["card"], foreground=p["text"],
                    rowheight=row_height, borderwidth=0)
    style.map("Treeview", background=[("selected", p["select"])], foreground=[("selected", p["text"])])
    style.configure("Treeview.Heading", background=p["card"], foreground=p["muted"], relief="flat",
                    font=("Segoe UI Semibold", 9), padding=(8, 6), bordercolor=p["border"],
                    lightcolor=p["card"], darkcolor=p["card"])
    style.map("Treeview.Heading", background=[("active", p["card"])])

    # Slim scrollbar without arrows
    style.layout("Vertical.TScrollbar", [("Vertical.Scrollbar.trough", {
        "sticky": "ns", "children": [("Vertical.Scrollbar.thumb", {"expand": "1", "sticky": "nswe"})]})])
    style.configure("Vertical.TScrollbar", background=p["scroll"], troughcolor=p["card"],
                    bordercolor=p["card"], lightcolor=p["scroll"], darkcolor=p["scroll"],
                    gripcount=0, arrowsize=10)
    scroll_bg = [("pressed", p["scroll_hover"]), ("active", p["scroll_hover"])]
    style.map("Vertical.TScrollbar", background=scroll_bg, lightcolor=scroll_bg, darkcolor=scroll_bg)

    # Slider
    style.configure("Horizontal.TScale", background=p["accent"], troughcolor=p["trough"],
                    bordercolor=p["card"], lightcolor=p["accent"], darkcolor=p["accent"],
                    gripcount=0, sliderlength=18, sliderthickness=18)
    slider_bg = [("pressed", p["accent_pressed"]), ("active", p["accent_hover"])]
    style.map("Horizontal.TScale", background=slider_bg, lightcolor=slider_bg, darkcolor=slider_bg)

    window.configure(background=p["bg"])
    set_title_bar(window, dark=name == "dark")
    return p


def style_text(widget, p):
    """Colour a plain tk.Text to match the ttk text boxes."""
    widget.configure(background=p["field"], foreground=p["text"], insertbackground=p["text"],
                     selectbackground=p["select"], selectforeground=p["text"], relief="flat",
                     borderwidth=0, padx=8, pady=6, highlightthickness=1,
                     highlightbackground=p["field_border"], highlightcolor=p["accent"])


def set_title_bar(window, dark):
    """Make the Windows title bar dark or light (Windows 10 1809+). Does nothing elsewhere."""
    try:
        window.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(window.winfo_id())
        value = ctypes.c_int(1 if dark else 0)
        # DWMWA_USE_IMMERSIVE_DARK_MODE is 20, or 19 on Windows 10 before 20H1.
        for attribute in (20, 19):
            if ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    hwnd, attribute, ctypes.byref(value), ctypes.sizeof(value)) == 0:
                break
        # Redraw the frame now, rather than when the window next loses focus.
        flags = 0x0001 | 0x0002 | 0x0004 | 0x0010 | 0x0020  # NOSIZE|NOMOVE|NOZORDER|NOACTIVATE|FRAMECHANGED
        ctypes.windll.user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, flags)
    except (AttributeError, OSError):
        pass
