import os
import csv
import time
import requests
import urllib.parse
import json
import re

# --- Helper Functions ---
def find_key(obj, key):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == key: return v
            if isinstance(v, (dict, list)):
                res = find_key(v, key)
                if res is not None: return res
    elif isinstance(obj, list):
        for item in obj:
            res = find_key(item, key)
            if res is not None: return res
    return None

def parse_github_url(url):
    url = url.replace("https://github.com/", "").replace("http://github.com/", "")
    parts = url.split('/')
    if len(parts) < 5 or parts[2] != 'tree':
        raise ValueError("Invalid GitHub folder URL.")
    owner, repo, branch = parts[0], parts[1], parts[3]
    folder_path = urllib.parse.unquote("/".join(parts[4:]))
    return owner, repo, branch, folder_path

def get_extension(url):
    parsed_path = urllib.parse.urlparse(url).path
    ext = os.path.splitext(parsed_path)[1].lower()
    if ext in ['.png', '.jpg', '.jpeg', '.webp', '.bmp']: return ext
    return '.png'

# --- Scraping Logic ---
def download_image(url, filename, callbacks, pause_event, max_retries=3):
    if not url: return False
    
    for attempt in range(1, max_retries + 1):
        pause_event.wait() 
        try:
            response = requests.get(url, stream=True, timeout=10)
            response.raise_for_status()
            
            with open(filename, 'wb') as f:
                for chunk in response.iter_content(1024):
                    pause_event.wait()
                    f.write(chunk)
            
            callbacks['log'](f"Saved: {os.path.basename(filename)}")
            return True
            
        except Exception as e:
            if attempt < max_retries:
                callbacks['log'](f"[ WARNING ] Attempt {attempt}/{max_retries} failed for {url}. Retrying...")
                time.sleep(2)
            else:
                callbacks['log'](f"[ ERROR ] Failed to download {url}.\nReason: {e}")
                callbacks['log']("--- AUTO-PAUSED DUE TO ERROR ---")
                callbacks['trigger_pause']()
                return False

def run_scraping_task(target_url, is_retry, output_dir, pause_event, callbacks):
    try:
        owner, repo, branch, folder_path = parse_github_url(target_url)
    except ValueError as e:
        callbacks['log'](f"Error: {e}"); callbacks['finish'](None, [])
        return

    folder_name = folder_path.split('/')[-1]
    output_path = os.path.join(output_dir, folder_name)
    os.makedirs(output_path, exist_ok=True)
    callbacks['log'](f"Saving images to: {output_path}")

    api_url = f"https://api.github.com/repos/{owner}/{repo}/contents/{folder_path}?ref={branch}"
    callbacks['log']("Fetching file list from API...\n")
    pause_event.wait()
    
    response = requests.get(api_url)
    if response.status_code != 200:
        callbacks['log'](f"Error accessing GitHub API: {response.status_code}"); callbacks['finish'](None, [])
        return

    files = response.json()
    if not isinstance(files, list):
        callbacks['log']("Error: URL does not point to a directory."); callbacks['finish'](None, [])
        return

    json_files = [f for f in files if f['name'].endswith('.json')]
    callbacks['init_file_list']([f['name'] for f in json_files], is_retry)

    csv_filename = os.path.join(output_path, "cards_data.csv")
    expected_images = []
    
    with open(csv_filename, mode='w', newline='', encoding='utf-8') as csv_file:
        csv_writer = csv.writer(csv_file)
        csv_writer.writerow(['ArkhamDB', 'ID', 'front name', 'back name', 'count'])

        for file_info in json_files:
            pause_event.wait()
            fname = file_info['name']
            callbacks['update_file_status'](fname, 'Processing...')
            callbacks['log'](f"Processing: {fname}")
            
            raw_url = file_info.get('download_url')
            if not raw_url:
                callbacks['log'](" -> Missing download URL. Skipping.\n" + "-"*30)
                callbacks['update_file_status'](fname, 'Error')
                continue
            
            try:
                json_resp = requests.get(raw_url, timeout=10)
                if json_resp.status_code == 200:
                    data = json_resp.json()
                    card_id = find_key(data, "CardID")
                    face_url = find_key(data, "FaceURL")
                    back_url = find_key(data, "BackURL")

                    if card_id is not None:
                        f_ext = get_extension(str(face_url)) if face_url and isinstance(face_url, str) else ""
                        b_ext = get_extension(str(back_url)) if back_url and isinstance(back_url, str) else ""

                        f_name = f"{card_id}_front{f_ext}" if face_url else ""
                        b_name = f"{card_id}_back{b_ext}" if back_url else ""

                        f_success = True
                        b_success = True

                        if f_name:
                            expected_images.append(f_name)
                            f_path = os.path.join(output_path, f_name)
                            if os.path.exists(f_path) and os.path.getsize(f_path) > 0:
                                callbacks['log'](f" -> Already exists: {f_name}")
                            else:
                                f_success = download_image(face_url, f_path, callbacks, pause_event)

                        if b_name:
                            expected_images.append(b_name)
                            b_path = os.path.join(output_path, b_name)
                            if os.path.exists(b_path) and os.path.getsize(b_path) > 0:
                                callbacks['log'](f" -> Already exists: {b_name}")
                            else:
                                b_success = download_image(back_url, b_path, callbacks, pause_event)

                        # Extract ArkhamDB value from GMNotes
                        arkham_db_val = ""
                        gm_notes = find_key(data, "GMNotes")
                        if gm_notes:
                            if isinstance(gm_notes, str):
                                try:
                                    parsed = json.loads(gm_notes)
                                    if isinstance(parsed, dict):
                                        arkham_db_val = str(parsed.get("id", ""))
                                except Exception:
                                    match = re.search(r'"id":\s*"([^"]+)"', gm_notes)
                                    if match:
                                        arkham_db_val = match.group(1)
                            elif isinstance(gm_notes, dict):
                                arkham_db_val = str(gm_notes.get("id", ""))

                        # UPDATED: Now writes ArkhamDB val and "1" for default count
                        csv_writer.writerow([arkham_db_val, card_id, f_name, b_name, "1"])
                        callbacks['log'](f"Logged ID {card_id} to CSV.")
                        
                        if f_success and b_success:
                            callbacks['update_file_status'](fname, 'OK')
                        else:
                            callbacks['update_file_status'](fname, 'Error')
                    else:
                        callbacks['log'](f" -> No CardID found.")
                        callbacks['update_file_status'](fname, 'Error')
                else:
                    callbacks['log'](f" -> GitHub Error. (Status: {json_resp.status_code})")
                    callbacks['update_file_status'](fname, 'Error')
            except Exception as e:
                callbacks['log'](f" -> Unexpected Error: {e}")
                callbacks['update_file_status'](fname, 'Error')
            
            callbacks['log']("-" * 30)

    callbacks['log']("\n--- Scraping Complete ---")
    callbacks['finish'](os.path.abspath(output_path), expected_images)

