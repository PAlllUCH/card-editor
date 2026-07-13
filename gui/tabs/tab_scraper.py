import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import threading
import os
import csv
from core.scraper import run_scraping_task, update_csv_quantities
from core.config import OUTPUT_DIR

class ScraperTab:
    def __init__(self, parent_notebook, app_controller):
        self.frame = ttk.Frame(parent_notebook)
        self.app = app_controller
        
        self.pause_event = threading.Event()
        self.pause_event.set()
        self.tree_items = {} 
        
        self.build_ui()

    def build_ui(self):
        left_frame = ttk.Frame(self.frame)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))

        right_frame = ttk.Frame(self.frame, width=280)
        right_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(5, 0))

        input_frame = ttk.Frame(left_frame, padding="10")
        input_frame.pack(fill=tk.X)

        ttk.Label(input_frame, text="GitHub Folder URL:").pack(anchor=tk.W, pady=2)
        self.url_entry = ttk.Entry(input_frame, width=80)
        self.url_entry.pack(fill=tk.X, pady=5)

        ttk.Label(input_frame, text="Output Folder:").pack(anchor=tk.W, pady=2)
        dir_selection_frame = ttk.Frame(input_frame)
        dir_selection_frame.pack(fill=tk.X, pady=5)
        
        self.dir_entry = ttk.Entry(dir_selection_frame)
        self.dir_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        self.dir_entry.insert(0, OUTPUT_DIR)
        
        self.browse_btn = ttk.Button(dir_selection_frame, text="Browse...", command=self.browse_output_directory)
        self.browse_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        self.check_csv_btn = ttk.Button(dir_selection_frame, text="Check CSV", command=self.check_existing_csv)
        self.check_csv_btn.pack(side=tk.LEFT)

        self.verify_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(input_frame, text="Verify Files After Downloading", variable=self.verify_var).pack(anchor=tk.W, pady=5)

        btn_frame = ttk.Frame(input_frame)
        btn_frame.pack(fill=tk.X, pady=10)

        self.run_btn = ttk.Button(btn_frame, text="Start Scraping", command=lambda: self.start_thread(is_retry=False))
        self.run_btn.pack(side=tk.LEFT, padx=5)

        self.pause_btn = ttk.Button(btn_frame, text="Pause", command=self.user_pause_script, state=tk.DISABLED)
        self.pause_btn.pack(side=tk.LEFT, padx=5)

        self.resume_btn = ttk.Button(btn_frame, text="Resume", command=self.user_resume_script, state=tk.DISABLED)
        self.resume_btn.pack(side=tk.LEFT, padx=5)

        self.retry_btn = ttk.Button(btn_frame, text="Retry Missing Files", command=lambda: self.start_thread(is_retry=True), state=tk.DISABLED)
        self.retry_btn.pack(side=tk.LEFT, padx=5)

        self.fetch_counts_btn = ttk.Button(btn_frame, text="Fetch ArkhamDB Counts", command=self.start_fetch_counts_thread, state=tk.DISABLED)
        self.fetch_counts_btn.pack(side=tk.LEFT, padx=5)

        self.verify_btn = ttk.Button(btn_frame, text="Verify & Go to Editor", command=self.verify_and_proceed, state=tk.DISABLED)
        self.verify_btn.pack(side=tk.RIGHT, padx=5)

        self.console = scrolledtext.ScrolledText(left_frame, wrap=tk.WORD, state=tk.DISABLED, bg="#1e1e1e", fg="#d4d4d4", font=("Consolas", 10))
        self.console.pack(expand=True, fill=tk.BOTH, padx=10, pady=(0, 10))

        ttk.Label(right_frame, text="File Processing Status:").pack(anchor=tk.W, pady=(10, 5))
        
        tree_scroll = ttk.Scrollbar(right_frame)
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.tree = ttk.Treeview(right_frame, columns=('Status',), selectmode='none', yscrollcommand=tree_scroll.set)
        self.tree.heading('#0', text='File Name', anchor=tk.W)
        self.tree.heading('Status', text='Status', anchor=tk.W)
        self.tree.column('#0', width=180, stretch=tk.YES)
        self.tree.column('Status', width=80, stretch=tk.NO)
        self.tree.pack(expand=True, fill=tk.BOTH)
        tree_scroll.config(command=self.tree.yview)

        self.tree.tag_configure('Pending', foreground='gray')
        self.tree.tag_configure('Processing...', foreground='orange')
        self.tree.tag_configure('OK', foreground='green')
        self.tree.tag_configure('Error', foreground='red')

    def browse_output_directory(self):
        chosen_dir = filedialog.askdirectory(initialdir=self.dir_entry.get())
        if chosen_dir:
            self.dir_entry.delete(0, tk.END)
            self.dir_entry.insert(0, os.path.abspath(chosen_dir))
            self.check_existing_csv()

    def check_existing_csv(self):
        target_path = self.dir_entry.get().strip()
        if not target_path or not os.path.exists(target_path):
            messagebox.showwarning("Folder Error", "The specified directory path does not exist.")
            return

        csv_path = os.path.join(target_path, "cards_data.csv")
        if not os.path.exists(csv_path):
            self.log(f"[ INFO ] No 'cards_data.csv' found inside: {target_path}. Ready for a fresh scrape.")
            return

        self.log(f"\n[ INFO ] Found existing 'cards_data.csv' in folder. Parsing files...")
        
        expected_images = []
        try:
            with open(csv_path, mode='r', newline='', encoding='utf-8') as f:
                reader = csv.reader(f)
                headers = next(reader)
                
                # Dynamically calculate indexes since card_name shifts them by 1
                f_idx = headers.index('front name') if 'front name' in headers else 3
                b_idx = headers.index('back name') if 'back name' in headers else 4
                
                for row in reader:
                    if len(row) > max(f_idx, b_idx):
                        front_file = row[f_idx].strip()
                        back_file = row[b_idx].strip()
                        if front_file and front_file != "N/A":
                            expected_images.append(front_file)
                        if back_file and back_file != "N/A":
                            expected_images.append(back_file)

            self.app.current_folder = target_path
            self.app.expected_images = expected_images
            
            self._set_gui_stopped_state()
            self.log(f"[ SUCCESS ] Loaded existing project metadata containing {len(expected_images)} indexed card images.")
            self.log("[ READY ] 'Retry Missing Files', 'Fetch ArkhamDB Counts', and 'Verify' are now unlocked.")
            
        except Exception as e:
            self.log(f"[ ERROR ] Failed to parse data from target file format: {e}")
            messagebox.showerror("Parsing Error", f"Failed to properly load local CSV tracking schema:\n{e}")

    # --- UI STATE MANAGEMENT ---
    def _set_gui_running_state(self):
        self.run_btn.config(state=tk.DISABLED)
        self.browse_btn.config(state=tk.DISABLED)
        self.check_csv_btn.config(state=tk.DISABLED)
        self.retry_btn.config(state=tk.DISABLED)
        self.fetch_counts_btn.config(state=tk.DISABLED)
        self.verify_btn.config(state=tk.DISABLED)
        self.pause_btn.config(state=tk.NORMAL)
        self.resume_btn.config(state=tk.DISABLED)

    def _set_gui_paused_state(self):
        self.run_btn.config(state=tk.DISABLED)
        self.browse_btn.config(state=tk.DISABLED)
        self.check_csv_btn.config(state=tk.DISABLED)
        self.retry_btn.config(state=tk.DISABLED)
        self.fetch_counts_btn.config(state=tk.DISABLED)
        self.verify_btn.config(state=tk.DISABLED)
        self.pause_btn.config(state=tk.DISABLED)
        self.resume_btn.config(state=tk.NORMAL)

    def _set_gui_stopped_state(self):
        self.run_btn.config(state=tk.NORMAL)
        self.browse_btn.config(state=tk.NORMAL)
        self.check_csv_btn.config(state=tk.NORMAL)
        self.retry_btn.config(state=tk.NORMAL)
        self.fetch_counts_btn.config(state=tk.NORMAL if self.app.current_folder else tk.DISABLED)
        self.verify_btn.config(state=tk.NORMAL)
        self.pause_btn.config(state=tk.DISABLED)
        self.resume_btn.config(state=tk.DISABLED)

    def user_pause_script(self):
        self.pause_event.clear(); self._set_gui_paused_state(); self.log("\n[ PAUSED by user ]")

    def user_resume_script(self):
        self.pause_event.set(); self._set_gui_running_state(); self.log("\n[ RESUMING... ]")

    def auto_pause_script(self):
        self.pause_event.clear(); self.app.root.after(0, self._set_gui_paused_state)

    def log(self, message):
        self.app.root.after(0, self._append_log, message)

    def _append_log(self, message):
        self.console.config(state=tk.NORMAL)
        self.console.insert(tk.END, message + "\n")
        self.console.see(tk.END)
        self.console.config(state=tk.DISABLED)

    def init_file_list(self, files, is_retry):
        if not is_retry:
            self.tree.delete(*self.tree.get_children())
            self.tree_items.clear()
            for f in files:
                item = self.tree.insert('', tk.END, text=f, values=('Pending',), tags=('Pending',))
                self.tree_items[f] = item
        else:
            for f in files:
                if f not in self.tree_items:
                    item = self.tree.insert('', tk.END, text=f, values=('Pending',), tags=('Pending',))
                    self.tree_items[f] = item

    def update_file_status(self, filename, status):
        if filename in self.tree_items:
            item = self.tree_items[filename]
            self.tree.item(item, values=(status,), tags=(status,))
            self.tree.see(item) 

    def finish_scraping(self, output_dir, expected_images):
        self.app.current_folder = output_dir
        self.app.expected_images = expected_images
        self.app.root.after(0, self._set_gui_stopped_state)
        self.log("\n[ READY ] Click 'Verify & Go to Editor' to proceed, or 'Fetch ArkhamDB Counts' to update quantities.")

    def start_thread(self, is_retry=False):
        target_url = self.url_entry.get().strip()
        chosen_output_dir = self.dir_entry.get().strip()
        
        if not target_url:
            messagebox.showwarning("Input Error", "Please enter a GitHub URL.")
            return
        if not chosen_output_dir:
            messagebox.showwarning("Input Error", "Please select a valid output directory.")
            return

        self._set_gui_running_state()
        if not is_retry:
            self.console.config(state=tk.NORMAL); self.console.delete(1.0, tk.END); self.console.config(state=tk.DISABLED)
        
        self.pause_event.set() 
        
        callbacks = {
            'log': self.log, 
            'trigger_pause': self.auto_pause_script, 
            'finish': lambda out, exp: self.app.root.after(0, self.finish_scraping, out, exp),
            'init_file_list': lambda files, retry: self.app.root.after(0, self.init_file_list, files, retry),
            'update_file_status': lambda f, s: self.app.root.after(0, self.update_file_status, f, s)
        }

        threading.Thread(
            target=run_scraping_task, 
            args=(target_url, is_retry, chosen_output_dir, self.pause_event, callbacks), 
            daemon=True
        ).start()

    def verify_and_proceed(self):
        if not self.app.expected_images or not self.app.current_folder:
            messagebox.showinfo("Info", "Nothing to verify. Start scraping first or check an existing project folder.")
            return
            
        missing_files = [img for img in self.app.expected_images if not os.path.exists(os.path.join(self.app.current_folder, img))]
        
        if missing_files:
            self.log(f"\n[ VERIFICATION FAILED ] {len(missing_files)} files are missing.")
            for mf in missing_files:
                self.log(f" -> Missing local path target: {os.path.join(self.app.current_folder, mf)}")
            messagebox.showwarning("Missing Files", f"{len(missing_files)} expected images are missing.\nPlease click 'Retry Missing Files' to attempt downloading them again.")
        else:
            self.log("\n[ VERIFICATION SUCCESS ] All expected files found. Switching to Editor.")
            self.app.switch_to_editor()

    def start_fetch_counts_thread(self):
        if not self.app.current_folder:
            messagebox.showwarning("Warning", "No folder selected. Please scrape cards first or load them via 'Check CSV'.")
            return

        csv_path = os.path.join(self.app.current_folder, "cards_data.csv")
        if not os.path.exists(csv_path):
            messagebox.showerror("Error", f"cards_data.csv not found in:\n{self.app.current_folder}")
            return

        self._set_gui_running_state()
        self.console.config(state=tk.NORMAL)
        self.console.delete(1.0, tk.END)
        self.console.config(state=tk.DISABLED)
        
        self.pause_event.set()

        def run_update():
            update_csv_quantities(csv_path, self.log, self.pause_event)
            self.app.root.after(0, self._set_gui_stopped_state)
            
        threading.Thread(target=run_update, daemon=True).start()