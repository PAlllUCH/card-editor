import tkinter as tk
from tkinter import ttk
from gui.tabs.tab_scraper import ScraperTab
from gui.tabs.tab_editor import EditorTab
from gui.tabs.tab_layout import LayoutTab
from gui.tabs.tab_pdf_editor import PdfEditorTab  # <-- NEW IMPORT
from gui.tabs.tab_upscaling import UpscalingTab

class MainAppWindow:
    def __init__(self, root):
        self.root = root
        self.root.title("GitHub TS Scraper & Editor")
        self.root.geometry("1150x850")
        
        # Shared Application State
        self.current_folder = ""
        self.expected_images = []
        
        self.create_notebook()

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