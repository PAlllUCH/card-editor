import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext, messagebox
import requests
import json
import os
import urllib.parse
import subprocess
import threading
import csv
import time

OUTPUT_DIR = "downloaded_cards"

def find_key(obj, key):
    """Recursively search for a key in a JSON object to handle nested structures."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == key:
                return v
            if isinstance(v, (dict, list)):
                res = find_key(v, key)
                if res is not None:
                    return res
    elif isinstance(obj, list):
        for item in obj:
            res = find_key(item, key)
            if res is not None:
                return res
    return None

def parse_github_url(url):
    """Parses a standard GitHub tree URL into its API components."""
    url = url.replace("https://github.com/", "").replace("http://github.com/", "")
    parts = url.split('/')
    
    if len(parts) < 5 or parts[2] != 'tree':
        raise ValueError("Invalid GitHub folder URL. It should look like: https://github.com/Owner/Repo/tree/branch/folder_path")
    
    owner = parts[0]
    repo = parts[1]
    branch = parts[3]
    folder_path = urllib.parse.unquote("/".join(parts[4:]))
    
    return owner, repo, branch, folder_path

def get_extension(url):
    """Extracts the file extension from a URL, defaulting to .png if none is found."""
    parsed_path = urllib.parse.urlparse(url).path
    ext = os.path.splitext(parsed_path)[1].lower()
    if ext in ['.png', '.jpg', '.jpeg', '.webp', '.bmp']:
        return ext
    return '.png'

class ScraperApp:
    def __init__(self, root):
        self.root = root
        self.root.title("GitHub TS Image Scraper")
        self.root.geometry("750x600")
        
        self.pause_event = threading.Event()
        self.pause_event.set()
        
        self.create_widgets()

    def create_widgets(self):
        input_frame = ttk.Frame(self.root, padding="10")
        input_frame.pack(fill=tk.X)

        ttk.Label(input_frame, text="GitHub Folder URL:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.url_entry = ttk.Entry(input_frame, width=70)
        self.url_entry.grid(row=0, column=1, columnspan=2, padx=5, pady=5)

        ttk.Label(input_frame, text="Post-process .bat file (optional):").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.bat_entry = ttk.Entry(input_frame, width=55)
        self.bat_entry.grid(row=1, column=1, padx=5, pady=5)
        
        self.browse_btn = ttk.Button(input_frame, text="Browse...", command=self.browse_bat)
        self.browse_btn.grid(row=1, column=2, padx=5, pady=5)

        # Checkbox for Verification
        self.verify_var = tk.BooleanVar(value=False)
        self.verify_chk = ttk.Checkbutton(
            input_frame, 
            text="Verify all downloaded files before executing script", 
            variable=self.verify_var
        )
        self.verify_chk.grid(row=2, column=0, columnspan=3, sticky=tk.W, pady=5)

        btn_frame = ttk.Frame(input_frame)
        btn_frame.grid(row=3, column=0, columnspan=3, pady=15)

        self.run_btn = ttk.Button(btn_frame, text="Start Scraping", command=self.start_thread)
        self.run_btn.pack(side=tk.LEFT, padx=5)

        self.pause_btn = ttk.Button(btn_frame, text="Pause", command=self.pause_script, state=tk.DISABLED)
        self.pause_btn.pack(side=tk.LEFT, padx=5)

        self.resume_btn = ttk.Button(btn_frame, text="Resume", command=self.resume_script, state=tk.DISABLED)
        self.resume_btn.pack(side=tk.LEFT, padx=5)

        self.console = scrolledtext.ScrolledText(self.root, wrap=tk.WORD, state=tk.DISABLED, bg="#1e1e1e", fg="#d4d4d4", font=("Consolas", 10))
        self.console.pack(expand=True, fill=tk.BOTH, padx=10, pady=(0, 10))

    def _set_gui_running_state(self):
        self.run_btn.config(state=tk.DISABLED)
        self.pause_btn.config(state=tk.NORMAL)
        self.resume_btn.config(state=tk.DISABLED)

    def _set_gui_paused_state(self):
        self.run_btn.config(state=tk.DISABLED)
        self.pause_btn.config(state=tk.DISABLED)
        self.resume_btn.config(state=tk.NORMAL)

    def _set_gui_stopped_state(self):
        self.run_btn.config(state=tk.NORMAL)
        self.pause_btn.config(state=tk.DISABLED)
        self.resume_btn.config(state=tk.DISABLED)

    def browse_bat(self):
        filename = filedialog.askopenfilename(
            title="Select Batch File",
            filetypes=(("Batch files", "*.bat"), ("All files", "*.*"))
        )
        if filename:
            self.bat_entry.delete(0, tk.END)
            self.bat_entry.insert(0, filename)

    def pause_script(self):
        self.pause_event.clear()
        self._set_gui_paused_state()
        self.log("\n[ PAUSED by user ]")

    def resume_script(self):
        self.pause_event.set()
        self._set_gui_running_state()
        self.log("\n[ RESUMING... ]")

    def log(self, message):
        self.root.after(0, self._append_log, message)

    def _append_log(self, message):
        self.console.config(state=tk.NORMAL)
        self.console.insert(tk.END, message + "\n")
        self.console.see(tk.END)
        self.console.config(state=tk.DISABLED)

    def download_image(self, url, filename, max_retries=3):
        if not url:
            return
        
        for attempt in range(1, max_retries + 1):
            self.pause_event.wait() 
            
            try:
                response = requests.get(url, stream=True, timeout=10)
                response.raise_for_status()
                
                with open(filename, 'wb') as f:
                    for chunk in response.iter_content(1024):
                        self.pause_event.wait()
                        f.write(chunk)
                        
                self.log(f"Saved: {os.path.basename(filename)}")
                return
                
            except Exception as e:
                if attempt < max_retries:
                    self.log(f"[ WARNING ] Attempt {attempt}/{max_retries} failed for {url}. Retrying in 2 seconds...")
                    time.sleep(2)
                else:
                    error_msg = f"[ ERROR ] Failed to download {url} after {max_retries} attempts.\nReason: {e}"
                    self.log(error_msg)
                    self.log("--- AUTO-PAUSED DUE TO DOWNLOAD ERROR ---")
                    
                    self.pause_event.clear()
                    self.root.after(0, self._set_gui_paused_state)
                    return 

    def start_thread(self):
        target_url = self.url_entry.get().strip()
        bat_path = self.bat_entry.get().strip()

        if not target_url:
            messagebox.showwarning("Input Error", "Please enter a GitHub URL.")
            return

        self._set_gui_running_state()
        self.console.config(state=tk.NORMAL)
        self.console.delete(1.0, tk.END)
        self.console.config(state=tk.DISABLED)
        
        self.pause_event.set() 

        threading.Thread(target=self.run_scraper, args=(target_url, bat_path), daemon=True).start()

    def run_scraper(self, target_url, bat_path):
        try:
            owner, repo, branch, folder_path = parse_github_url(target_url)
        except ValueError as e:
            self.log(f"Error: {e}")
            self.root.after(0, self._set_gui_stopped_state)
            return

        folder_name = folder_path.split('/')[-1]
        output_path = os.path.join(OUTPUT_DIR, folder_name)
        os.makedirs(output_path, exist_ok=True)
        self.log(f"Saving images to: {output_path}")

        api_url = f"https://api.github.com/repos/{owner}/{repo}/contents/{folder_path}?ref={branch}"
        self.log("Fetching file list from API...\n")
        
        self.pause_event.wait()
        
        response = requests.get(api_url)
        if response.status_code != 200:
            self.log(f"Error accessing GitHub API: {response.status_code} - {response.text}")
            self.root.after(0, self._set_gui_stopped_state)
            return

        files = response.json()
        if not isinstance(files, list):
            self.log("Error: The URL does not point to a directory.")
            self.root.after(0, self._set_gui_stopped_state)
            return

        csv_filename = os.path.join(output_path, "cards_data.csv")
        expected_images = []  # List to track all image names we expect to download
        
        with open(csv_filename, mode='w', newline='', encoding='utf-8') as csv_file:
            csv_writer = csv.writer(csv_file)
            csv_writer.writerow(['ID', 'front name', 'back name', 'count'])

            for file_info in files:
                self.pause_event.wait()
                
                if file_info['name'].endswith('.json'):
                    self.log(f"Processing: {file_info['name']}")
                    
                    raw_url = file_info.get('download_url')
                    if not raw_url:
                        self.log(" -> Missing download URL (File might be a folder). Skipping.")
                        self.log("-" * 30)
                        continue
                    
                    try:
                        json_resp = requests.get(raw_url, timeout=10)
                        
                        if json_resp.status_code == 200:
                            data = json_resp.json()
                            card_id = find_key(data, "CardID")
                            face_url = find_key(data, "FaceURL")
                            back_url = find_key(data, "BackURL")

                            if card_id is not None:
                                face_ext = get_extension(str(face_url)) if face_url and isinstance(face_url, str) else ""
                                back_ext = get_extension(str(back_url)) if back_url and isinstance(back_url, str) else ""

                                front_name = f"{card_id}_front{face_ext}" if face_url else ""
                                back_name = f"{card_id}_back{back_ext}" if back_url else ""

                                # Log expected files for the verification step
                                if front_name:
                                    expected_images.append(front_name)
                                if back_name:
                                    expected_images.append(back_name)

                                if face_url and isinstance(face_url, str):
                                    face_filename = os.path.join(output_path, front_name)
                                    self.download_image(face_url, face_filename)
                                
                                if back_url and isinstance(back_url, str):
                                    back_filename = os.path.join(output_path, back_name)
                                    self.download_image(back_url, back_filename)

                                csv_writer.writerow([card_id, front_name, back_name, ""])
                                self.log(f"Logged ID {card_id} to CSV.")
                            else:
                                self.log(f" -> No CardID found in {file_info['name']}. Skipping.")
                                
                        else:
                            self.log(f" -> GitHub Error: Failed to fetch JSON. (Status: {json_resp.status_code})")
                            
                    except json.JSONDecodeError:
                        self.log(f" -> JSON Decode Error: Could not parse contents of {file_info['name']}")
                    except Exception as e:
                        self.log(f" -> Unexpected Error parsing {file_info['name']}: {e}")
                        
                    self.log("-" * 30)

        self.log("\n--- Scraping & CSV Generation Complete ---")

        # --- VERIFICATION STEP ---
        if self.verify_var.get():
            self.log("\n--- Running File Verification ---")
            missing_files = []
            for img_name in expected_images:
                if not os.path.exists(os.path.join(output_path, img_name)):
                    missing_files.append(img_name)
            
            if missing_files:
                self.log(f"[ WARNING ] {len(missing_files)} expected file(s) are missing:")
                for mf in missing_files:
                    self.log(f" -> Missing: {mf}")
                
                self.log("--- AUTO-PAUSED (Check missing files before batch execution) ---")
                self.pause_event.clear()
                self.root.after(0, self._set_gui_paused_state)
                self.pause_event.wait()  # Wait for user to click Resume
                
                self.log("[ VERIFICATION ACKNOWLEDGED ] Resuming...")
            else:
                self.log("[ OK ] All expected files are present.")

        # --- POST-PROCESSING ---
        if bat_path and os.path.exists(bat_path):
            self.pause_event.wait()
            
            abs_output_path = os.path.abspath(output_path)
            self.log(f"\nExecuting post-process script: {bat_path}")
            self.log(f"Working Directory set to: {abs_output_path}")
            try:
                process = subprocess.Popen(
                    [bat_path], 
                    shell=True, 
                    cwd=abs_output_path, 
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.PIPE, 
                    text=True
                )
                
                for line in process.stdout:
                    if line.strip():
                        self.log(line.strip())
                
                process.wait() 
                
                if process.returncode == 0:
                    self.log(f"--- Batch script finished successfully (Exit Code: {process.returncode}) ---")
                else:
                    self.log(f"--- Batch script failed (Exit Code: {process.returncode}) ---")
                    for err_line in process.stderr:
                        if err_line.strip():
                            self.log(f"[ERROR] {err_line.strip()}")
                            
            except Exception as e:
                self.log(f"Failed to execute batch file: {e}")

        self.root.after(0, self._set_gui_stopped_state)

if __name__ == "__main__":
    root = tk.Tk()
    app = ScraperApp(root)
    root.mainloop()