def update_csv_quantities(csv_path, log_callback, pause_event=None):
    if not os.path.exists(csv_path):
        log_callback(f"[ ERROR ] CSV file not found at: {csv_path}")
        return False
    
    log_callback("Starting ArkhamDB quantity updates...\n")
    
    # Read rows
    rows = []
    headers = []
    try:
        with open(csv_path, mode='r', newline='', encoding='utf-8') as f:
            reader = csv.reader(f)
            headers = next(reader)
            rows = list(reader)
    except Exception as e:
        log_callback(f"[ ERROR ] Failed to read CSV: {e}")
        return False

    if 'ArkhamDB' not in headers or 'count' not in headers:
        log_callback("[ ERROR ] CSV missing 'ArkhamDB' or 'count' columns.")
        return False
        
    adb_idx = headers.index('ArkhamDB')
    count_idx = headers.index('count')
    
    updated_count = 0
    failed_cards = []
    
    for i, row in enumerate(rows):
        if pause_event:
            pause_event.wait()
            
        if len(row) <= max(adb_idx, count_idx):
            continue
            
        card_code = row[adb_idx].strip()
        if not card_code:
            continue
            
        try:
            url = f"https://arkhamdb.com/api/public/card/{card_code}"
            headers_req = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
            resp = requests.get(url, headers=headers_req, timeout=10)
            if resp.status_code == 200:
                card_data = resp.json()
                card_name = card_data.get('name', 'Unknown')
                qty = card_data.get('quantity', 1)
                row[count_idx] = str(qty)
                log_callback(f"Fetching ArkhamDB ID: {card_code} ({card_name})...")
                log_callback(f" -> Set count to {qty}")
                updated_count += 1
            else:
                log_callback(f"Fetching ArkhamDB ID: {card_code}...")
                log_callback(f" -> [ WARNING ] Failed to fetch (Status: {resp.status_code})")
                failed_cards.append((card_code, "Unknown (HTTP Error)"))
        except Exception as e:
            log_callback(f"Fetching ArkhamDB ID: {card_code}...")
            log_callback(f" -> [ WARNING ] Error fetching: {e}")
            failed_cards.append((card_code, f"Unknown ({type(e).__name__})"))
            
        time.sleep(0.5)
        
    # Write back
    try:
        with open(csv_path, mode='w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            writer.writerows(rows)
        log_callback(f"\nSuccessfully updated {updated_count} cards in CSV.")
        
        if failed_cards:
            log_callback("\n[ WARNING ] The following cards could not be updated:")
            for code, name in failed_cards:
                log_callback(f"  - ID: {code} (Name: {name})")
        return True
    except Exception as e:
        log_callback(f"[ ERROR ] Failed to write updated CSV: {e}")
        return False