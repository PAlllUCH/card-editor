"""Theme manager for dark/light mode switching using ttk.Style and manual tk widget updates."""

import tkinter as tk
from tkinter import ttk
import json
import os

CONFIG_FILE = "config.json"

# ── Color Palettes ──────────────────────────────────────────────────

LIGHT_COLORS = {
    # ttk widget colors (used in Style configurations)
    "bg": "#f0f0f0",
    "fg": "#000000",
    "select_bg": "#0078d7",
    "select_fg": "#ffffff",
    "frame_bg": "#f0f0f0",
    "label_bg": "#f0f0f0",
    "label_fg": "#000000",
    "entry_fg": "#000000",
    "entry_bg": "#ffffff",
    "button_bg": "#e1e1e1",
    "button_fg": "#000000",
    "button_active_bg": "#d0d0d0",
    "combobox_bg": "#ffffff",
    "combobox_fg": "#000000",
    "checkbutton_bg": "#f0f0f0",
    "checkbutton_fg": "#000000",
    "labelframe_bg": "#f0f0f0",
    "labelframe_fg": "#000000",
    "notebook_bg": "#f0f0f0",
    "notebook_fg": "#000000",
    "notebook_tab_bg": "#d9d9d9",
    "notebook_tab_fg": "#000000",
    "notebook_tab_sel_bg": "#f0f0f0",
    "notebook_tab_sel_fg": "#000000",
    "scrollbar_bg": "#c0c0c0",
    "scrollbar_trough": "#f0f0f0",
    "treeview_bg": "#ffffff",
    "treeview_fg": "#000000",
    "treeview_sel_bg": "#0078d7",
    "treeview_sel_fg": "#ffffff",
    "treeview_heading_bg": "#e1e1e1",
    "treeview_heading_fg": "#000000",
    "scale_bg": "#f0f0f0",
    "scale_fg": "#000000",
    "scale_trough": "#c0c0c0",
    # tk widget colors
    "tk_bg": "#f0f0f0",
    "tk_fg": "#000000",
    "tk_canvas_bg": "#ffffff",
    "tk_text_bg": "#ffffff",
    "tk_text_fg": "#000000",
    "tk_label_bg": "#f0f0f0",
    "tk_label_fg": "#000000",
    "tk_scale_bg": "#f0f0f0",
    "tk_scale_fg": "#000000",
    "tk_scale_trough": "#c0c0c0",
    "tk_scale_highlight": "#f0f0f0",
    # Console / log colors
    "console_bg": "#ffffff",
    "console_fg": "#000000",
    "size_calc_bg": "#ffffff",
    "size_calc_fg": "#000000",
    "highlight_bg": "#0078d7",
    "highlight_fg": "#ffffff",
    "file_row_bg": "#f0f0f0",
    "file_row_fg": "#000000",
    # Treeview tag colors
    "tag_pending": "gray",
    "tag_processing": "orange",
    "tag_ok": "green",
    "tag_error": "red",
    # Canvas
    "preview_bg": "#ffffff",
    "preview_fg": "#000000",
}

