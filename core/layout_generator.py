import os
import csv
from PIL import Image

def _get_column_indices(headers, log_callback):
    """Helper to safely find column indices based on standard or fallback names."""
    try:
        id_idx = headers.index('ID')
    except ValueError:
        id_idx = 1 # Fallback to 2nd column based on your ArkhamDB structure

    try:
        front_idx = headers.index('front name')
    except ValueError:
        front_idx = 2  

    try:
        back_idx = headers.index('back name')
    except ValueError:
        back_idx = 3  

    if 'count' in headers:
        count_idx = headers.index('count')
    else:
        # If 'count' is missing (e.g., header says '0'), default to the last column
        count_idx = len(headers) - 1 

    return id_idx, front_idx, back_idx, count_idx

def generate_pdf_layout(csv_path, page_params, log_callback):
    page_w_mm = float(page_params.get('page_w_mm', 210.0))
    page_h_mm = float(page_params.get('page_h_mm', 297.0))
    margin_t_mm = float(page_params.get('margin_top_mm', 10.0))
    margin_b_mm = float(page_params.get('margin_bottom_mm', 10.0))
    margin_l_mm = float(page_params.get('margin_left_mm', 10.0))
    margin_r_mm = float(page_params.get('margin_right_mm', 10.0))
    gap_mm = float(page_params.get('gap_mm', 2.0))
    dpi = int(page_params.get('dpi', 300))
    output_dir = page_params.get('output_dir', '')
    duplex_mode = page_params.get('duplex_mode', 'Long Edge (Horizontal)')

    if not output_dir:
        log_callback("[ ERROR ] Output directory not specified.")
        return False

    output_pdf_path = os.path.join(output_dir, "print_layout.pdf")
    folder_dir = os.path.dirname(csv_path)
    
    # Calculate pixel dimensions
    page_w_px = int((page_w_mm / 25.4) * dpi)
    page_h_px = int((page_h_mm / 25.4) * dpi)
    margin_t_px = int((margin_t_mm / 25.4) * dpi)
    margin_b_px = int((margin_b_mm / 25.4) * dpi)
    margin_l_px = int((margin_l_mm / 25.4) * dpi)
    margin_r_px = int((margin_r_mm / 25.4) * dpi)
    gap_px = int((gap_mm / 25.4) * dpi)

    log_callback("Reading CSV card list...")
    rows = []
    try:
        with open(csv_path, mode='r', newline='', encoding='utf-8') as f:
            reader = csv.reader(f)
            headers = next(reader)
            rows = list(reader)
    except Exception as e:
        log_callback(f"[ ERROR ] Failed to read CSV: {e}")
        return False

    id_idx, front_idx, back_idx, count_idx = _get_column_indices(headers, log_callback)

    # Build deck list of copies
    deck_list = []
    card_w_px = 0
    card_h_px = 0

    for row in rows:
        if len(row) <= max(front_idx, back_idx, count_idx):
            continue
        front_file = row[front_idx].strip()
        back_file = row[back_idx].strip()
        try:
            count = int(row[count_idx].strip() or 1)
        except ValueError:
            count = 1

        front_path = os.path.join(folder_dir, front_file) if front_file else ""
        back_path = os.path.join(folder_dir, back_file) if back_file else ""

        if not front_path or not os.path.exists(front_path):
            continue

        # Detect dimensions from the first valid front image
        if card_w_px == 0:
            try:
                with Image.open(front_path) as test_img:
                    card_w_px, card_h_px = test_img.size
                log_callback(f"Detected card size from {front_file}: {card_w_px}x{card_h_px} pixels.")
            except Exception as e:
                log_callback(f"[ WARNING ] Could not open {front_file} for size check: {e}")

        for _ in range(count):
            deck_list.append((front_path, back_path))

    if not deck_list:
        log_callback("[ ERROR ] No valid cards to layout. Make sure image files exist and count > 0.")
        return False

    if card_w_px == 0 or card_h_px == 0:
        card_w_px = int((63.0 / 25.4) * dpi)
        card_h_px = int((88.0 / 25.4) * dpi)
        log_callback(f"No size detected. Defaulting to standard 63x88mm ({card_w_px}x{card_h_px} px).")

    # Calculate grid layout
    avail_w = page_w_px - margin_l_px - margin_r_px
    avail_h = page_h_px - margin_t_px - margin_b_px

    cols = (avail_w + gap_px) // (card_w_px + gap_px)
    rows_per_page = (avail_h + gap_px) // (card_h_px + gap_px)

    if cols <= 0 or rows_per_page <= 0:
        log_callback(f"[ ERROR ] Grid spacing issues. Available area {avail_w}x{avail_h}px is smaller than card size {card_w_px}x{card_h_px}px.")
        return False

    cards_per_page = cols * rows_per_page
    log_callback(f"Layout Grid: {cols} columns x {rows_per_page} rows. Total {cards_per_page} cards per page.")

    grid_w_px = cols * card_w_px + (cols - 1) * gap_px
    grid_h_px = rows_per_page * card_h_px + (rows_per_page - 1) * gap_px

    extra_w_px = avail_w - grid_w_px
    extra_h_px = avail_h - grid_h_px

    start_x_f = margin_l_px + extra_w_px // 2
    start_y_f = margin_t_px + extra_h_px // 2

    start_x_b = margin_r_px + extra_w_px // 2
    start_y_b = margin_b_px + extra_h_px // 2

    pages_images = []
    chunked_cards = [deck_list[i:i + cards_per_page] for i in range(0, len(deck_list), cards_per_page)]

    for page_idx, chunk in enumerate(chunked_cards):
        log_callback(f"Laying out page {page_idx + 1}...")
        
        front_page = Image.new('RGB', (page_w_px, page_h_px), 'white')
        back_page = Image.new('RGB', (page_w_px, page_h_px), 'white')

        for idx, (f_path, b_path) in enumerate(chunk):
            r = idx // cols
            c = idx % cols

            # Paste Front
            try:
                with Image.open(f_path) as f_img:
                    if f_img.size != (card_w_px, card_h_px):
                        f_img = f_img.resize((card_w_px, card_h_px), Image.Resampling.LANCZOS)
                    x_f = start_x_f + c * (card_w_px + gap_px)
                    y_f = start_y_f + r * (card_h_px + gap_px)
                    front_page.paste(f_img, (x_f, y_f))
            except Exception as e:
                log_callback(f" -> [ WARNING ] Failed to paste front {os.path.basename(f_path)}: {e}")

            # Paste Back
            if b_path and os.path.exists(b_path):
                try:
                    with Image.open(b_path) as b_img:
                        if b_img.size != (card_w_px, card_h_px):
                            b_img = b_img.resize((card_w_px, card_h_px), Image.Resampling.LANCZOS)
                        
                        if duplex_mode == 'Short Edge (Vertical)':
                            r_mirrored = rows_per_page - 1 - r
                            x_b = start_x_f + c * (card_w_px + gap_px)
                            y_b = start_y_b + r_mirrored * (card_h_px + gap_px)
                        else:
                            c_mirrored = cols - 1 - c
                            x_b = start_x_b + c_mirrored * (card_w_px + gap_px)
                            y_b = start_y_f + r * (card_h_px + gap_px)
                            
                        back_page.paste(b_img, (x_b, y_b))
                except Exception as e:
                    log_callback(f" -> [ WARNING ] Failed to paste back {os.path.basename(b_path)}: {e}")

        pages_images.append(front_page)
        pages_images.append(back_page)

    log_callback(f"Saving compiled pages to PDF: {os.path.basename(output_pdf_path)}")
    try:
        pages_images[0].save(
            output_pdf_path,
            "PDF",
            save_all=True,
            append_images=pages_images[1:],
            resolution=dpi
        )
        log_callback(f"\n[ SUCCESS ] Print-ready PDF generated successfully at:\n{output_pdf_path}")
        return True
    except Exception as e:
        log_callback(f"[ ERROR ] Failed to save PDF: {e}")
        return False


