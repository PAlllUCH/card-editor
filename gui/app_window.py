import tkinter as tk
from tkinter import ttk
from gui.tabs.tab_scraper import ScraperTab
from gui.tabs.tab_editor import EditorTab
from gui.tabs.tab_layout import LayoutTab
from gui.tabs.tab_pdf_editor import PdfEditorTab  # <-- NEW IMPORT
from gui.tabs.tab_upscaling import UpscalingTab
from gui.theme_manager import ThemeManager

class MainAppWindow:
    def __init__(self, root):
        self.root = root
        self.root.title("GitHub TS Scraper & Editor")
        self.root.geometry("1150x850")
        
        # Shared Application State
        self.current_folder = ""
        self.expected_images = []
        
        # Theme manager (must be created before any widgets that depend on it)
        self.theme_manager = ThemeManager(root)
        
        self.create_menubar()
        self.create_notebook()

    def create_menubar(self):
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        view_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="View", menu=view_menu)
        
        self.theme_var = tk.StringVar(value=self.theme_manager.theme)
        view_menu.add_radiobutton(
            label="Light Mode",
            variable=self.theme_var,
            value="light",
            command=lambda: self._set_theme("light")
        )
        view_menu.add_radiobutton(
            label="Dark Mode",
            variable=self.theme_var,
            value="dark",
            command=lambda: self._set_theme("dark")
        )
        view_menu.add_separator()
        view_menu.add_command(label="Toggle Theme", command=self._toggle_theme)

    def _set_theme(self, theme_name):
        self.theme_var.set(theme_name)
        self.theme_manager.theme = theme_name

    def _toggle_theme(self):
        new = self.theme_manager.toggle()
        self.theme_var.set(new)

    def create_notebook(self):
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(expand=True, fill=tk.BOTH, padx=10, pady=10)

        # Pass self (app_controller) to the tabs so they can communicate
        self.scraper_tab = ScraperTab(self.notebook, self)
        self.editor_tab = EditorTab(self.notebook, self)
        self.layout_tab = LayoutTab(self.notebook, self)
        self.pdf_editor_tab = PdfEditorTab(self.notebook, self)  # <-- NEW INSTANCE
        self.upscaling_tab = UpscalingTab(self.notebook, self)

        self.notebook.add(self.scraper_tab.frame, text="1. Scraper")
        self.notebook.add(self.editor_tab.frame, text="2. Image Editor")
        self.notebook.add(self.layout_tab.frame, text="3. Print Layout")
        self.notebook.add(self.pdf_editor_tab.frame, text="4. PDF Editor")  # <-- NEW TAB
        self.notebook.add(self.upscaling_tab.frame, text="5. Upscaling")

    def switch_to_editor(self):
        self.editor_tab.load_editor_files()
        self.notebook.select(self.editor_tab.frame)