DARK_COLORS = {
    "bg": "#2d2d2d",
    "fg": "#ffffff",
    "select_bg": "#0078d7",
    "select_fg": "#ffffff",
    "frame_bg": "#2d2d2d",
    "label_bg": "#2d2d2d",
    "label_fg": "#ffffff",
    "entry_fg": "#ffffff",
    "entry_bg": "#3c3c3c",
    "button_bg": "#3c3c3c",
    "button_fg": "#ffffff",
    "button_active_bg": "#505050",
    "combobox_bg": "#3c3c3c",
    "combobox_fg": "#ffffff",
    "checkbutton_bg": "#2d2d2d",
    "checkbutton_fg": "#ffffff",
    "labelframe_bg": "#2d2d2d",
    "labelframe_fg": "#ffffff",
    "notebook_bg": "#2d2d2d",
    "notebook_fg": "#ffffff",
    "notebook_tab_bg": "#3c3c3c",
    "notebook_tab_fg": "#aaaaaa",
    "notebook_tab_sel_bg": "#2d2d2d",
    "notebook_tab_sel_fg": "#ffffff",
    "scrollbar_bg": "#3c3c3c",
    "scrollbar_trough": "#2d2d2d",
    "treeview_bg": "#3c3c3c",
    "treeview_fg": "#ffffff",
    "treeview_sel_bg": "#0078d7",
    "treeview_sel_fg": "#ffffff",
    "treeview_heading_bg": "#3c3c3c",
    "treeview_heading_fg": "#ffffff",
    "scale_bg": "#2d2d2d",
    "scale_fg": "#ffffff",
    "scale_trough": "#3c3c3c",
    # tk widget colors
    "tk_bg": "#2d2d2d",
    "tk_fg": "#ffffff",
    "tk_canvas_bg": "#3c3c3c",
    "tk_text_bg": "#1e1e1e",
    "tk_text_fg": "#d4d4d4",
    "tk_label_bg": "#2d2d2d",
    "tk_label_fg": "#ffffff",
    "tk_scale_bg": "#2d2d2d",
    "tk_scale_fg": "#ffffff",
    "tk_scale_trough": "#3c3c3c",
    "tk_scale_highlight": "#2d2d2d",
    # Console / log colors
    "console_bg": "#1e1e1e",
    "console_fg": "#d4d4d4",
    "size_calc_bg": "#333333",
    "size_calc_fg": "#00ff00",
    "highlight_bg": "#0078d7",
    "highlight_fg": "#ffffff",
    "file_row_bg": "#2d2d2d",
    "file_row_fg": "#000000",
    # Treeview tag colors
    "tag_pending": "gray",
    "tag_processing": "orange",
    "tag_ok": "green",
    "tag_error": "red",
    # Canvas preview
    "preview_bg": "#2d2d2d",
    "preview_fg": "#ffffff",
}

PALETTES = {
    "light": LIGHT_COLORS,
    "dark": DARK_COLORS,
}