def generate_individual_pdfs(csv_path, page_params, log_callback):
    dpi = int(page_params.get('dpi', 300))
    output_dir = page_params.get('output_dir', '')
    
    if not output_dir:
        log_callback("[ ERROR ] Output directory not specified.")
        return False

    folder_dir = os.path.dirname(csv_path)
    target_dir = os.path.join(output_dir, "Individual_PDFs")
    os.makedirs(target_dir, exist_ok=True)
    log_callback(f"Creating Individual PDFs in:\n{target_dir}")

    try:
        with open(csv_path, mode='r', newline='', encoding='utf-8') as f:
            reader = csv.reader(f)
            headers = next(reader)
            rows = list(reader)
    except Exception as e:
        log_callback(f"[ ERROR ] Failed to read CSV: {e}")
        return False

    id_idx, front_idx, back_idx, count_idx = _get_column_indices(headers, log_callback)

    processed = 0
    # NEW: Global dictionary to track copies across duplicate CSV rows
    id_counters = {} 

    for idx, row in enumerate(rows):
        if len(row) <= max(front_idx, back_idx, count_idx): continue
        
        card_id = row[id_idx].strip() if len(row) > id_idx else f"card_{idx+1}"
        front_file = row[front_idx].strip()
        back_file = row[back_idx].strip()
        
        try: 
            count = int(row[count_idx].strip() or 1)
        except ValueError: 
            count = 1

        if count <= 0: continue

        front_path = os.path.join(folder_dir, front_file) if front_file else ""
        back_path = os.path.join(folder_dir, back_file) if back_file else ""

        if not front_path or not os.path.exists(front_path):
            log_callback(f" -> [ SKIP ] Front image missing for ID {card_id}")
            continue

        try:
            front_img = Image.open(front_path).convert('RGB')
            back_img = None
            if back_path and os.path.exists(back_path):
                back_img = Image.open(back_path).convert('RGB')

            # Fetch the running total of copies for this specific ID (defaults to 0)
            current_base_count = id_counters.get(card_id, 0)

            for i in range(1, count + 1):
                pages = [front_img.copy()]
                if back_img:
                    pages.append(back_img.copy())

                # Add the base count so duplicate rows continue incrementing (e.g., _3, _4)
                file_index = current_base_count + i
                pdf_filename = f"{card_id}_{file_index}.pdf"
                pdf_out_path = os.path.join(target_dir, pdf_filename)
                
                pages[0].save(
                    pdf_out_path,
                    "PDF",
                    save_all=True,
                    append_images=pages[1:],
                    resolution=dpi
                )
                processed += 1
                
            # Update the dictionary with the new total for this ID
            id_counters[card_id] = current_base_count + count
            log_callback(f" -> Exported {count} copies of ID {card_id}")

        except Exception as e:
            log_callback(f" -> [ ERROR ] Failed to process ID {card_id}: {e}")

    log_callback(f"\n[ SUCCESS ] Generated {processed} individual card PDFs.")
    return True