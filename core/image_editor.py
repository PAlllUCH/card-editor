import os
import cv2
import numpy as np
from PIL import Image

def process_image_advanced(
    filepath, 
    # 1. Base Sizing
    do_resize_mm=True, target_w_mm=63.0, target_h_mm=88.0, dpi=300,
    # 2. Corner Fill
    do_corner_fill=True, fill_mode='Dual-Axis Mirror', corner_size=10, inpaint_radius=15,
    # 3. Color Grading
    do_color=True, saturation=100, contrast=100, brightness=0, sepia=0,
    # 4. Spad (Bleed)
    do_spad=True, spad_t=2.0, spad_b=2.0, spad_l=2.0, spad_r=2.0,
    # 5. Gradient Blending
    do_blend=True, blend_stage='Before Bleed', blend_type='Shadow (Vignette)', 
    corner_fade=15, margin_fade=0, blend_strength=100, noise_amount=0,
    # 6. Legacy
    upscale_factor=1.0, save=False
):
    try:
        file_bytes = np.fromfile(filepath, dtype=np.uint8)
        img = cv2.imdecode(file_bytes, cv2.IMREAD_UNCHANGED)
        
        if img is None: 
            print(f"Failed to decode image data for: {filepath}")
            return None

        if len(img.shape) == 3 and img.shape[2] == 4:
            bgr = img[:, :, :3]
        else:
            bgr = img.copy()

