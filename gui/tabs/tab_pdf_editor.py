import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import threading
import os
from core.pdf_editor import add_bleed_to_pdf

class PdfEditorTab:
    def __init__(self, parent_notebook, app_controller):
        self.frame = ttk.Frame(parent_notebook)
        self.app = app_controller
        self.build_ui()

    def build_ui(self):
        config_frame = ttk.LabelFrame(self.frame, text="PDF Bleed Settings", padding="10")
        config_frame.pack(fill=tk.X, padx=10, pady=10)

        # 1. Input PDF
        row_in = ttk.Frame(config_frame)
        row_in.pack(fill=tk.X, pady=5)
        ttk.Label(row_in, text="Input PDF:", width=15, anchor=tk.W).pack(side=tk.LEFT)
        self.in_pdf_var = tk.StringVar()
        ttk.Entry(row_in, textvariable=self.in_pdf_var).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        ttk.Button(row_in, text="Browse...", command=self.browse_input).pack(side=tk.RIGHT)

        # 2. Bleed Settings
        row_bleed = ttk.Frame(config_frame)
        row_bleed.pack(fill=tk.X, pady=10)
        
        ttk.Label(row_bleed, text="Bleed (mm):", font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Label(row_bleed, text="Top:").pack(side=tk.LEFT)
        self.bleed_t = tk.StringVar(value="2.0")
        ttk.Entry(row_bleed, textvariable=self.bleed_t, width=5).pack(side=tk.LEFT, padx=(2, 10))
        
        ttk.Label(row_bleed, text="Bottom:").pack(side=tk.LEFT)
        self.bleed_b = tk.StringVar(value="2.0")
        ttk.Entry(row_bleed, textvariable=self.bleed_b, width=5).pack(side=tk.LEFT, padx=(2, 10))
        
        ttk.Label(row_bleed, text="Left:").pack(side=tk.LEFT)
        self.bleed_l = tk.StringVar(value="2.0")
        ttk.Entry(row_bleed, textvariable=self.bleed_l, width=5).pack(side=tk.LEFT, padx=(2, 10))
        
        ttk.Label(row_bleed, text="Right:").pack(side=tk.LEFT)
        self.bleed_r = tk.StringVar(value="2.0")
        ttk.Entry(row_bleed, textvariable=self.bleed_r, width=5).pack(side=tk.LEFT, padx=(2, 10))

        ttk.Label(row_bleed, text="DPI:").pack(side=tk.LEFT, padx=(15, 2))
        self.dpi_var = tk.StringVar(value="300")
        ttk.Entry(row_bleed, textvariable=self.dpi_var, width=5).pack(side=tk.LEFT)

        # 3. Output PDF
        row_out = ttk.Frame(config_frame)
        row_out.pack(fill=tk.X, pady=5)
        ttk.Label(row_out, text="Output PDF:", width=15, anchor=tk.W).pack(side=tk.LEFT)
        self.out_pdf_var = tk.StringVar()
        ttk.Entry(row_out, textvariable=self.out_pdf_var).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        ttk.Button(row_out, text="Save As...", command=self.browse_output).pack(side=tk.RIGHT)

        # Actions
        action_frame = ttk.Frame(self.frame)
        action_frame.pack(fill=tk.X, padx=10, pady=5)
        self.process_btn = ttk.Button(action_frame, text="Add Bleed to PDF", command=self.start_processing)
        self.process_btn.pack(fill=tk.X)

        # Console
        self.console = scrolledtext.ScrolledText(self.frame, wrap=tk.WORD, bg="#1e1e1e", fg="#d4d4d4", font=("Consolas", 10))
        self.console.pack(expand=True, fill=tk.BOTH, padx=10, pady=(5, 10))

    def browse_input(self):
        filepath = filedialog.askopenfilename(filetypes=[("PDF Files", "*.pdf")])
        if filepath:
            self.in_pdf_var.set(filepath)
            dir_name = os.path.dirname(filepath)
            base_name = os.path.splitext(os.path.basename(filepath))[0]
            self.out_pdf_var.set(os.path.join(dir_name, f"{base_name}_bleed.pdf"))

    def browse_output(self):
        filepath = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF Files", "*.pdf")])
        if filepath:
            self.out_pdf_var.set(filepath)

    def log(self, message):
        self.app.root.after(0, self._append_log, message)

    def _append_log(self, message):
        self.console.config(state=tk.NORMAL)
        self.console.insert(tk.END, message + "\n")
        self.console.see(tk.END)
        self.console.config(state=tk.DISABLED)

    def start_processing(self):
        in_pdf = self.in_pdf_var.get().strip()
        out_pdf = self.out_pdf_var.get().strip()

        if not in_pdf or not os.path.exists(in_pdf):
            messagebox.showerror("Error", "Please select a valid input PDF.")
            return
        if not out_pdf:
            messagebox.showerror("Error", "Please specify an output PDF path.")
            return

        params = {
            't_mm': float(self.bleed_t.get() or 0),
            'b_mm': float(self.bleed_b.get() or 0),
            'l_mm': float(self.bleed_l.get() or 0),
            'r_mm': float(self.bleed_r.get() or 0),
            'dpi': int(self.dpi_var.get() or 300)
        }

        self.process_btn.config(state=tk.DISABLED)
        self.console.config(state=tk.NORMAL)
        self.console.delete(1.0, tk.END)
        self.console.config(state=tk.DISABLED)

        def run():
            success = add_bleed_to_pdf(in_pdf, out_pdf, params, self.log)
            self.app.root.after(0, lambda: self.process_btn.config(state=tk.NORMAL))
            if success:
                self.app.root.after(0, lambda: messagebox.showinfo("Done", "PDF bleed added successfully!"))

        threading.Thread(target=run, daemon=True).start()