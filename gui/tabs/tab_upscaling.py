import os
import json
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import threading
from PIL import Image
import numpy as np
import cv2

from core.upscaler import upscale_image_pipeline
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

        # Tab 1: KIE.ai
        self.kie_tab = ttk.Frame(self.engine_notebook, padding="10")
        self.engine_notebook.add(self.kie_tab, text="KIE.ai")

        kie_desc = ttk.Label(
            self.kie_tab, 
            text="KIE.ai uses cloud-based AI models to upscale images.\n• recraft/crisp-upscale: 0.5 credits (~$0.0025 USD). Great for clean vector/illustrations.\n• topaz/image-upscale: 10 credits (~$0.05) per <=2K image, 20 credits (~$0.10) per 4K image.\n• nano/banana-pro: 18 credits (~$0.09) per <=2K image, 24 credits (~$0.12) per 4K image.",
            font=("Segoe UI", 9, "italic"),
            justify=tk.LEFT
        )
        kie_desc.pack(anchor=tk.W, pady=(0, 10))

        # Row 1: API Key
        row1 = ttk.Frame(self.kie_tab)
        row1.pack(fill=tk.X, pady=2)
        
        ttk.Label(row1, text="KIE API Key:", width=16, anchor=tk.W).pack(side=tk.LEFT)
        self.api_key_var = tk.StringVar()
        self.api_key_entry = ttk.Entry(row1, textvariable=self.api_key_var, show="*")
        self.api_key_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        
        self.show_key_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(row1, text="Show", variable=self.show_key_var, command=self.toggle_key_visibility).pack(side=tk.LEFT)

        # Row 1b: Credit Balance Info
        row1b = ttk.Frame(self.kie_tab)
        row1b.pack(fill=tk.X, pady=(2, 6))
        ttk.Label(row1b, text="KIE Credits:", width=16, anchor=tk.W).pack(side=tk.LEFT)
        self.balance_lbl = ttk.Label(row1b, text="Click 'Refresh' to load...", font=("Segoe UI", 9, "bold"))
        self.balance_lbl.pack(side=tk.LEFT, padx=(0, 10))
        self.refresh_balance_btn = ttk.Button(row1b, text="Refresh Balance", command=self.refresh_balance, width=15)
        self.refresh_balance_btn.pack(side=tk.LEFT)

        # Row 2: Model & Factor Selection
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

        # Row 2b: Custom Prompt (NEW)
        row_prompt = ttk.Frame(self.kie_tab)
        row_prompt.pack(fill=tk.X, pady=6)
        ttk.Label(row_prompt, text="Custom Prompt:", width=16, anchor=tk.W).pack(side=tk.LEFT)
        self.custom_prompt_var = tk.StringVar(value="")
        self.custom_prompt_entry = ttk.Entry(row_prompt, textvariable=self.custom_prompt_var)
        self.custom_prompt_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Row 2c: Extra parameters (JSON)
        row_extra = ttk.Frame(self.kie_tab)
        row_extra.pack(fill=tk.X, pady=6)
        ttk.Label(row_extra, text="Extra Params (JSON):", width=16, anchor=tk.W).pack(side=tk.LEFT)
        self.extra_params_var = tk.StringVar(value="{}")
        self.extra_params_entry = ttk.Entry(row_extra, textvariable=self.extra_params_var)
        self.extra_params_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Tab 2: Future / Local Engine Placeholder
        self.future_tab = ttk.Frame(self.engine_notebook, padding="10")
        self.engine_notebook.add(self.future_tab, text="Local / Other (Future)")
        
        future_desc = ttk.Label(
            self.future_tab,
            text="Modular engine placeholder.\nIn the future, you can configure other cloud providers or run\na local upscaler model (e.g. Real-ESRGAN) directly on your GPU.",
            font=("Segoe UI", 9, "italic"),
            justify=tk.LEFT
        )
        future_desc.pack(anchor=tk.W, pady=(0, 10))

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
            
            # Default Output folder to [csv_dir]/upscaled
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
                        messagebox.showerror("Error", "Extra parameters JSON must be an object (e.g., {\"key\": \"value\"}).")
                        return False
                except json.JSONDecodeError as e:
                    messagebox.showerror("Error", f"Invalid JSON in Extra Params:\n{e}")
                    return False
        elif selected_engine == "Local / Other (Future)":
            messagebox.showwarning("Not Implemented", "The Local / Other engine is a modular placeholder. Please use KIE.ai to upscale images.")
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
        
        api_key = self.api_key_var.get().strip()
        model = self.get_api_model()
        factor = self.factor_var.get()
        output_dir = self.out_dir_var.get().strip()
        custom_prompt = self.custom_prompt_var.get().strip()
        
        extra_params_str = self.extra_params_var.get().strip()
        extra_params = json.loads(extra_params_str) if extra_params_str else {}
        
        def run():
            try:
                self.log(f"Starting upscale for single image: {filename}")
                out_path = upscale_image_pipeline(
                    file_path=filepath,
                    model=model,
                    api_key=api_key,
                    output_dir=output_dir,
                    upscale_factor=factor,
                    log_fn=self.log,
                    extra_params=extra_params,
                    custom_prompt=custom_prompt
                )
                self.log(f"[SUCCESS] Upscaled file saved to: {out_path}")
                self.app.root.after(0, lambda: messagebox.showinfo("Finished", f"Upscaling finished successfully!\nSaved to: {out_path}"))
            except Exception as e:
                self.log(f"[ERROR] Upscale failed: {str(e)}")
            finally:
                self.app.root.after(0, lambda: self.set_buttons_state(tk.NORMAL))
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
        if not messagebox.askyesno("Confirm Bulk Upscale", f"Are you sure you want to upscale all {len(files)} images in bulk using {selected_engine}? This will consume credits/resources."):
            return
            
        self.save_config()
        self.set_buttons_state(tk.DISABLED)
        self.console.config(state=tk.NORMAL)
        self.console.delete(1.0, tk.END)
        self.console.config(state=tk.DISABLED)
        
        api_key = self.api_key_var.get().strip()
        model = self.get_api_model()
        factor = self.factor_var.get()
        output_dir = self.out_dir_var.get().strip()
        csv_path = self.csv_path_var.get().strip()
        base_folder = os.path.dirname(csv_path)
        custom_prompt = self.custom_prompt_var.get().strip()
        
        extra_params_str = self.extra_params_var.get().strip()
        extra_params = json.loads(extra_params_str) if extra_params_str else {}
        
        def run():
            success_count = 0
            fail_count = 0
            for idx, filename in enumerate(files, 1):
                filepath = os.path.join(base_folder, filename)
                self.log(f"\n--- [{idx}/{len(files)}] Processing {filename} ---")
                try:
                    upscale_image_pipeline(
                        file_path=filepath,
                        model=model,
                        api_key=api_key,
                        output_dir=output_dir,
                        upscale_factor=factor,
                        log_fn=self.log,
                        extra_params=extra_params,
                        custom_prompt=custom_prompt
                    )
                    success_count += 1
                except Exception as e:
                    self.log(f"[ERROR] Failed to upscale {filename}: {str(e)}")
                    fail_count += 1
                    
            self.log(f"\n======================================")
            self.log(f"Bulk processing finished!")
            self.log(f"Success: {success_count}")
            self.log(f"Failed: {fail_count}")
            self.log(f"======================================")
            
            self.app.root.after(0, lambda: messagebox.showinfo(
                "Bulk Upscale Finished", 
                f"Completed {len(files)} files.\nSuccess: {success_count}\nFailed: {fail_count}"
            ))
            self.app.root.after(0, lambda: self.set_buttons_state(tk.NORMAL))
            self.app.root.after(0, self.refresh_balance)
            
        threading.Thread(target=run, daemon=True).start()

    def set_buttons_state(self, state):
        self.upscale_single_btn.config(state=state)
        self.upscale_bulk_btn.config(state=state)