# --- Helper Function: Precise Quadratic Gradient Blending (Percentage-Based) ---
        def apply_gradient_blend(image_bgr):
            curr_h, curr_w = image_bgr.shape[:2]
            # Reference dimension for percentage calculations (shortest side)
            ref_dim = min(curr_h, curr_w)
            
            # Convert % input to actual pixel distance
            c_fade_px = (float(corner_fade) / 100.0) * ref_dim
            m_fade_px = (float(margin_fade) / 100.0) * ref_dim
            strength_multiplier = float(blend_strength) / 100.0
            
            if c_fade_px <= 0 and m_fade_px <= 0: return image_bgr
            
            # 1. PERIMETER MASK
            mask_binary = np.zeros((curr_h, curr_w), dtype=np.uint8)
            mask_binary[0, :] = 255
            mask_binary[curr_h-1, :] = 255
            mask_binary[:, 0] = 255
            mask_binary[:, curr_w-1] = 255
            
            # 2. DISTANCE TRANSFORM
            dist = cv2.distanceTransform(cv2.bitwise_not(mask_binary), cv2.DIST_L2, 5)
            
            # 3. QUADRATIC GRADIENT MASK
            power = 2.0 
            final_mask = np.zeros((curr_h, curr_w), dtype=np.float32)
            
            # Apply Margin Fade
            if m_fade_px > 0:
                ratio = np.clip(dist / (m_fade_px + 0.0001), 0, 1.0)
                final_mask = np.maximum(final_mask, 1.0 - (ratio ** power))
            
            # Apply Corner Fade
            if c_fade_px > 0:
                curr_cr = max(1, int(min(curr_w, curr_h) * (corner_size / 100.0)))
                corner_zones = np.zeros((curr_h, curr_w), dtype=np.float32)
                corner_zones[0:curr_cr, 0:curr_cr] = 1.0
                corner_zones[0:curr_cr, curr_w-curr_cr:curr_w] = 1.0
                corner_zones[curr_h-curr_cr:curr_h, 0:curr_cr] = 1.0
                corner_zones[curr_h-curr_cr:curr_h, curr_w-curr_cr:curr_w] = 1.0
                
                ratio = np.clip(dist / (c_fade_px + 0.0001), 0, 1.0)
                final_mask = np.maximum(final_mask, (1.0 - (ratio ** power)) * corner_zones)
                
            final_mask = np.clip(final_mask * strength_multiplier, 0, 1.0)
            final_mask_3d = np.expand_dims(final_mask, axis=-1)

            # 4. EXECUTION
            if blend_type == 'Blur (Soft)':
                target_img = cv2.GaussianBlur(image_bgr, (21, 21), 0)
            else: 
                target_img = np.zeros_like(image_bgr) # Shadow

            blended = (image_bgr.astype(np.float32) * (1.0 - final_mask_3d) + 
                       target_img.astype(np.float32) * final_mask_3d).astype(np.uint8)

            if int(noise_amount) > 0:
                noise = np.random.normal(0, int(noise_amount), blended.shape).astype(np.float32)
                blended = np.clip(blended.astype(np.float32) + (noise * final_mask_3d), 0, 255).astype(np.uint8)

            return blended

        # ==========================================
        # STEP 1: BASE CARD RESIZING (MM -> PX)
        # ==========================================
        if do_resize_mm and target_w_mm > 0 and target_h_mm > 0 and dpi > 0:
            target_w_px = int((float(target_w_mm) / 25.4) * float(dpi))
            target_h_px = int((float(target_h_mm) / 25.4) * float(dpi))
            bgr = cv2.resize(bgr, (target_w_px, target_h_px), interpolation=cv2.INTER_LANCZOS4)

        # ==========================================
        # STEP 2: CORNER INPAINTING
        # ==========================================
        if do_corner_fill:
            h, w = bgr.shape[:2]
            cr = max(1, int(min(w, h) * (corner_size / 100.0)))
            mask = np.zeros((h, w), dtype=np.uint8)

            corners = [
                (0, 0, cr, cr, 1, 1),               
                (w-cr, 0, w, cr, -1, 1),            
                (0, h-cr, cr, h, 1, -1),            
                (w-cr, h-cr, w, h, -1, -1)          
            ]
            
            for (x1, y1, x2, y2, dx, dy) in corners:
                corner_roi = bgr[y1:y2, x1:x2]
                white_mask = cv2.inRange(corner_roi, (200, 200, 200), (255, 255, 255))
                mask[y1:y2, x1:x2] = white_mask

            if fill_mode == 'Telea Inpaint (Soft)':
                bgr = cv2.inpaint(bgr, mask, inpaintRadius=int(inpaint_radius), flags=cv2.INPAINT_TELEA)

            elif fill_mode == 'Navier-Stokes (Sharp)':
                bgr = cv2.inpaint(bgr, mask, inpaintRadius=int(inpaint_radius), flags=cv2.INPAINT_NS)

            elif fill_mode == 'Pixel Stretch' or fill_mode == 'Smooth Pixel Stretch':
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
                    
                    if fill_mode == 'Smooth Pixel Stretch':
                        blurred_roi = cv2.GaussianBlur(roi, (15, 15), 0)
                        wm_3d = wm[:, :, np.newaxis] > 0
                        bgr[y1:y2, x1:x2] = np.where(wm_3d, blurred_roi, roi)
                    else:
                        bgr[y1:y2, x1:x2] = roi

            elif fill_mode == 'Edge Mirror':
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
                        
            elif fill_mode == 'Dual-Axis Mirror':
                for (x1, y1, x2, y2, dx, dy) in corners:
                    wm = mask[y1:y2, x1:x2, np.newaxis] > 0
                    if not np.any(wm): continue
                    try:
                        h_src = bgr[y1:y2, x2:x2+cr] if dx == 1 else bgr[y1:y2, x1-cr:x1]
                        v_src = bgr[y2:y2+cr, x1:x2] if dy == 1 else bgr[y1-cr:y1, x1:x2]
                        h_flip = cv2.flip(h_src, 1)
                        v_flip = cv2.flip(v_src, 0)
                        avg = cv2.addWeighted(h_flip, 0.5, v_flip, 0.5, 0)
                        bgr[y1:y2, x1:x2] = np.where(wm, avg, bgr[y1:y2, x1:x2])
                    except cv2.error:
                        pass 

        # ==========================================
        # STEP 3: BLEND (Stage: Before Color)
        # ==========================================
        if do_blend and blend_stage == 'Before Color':
            bgr = apply_gradient_blend(bgr)

        # ==========================================
        # STEP 4: COLOR GRADING
        # ==========================================
        if do_color:
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
        # STEP 5: BLEND (Stage: Before Bleed)
        # ==========================================
        if do_blend and blend_stage == 'Before Bleed':
            bgr = apply_gradient_blend(bgr)

        # ==========================================
        # STEP 6: NATIVE SPAD (DIRECTIONAL BLEED)
        # ==========================================
        if do_spad and dpi > 0:
            top_px = int((float(spad_t) / 25.4) * float(dpi))
            bottom_px = int((float(spad_b) / 25.4) * float(dpi))
            left_px = int((float(spad_l) / 25.4) * float(dpi))
            right_px = int((float(spad_r) / 25.4) * float(dpi))
            bgr = cv2.copyMakeBorder(bgr, top_px, bottom_px, left_px, right_px, cv2.BORDER_REFLECT_101)

        # ==========================================
        # STEP 7: BLEND (Stage: After Bleed)
        # ==========================================
        if do_blend and blend_stage == 'After Bleed':
            bgr = apply_gradient_blend(bgr)

        # ==========================================
        # STEP 8: LEGACY SCALING (Fallback)
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