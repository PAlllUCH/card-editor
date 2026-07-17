import os
import cv2
import numpy as np
from PIL import Image

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None

def add_bleed_to_pdf(input_pdf, output_pdf, params, log_callback):
    if fitz is None:
        log_callback("[ ERROR ] PyMuPDF (fitz) is not installed. Please run: pip install pymupdf")
        return False

    dpi = params.get('dpi', 300)
    t_mm = params.get('t_mm', 2.0)
    b_mm = params.get('b_mm', 2.0)
    l_mm = params.get('l_mm', 2.0)
    r_mm = params.get('r_mm', 2.0)

    # Convert mm to pixels
    t_px = int((t_mm / 25.4) * dpi)
    b_px = int((b_mm / 25.4) * dpi)
    l_px = int((l_mm / 25.4) * dpi)
    r_px = int((r_mm / 25.4) * dpi)

    log_callback(f"Opening PDF: {os.path.basename(input_pdf)}")
    
    try:
        doc = fitz.open(input_pdf)
        total_pages = len(doc)
        log_callback(f"Found {total_pages} pages. Target DPI: {dpi}")
        
        # PyMuPDF zoom matrix for DPI
        zoom = dpi / 72.0 
        mat = fitz.Matrix(zoom, zoom)
        
        processed_images = []

        for page_num in range(total_pages):
            log_callback(f"Processing page {page_num + 1}/{total_pages}...")
            page = doc.load_page(page_num)
            
            # Render page to a pixmap
            pix = page.get_pixmap(matrix=mat, alpha=False)
            
            # Convert pixmap to numpy array (OpenCV format)
            img_np = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.h, pix.w, pix.n)
            
            # If RGB, convert to BGR for OpenCV
            if pix.n == 3:
                img_bgr = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)
            else:
                img_bgr = img_np
                
            # Add Bleed using OpenCV Reflection (same as your image editor)
            img_bleed = cv2.copyMakeBorder(
                img_bgr, 
                t_px, b_px, l_px, r_px, 
                cv2.BORDER_REFLECT_101
            )
            
            # Convert back to PIL Image (RGB) for PDF saving
            img_rgb = cv2.cvtColor(img_bleed, cv2.COLOR_BGR2RGB)
            pil_img = Image.fromarray(img_rgb)
            processed_images.append(pil_img)

        # Save all images back to a single PDF
        log_callback("Saving new PDF with bleed...")
        if processed_images:
            processed_images[0].save(
                output_pdf,
                "PDF",
                save_all=True,
                append_images=processed_images[1:],
                resolution=dpi
            )
        
        doc.close()
        log_callback(f"\n[ SUCCESS ] Saved to:\n{output_pdf}")
        return True

    except Exception as e:
        log_callback(f"[ ERROR ] {e}")
        return False