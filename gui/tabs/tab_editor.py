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
        
        self.build_ui()

    def build_ui(self):
        left_panel = ttk.Frame(self.frame, width=250)
        left_panel.pack(side=tk.LEFT, fill=tk.Y, padx=10, pady=10)
        
        ttk.Button(left_panel, text="Load Folder via CSV", command=self.load_from_csv).pack(fill=tk.X, pady=(0, 10))
        ttk.Label(left_panel, text="Downloaded Cards:").pack(anchor=tk.W)
        self.file_listbox = tk.Listbox(left_panel, width=30, exportselection=False)
        self.file_listbox.pack(expand=True, fill=tk.Y, pady=5)
        self.file_listbox.bind('<<ListboxSelect>>', self.on_file_select)
        
        right_panel = ttk.Frame(self.frame)
        right_panel.pack(side=tk.RIGHT, expand=True, fill=tk.BOTH, padx=10, pady=10)

        self.preview_lbl = ImagePreviewComponent(right_panel)
        self.preview_lbl.pack(expand=True, fill=tk.BOTH, pady=(0, 10))

        controls = ttk.LabelFrame(right_panel, text="OpenCV Processing Pipeline", padding="5")
        controls.pack(fill=tk.X, pady=5)

        col1 = ttk.Frame(controls)
        col1.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)
        col2 = ttk.Frame(controls)
        col2.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)
        col3 = ttk.Frame(controls)
        col3.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)

        # ----------------------------------------------------
        # COL 1: CORNER FILL & BLENDING
        # ----------------------------------------------------
        fill_group = ttk.LabelFrame(col1, text="1. Corner Fill Algorithm", padding="5")
        fill_group.pack(fill=tk.X, pady=(0, 5))

        self.fill_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(fill_group, text="Enable Fill", variable=self.fill_var).grid(row=0, column=0, sticky=tk.W)
        
        self.fill_mode = tk.StringVar(value="Dual-Axis Mirror")
        modes = ["Telea Inpaint (Soft)", "Navier-Stokes (Sharp)", "Pixel Stretch", "Smooth Pixel Stretch", "Edge Mirror", "Dual-Axis Mirror"]
        ttk.Combobox(fill_group, textvariable=self.fill_mode, values=modes, state="readonly", width=18).grid(row=0, column=1, sticky=tk.W, padx=5)

        ttk.Label(fill_group, text="Corner Size (%):").grid(row=1, column=0, sticky=tk.E)
        self.fill_size = tk.Scale(fill_group, from_=1, to=30, orient=tk.HORIZONTAL, length=100)
        self.fill_size.set(10) 
        self.fill_size.grid(row=1, column=1, sticky=tk.W)

        ttk.Label(fill_group, text="Inpaint Radius:").grid(row=2, column=0, sticky=tk.E)
        self.inpaint_rad = tk.Scale(fill_group, from_=1, to=50, orient=tk.HORIZONTAL, length=100)
        self.inpaint_rad.set(15) 
        self.inpaint_rad.grid(row=2, column=1, sticky=tk.W)

        # --- BLENDING SUB-GROUP ---
        blend_group = ttk.LabelFrame(col1, text="2. Gradient Blending (%)", padding="5")
        blend_group.pack(fill=tk.X)

        self.blend_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(blend_group, text="Enable Blend", variable=self.blend_var).grid(row=0, column=0, sticky=tk.W)

        self.blend_stage = tk.StringVar(value="Before Bleed")
        ttk.Combobox(blend_group, textvariable=self.blend_stage, values=["Before Color", "Before Bleed", "After Bleed"], state="readonly", width=14).grid(row=0, column=1, sticky=tk.W, padx=5)

        self.blend_type = tk.StringVar(value="Shadow (Vignette)")
        ttk.Combobox(blend_group, textvariable=self.blend_type, values=["Shadow (Vignette)", "Blur (Soft)"], state="readonly", width=14).grid(row=1, column=1, sticky=tk.W, padx=5, pady=2)
        ttk.Label(blend_group, text="Blend Style:").grid(row=1, column=0, sticky=tk.E)

        ttk.Label(blend_group, text="Corner Fade (%):").grid(row=2, column=0, sticky=tk.E)
        self.corner_fade = tk.Scale(blend_group, from_=0, to=50, orient=tk.HORIZONTAL, length=100)
        self.corner_fade.set(15) 
        self.corner_fade.grid(row=2, column=1, sticky=tk.W)

        ttk.Label(blend_group, text="Margin Fade (%):").grid(row=3, column=0, sticky=tk.E)
        self.margin_fade = tk.Scale(blend_group, from_=0, to=50, orient=tk.HORIZONTAL, length=100)
        self.margin_fade.set(5) 
        self.margin_fade.grid(row=3, column=1, sticky=tk.W)

        ttk.Label(blend_group, text="Blend Strength (%):").grid(row=4, column=0, sticky=tk.E)
        self.blend_str = tk.Scale(blend_group, from_=1, to=100, orient=tk.HORIZONTAL, length=100)
        self.blend_str.set(100) 
        self.blend_str.grid(row=4, column=1, sticky=tk.W)

        ttk.Label(blend_group, text="Add Grain/Noise:").grid(row=5, column=0, sticky=tk.E)
        self.noise_amount = tk.Scale(blend_group, from_=0, to=50, orient=tk.HORIZONTAL, length=100)
        self.noise_amount.set(5) 
        self.noise_amount.grid(row=5, column=1, sticky=tk.W)

        # ----------------------------------------------------
        # COL 2: COLOR GRADING
        # ----------------------------------------------------
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

        # ----------------------------------------------------
        # COL 3: PHYSICAL SIZING & BLEED (SPAD)
        # ----------------------------------------------------
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

        calc_lbl = tk.Label(size_group, textvariable=self.size_info_var, justify=tk.LEFT, bg="#333", fg="#0f0", font=("Consolas", 8))
        calc_lbl.pack(fill=tk.X, pady=(10, 0))

        # ----------------------------------------------------
        # ACTIONS / BAT
        # ----------------------------------------------------
        actions = ttk.Frame(right_panel)
        actions.pack(fill=tk.X, pady=10)

        ttk.Label(actions, text="Legacy Scale:").pack(side=tk.LEFT, padx=5)
        self.upscale_var = tk.StringVar(value="1.0")
        ttk.Combobox(actions, textvariable=self.upscale_var, values=["1.0", "1.5", "2.0"], width=5, state="readonly").pack(side=tk.LEFT, padx=5)

        ttk.Button(actions, text="Preview Edit", command=self.preview_current_edit).pack(side=tk.LEFT, padx=15)
        ttk.Button(actions, text="Save Current", command=self.save_current_edit).pack(side=tk.LEFT, padx=5)
        ttk.Button(actions, text="Batch Apply to ALL", command=self.batch_apply_edits).pack(side=tk.LEFT, padx=5)
        
        bat_frame = ttk.Frame(right_panel)
        bat_frame.pack(fill=tk.X, pady=5)
        ttk.Label(bat_frame, text="Post-process .bat file (Optional):").pack(side=tk.LEFT, padx=5)
        self.bat_entry = ttk.Entry(bat_frame, width=30)
        self.bat_entry.pack(side=tk.LEFT, padx=5)
        ttk.Button(bat_frame, text="Browse", command=self.browse_bat).pack(side=tk.LEFT, padx=5)
        ttk.Button(bat_frame, text="Run Bat Script", command=self.execute_bat).pack(side=tk.RIGHT, padx=5)

    # --- Methods [update_size_labels, load_from_csv, apply_color_preset, browse_bat, load_editor_files, on_file_select, _get_current_params, preview_current_edit, save_current_edit, batch_apply_edits, execute_bat] remain unchanged ---
    def update_size_labels(self, *args):
        # (This method remains unchanged as per previous instruction)
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
        except ValueError:
            self.size_info_var.set("Waiting for valid numbers...")

    def load_from_csv(self):
        filepath = filedialog.askopenfilename(
            title="Select cards_data.csv", 
            filetypes=(("CSV Files", "*.csv"), ("All files", "*.*"))
        )
        if filepath:
            self.app.current_folder = os.path.dirname(filepath)
            self.load_editor_files()
            messagebox.showinfo("Loaded", f"Loaded directory:\n{self.app.current_folder}")

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

    def load_editor_files(self):
        self.file_listbox.delete(0, tk.END)
        if not self.app.current_folder: return
        valid_exts = ('.png', '.jpg', '.jpeg', '.webp', '.bmp')
        for file in os.listdir(self.app.current_folder):
            if file.lower().endswith(valid_exts):
                self.file_listbox.insert(tk.END, file)

    def on_file_select(self, event):
        selection = self.file_listbox.curselection()
        if not selection: return
        
        filename = self.file_listbox.get(selection[0])
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
            'do_resize_mm': self.resize_var.get(),
            'target_w_mm': t_w,
            'target_h_mm': t_h,
            'dpi': dpi,
            
            'do_corner_fill': self.fill_var.get(),
            'fill_mode': self.fill_mode.get(),
            'corner_size': self.fill_size.get(),
            'inpaint_radius': self.inpaint_rad.get(),
            
            'do_blend': self.blend_var.get(),
            'blend_stage': self.blend_stage.get(),
            'blend_type': self.blend_type.get(),
            'corner_fade': self.corner_fade.get(),
            'margin_fade': self.margin_fade.get(),
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
            'spad_r': s_r,
            
            'upscale_factor': self.upscale_var.get()
        }

    def preview_current_edit(self):
        selection = self.file_listbox.curselection()
        if not selection:
            messagebox.showinfo("Select", "Select an image from the list first.")
            return
            
        filename = self.file_listbox.get(selection[0])
        filepath = os.path.join(self.app.current_folder, filename)
        
        self.preview_lbl.config(image='', text="Processing preview...")
        self.app.root.update_idletasks() 
        
        params = self._get_current_params()
        img = process_image_advanced(filepath=filepath, save=False, **params)
        self.preview_lbl.display_image(img)

    def save_current_edit(self):
        selection = self.file_listbox.curselection()
        if not selection: return
        
        filename = self.file_listbox.get(selection[0])
        filepath = os.path.join(self.app.current_folder, filename)
        
        params = self._get_current_params()
        process_image_advanced(filepath=filepath, save=True, **params)
        
        messagebox.showinfo("Saved", f"Overwrote {filename} with edits.")
        self.on_file_select(None) 

    def batch_apply_edits(self):
        if not self.app.current_folder: return
        if not messagebox.askyesno("Confirm Batch", "This will permanently overwrite all downloaded images with the current settings. Proceed?"):
            return

        self.preview_lbl.config(image='', text="Processing batch... Please wait.")
        self.app.root.update_idletasks()

        params = self._get_current_params()
        items = self.file_listbox.get(0, tk.END)
        for filename in items:
            filepath = os.path.join(self.app.current_folder, filename)
            process_image_advanced(filepath=filepath, save=True, **params)
        
        messagebox.showinfo("Done", "Batch processing complete.")
        self.preview_lbl.config(text="Batch complete. Select an image.")

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