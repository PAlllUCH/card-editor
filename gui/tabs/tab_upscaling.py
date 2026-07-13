import os
import json
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import threading
from PIL import Image
import numpy as np
import cv2

# Import the new local execution pipeline
from core.upscaler import upscale_image_pipeline, upscale_image_local_upscayl
from gui.components.image_preview import ImagePreviewComponent

CONFIG_FILE = "config.json"

class UpscalingTab:
    def __init__(self, parent_notebook, app_controller):
        self.frame = ttk.Frame(parent_notebook)
        self.app = app_controller
        self.config_data = self.load_config()
        
        self.build_ui()
        self.load_saved_settings()

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def save_config(self):
        self.config_data["kie_api_key"] = self.api_key_var.get().strip()
        self.config_data["last_csv_path"] = self.csv_path_var.get().strip()
        self.config_data["last_model"] = self.model_var.get()
        self.config_data["upscale_factor"] = self.factor_var.get()
        self.config_data["output_dir"] = self.out_dir_var.get().strip()
        
        if hasattr(self, "custom_prompt_var"):
            self.config_data["custom_prompt"] = self.custom_prompt_var.get().strip()
            
        if hasattr(self, "extra_params_var"):
            self.config_data["kie_extra_params"] = self.extra_params_var.get().strip()
            
        # Save local engine parameters
        self.config_data["upscayl_bin_path"] = self.local_bin_var.get().strip()
        self.config_data["local_model"] = self.local_model_var.get()
        self.config_data["local_factor"] = self.local_factor_var.get()

        if hasattr(self, "engine_notebook"):
            try:
                selected_tab_text = self.engine_notebook.tab(self.engine_notebook.select(), "text")
                self.config_data["last_engine"] = selected_tab_text
            except Exception:
                pass
        try:
            with open(CONFIG_FILE, 'w') as f:
                json.dump(self.config_data, f, indent=4)
        except Exception as e:
            self.log(f"[WARNING] Failed to save config: {e}")

    def load_saved_settings(self):
        if "kie_api_key" in self.config_data:
            self.api_key_var.set(self.config_data["kie_api_key"])
        if "last_csv_path" in self.config_data:
            csv_path = self.config_data["last_csv_path"]
            if os.path.exists(csv_path):
                self.csv_path_var.set(csv_path)
                self.load_files_from_csv(csv_path)
        if "last_model" in self.config_data:
            self.model_var.set(self.config_data["last_model"])
        if "upscale_factor" in self.config_data:
            self.factor_var.set(self.config_data["upscale_factor"])
        if "output_dir" in self.config_data:
            self.out_dir_var.set(self.config_data["output_dir"])
        if "custom_prompt" in self.config_data:
            self.custom_prompt_var.set(self.config_data["custom_prompt"])
        if "kie_extra_params" in self.config_data:
            self.extra_params_var.set(self.config_data["kie_extra_params"])
            
        # Load local engine settings
        if "upscayl_bin_path" in self.config_data:
            self.local_bin_var.set(self.config_data["upscayl_bin_path"])
        if "local_model" in self.config_data:
            self.local_model_var.set(self.config_data["local_model"])
        if "local_factor" in self.config_data:
            self.local_factor_var.set(self.config_data["local_factor"])
            
        if "last_engine" in self.config_data and hasattr(self, "engine_notebook"):
            last_eng = self.config_data["last_engine"]
            for tab_id in self.engine_notebook.tabs():
                if self.engine_notebook.tab(tab_id, "text") == last_eng:
                    self.engine_notebook.select(tab_id)
                    break
            
        self.on_model_change()
        if self.api_key_var.get().strip():
            self.refresh_balance()

    def build_ui(self):
        # Left Panel: File Selection & Preview
        left_panel = ttk.Frame(self.frame, width=280)
        left_panel.pack(side=tk.LEFT, fill=tk.Y, padx=10, pady=10)
        
        ttk.Label(left_panel, text="1. Select Cards CSV:").pack(anchor=tk.W, pady=(0, 2))
        
        csv_row = ttk.Frame(left_panel)
        csv_row.pack(fill=tk.X, pady=(0, 10))
        self.csv_path_var = tk.StringVar()
        ttk.Entry(csv_row, textvariable=self.csv_path_var, width=20).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        ttk.Button(csv_row, text="...", command=self.browse_csv, width=3).pack(side=tk.RIGHT)
        
        ttk.Label(left_panel, text="Images in CSV Folder:").pack(anchor=tk.W)
        self.file_listbox = tk.Listbox(left_panel, width=30, exportselection=False)
        self.file_listbox.pack(expand=True, fill=tk.Y, pady=5)
        self.file_listbox.bind('<<ListboxSelect>>', self.on_file_select)

        # Right Panel: Preview, Config, Action Controls
        right_panel = ttk.Frame(self.frame)
        right_panel.pack(side=tk.RIGHT, expand=True, fill=tk.BOTH, padx=10, pady=10)

        # Image Preview Component
        self.preview_lbl = ImagePreviewComponent(right_panel)
        self.preview_lbl.pack(expand=True, fill=tk.BOTH, pady=(0, 10))

        # Engine Settings Notebook
        self.engine_notebook = ttk.Notebook(right_panel)
        self.engine_notebook.pack(fill=tk.X, pady=(0, 5))
        self.engine_notebook.bind("<<NotebookTabChanged>>", lambda e: self.save_config())

        # ==================== TAB 1: KIE.ai ====================
        self.kie_tab = ttk.Frame(self.engine_notebook, padding="10")
        self.engine_notebook.add(self.kie_tab, text="KIE.ai")

        kie_desc = ttk.Label(
            self.kie_tab, 
            text="KIE.ai uses cloud-based AI models to upscale images.\n• recraft/crisp-upscale: 0.5 credits (~$0.0025 USD). Great for clean vector/illustrations.\n• topaz/image-upscale: 10 credits (~$0.05) per <=2K image, 20 credits (~$0.10) per 4K image.\n• nano/banana-pro: 18 credits (~$0.09) per <=2K image, 24 credits (~$0.12) per 4K image.",
            font=("Segoe UI", 9, "italic"),
            justify=tk.LEFT
        )
        kie_desc.pack(anchor=tk.W, pady=(0, 10))

        row1 = ttk.Frame(self.kie_tab)
        row1.pack(fill=tk.X, pady=2)
        
        ttk.Label(row1, text="KIE API Key:", width=16, anchor=tk.W).pack(side=tk.LEFT)
        self.api_key_var = tk.StringVar()
        self.api_key_entry = ttk.Entry(row1, textvariable=self.api_key_var, show="*")
        self.api_key_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        
        self.show_key_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(row1, text="Show", variable=self.show_key_var, command=self.toggle_key_visibility).pack(side=tk.LEFT)

        row1b = ttk.Frame(self.kie_tab)
        row1b.pack(fill=tk.X, pady=(2, 6))
        ttk.Label(row1b, text="KIE Credits:", width=16, anchor=tk.W).pack(side=tk.LEFT)
        self.balance_lbl = ttk.Label(row1b, text="Click 'Refresh' to load...", font=("Segoe UI", 9, "bold"))
        self.balance_lbl.pack(side=tk.LEFT, padx=(0, 10))
        self.refresh_balance_btn = ttk.Button(row1b, text="Refresh Balance", command=self.refresh_balance, width=15)
        self.refresh_balance_btn.pack(side=tk.LEFT)

        row2 = ttk.Frame(self.kie_tab)
        row2.pack(fill=tk.X, pady=6)

        ttk.Label(row2, text="Upscale Model:", width=16, anchor=tk.W).pack(side=tk.LEFT)
        self.model_var = tk.StringVar(value="recraft/crisp-upscale")
        model_options = [
            "recraft/crisp-upscale (0.5 credits / ~$0.0025 USD)",
            "topaz/image-upscale (10-20 credits / ~$0.05-$0.10 USD)",
            "nano-banana-2-1k (2 credits / ~$0.01 USD)",
            "nano-banana-2-2k (4 credits / ~$0.02 USD)",
            "gpt-image-2-1k (4 credits / ~$0.02 USD)",
            "gpt-image-2-2k (8 credits / ~$0.04 USD)"
        ]
        self.model_cb = ttk.Combobox(row2, textvariable=self.model_var, values=model_options, state="normal", width=38)
        self.model_cb.pack(side=tk.LEFT, padx=(0, 15))
        self.model_cb.bind("<<ComboboxSelected>>", self.on_model_change)

        self.factor_label = ttk.Label(row2, text="Factor:")
        self.factor_label.pack(side=tk.LEFT)
        self.factor_var = tk.StringVar(value="2")
        self.factor_cb = ttk.Combobox(row2, textvariable=self.factor_var, values=["2", "4"], state="readonly", width=5)
        self.factor_cb.pack(side=tk.LEFT, padx=(5, 0))

        row_prompt = ttk.Frame(self.kie_tab)
        row_prompt.pack(fill=tk.X, pady=6)
        ttk.Label(row_prompt, text="Custom Prompt:", width=16, anchor=tk.W).pack(side=tk.LEFT)
        self.custom_prompt_var = tk.StringVar(value="")
        self.custom_prompt_entry = ttk.Entry(row_prompt, textvariable=self.custom_prompt_var)
        self.custom_prompt_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

        row_extra = ttk.Frame(self.kie_tab)
        row_extra.pack(fill=tk.X, pady=6)
        ttk.Label(row_extra, text="Extra Params (JSON):", width=16, anchor=tk.W).pack(side=tk.LEFT)
        self.extra_params_var = tk.StringVar(value="{}")
        self.extra_params_entry = ttk.Entry(row_extra, textvariable=self.extra_params_var)
        self.extra_params_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # ==================== TAB 2: LOCAL UPSCAYL ====================
        self.future_tab = ttk.Frame(self.engine_notebook, padding="10")
        self.engine_notebook.add(self.future_tab, text="Local Upscayl")
        
        local_desc = ttk.Label(
            self.future_tab,
            text="Upscayl uses local GPU capabilities via its CLI tool.\nRequires 'upscayl-bin' or the executable command setup on your host.",
            font=("Segoe UI", 9, "italic"),
            justify=tk.LEFT
        )
        local_desc.pack(anchor=tk.W, pady=(0, 10))

        # CLI Executable File Path Row
        local_row1 = ttk.Frame(self.future_tab)
        local_row1.pack(fill=tk.X, pady=4)
        ttk.Label(local_row1, text="Upscayl Executable:", width=18, anchor=tk.W).pack(side=tk.LEFT)
        self.local_bin_var = tk.StringVar(value="upscayl")
        self.local_bin_entry = ttk.Entry(local_row1, textvariable=self.local_bin_var)
        self.local_bin_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        ttk.Button(local_row1, text="Browse...", command=self.browse_upscayl_bin, width=9).pack(side=tk.RIGHT)

        # Model and Scale Factor Controls
        local_row2 = ttk.Frame(self.future_tab)
        local_row2.pack(fill=tk.X, pady=6)
        
        ttk.Label(local_row2, text="Local Model:", width=18, anchor=tk.W).pack(side=tk.LEFT)
        self.local_model_var = tk.StringVar(value="ultrasharp-4x")
        
        # FIXED: Correct names corresponding to Upscayl's file architecture
        upscayl_models = [
            "upscayl-standard-4x",
            "upscayl-lite-4x",
            "digital-art-4x",
            "ultrasharp-4x",
            "remacri-4x",
            "ultramix-balanced-4x"
        ]
        self.local_model_cb = ttk.Combobox(local_row2, textvariable=self.local_model_var, values=upscayl_models, state="readonly", width=20)
        self.local_model_cb.pack(side=tk.LEFT, padx=(0, 15))

        ttk.Label(local_row2, text="Scale:").pack(side=tk.LEFT)
        self.local_factor_var = tk.StringVar(value="4")
        self.local_factor_cb = ttk.Combobox(local_row2, textvariable=self.local_factor_var, values=["2", "3", "4"], state="readonly", width=4)
        self.local_factor_cb.pack(side=tk.LEFT, padx=(5, 0))

        # Shared Destination Output Configuration Frame
        output_frame = ttk.LabelFrame(right_panel, text="Output Configuration", padding="10")
        output_frame.pack(fill=tk.X, pady=(0, 5))

        # Output Folder Row
        row3 = ttk.Frame(output_frame)
        row3.pack(fill=tk.X, pady=2)
        ttk.Label(row3, text="Output Folder:", width=12, anchor=tk.W).pack(side=tk.LEFT)
        self.out_dir_var = tk.StringVar()
        ttk.Entry(row3, textvariable=self.out_dir_var).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        ttk.Button(row3, text="Browse...", command=self.browse_output_dir).pack(side=tk.RIGHT)

        # Action Buttons
        actions_frame = ttk.Frame(right_panel)
        actions_frame.pack(fill=tk.X, pady=5)
        
        self.upscale_single_btn = ttk.Button(actions_frame, text="Upscale Selected (Test)", command=self.start_single_upscale)
        self.upscale_single_btn.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 5))

        self.upscale_bulk_btn = ttk.Button(actions_frame, text="Upscale Bulk (Deploy)", command=self.start_bulk_upscale)
        self.upscale_bulk_btn.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(5, 0))

        # Console logs
        self.console = scrolledtext.ScrolledText(right_panel, wrap=tk.WORD, bg="#1e1e1e", fg="#d4d4d4", font=("Consolas", 9), height=10)
        self.console.pack(expand=True, fill=tk.BOTH, pady=(5, 0))

    def browse_upscayl_bin(self):
        filename = filedialog.askopenfilename(
            title="Select Upscayl Binary / Executable",
            filetypes=(("Executable Files", "*.exe"), ("All files", "*.*"))
        )
        if filename:
            self.local_bin_var.set(filename)
            self.save_config()

    def toggle_key_visibility(self):
        if self.show_key_var.get():
            self.api_key_entry.config(show="")
        else:
            self.api_key_entry.config(show="*")

    def on_model_change(self, event=None):
        model = self.model_var.get()
        if "topaz" in model.lower():
            self.factor_label.pack(side=tk.LEFT)
            self.factor_cb.pack(side=tk.LEFT, padx=(5, 0))
        else:
            self.factor_label.pack_forget()
            self.factor_cb.pack_forget()

    def browse_csv(self):
        filename = filedialog.askopenfilename(
            title="Select cards_data.csv", 
            filetypes=(("CSV Files", "*.csv"), ("All files", "*.*"))
        )
        if filename:
            self.csv_path_var.set(filename)
            self.load_files_from_csv(filename)
            
            dir_name = os.path.dirname(filename)
            self.out_dir_var.set(os.path.join(dir_name, "upscaled"))
            self.save_config()

    def load_files_from_csv(self, csv_path):
        self.file_listbox.delete(0, tk.END)
        folder = os.path.dirname(csv_path)
        valid_exts = ('.png', '.jpg', '.jpeg', '.webp', '.bmp')
        if os.path.exists(folder):
            for file in os.listdir(folder):
                if file.lower().endswith(valid_exts):
                    self.file_listbox.insert(tk.END, file)

    def browse_output_dir(self):
        dirname = filedialog.askdirectory(title="Select Output Folder")
        if dirname:
            self.out_dir_var.set(dirname)
            self.save_config()

    def on_file_select(self, event):
        selection = self.file_listbox.curselection()
        if not selection: return
        
        filename = self.file_listbox.get(selection[0])
        csv_path = self.csv_path_var.get().strip()
        if not csv_path: return
        
        filepath = os.path.join(os.path.dirname(csv_path), filename)
        
        try:
            file_bytes = np.fromfile(filepath, dtype=np.uint8)
            img = cv2.imdecode(file_bytes, cv2.IMREAD_UNCHANGED)
            if img is not None:
                if len(img.shape) == 3 and img.shape[2] == 4:
                    img = img[:, :, :3]
                rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                self.preview_lbl.display_image(Image.fromarray(rgb))
        except Exception as e:
            self.log(f"[ERROR] Failed to load preview: {e}")

    def log(self, message):
        self.app.root.after(0, self._append_log, message)

    def _append_log(self, message):
        self.console.config(state=tk.NORMAL)
        self.console.insert(tk.END, message + "\n")
        self.console.see(tk.END)
        self.console.config(state=tk.DISABLED)

    def refresh_balance(self):
        api_key = self.api_key_var.get().strip()
        if not api_key:
            self.balance_lbl.config(text="API key required")
            return
            
        self.balance_lbl.config(text="Checking...")
        self.refresh_balance_btn.config(state=tk.DISABLED)
        
        def run():
            try:
                from core.upscaler import get_kie_credits
                credits = get_kie_credits(api_key)
                usd_value = credits * 0.005
                self.app.root.after(0, lambda: self.balance_lbl.config(
                    text=f"{credits:.1f} credits (~${usd_value:.3f} USD)"
                ))
            except Exception as e:
                self.app.root.after(0, lambda: self.balance_lbl.config(
                    text=f"Error checking: {e}"
                ))
            finally:
                self.app.root.after(0, lambda: self.refresh_balance_btn.config(state=tk.NORMAL))
                
        threading.Thread(target=run, daemon=True).start()

    def get_api_model(self):
        model_str = self.model_var.get().strip()
        if " " in model_str:
            return model_str.split(" ")[0]
        return model_str

    def validate_inputs(self):
        selected_engine = self.engine_notebook.tab(self.engine_notebook.select(), "text")
        if selected_engine == "KIE.ai":
            api_key = self.api_key_var.get().strip()
            if not api_key:
                messagebox.showerror("Error", "Please enter your KIE.ai API Key.")
                return False
            extra_params_str = self.extra_params_var.get().strip()
            if extra_params_str:
                try:
                    params = json.loads(extra_params_str)
                    if not isinstance(params, dict):
                        messagebox.showerror("Error", "Extra parameters JSON must be an object.")
                        return False
                except json.JSONDecodeError as e:
                    messagebox.showerror("Error", f"Invalid JSON in Extra Params:\n{e}")
                    return False
        elif selected_engine == "Local Upscayl":
            if not self.local_bin_var.get().strip():
                messagebox.showerror("Error", "Please configure the Upscayl execution path/binary.")
                return False
            
        csv_path = self.csv_path_var.get().strip()
        if not csv_path or not os.path.exists(csv_path):
            messagebox.showerror("Error", "Please select a valid CSV file.")
            return False
            
        out_dir = self.out_dir_var.get().strip()
        if not out_dir:
            messagebox.showerror("Error", "Please select or specify an output directory.")
            return False
            
        return True

    def start_single_upscale(self):
        if not self.validate_inputs():
            return
            
        selection = self.file_listbox.curselection()
        if not selection:
            messagebox.showerror("Error", "Please select an image from the list first.")
            return
            
        filename = self.file_listbox.get(selection[0])
        csv_path = self.csv_path_var.get().strip()
        filepath = os.path.join(os.path.dirname(csv_path), filename)
        
        self.save_config()
        self.set_buttons_state(tk.DISABLED)
        self.console.config(state=tk.NORMAL)
        self.console.delete(1.0, tk.END)
        self.console.config(state=tk.DISABLED)
        
        selected_engine = self.engine_notebook.tab(self.engine_notebook.select(), "text")
        output_dir = self.out_dir_var.get().strip()

        # Gather engine-specific configurations
        api_key = self.api_key_var.get().strip()
        model = self.get_api_model()
        factor = self.factor_var.get()
        custom_prompt = self.custom_prompt_var.get().strip()
        extra_params_str = self.extra_params_var.get().strip()
        extra_params = json.loads(extra_params_str) if extra_params_str else {}

        upscayl_bin = self.local_bin_var.get().strip()
        local_model = self.local_model_var.get()
        local_factor = self.local_factor_var.get()
        
        def run():
            try:
                if selected_engine == "KIE.ai":
                    self.log(f"Starting cloud upscale for single image: {filename}")
                    out_path = upscale_image_pipeline(
                        file_path=filepath, model=model, api_key=api_key, output_dir=output_dir,
                        upscale_factor=factor, log_fn=self.log, extra_params=extra_params, custom_prompt=custom_prompt
                    )
                else:
                    out_path = upscale_image_local_upscayl(
                        file_path=filepath, model=local_model, upscayl_bin=upscayl_bin,
                        output_dir=output_dir, upscale_factor=local_factor, log_fn=self.log
                    )
                self.log(f"[SUCCESS] Upscaled file saved to: {out_path}")
                self.app.root.after(0, lambda: messagebox.showinfo("Finished", f"Upscaling finished successfully!\nSaved to: {out_path}"))
            except Exception as e:
                self.log(f"[ERROR] Upscale failed: {str(e)}")
            finally:
                self.app.root.after(0, lambda: self.set_buttons_state(tk.NORMAL))
                if selected_engine == "KIE.ai":
                    self.app.root.after(0, self.refresh_balance)
                
        threading.Thread(target=run, daemon=True).start()

    def start_bulk_upscale(self):
        if not self.validate_inputs():
            return
            
        files = self.file_listbox.get(0, tk.END)
        if not files:
            messagebox.showerror("Error", "No images found in the selected CSV directory.")
            return
            
        selected_engine = self.engine_notebook.tab(self.engine_notebook.select(), "text")
        if not messagebox.askyesno("Confirm Bulk Upscale", f"Are you sure you want to upscale all {len(files)} images in bulk using {selected_engine}?"):
            return
            
        self.save_config()
        self.set_buttons_state(tk.DISABLED)
        self.console.config(state=tk.NORMAL)
        self.console.delete(1.0, tk.END)
        self.console.config(state=tk.DISABLED)
        
        output_dir = self.out_dir_var.get().strip()
        csv_path = self.csv_path_var.get().strip()
        base_folder = os.path.dirname(csv_path)

        api_key = self.api_key_var.get().strip()
        model = self.get_api_model()
        factor = self.factor_var.get()
        custom_prompt = self.custom_prompt_var.get().strip()
        extra_params_str = self.extra_params_var.get().strip()
        extra_params = json.loads(extra_params_str) if extra_params_str else {}

        upscayl_bin = self.local_bin_var.get().strip()
        local_model = self.local_model_var.get()
        local_factor = self.local_factor_var.get()
        
        def run():
            import csv  # Imported inside the worker thread
            success_count = 0
            fail_count = 0
            
            # Dictionary to map original filename -> upscaled filename
            upscaled_mapping = {} 

            for idx, filename in enumerate(files, 1):
                filepath = os.path.join(base_folder, filename)
                self.log(f"\n--- [{idx}/{len(files)}] Processing {filename} ---")
                try:
                    if selected_engine == "KIE.ai":
                        out_path = upscale_image_pipeline(
                            file_path=filepath, model=model, api_key=api_key, output_dir=output_dir,
                            upscale_factor=factor, log_fn=self.log, extra_params=extra_params, custom_prompt=custom_prompt
                        )
                    else:
                        out_path = upscale_image_local_upscayl(
                            file_path=filepath, model=local_model, upscayl_bin=upscayl_bin,
                            output_dir=output_dir, upscale_factor=local_factor, log_fn=self.log
                        )
                    success_count += 1
                    
                    # Track what file was successfully saved out
                    upscaled_mapping[filename] = os.path.basename(out_path)
                    
                except Exception as e:
                    self.log(f"[ERROR] Failed to upscale {filename}: {str(e)}")
                    fail_count += 1
            
            # ==================== NEW: RECREATE & UPDATE CSV FILE ====================
            if success_count > 0:
                self.log("\n--- Recreating tracking CSV inside output folder ---")
                try:
                    new_csv_path = os.path.join(output_dir, os.path.basename(csv_path))
                    
                    # Read the original CSV safely handling potential Excel BOM encoding quirks
                    with open(csv_path, 'r', encoding='utf-8-sig', errors='replace', newline='') as infile:
                        content = infile.read()
                        infile.seek(0)
                        
                        # Robust delimiter auto-fallback check
                        delimiter = ','
                        if content.count(';') > content.count(','):
                            delimiter = ';'
                            
                        reader = csv.reader(infile, delimiter=delimiter)
                        rows = list(reader)
                    
                    # Traverse layout cells and swap outdated image names
                    updated_rows = []
                    for row in rows:
                        new_row = []
                        for cell in row:
                            updated_cell = cell
                            cell_clean = cell.strip().replace('\\', '/')
                            
                            for orig_name, new_name in upscaled_mapping.items():
                                orig_clean = orig_name.replace('\\', '/')
                                # Direct exact string match check
                                if cell_clean == orig_clean:
                                    updated_cell = new_name
                                    break
                                # Relative subdirectory match check (e.g. "images/card.jpg")
                                elif cell_clean.endswith('/' + orig_clean):
                                    prefix = cell[:-len(orig_name)]
                                    updated_cell = prefix + new_name
                                    break
                            new_row.append(updated_cell)
                        updated_rows.append(new_row)
                    
                    # Write out updated file clone into the designated upscaled directory
                    with open(new_csv_path, 'w', encoding='utf-8', newline='') as outfile:
                        writer = csv.writer(outfile, delimiter=delimiter)
                        writer.writerows(updated_rows)
                        
                    self.log(f"[SUCCESS] Recreated updated configuration file: '{os.path.basename(new_csv_path)}'")
                    
                except Exception as csv_err:
                    self.log(f"[ERROR] Failed to clone structural CSV: {str(csv_err)}")
            # =========================================================================
                    
            self.log(f"\n======================================")
            self.log(f"Bulk processing finished!")
            self.log(f"Success: {success_count}")
            self.log(f"Failed: {fail_count}")
            self.log(f"======================================")
            
            self.app.root.after(0, lambda: messagebox.showinfo(
                "Bulk Upscale Finished", 
                f"Completed {len(files)} files.\nSuccess: {success_count}\nFailed: {fail_count}\n\nCSV file updated in output directory!"
            ))
            self.app.root.after(0, lambda: self.set_buttons_state(tk.NORMAL))
            if selected_engine == "KIE.ai":
                self.app.root.after(0, self.refresh_balance)
            
        threading.Thread(target=run, daemon=True).start()

    def set_buttons_state(self, state):
        self.upscale_single_btn.config(state=state)
        self.upscale_bulk_btn.config(state=state)