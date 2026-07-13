import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
import subprocess
import cv2
import numpy as np
from core.image_editor import process_image_advanced
from gui.components.image_preview import ImagePreviewComponent

class EditorTab:
    def __init__(self, parent_notebook, app_controller):
        self.frame = ttk.Frame(parent_notebook)
        self.app = app_controller
        
        self.orig_w_px = 0
        self.orig_h_px = 0
        self.size_info_var = tk.StringVar(value="Select an image to see dimensions.")
        
        # Track data structures for selection and sequence mechanics
        self.file_checks = {}
        self.file_labels = {}       # Maps filename -> tk.Label widget reference
        self.filenames_list = []    # Keeps an ordered list of current files for step navigation
        self.selected_label_item = None
        self.selected_filename = None
        
        self.build_ui()
        self.bind_keyboard_navigation()
        # Register for theme changes
        if hasattr(self.app, 'theme_manager'):
            self.app.theme_manager.register(self._apply_theme)

    def build_ui(self):
        # ----------------------------------------------------
        # LEFT PANEL: Interactive Checkbox Queue & Directories
        # ----------------------------------------------------
        left_panel = ttk.Frame(self.frame, width=280)
        left_panel.pack(side=tk.LEFT, fill=tk.Y, padx=10, pady=10)
        left_panel.pack_propagate(False) 
        
        ttk.Button(left_panel, text="Load Folder via CSV", command=self.load_from_csv).pack(fill=tk.X, pady=(0, 10))
        
        # Target Output Directory Selector
        out_group = ttk.LabelFrame(left_panel, text="Output Directory Setup", padding="5")
        out_group.pack(fill=tk.X, pady=(0, 10))
        self.out_folder_var = tk.StringVar()
        ttk.Entry(out_group, textvariable=self.out_folder_var, width=18).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        ttk.Button(out_group, text="Browse", command=self.browse_output_folder, width=6).pack(side=tk.RIGHT)
        
        tool_frame = ttk.Frame(left_panel)
        tool_frame.pack(fill=tk.X, pady=(0, 5))
        ttk.Button(tool_frame, text="Select All", command=self.select_all_files, width=10).pack(side=tk.LEFT, padx=(0, 2))
        ttk.Button(tool_frame, text="Deselect All", command=self.deselect_all_files, width=12).pack(side=tk.LEFT)
        
        ttk.Label(left_panel, text="Queue List (Click text to select preview):").pack(anchor=tk.W, pady=(5, 0))
        
        list_container = ttk.Frame(left_panel, relief=tk.SUNKEN, borderwidth=1)
        list_container.pack(expand=True, fill=tk.BOTH, pady=5)
        
        self.canvas = tk.Canvas(list_container, bd=0, highlightthickness=0, bg=getattr(self.app, 'theme_manager', None) and self.app.theme_manager.c("tk_canvas_bg") or "#ffffff")
        scrollbar = ttk.Scrollbar(list_container, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = ttk.Frame(self.canvas)
        
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=scrollbar.set)
        
        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # ----------------------------------------------------
        # RIGHT PANEL: Main Processing Workflow
        # ----------------------------------------------------
        right_panel = ttk.Frame(self.frame)
        right_panel.pack(side=tk.RIGHT, expand=True, fill=tk.BOTH, padx=10, pady=10)

        self.preview_lbl = ImagePreviewComponent(right_panel, theme_manager=getattr(self.app, 'theme_manager', None))
        self.preview_lbl.pack(expand=True, fill=tk.BOTH, pady=(0, 10))

        controls = ttk.LabelFrame(right_panel, text="OpenCV Processing Pipeline", padding="5")
        controls.pack(fill=tk.X, pady=5)

        col1 = ttk.Frame(controls)
        col1.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)
        col2 = ttk.Frame(controls)
        col2.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)
        col3 = ttk.Frame(controls)
        col3.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)

        # --- STEP 0: BACKGROUND REMOVAL ---
        bg_group = ttk.LabelFrame(col1, text="0. Background Removal", padding="5")
        bg_group.pack(fill=tk.X, pady=(0, 5))

        self.bg_remove_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(bg_group, text="Enable Removal", variable=self.bg_remove_var).grid(row=0, column=0, sticky=tk.W)
        
        self.bg_method_var = tk.StringVar(value="Contour Isolation")
        bg_methods = ["Contour Isolation", "GrabCut Auto"]
        ttk.Combobox(bg_group, textvariable=self.bg_method_var, values=bg_methods, state="readonly", width=18).grid(row=0, column=1, sticky=tk.W, padx=5)

        # --- STEP 1: CORNER FILL ---
        fill_group = ttk.LabelFrame(col1, text="1. Corner Fill Algorithm", padding="5")
        fill_group.pack(fill=tk.X, pady=(0, 5))

        self.fill_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(fill_group, text="Enable Fill", variable=self.fill_var).grid(row=0, column=0, sticky=tk.W)
        
        self.fill_mode = tk.StringVar(value="Dual-Axis Mirror")
        modes = ["Telea Inpaint (Soft)", "Navier-Stokes (Sharp)", "Pixel Stretch", "Smooth Pixel Stretch", "Edge Mirror", "Dual-Axis Mirror", "Gradient Edge Blend"]
        ttk.Combobox(fill_group, textvariable=self.fill_mode, values=modes, state="readonly", width=18).grid(row=0, column=1, sticky=tk.W, padx=5)

        self.fill_size_lbl = ttk.Label(fill_group, text="Corner Size:")
        self.fill_size_lbl.grid(row=1, column=0, columnspan=2, sticky=tk.W, pady=(5, 0))
        self.fill_size = tk.Scale(fill_group, from_=0.1, to=15.0, resolution=0.1, orient=tk.HORIZONTAL, length=180, command=self.update_pixel_labels)
        self.fill_size.set(3.0) 
        self.fill_size.grid(row=2, column=0, columnspan=2, sticky=tk.EW)

        ttk.Label(fill_group, text="Inpaint Radius (px):").grid(row=3, column=0, sticky=tk.E, pady=(5, 0))
        self.inpaint_rad = tk.Scale(fill_group, from_=1, to=50, orient=tk.HORIZONTAL, length=100)
        self.inpaint_rad.set(15) 
        self.inpaint_rad.grid(row=3, column=1, sticky=tk.W, pady=(5, 0))

        # --- BLENDING SUB-GROUP ---
        blend_group = ttk.LabelFrame(col1, text="2. Gradient Blending", padding="5")
        blend_group.pack(fill=tk.X)

        self.blend_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(blend_group, text="Enable Blend", variable=self.blend_var).grid(row=0, column=0, sticky=tk.W)

        self.blend_stage = tk.StringVar(value="Before Bleed")
        ttk.Combobox(blend_group, textvariable=self.blend_stage, values=["Before Color", "Before Bleed", "After Bleed"], state="readonly", width=14).grid(row=0, column=1, sticky=tk.W, padx=5)

        self.blend_type = tk.StringVar(value="Shadow (Vignette)")
        ttk.Combobox(blend_group, textvariable=self.blend_type, values=["Shadow (Vignette)", "Blur (Soft)"], state="readonly", width=14).grid(row=1, column=1, sticky=tk.W, padx=5, pady=2)
        ttk.Label(blend_group, text="Blend Style:").grid(row=1, column=0, sticky=tk.E)

        self.corner_fade_lbl = ttk.Label(blend_group, text="Corner Fade:")
        self.corner_fade_lbl.grid(row=2, column=0, columnspan=2, sticky=tk.W, pady=(5, 0))
        self.corner_fade = tk.Scale(blend_group, from_=0.0, to=15.0, resolution=0.1, orient=tk.HORIZONTAL, length=180, command=self.update_pixel_labels)
        self.corner_fade.set(2.0) 
        self.corner_fade.grid(row=3, column=0, columnspan=2, sticky=tk.EW)

        self.margin_fade_lbl = ttk.Label(blend_group, text="Margin Fade:")
        self.margin_fade_lbl.grid(row=4, column=0, columnspan=2, sticky=tk.W, pady=(5, 0))
        self.margin_fade = tk.Scale(blend_group, from_=0.0, to=10.0, resolution=0.1, orient=tk.HORIZONTAL, length=180, command=self.update_pixel_labels)
        self.margin_fade.set(1.0) 
        self.margin_fade.grid(row=5, column=0, columnspan=2, sticky=tk.EW)

        ttk.Label(blend_group, text="Blend Strength (%):").grid(row=6, column=0, sticky=tk.E, pady=5)
        self.blend_str = tk.Scale(blend_group, from_=1, to=100, orient=tk.HORIZONTAL, length=100)
        self.blend_str.set(100) 
        self.blend_str.grid(row=6, column=1, sticky=tk.W, pady=5)

        ttk.Label(blend_group, text="Add Grain/Noise:").grid(row=7, column=0, sticky=tk.E)
        self.noise_amount = tk.Scale(blend_group, from_=0, to=50, orient=tk.HORIZONTAL, length=100)
        self.noise_amount.set(5) 
        self.noise_amount.grid(row=7, column=1, sticky=tk.W)

        # --- COL 2: COLOR GRADING ---
        color_group = ttk.LabelFrame(col2, text="3. Color Grading", padding="5")
        color_group.pack(fill=tk.BOTH, expand=True)

        self.color_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(color_group, text="Enable Grading", variable=self.color_var).grid(row=0, column=0, sticky=tk.W, pady=2)

        self.color_preset = tk.StringVar(value="Arkham Horror LCG")
        preset_cb = ttk.Combobox(color_group, textvariable=self.color_preset, values=["Custom", "Arkham Horror LCG", "Vibrant", "Dark & Gritty", "Vintage Sepia"], state="readonly", width=16)
        preset_cb.grid(row=0, column=1, sticky=tk.W, padx=5)
        preset_cb.bind("<<ComboboxSelected>>", self.apply_color_preset)

        ttk.Label(color_group, text="Sat (%):").grid(row=1, column=0, sticky=tk.E)
        self.col_sat = tk.Scale(color_group, from_=0, to=200, orient=tk.HORIZONTAL, length=100)
        self.col_sat.grid(row=1, column=1, sticky=tk.W)

        ttk.Label(color_group, text="Con (%):").grid(row=2, column=0, sticky=tk.E)
        self.col_con = tk.Scale(color_group, from_=0, to=200, orient=tk.HORIZONTAL, length=100)
        self.col_con.grid(row=2, column=1, sticky=tk.W)

        ttk.Label(color_group, text="Bright:").grid(row=3, column=0, sticky=tk.E)
        self.col_bri = tk.Scale(color_group, from_=-100, to=100, orient=tk.HORIZONTAL, length=100)
        self.col_bri.grid(row=3, column=1, sticky=tk.W)

        ttk.Label(color_group, text="Sepia (%):").grid(row=4, column=0, sticky=tk.E)
        self.col_sepia = tk.Scale(color_group, from_=0, to=100, orient=tk.HORIZONTAL, length=100)
        self.col_sepia.grid(row=4, column=1, sticky=tk.W)
        self.apply_color_preset()

        # --- COL 3: PHYSICAL SIZING & BLEED ---
        size_group = ttk.LabelFrame(col3, text="4. Sizing & Bleed (Spad)", padding="5")
        size_group.pack(fill=tk.BOTH, expand=True)

        self.dpi_var = tk.StringVar(value="300")
        self.resize_var = tk.BooleanVar(value=True)
        self.base_w = tk.StringVar(value="63.0")
        self.base_h = tk.StringVar(value="88.0")
        self.spad_var = tk.BooleanVar(value=True)
        self.spad_t = tk.StringVar(value="2.0")
        self.spad_b = tk.StringVar(value="2.0")
        self.spad_l = tk.StringVar(value="2.0")
        self.spad_r = tk.StringVar(value="2.0")

        for var in [self.dpi_var, self.resize_var, self.base_w, self.base_h, self.spad_var, self.spad_t, self.spad_b, self.spad_l, self.spad_r]:
            var.trace_add('write', self.update_size_labels)

        row0 = ttk.Frame(size_group)
        row0.pack(fill=tk.X, pady=2)
        ttk.Checkbutton(row0, text="Fix Base Size to:", variable=self.resize_var).pack(side=tk.LEFT)
        ttk.Entry(row0, textvariable=self.dpi_var, width=4).pack(side=tk.RIGHT)
        ttk.Label(row0, text="DPI:").pack(side=tk.RIGHT, padx=2)

        row1 = ttk.Frame(size_group)
        row1.pack(fill=tk.X, pady=2)
        ttk.Entry(row1, textvariable=self.base_w, width=6).pack(side=tk.LEFT, padx=2)
        ttk.Label(row1, text="W  x ").pack(side=tk.LEFT)
        ttk.Entry(row1, textvariable=self.base_h, width=6).pack(side=tk.LEFT, padx=2)
        ttk.Label(row1, text="H (mm)").pack(side=tk.LEFT)

        row2 = ttk.Frame(size_group)
        row2.pack(fill=tk.X, pady=(10, 2))
        ttk.Checkbutton(row2, text="Add Bleed (Spad)", variable=self.spad_var).pack(side=tk.LEFT)

        row3 = ttk.Frame(size_group)
        row3.pack(fill=tk.X, pady=2)
        ttk.Label(row3, text="T:").pack(side=tk.LEFT)
        ttk.Entry(row3, textvariable=self.spad_t, width=4).pack(side=tk.LEFT, padx=2)
        ttk.Label(row3, text="B:").pack(side=tk.LEFT)
        ttk.Entry(row3, textvariable=self.spad_b, width=4).pack(side=tk.LEFT, padx=2)
        ttk.Label(row3, text="L:").pack(side=tk.LEFT)
        ttk.Entry(row3, textvariable=self.spad_l, width=4).pack(side=tk.LEFT, padx=2)
        ttk.Label(row3, text="R:").pack(side=tk.LEFT)
        ttk.Entry(row3, textvariable=self.spad_r, width=4).pack(side=tk.LEFT, padx=2)

        self.calc_lbl = tk.Label(size_group, textvariable=self.size_info_var, justify=tk.LEFT, font=("Consolas", 8))
        self.calc_lbl.pack(fill=tk.X, pady=(10, 0))

        # ----------------------------------------------------
        # BOTTOM CONTROLS ACTIONS PANEL
        # ----------------------------------------------------
        actions = ttk.Frame(right_panel)
        actions.pack(fill=tk.X, pady=10)

        # Group 1: Consolidated Navigation & Preview Controls
        nav_preview_group = ttk.LabelFrame(actions, text="Navigation & Preview Controls", padding="5")
        nav_preview_group.pack(side=tk.LEFT, padx=(0, 10))

        ttk.Button(nav_preview_group, text="◀ Prev", command=lambda: self.navigate_queue(-1), width=8).pack(side=tk.LEFT, padx=2)
        self.toggle_check_btn = ttk.Button(nav_preview_group, text="Select/Deselect", command=self.toggle_current_file_check, width=15)
        self.toggle_check_btn.pack(side=tk.LEFT, padx=2)
        ttk.Button(nav_preview_group, text="Next ▶", command=lambda: self.navigate_queue(1), width=8).pack(side=tk.LEFT, padx=2)
        ttk.Button(nav_preview_group, text="Preview Edit", command=self.preview_current_edit).pack(side=tk.LEFT, padx=(10, 2))

        # Group 2: Deployment Management (To New Subfolder via Suffix renaming)
        deploy_group = ttk.LabelFrame(actions, text="Deployment Management", padding="5")
        deploy_group.pack(side=tk.LEFT, padx=(0, 10))

        ttk.Button(deploy_group, text="Save Current", command=self.save_current_edit).pack(side=tk.LEFT, padx=2)
        ttk.Button(deploy_group, text="Batch Apply to SELECTED", command=self.batch_apply_edits).pack(side=tk.LEFT, padx=2)
        
        # Group 3: Overwrite Management (Modifies files directly in place, keeps CSV unchanged)
        overwrite_group = ttk.LabelFrame(actions, text="Overwrite Management", padding="5")
        overwrite_group.pack(side=tk.LEFT)

        ttk.Button(overwrite_group, text="Overwrite Current", command=self.overwrite_current_in_place).pack(side=tk.LEFT, padx=2)
        ttk.Button(overwrite_group, text="Batch Overwrite SELECTED", command=self.batch_overwrite_in_place).pack(side=tk.LEFT, padx=2)

        # Group 4: Integrated Post-Processing BAT Automation Block
        bat_group = ttk.LabelFrame(right_panel, text="Post-Process automation Script (.bat)", padding="5")
        bat_group.pack(fill=tk.X, pady=5)
        
        self.bat_entry = ttk.Entry(bat_group, width=30)
        self.bat_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 5))
        ttk.Button(bat_group, text="Browse Script", command=self.browse_bat).pack(side=tk.LEFT, padx=2)
        ttk.Button(bat_group, text="Run Bat Script", command=self.execute_bat).pack(side=tk.RIGHT, padx=5)

    def bind_keyboard_navigation(self):
        self.app.root.bind("<Up>", lambda event: self.handle_arrow_navigation(-1))
        self.app.root.bind("<Down>", lambda event: self.handle_arrow_navigation(1))

    def handle_arrow_navigation(self, direction):
        focused_widget = self.app.root.focus_get()
        if isinstance(focused_widget, (tk.Entry, ttk.Entry, ttk.Combobox)):
            return 
        self.navigate_queue(direction)

    def navigate_queue(self, direction):
        if not self.filenames_list: return
        if self.selected_filename in self.filenames_list:
            curr_idx = self.filenames_list.index(self.selected_filename)
            new_idx = curr_idx + direction
            new_idx = max(0, min(new_idx, len(self.filenames_list) - 1))
        else:
            new_idx = 0
            
        target_file = self.filenames_list[new_idx]
        target_label = self.file_labels.get(target_file)
        
        if target_label:
            self.on_custom_file_click(target_file, target_label)
            self.scroll_to_visible(target_label)

    def scroll_to_visible(self, label_widget):
        self.canvas.update_idletasks()
        row_frame = label_widget.master 
        y_pos = row_frame.winfo_y()
        frame_height = self.scrollable_frame.winfo_height()
        canvas_height = self.canvas.winfo_height()
        
        if frame_height > canvas_height:
            fraction = y_pos / float(frame_height)
            self.canvas.yview_moveto(max(0, fraction - (canvas_height / (2.0 * frame_height))))

    def toggle_current_file_check(self):
        if not self.selected_filename: return
        var = self.file_checks.get(self.selected_filename)
        if var:
            var.set(not var.get())

    def browse_output_folder(self):
        folder = filedialog.askdirectory(title="Select Output Directory for Edited Cards")
        if folder:
            self.out_folder_var.set(folder)

    def load_from_csv(self):
        filepath = filedialog.askopenfilename(
            title="Select cards_data.csv", 
            filetypes=(("CSV Files", "*.csv"), ("All files", "*.*"))
        )
        if filepath:
            self.app.current_folder = os.path.dirname(filepath)
            self.load_editor_files()
            messagebox.showinfo("Loaded", f"Loaded directory:\n{self.app.current_folder}")

    def load_editor_files(self):
        for child in self.scrollable_frame.winfo_children():
            child.destroy()
        self.file_checks.clear()
        self.file_labels.clear()
        self.filenames_list = []
        self.selected_label_item = None
        self.selected_filename = None

        if not self.app.current_folder: return
        valid_exts = ('.png', '.jpg', '.jpeg', '.webp', '.bmp')
        sorted_files = sorted(os.listdir(self.app.current_folder))
        
        for file in sorted_files:
            if file.lower().endswith(valid_exts):
                self.filenames_list.append(file)
                row = ttk.Frame(self.scrollable_frame)
                row.pack(fill=tk.X, anchor=tk.W, pady=1, padx=2)
                
                var = tk.BooleanVar(value=True)
                self.file_checks[file] = var
                
                cb = ttk.Checkbutton(row, variable=var)
                cb.pack(side=tk.LEFT)
                
                tm = getattr(self.app, 'theme_manager', None)
                row_bg = tm.c("file_row_bg") if tm else self.frame.winfo_toplevel().cget("bg")
                row_fg = tm.c("file_row_fg") if tm else "black"
                lbl = tk.Label(row, text=file, anchor=tk.W, bg=row_bg, fg=row_fg, padx=3)
                lbl.pack(side=tk.LEFT, fill=tk.X, expand=True)
                
                self.file_labels[file] = lbl
                lbl.bind("<Button-1>", lambda event, f=file, l=lbl: self.on_custom_file_click(f, l))

    def on_custom_file_click(self, filename, label_widget):
        tm = getattr(self.app, 'theme_manager', None)
        if self.selected_label_item:
            normal_bg = tm.c("file_row_bg") if tm else self.frame.winfo_toplevel().cget("bg")
            normal_fg = tm.c("file_row_fg") if tm else "black"
            self.selected_label_item.config(bg=normal_bg, fg=normal_fg)
            
        self.selected_label_item = label_widget
        self.selected_filename = filename
        hl_bg = tm.c("highlight_bg") if tm else "#0078d7"
        hl_fg = tm.c("highlight_fg") if tm else "white"
        label_widget.config(bg=hl_bg, fg=hl_fg) 
        
        filepath = os.path.join(self.app.current_folder, filename)
        try:
            file_bytes = np.fromfile(filepath, dtype=np.uint8)
            img = cv2.imdecode(file_bytes, cv2.IMREAD_UNCHANGED)
            if img is not None:
                self.orig_h_px, self.orig_w_px = img.shape[:2]
                self.update_size_labels() 
                
                if len(img.shape) == 3 and img.shape[2] == 4:
                    img = img[:, :, :3]
                rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                from PIL import Image
                self.preview_lbl.display_image(Image.fromarray(rgb))
        except Exception as e:
            self.preview_lbl.config(image='', text=f"Error loading original:\n{e}")

    def select_all_files(self):
        for var in self.file_checks.values():
            var.set(True)

    def deselect_all_files(self):
        for var in self.file_checks.values():
            var.set(False)

    def _apply_theme(self, tm):
        """Update tk widget colors when theme changes."""
        colors = tm.colors()
        # Canvas (file list container)
        if hasattr(self, 'canvas'):
            self.canvas.configure(bg=colors["tk_canvas_bg"])
        # Size calc label
        if hasattr(self, 'calc_lbl'):
            self.calc_lbl.configure(bg=colors["size_calc_bg"], fg=colors["size_calc_fg"])
        # tk.Scale widgets
        for attr in ('fill_size', 'inpaint_rad', 'corner_fade', 'margin_fade',
                     'blend_str', 'noise_amount', 'col_sat', 'col_con',
                     'col_bri', 'col_sepia'):
            widget = getattr(self, attr, None)
            if widget:
                widget.configure(bg=colors["tk_scale_bg"],
                                 fg=colors["tk_scale_fg"],
                                 troughcolor=colors["tk_scale_trough"],
                                 highlightbackground=colors["tk_scale_highlight"])
        # File labels (dynamically created)
        normal_bg = colors["file_row_bg"]
        normal_fg = colors["file_row_fg"]
        hl_bg = colors["highlight_bg"]
        hl_fg = colors["highlight_fg"]
        for filename, lbl in self.file_labels.items():
            if lbl is self.selected_label_item:
                lbl.configure(bg=hl_bg, fg=hl_fg)
            else:
                lbl.configure(bg=normal_bg, fg=normal_fg)

    def preview_current_edit(self):
        if not self.selected_filename:
            messagebox.showinfo("Select", "Click on a card filename text in the queue to select it for preview first.")
            return
            
        filepath = os.path.join(self.app.current_folder, self.selected_filename)
        self.preview_lbl.config(image='', text="Processing preview...")
        self.app.root.update_idletasks() 
        
        params = self._get_current_params()
        img = process_image_advanced(filepath=filepath, save=False, **params)
        self.preview_lbl.display_image(img)

    def save_current_edit(self):
        if not self.selected_filename: return
        out_dir = self.out_folder_var.get().strip()
        if not out_dir:
            messagebox.showerror("Error", "Please configure your Output Directory first.")
            return
            
        os.makedirs(out_dir, exist_ok=True)
        filepath = os.path.join(self.app.current_folder, self.selected_filename)
        name, ext = os.path.splitext(self.selected_filename)
        new_filename = f"{name}_edited{ext}"
        save_path = os.path.join(out_dir, new_filename)
        
        params = self._get_current_params()
        process_image_advanced(filepath=filepath, save=True, save_path=save_path, **params)
        
        messagebox.showinfo("Saved", f"Exported file to target output folder:\n{new_filename}")

    def overwrite_current_in_place(self):
        """Directly updates the current image inside the source folder without renaming."""
        if not self.selected_filename: return
        filepath = os.path.join(self.app.current_folder, self.selected_filename)
        
        params = self._get_current_params()
        # Passing save_path=filepath triggers an absolute file overwrite
        process_image_advanced(filepath=filepath, save=True, save_path=filepath, **params)
        
        messagebox.showinfo("Overwritten", f"Overwrote original file source in place:\n{self.selected_filename}")
        self.on_custom_file_click(self.selected_filename, self.selected_label_item)

    def batch_overwrite_in_place(self):
        """Overwrites all checked items inside the working source directory in place."""
        if not self.app.current_folder: return
        
        selected_targets = [filename for filename, var in self.file_checks.items() if var.get()]
        if not selected_targets:
            messagebox.showwarning("No Selection", "No card checkboxes are ticked for overwrite operations.")
            return
            
        confirm_msg = f"CRITICAL: This will permanently modify and overwrite {len(selected_targets)} raw source files in place without renaming or changing the CSV layout. Proceed?"
        if not messagebox.askyesno("Confirm In-Place Overwrite", confirm_msg):
            return

        self.preview_lbl.config(image='', text="Processing structural overwrites... Please wait.")
        self.app.root.update_idletasks()

        params = self._get_current_params()
        for filename in selected_targets:
            filepath = os.path.join(self.app.current_folder, filename)
            process_image_advanced(filepath=filepath, save=True, save_path=filepath, **params)
            
        messagebox.showinfo("Done", f"Successfully updated {len(selected_targets)} images inside the working source directory.")
        if self.selected_filename:
            self.on_custom_file_click(self.selected_filename, self.selected_label_item)

    def batch_apply_edits(self):
        import csv 
        
        if not self.app.current_folder: return
        out_dir = self.out_folder_var.get().strip()
        if not out_dir:
            messagebox.showerror("Error", "Please configure your Output Directory first.")
            return
        
        selected_targets = [filename for filename, var in self.file_checks.items() if var.get()]
        if not selected_targets:
            messagebox.showwarning("No Selection", "No card checkboxes are ticked for batch operations.")
            return
            
        confirm_msg = f"This will process and export {len(selected_targets)} cards to the target directory. Proceed?"
        if not messagebox.askyesno("Confirm Batch", confirm_msg):
            return

        self.preview_lbl.config(image='', text="Processing batch selection... Please wait.")
        self.app.root.update_idletasks()

        os.makedirs(out_dir, exist_ok=True)
        processed_set = set()
        params = self._get_current_params()
        
        for filename in selected_targets:
            filepath = os.path.join(self.app.current_folder, filename)
            name, ext = os.path.splitext(filename)
            new_filename = f"{name}_edited{ext}"
            save_path = os.path.join(out_dir, new_filename)
            
            process_image_advanced(filepath=filepath, save=True, save_path=save_path, **params)
            processed_set.add(filename)

        src_csv_path = os.path.join(self.app.current_folder, "cards_data.csv")
        dest_csv_path = os.path.join(out_dir, "cards_data.csv")
        
        if os.path.exists(src_csv_path):
            try:
                with open(src_csv_path, 'r', encoding='utf-8') as f:
                    sample = f.read(4096)
                    if '\t' in sample:
                        delim = '\t'
                    elif ';' in sample:
                        delim = ';'
                    else:
                        delim = ','

                rows = []
                with open(src_csv_path, 'r', encoding='utf-8', newline='') as f:
                    reader = csv.DictReader(f, delimiter=delim, skipinitialspace=True)
                    fieldnames = reader.fieldnames
                    for row in reader:
                        rows.append(dict(row))

                for row in rows:
                    orig_front = row.get('front name', '')
                    orig_back = row.get('back name', '')
                    
                    if orig_front in processed_set:
                        f_name, f_ext = os.path.splitext(orig_front)
                        row['front name'] = f"{f_name}_edited{f_ext}"
                        
                    if orig_back in processed_set:
                        b_name, b_ext = os.path.splitext(orig_back)
                        row['back name'] = f"{b_name}_edited{b_ext}"

                with open(dest_csv_path, 'w', encoding='utf-8', newline='') as f:
                    writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=delim, quoting=csv.QUOTE_MINIMAL)
                    writer.writeheader()
                    writer.writerows(rows)
                    
                csv_status_msg = "\nMirrored and updated source 'cards_data.csv' to output folder."
            except Exception as e:
                csv_status_msg = f"\n[Warning] Could not update source CSV metadata: {e}"
        else:
            csv_status_msg = "\n[Warning] Source 'cards_data.csv' not found. Skip mapping updates."
        
        messagebox.showinfo("Done", f"Batch complete! Exported {len(selected_targets)} cards.{csv_status_msg}")
        self.preview_lbl.config(text="Batch complete. Select an image text to preview.")

    def _get_target_min_px(self):
        try:
            dpi = float(self.dpi_var.get() or 300)
            if self.resize_var.get():
                base_w = float(self.base_w.get() or 0)
                base_h = float(self.base_h.get() or 0)
                w_px = int((base_w / 25.4) * dpi)
                h_px = int((base_h / 25.4) * dpi)
            else:
                w_px = self.orig_w_px
                h_px = self.orig_h_px
            return min(w_px, h_px) if (w_px and h_px) else 0
        except ValueError:
            return 0

    def update_pixel_labels(self, *args):
        min_px = self._get_target_min_px()
        fs_val = float(self.fill_size.get())
        cf_val = float(self.corner_fade.get())
        mf_val = float(self.margin_fade.get())
        
        if min_px > 0:
            self.fill_size_lbl.config(text=f"Corner Size: {fs_val:.1f}% ({int(min_px * fs_val / 100)} px)")
            self.corner_fade_lbl.config(text=f"Corner Fade: {cf_val:.1f}% ({int(min_px * cf_val / 100)} px)")
            self.margin_fade_lbl.config(text=f"Margin Fade: {mf_val:.1f}% ({int(min_px * mf_val / 100)} px)")
        else:
            self.fill_size_lbl.config(text=f"Corner Size: {fs_val:.1f}% (-- px)")
            self.corner_fade_lbl.config(text=f"Corner Fade: {cf_val:.1f}% (-- px)")
            self.margin_fade_lbl.config(text=f"Margin Fade: {mf_val:.1f}% (-- px)")

    def update_size_labels(self, *args):
        try:
            dpi = float(self.dpi_var.get() or 300)
            if dpi <= 0: return

            if self.resize_var.get():
                base_w = float(self.base_w.get() or 0)
                base_h = float(self.base_h.get() or 0)
            else:
                base_w = (self.orig_w_px / dpi) * 25.4 if self.orig_w_px else 0
                base_h = (self.orig_h_px / dpi) * 25.4 if self.orig_h_px else 0
                
            if self.spad_var.get():
                t = float(self.spad_t.get() or 0)
                b = float(self.spad_b.get() or 0)
                l = float(self.spad_l.get() or 0)
                r = float(self.spad_r.get() or 0)
            else:
                t = b = l = r = 0
                
            final_w_mm = base_w + l + r
            final_h_mm = base_h + t + b
            
            final_w_px = int((final_w_mm / 25.4) * dpi)
            final_h_px = int((final_h_mm / 25.4) * dpi)
            
            info_str = f"Orig Px: {self.orig_w_px} x {self.orig_h_px}\n"
            info_str += f"Final mm: {final_w_mm:.1f} x {final_h_mm:.1f}\n"
            info_str += f"Final Px: {final_w_px} x {final_h_px}"
            
            self.size_info_var.set(info_str)
            self.update_pixel_labels()
        except ValueError:
            self.size_info_var.set("Waiting for valid numbers...")

    def apply_color_preset(self, event=None):
        preset = self.color_preset.get()
        presets = {
            'Arkham Horror LCG': {'sat': 110, 'con': 105, 'bri': 2, 'sepia': 0},
            'Vibrant': {'sat': 130, 'con': 110, 'bri': 5, 'sepia': 0},
            'Dark & Gritty': {'sat': 85, 'con': 115, 'bri': -10, 'sepia': 0},
            'Vintage Sepia': {'sat': 80, 'con': 100, 'bri': 0, 'sepia': 65}
        }
        if preset in presets:
            vals = presets[preset]
            self.col_sat.set(vals['sat'])
            self.col_con.set(vals['con'])
            self.col_bri.set(vals['bri'])
            self.col_sepia.set(vals['sepia'])

    def browse_bat(self):
        filename = filedialog.askopenfilename(title="Select Batch File", filetypes=(("Batch files", "*.bat"), ("All files", "*.*")))
        if filename:
            self.bat_entry.delete(0, tk.END); self.bat_entry.insert(0, filename)

    def _get_current_params(self):
        self.color_preset.set("Custom")
        try: t_w = float(self.base_w.get() or 63.0)
        except ValueError: t_w = 63.0
        try: t_h = float(self.base_h.get() or 88.0)
        except ValueError: t_h = 88.0
        try: dpi = float(self.dpi_var.get() or 300)
        except ValueError: dpi = 300
        try: s_t = float(self.spad_t.get() or 0)
        except ValueError: s_t = 0
        try: s_b = float(self.spad_b.get() or 0)
        except ValueError: s_b = 0
        try: s_l = float(self.spad_l.get() or 0)
        except ValueError: s_l = 0
        try: s_r = float(self.spad_r.get() or 0)
        except ValueError: s_r = 0

        return {
            'do_bg_remove': self.bg_remove_var.get(),
            'bg_method': self.bg_method_var.get(),
            
            'do_resize_mm': self.resize_var.get(),
            'target_w_mm': t_w,
            'target_h_mm': t_h,
            'dpi': dpi,
            
            'do_corner_fill': self.fill_var.get(),
            'fill_mode': self.fill_mode.get(),
            'corner_size': float(self.fill_size.get()),
            'inpaint_radius': self.inpaint_rad.get(),
            
            'do_blend': self.blend_var.get(),
            'blend_stage': self.blend_stage.get(),
            'blend_type': self.blend_type.get(),
            'corner_fade': float(self.corner_fade.get()),
            'margin_fade': float(self.margin_fade.get()),
            'blend_strength': self.blend_str.get(),
            'noise_amount': self.noise_amount.get(),
            
            'do_color': self.color_var.get(),
            'saturation': self.col_sat.get(),
            'contrast': self.col_con.get(),
            'brightness': self.col_bri.get(),
            'sepia': self.col_sepia.get(),
            
            'do_spad': self.spad_var.get(),
            'spad_t': s_t,
            'spad_b': s_b,
            'spad_l': s_l,
            'spad_r': s_r
        }

    def execute_bat(self):
        bat_path = self.bat_entry.get().strip()
        if not bat_path or not os.path.exists(bat_path):
            messagebox.showerror("Error", "Please select a valid .bat file.")
            return
        if not self.app.current_folder:
            messagebox.showerror("Error", "No scraped folder found to execute in.")
            return

        try:
            self.preview_lbl.config(image='', text="Running BAT script...\nCheck Scraper console for logs.")
            self.app.root.update_idletasks()
            self.app.notebook.select(self.app.scraper_tab.frame)
            self.app.scraper_tab.log("\n[ EXECUTING .BAT SCRIPT ]")
            
            process = subprocess.Popen(
                [bat_path], shell=True, cwd=self.app.current_folder, 
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )
            for line in process.stdout:
                if line.strip(): self.app.scraper_tab.log(line.strip())
            process.wait() 
            
            if process.returncode == 0:
                self.app.scraper_tab.log(f"--- Batch script finished successfully ---")
            else:
                self.app.scraper_tab.log(f"--- Batch script failed (Exit Code: {process.returncode}) ---")
                for err in process.stderr:
                    if err.strip(): self.app.scraper_tab.log(f"[ERROR] {err.strip()}")
        except Exception as e:
            self.app.scraper_tab.log(f"Failed to execute batch file: {e}")