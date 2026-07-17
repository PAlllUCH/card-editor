import os
import urllib.parse
import cv2
import numpy as np
from PIL import Image

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

def process_image_advanced(
    filepath, 
    do_bleed=True, bleed_mode='Telea Inpaint (Soft)', bleed_size=10, inpaint_radius=15, blur_amount=15, fade_spread=10,
    enhance_color=False, saturation=100, contrast=100, brightness=0, sepia=0,
    do_spad=False, spad_margin=24,
    upscale_factor=1.0, 
    save=False
):
    try:
        file_bytes = np.fromfile(filepath, dtype=np.uint8)
        img = cv2.imdecode(file_bytes, cv2.IMREAD_UNCHANGED)
        
        if img is None: 
            print(f"Failed to decode image data for: {filepath}")
            return None

        # Drop alpha channel for processing
        if len(img.shape) == 3 and img.shape[2] == 4:
            bgr = img[:, :, :3]
        else:
            bgr = img.copy()

        # ==========================================
        # 1. CORNER BLEEDING ALGORITHMS
        # ==========================================
        if do_bleed:
            h, w = bgr.shape[:2]
            cr = max(1, int(min(w, h) * (bleed_size / 100.0)))
            mask = np.zeros((h, w), dtype=np.uint8)

            corners = [
                (0, 0, cr, cr, 1, 1),               # Top Left
                (w-cr, 0, w, cr, -1, 1),            # Top Right
                (0, h-cr, cr, h, 1, -1),            # Bottom Left
                (w-cr, h-cr, w, h, -1, -1)          # Bottom Right
            ]
            
            for (x1, y1, x2, y2, dx, dy) in corners:
                corner_roi = bgr[y1:y2, x1:x2]
                white_mask = cv2.inRange(corner_roi, (200, 200, 200), (255, 255, 255))
                mask[y1:y2, x1:x2] = white_mask

            if bleed_mode == 'Telea Inpaint (Soft)':
                bgr = cv2.inpaint(bgr, mask, inpaintRadius=int(inpaint_radius), flags=cv2.INPAINT_TELEA)
                if blur_amount > 0 or fade_spread > 0:
                    k = int(blur_amount) * 2 + 1 if blur_amount > 0 else 1
                    blurred_bgr = cv2.GaussianBlur(bgr, (k, k), 0) if k > 1 else bgr
                    dilated_mask = cv2.dilate(mask, np.ones((3, 3), np.uint8), iterations=int(fade_spread))
                    feather_k = max(15, int(blur_amount) * 4 + 1) 
                    if feather_k % 2 == 0: feather_k += 1 
                    feathered_mask = cv2.GaussianBlur(dilated_mask, (feather_k, feather_k), 0).astype(np.float32) / 255.0
                    feathered_mask = np.expand_dims(feathered_mask, axis=-1)
                    bgr = (bgr * (1.0 - feathered_mask) + blurred_bgr * feathered_mask).astype(np.uint8)

            elif bleed_mode == 'Navier-Stokes (Sharp)':
                bgr = cv2.inpaint(bgr, mask, inpaintRadius=int(inpaint_radius), flags=cv2.INPAINT_NS)

            elif bleed_mode == 'Pixel Stretch':
                for (x1, y1, x2, y2, dx, dy) in corners:
                    roi = bgr[y1:y2, x1:x2]
                    wm = mask[y1:y2, x1:x2]
                    if cv2.countNonZero(wm) > 0:
                        y_range = range(roi.shape[0]) if dy == 1 else reversed(range(roi.shape[0]))
                        x_range = range(roi.shape[1]) if dx == 1 else reversed(range(roi.shape[1]))
                        for y in y_range:
                            for x in x_range:
                                if wm[y, x] > 0:
                                    safe_x = x + dx if 0 <= x + dx < roi.shape[1] else x
                                    safe_y = y + dy if 0 <= y + dy < roi.shape[0] else y
                                    roi[y, x] = roi[safe_y, safe_x]
                    bgr[y1:y2, x1:x2] = roi
                    
            elif bleed_mode == 'Smooth Pixel Stretch':
                # First stretch the pixels
                for (x1, y1, x2, y2, dx, dy) in corners:
                    roi = bgr[y1:y2, x1:x2]
                    wm = mask[y1:y2, x1:x2]
                    if cv2.countNonZero(wm) > 0:
                        y_range = range(roi.shape[0]) if dy == 1 else reversed(range(roi.shape[0]))
                        x_range = range(roi.shape[1]) if dx == 1 else reversed(range(roi.shape[1]))
                        for y in y_range:
                            for x in x_range:
                                if wm[y, x] > 0:
                                    safe_x = x + dx if 0 <= x + dx < roi.shape[1] else x
                                    safe_y = y + dy if 0 <= y + dy < roi.shape[0] else y
                                    roi[y, x] = roi[safe_y, safe_x]
                    
                    # Then apply a blur exclusively to the stretched white_mask area
                    blurred_roi = cv2.GaussianBlur(roi, (15, 15), 0)
                    wm_3d = wm[:, :, np.newaxis] > 0
                    bgr[y1:y2, x1:x2] = np.where(wm_3d, blurred_roi, roi)

            elif bleed_mode == 'Edge Mirror':
                for (x1, y1, x2, y2, dx, dy) in corners:
                    px1 = x2 if dx == 1 else x1 - cr
                    px2 = px1 + cr
                    py1 = y2 if dy == 1 else y1 - cr
                    py2 = py1 + cr
                    
                    if px1 >= 0 and py1 >= 0 and px2 <= w and py2 <= h:
                        patch = bgr[py1:py2, px1:px2]
                        flipped = cv2.flip(patch, -1) 
                        wm = mask[y1:y2, x1:x2, np.newaxis] > 0
                        bgr[y1:y2, x1:x2] = np.where(wm, flipped, bgr[y1:y2, x1:x2])
                        
            elif bleed_mode == 'Dual-Axis Mirror':
                for (x1, y1, x2, y2, dx, dy) in corners:
                    wm = mask[y1:y2, x1:x2, np.newaxis] > 0
                    if not np.any(wm): continue

                    try:
                        # Grab adjacent horizontal and vertical border patches
                        h_src = bgr[y1:y2, x2:x2+cr] if dx == 1 else bgr[y1:y2, x1-cr:x1]
                        v_src = bgr[y2:y2+cr, x1:x2] if dy == 1 else bgr[y1-cr:y1, x1:x2]

                        # Mirror them inward
                        h_flip = cv2.flip(h_src, 1)
                        v_flip = cv2.flip(v_src, 0)
                        
                        # Blend the two reflections together perfectly
                        avg = cv2.addWeighted(h_flip, 0.5, v_flip, 0.5, 0)
                        bgr[y1:y2, x1:x2] = np.where(wm, avg, bgr[y1:y2, x1:x2])
                    except cv2.error:
                        pass # Fallback safely if image is too small for this radius

        # ==========================================
        # 2. COLOR GRADING ENGINE
        # ==========================================
        if enhance_color:
            if saturation != 100:
                hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV).astype(np.float32)
                hsv[:, :, 1] *= (saturation / 100.0)
                hsv[:, :, 1] = np.clip(hsv[:, :, 1], 0, 255)
                bgr = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)

            if contrast != 100 or brightness != 0:
                alpha = contrast / 100.0
                beta = brightness
                bgr = cv2.convertScaleAbs(bgr, alpha=alpha, beta=beta)

            if sepia > 0:
                sepia_strength = sepia / 100.0
                kernel = np.array([[0.272, 0.534, 0.131],
                                   [0.349, 0.686, 0.168],
                                   [0.393, 0.769, 0.189]])
                sepia_bgr = cv2.transform(bgr, kernel)
                bgr = cv2.addWeighted(sepia_bgr, sepia_strength, bgr, 1.0 - sepia_strength, 0)

        # ==========================================
        # 3. NATIVE SPAD (MIRROR PADDING)
        # ==========================================
        if do_spad and spad_margin > 0:
            margin = int(spad_margin)
            # This perfectly replaces the ImageMagick -virtual-pixel Mirror command
            bgr = cv2.copyMakeBorder(bgr, margin, margin, margin, margin, cv2.BORDER_REFLECT_101)

        # ==========================================
        # 4. UPSCALING
        # ==========================================
        upscale_factor = float(upscale_factor)
        if upscale_factor > 1.0:
            new_w = int(bgr.shape[1] * upscale_factor)
            new_h = int(bgr.shape[0] * upscale_factor)
            bgr = cv2.resize(bgr, (new_w, new_h), interpolation=cv2.INTER_LANCZOS4)

        if save:
            ext = os.path.splitext(filepath)[1]
            is_success, buffer = cv2.imencode(ext, bgr)
            if is_success:
                buffer.tofile(filepath)

        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        return Image.fromarray(rgb)

    except Exception as e:
        print(f"OpenCV processing failed for {filepath}: {e}")
        return None