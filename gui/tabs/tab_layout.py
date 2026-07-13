import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import threading
from core.layout_generator import generate_pdf_layout, generate_individual_pdfs

class LayoutTab:
    def __init__(self, parent_notebook, app_controller):
        self.frame = ttk.Frame(parent_notebook)
        self.app = app_controller
        
        self.build_ui()

    def build_ui(self):
        # Top Config Frame
        config_frame = ttk.LabelFrame(self.frame, text="Page & Grid Settings", padding="10")
        config_frame.pack(fill=tk.X, padx=10, pady=10)

        # Row 1: CSV Selection
        row_csv = ttk.Frame(config_frame)
        row_csv.pack(fill=tk.X, pady=5)
        ttk.Label(row_csv, text="Cards CSV File:", width=15, anchor=tk.W).pack(side=tk.LEFT)
        self.csv_path_var = tk.StringVar()
        self.csv_entry = ttk.Entry(row_csv, textvariable=self.csv_path_var)
        self.csv_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        ttk.Button(row_csv, text="Browse...", command=self.browse_csv).pack(side=tk.RIGHT)

        # Row 2: Page Presets & Custom Sizes
        row_size = ttk.Frame(config_frame)
        row_size.pack(fill=tk.X, pady=5)
        
        ttk.Label(row_size, text="Page Size Preset:", width=15, anchor=tk.W).pack(side=tk.LEFT)
        self.preset_var = tk.StringVar(value="A4")
        presets_cb = ttk.Combobox(row_size, textvariable=self.preset_var, values=["A4", "US Letter", "A3", "SRA3", "Custom"], state="readonly", width=12)
        presets_cb.pack(side=tk.LEFT, padx=5)
        presets_cb.bind("<<ComboboxSelected>>", self.on_preset_change)

        ttk.Label(row_size, text="Width (mm):").pack(side=tk.LEFT, padx=(15, 2))
        self.page_w_var = tk.StringVar(value="210.0")
        self.page_w_entry = ttk.Entry(row_size, textvariable=self.page_w_var, width=8)
        self.page_w_entry.pack(side=tk.LEFT)

        ttk.Label(row_size, text="Height (mm):").pack(side=tk.LEFT, padx=(15, 2))
        self.page_h_var = tk.StringVar(value="297.0")
        self.page_h_entry = ttk.Entry(row_size, textvariable=self.page_h_var, width=8)
        self.page_h_entry.pack(side=tk.LEFT)

        ttk.Label(row_size, text="DPI:").pack(side=tk.LEFT, padx=(15, 2))
        self.dpi_var = tk.StringVar(value="300")
        self.dpi_entry = ttk.Entry(row_size, textvariable=self.dpi_var, width=6)
        self.dpi_entry.pack(side=tk.LEFT)

        # Row 3: Margins & Gaps
        row_margins = ttk.Frame(config_frame)
        row_margins.pack(fill=tk.X, pady=5)

        ttk.Label(row_margins, text="Margin Top (mm):").pack(side=tk.LEFT, padx=(0, 2))
        self.margin_t_var = tk.StringVar(value="10.0")
        ttk.Entry(row_margins, textvariable=self.margin_t_var, width=6).pack(side=tk.LEFT, padx=(0, 10))

        ttk.Label(row_margins, text="Margin Bottom (mm):").pack(side=tk.LEFT, padx=(0, 2))
        self.margin_b_var = tk.StringVar(value="10.0")
        ttk.Entry(row_margins, textvariable=self.margin_b_var, width=6).pack(side=tk.LEFT, padx=(0, 10))

        ttk.Label(row_margins, text="Margin Left (mm):").pack(side=tk.LEFT, padx=(0, 2))
        self.margin_l_var = tk.StringVar(value="10.0")
        ttk.Entry(row_margins, textvariable=self.margin_l_var, width=6).pack(side=tk.LEFT, padx=(0, 10))

        ttk.Label(row_margins, text="Margin Right (mm):").pack(side=tk.LEFT, padx=(0, 2))
        self.margin_r_var = tk.StringVar(value="10.0")
        ttk.Entry(row_margins, textvariable=self.margin_r_var, width=6).pack(side=tk.LEFT, padx=(0, 10))

        ttk.Label(row_margins, text="Card Gap (mm):", font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT, padx=(10, 2))
        self.gap_var = tk.StringVar(value="2.0")
        ttk.Entry(row_margins, textvariable=self.gap_var, width=6).pack(side=tk.LEFT)

        # Row 3.5: Duplex Mode
        row_duplex = ttk.Frame(config_frame)
        row_duplex.pack(fill=tk.X, pady=5)
        ttk.Label(row_duplex, text="Duplex Mirroring:", width=15, anchor=tk.W).pack(side=tk.LEFT)
        self.duplex_var = tk.StringVar(value="Long Edge (Horizontal)")
        duplex_cb = ttk.Combobox(row_duplex, textvariable=self.duplex_var, values=["Long Edge (Horizontal)", "Short Edge (Vertical)"], state="readonly", width=22)
        duplex_cb.pack(side=tk.LEFT, padx=5)

        # Row 4: Output Folder (UPDATED)
        row_out = ttk.Frame(config_frame)
        row_out.pack(fill=tk.X, pady=5)
        ttk.Label(row_out, text="Output Folder:", width=15, anchor=tk.W).pack(side=tk.LEFT)
        self.out_dir_var = tk.StringVar()
        self.out_entry = ttk.Entry(row_out, textvariable=self.out_dir_var)
        self.out_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        ttk.Button(row_out, text="Browse...", command=self.browse_dir).pack(side=tk.RIGHT)

        # Action Button Frame
        action_frame = ttk.Frame(self.frame)
        action_frame.pack(fill=tk.X, padx=10, pady=5)

        # Button 1: Grid Layout
        self.generate_btn = ttk.Button(action_frame, text="Generate Print PDF Layout", command=self.start_generation_thread)
        self.generate_btn.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 5))

        # Button 2: Individual PDFs
        self.indiv_btn = ttk.Button(action_frame, text="Generate Individual PDFs", command=self.start_individual_thread)
        self.indiv_btn.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(5, 0))

        # Scrolled Text Box for logs
        self.console = scrolledtext.ScrolledText(self.frame, wrap=tk.WORD, bg="#1e1e1e", fg="#d4d4d4", font=("Consolas", 10))
        self.console.pack(expand=True, fill=tk.BOTH, padx=10, pady=(5, 10))

    def on_preset_change(self, event=None):
        preset = self.preset_var.get()
        if preset == "A4":
            self.page_w_var.set("210.0")
            self.page_h_var.set("297.0")
        elif preset == "US Letter":
            self.page_w_var.set("215.9")
            self.page_h_var.set("279.4")
        elif preset == "A3":
            self.page_w_var.set("297.0")
            self.page_h_var.set("420.0")
        elif preset == "SRA3":
            self.page_w_var.set("320.0")
            self.page_h_var.set("450.0")

    def browse_csv(self):
        filename = filedialog.askopenfilename(
            title="Select cards_data.csv", 
            filetypes=(("CSV Files", "*.csv"), ("All files", "*.*"))
        )
        if filename:
            self.csv_path_var.set(filename)
            # Default Output Folder logic
            dir_name = os.path.dirname(filename)
            self.out_dir_var.set(dir_name)

    def browse_dir(self):
        dirname = filedialog.askdirectory(title="Select Output Folder")
        if dirname:
            self.out_dir_var.set(dirname)

    def log(self, message):
        self.app.root.after(0, self._append_log, message)

    def _append_log(self, message):
        self.console.config(state=tk.NORMAL)
        self.console.insert(tk.END, message + "\n")
        self.console.see(tk.END)
        self.console.config(state=tk.DISABLED)

    def _get_params(self):
        csv_path = self.csv_path_var.get().strip()
        if not csv_path or not os.path.exists(csv_path):
            if self.app.current_folder:
                suggested_csv = os.path.join(self.app.current_folder, "cards_data.csv")
                if os.path.exists(suggested_csv):
                    self.csv_path_var.set(suggested_csv)
                    csv_path = suggested_csv
                    self.out_dir_var.set(self.app.current_folder)
            if not csv_path or not os.path.exists(csv_path):
                messagebox.showerror("Error", "Please select a valid cards_data.csv file first.")
                return None, None

        out_dir = self.out_dir_var.get().strip()
        if not out_dir:
            out_dir = os.path.dirname(csv_path)
            self.out_dir_var.set(out_dir)

        params = {
            'page_w_mm': self.page_w_var.get(),
            'page_h_mm': self.page_h_var.get(),
            'margin_top_mm': self.margin_t_var.get(),
            'margin_bottom_mm': self.margin_b_var.get(),
            'margin_left_mm': self.margin_l_var.get(),
            'margin_right_mm': self.margin_r_var.get(),
            'gap_mm': self.gap_var.get(),
            'dpi': self.dpi_var.get(),
            'output_dir': out_dir,
            'duplex_mode': self.duplex_var.get()
        }
        return csv_path, params

    def start_generation_thread(self):
        csv_path, params = self._get_params()
        if not csv_path: return

        self.generate_btn.config(state=tk.DISABLED)
        self.indiv_btn.config(state=tk.DISABLED)
        self.console.config(state=tk.NORMAL)
        self.console.delete(1.0, tk.END)
        self.console.config(state=tk.DISABLED)

        def run_layout():
            success = generate_pdf_layout(csv_path, params, self.log)
            self.app.root.after(0, lambda: self.generate_btn.config(state=tk.NORMAL))
            self.app.root.after(0, lambda: self.indiv_btn.config(state=tk.NORMAL))
            if success:
                self.app.root.after(0, lambda: messagebox.showinfo("Finished", "PDF Layout saved successfully!"))
            else:
                self.app.root.after(0, lambda: messagebox.showerror("Error", "Failed to generate print layout PDF. Check log window."))

        threading.Thread(target=run_layout, daemon=True).start()

    def start_individual_thread(self):
        csv_path, params = self._get_params()
        if not csv_path: return

        self.generate_btn.config(state=tk.DISABLED)
        self.indiv_btn.config(state=tk.DISABLED)
        self.console.config(state=tk.NORMAL)
        self.console.delete(1.0, tk.END)
        self.console.config(state=tk.DISABLED)

        def run_indiv():
            success = generate_individual_pdfs(csv_path, params, self.log)
            self.app.root.after(0, lambda: self.generate_btn.config(state=tk.NORMAL))
            self.app.root.after(0, lambda: self.indiv_btn.config(state=tk.NORMAL))
            if success:
                self.app.root.after(0, lambda: messagebox.showinfo("Finished", "Individual PDFs generated successfully!"))
            else:
                self.app.root.after(0, lambda: messagebox.showerror("Error", "Failed to generate individual PDFs. Check log window."))

        threading.Thread(target=run_indiv, daemon=True).start()