class ThemeManager:
    """Manages light/dark theme switching for the application."""

    def __init__(self, root):
        self.root = root
        self.style = ttk.Style(root)
        self._theme_var = tk.StringVar(value="dark")  # default

        # Maps registrants -> (callback_or_none)
        self._observers = []

        # Load saved preference
        saved = self._load_theme_pref()
        self._theme_var.set(saved)

        # Apply initial theme
        self._current_theme = None
        self.apply(saved)

    # ── Public API ────────────────────────────────────────────────

    @property
    def theme(self):
        return self._theme_var.get()

    @theme.setter
    def theme(self, value):
        if value in PALETTES:
            self._theme_var.set(value)
            self.apply(value)
            self._save_theme_pref(value)

    def toggle(self):
        new = "light" if self._theme_var.get() == "dark" else "dark"
        self.theme = new
        return new

    def colors(self):
        return PALETTES.get(self._theme_var.get(), DARK_COLORS)

    def c(self, key, default=None):
        """Shorthand: get a single color value by key."""
        return self.colors().get(key, default)

    def register(self, callback_or_widget):
        """Register a callable(widget, theme_manager) or a tk widget for
        theme updates.  When the theme changes, the callable is invoked
        so it can reconfigure colors itself.
        """
        self._observers.append(callback_or_widget)

    def notify_all(self, theme_name):
        for cb in list(self._observers):
            try:
                cb(self)
            except Exception:
                pass

    # ── Theme application ──────────────────────────────────────────

    def apply(self, theme_name):
        if theme_name == self._current_theme:
            return
        self._current_theme = theme_name
        colors = PALETTES[theme_name]

        # Start from 'clam' (most customizable built-in theme)
        self.style.theme_use("clam")

        # -- Root / toplevel --
        self.root.configure(bg=colors["bg"])

        # -- TFrame --
        self.style.configure("TFrame", background=colors["frame_bg"])

        # -- TLabel --
        self.style.configure("TLabel",
                             background=colors["label_bg"],
                             foreground=colors["label_fg"])

        # -- TButton --
        self.style.configure("TButton",
                             background=colors["button_bg"],
                             foreground=colors["button_fg"],
                             bordercolor=colors["bg"],
                             lightcolor=colors["button_bg"],
                             darkcolor=colors["button_bg"])
        self.style.map("TButton",
                       background=[("active", colors["button_active_bg"]),
                                   ("pressed", colors["button_active_bg"])])

        # -- TEntry --
        self.style.configure("TEntry",
                             fieldbackground=colors["entry_bg"],
                             foreground=colors["entry_fg"],
                             insertcolor=colors["entry_fg"])

        # -- TCombobox --
        self.style.configure("TCombobox",
                             fieldbackground=colors["combobox_bg"],
                             foreground=colors["combobox_fg"],
                             arrowcolor=colors["fg"])
        self.style.map("TCombobox",
                       fieldbackground=[("readonly", colors["combobox_bg"])])

        # -- TCheckbutton --
        self.style.configure("TCheckbutton",
                             background=colors["checkbutton_bg"],
                             foreground=colors["checkbutton_fg"],
                             indicatorcolor=colors["button_bg"])
        self.style.map("TCheckbutton",
                       indicatorcolor=[("selected", colors["select_bg"])])

        # -- TLabelframe --
        self.style.configure("TLabelframe",
                             background=colors["labelframe_bg"],
                             foreground=colors["labelframe_fg"],
                             bordercolor=colors["scrollbar_bg"])
        self.style.configure("TLabelframe.Label",
                             background=colors["labelframe_bg"],
                             foreground=colors["labelframe_fg"])

        # -- TNotebook --
        self.style.configure("TNotebook",
                             background=colors["notebook_bg"],
                             borderwidth=1)
        self.style.configure("TNotebook.Tab",
                             background=colors["notebook_tab_bg"],
                             foreground=colors["notebook_tab_fg"],
                             padding=[12, 4])
        self.style.map("TNotebook.Tab",
                       background=[("selected", colors["notebook_tab_sel_bg"])],
                       foreground=[("selected", colors["notebook_tab_sel_fg"])])

        # -- TScrollbar --
        self.style.configure("TScrollbar",
                             background=colors["scrollbar_bg"],
                             troughcolor=colors["scrollbar_trough"],
                             bordercolor=colors["scrollbar_bg"],
                             arrowcolor=colors["fg"],
                             lightcolor=colors["scrollbar_bg"],
                             darkcolor=colors["scrollbar_bg"])
        self.style.map("TScrollbar",
                       background=[("active", colors["button_active_bg"])])

        # -- Treeview --
        self.style.configure("Treeview",
                             background=colors["treeview_bg"],
                             foreground=colors["treeview_fg"],
                             fieldbackground=colors["treeview_bg"],
                             bordercolor=colors["scrollbar_bg"])
        self.style.map("Treeview",
                       background=[("selected", colors["treeview_sel_bg"])],
                       foreground=[("selected", colors["treeview_sel_fg"])])
        self.style.configure("Treeview.Heading",
                             background=colors["treeview_heading_bg"],
                             foreground=colors["treeview_heading_fg"],
                             bordercolor=colors["scrollbar_bg"])
        self.style.map("Treeview.Heading",
                       background=[("active", colors["button_active_bg"])])

        # -- Horizontal & Vertical TScale (ttk) --
        self.style.configure("TScale",
                             background=colors["scale_bg"],
                             foreground=colors["scale_fg"],
                             troughcolor=colors["scale_trough"],
                             bordercolor=colors["scale_bg"])
        self.style.configure("Horizontal.TScale",
                             background=colors["scale_bg"],
                             troughcolor=colors["scale_trough"])
        self.style.configure("Vertical.TScale",
                             background=colors["scale_bg"],
                             troughcolor=colors["scale_trough"])

        # Notify observers
        self.notify_all(theme_name)

    # ── Persistence ────────────────────────────────────────────────

    def _load_theme_pref(self):
        try:
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, "r") as f:
                    data = json.load(f)
                val = data.get("theme", "dark")
                if val in PALETTES:
                    return val
        except Exception:
            pass
        return "dark"

    def _save_theme_pref(self, value):
        try:
            data = {}
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, "r") as f:
                    data = json.load(f)
            data["theme"] = value
            with open(CONFIG_FILE, "w") as f:
                json.dump(data, f, indent=4)
        except Exception:
            pass
