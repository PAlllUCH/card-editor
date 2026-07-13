import tkinter as tk
from PIL import Image, ImageTk

class ImagePreviewComponent(tk.Canvas):
    """A reusable UI component that handles scaling, displaying, zooming,
    and panning PIL Images safely using a tkinter Canvas.
    """
    def __init__(self, parent, theme_manager=None, **kwargs):
        # Pop standard label options that canvas doesn't support directly
        self._theme_manager = theme_manager
        if theme_manager:
            bg = kwargs.pop('bg', theme_manager.c("preview_bg"))
            fg = kwargs.pop('fg', theme_manager.c("preview_fg"))
        else:
            bg = kwargs.pop('bg', "#2d2d2d")
            fg = kwargs.pop('fg', "white")
        text = kwargs.pop('text', "Select an image to preview")
        highlightthickness = kwargs.pop('highlightthickness', 0)
        
        super().__init__(parent, bg=bg, highlightthickness=highlightthickness, **kwargs)
        
        self.fg_color = fg
        self.text_content = text
        self.orig_image = None
        self.preview_image_tk = None
        
        self.zoom_factor = 1.0
        self.pan_x = 0
        self.pan_y = 0
        
        # Register for theme updates if theme_manager provided
        if theme_manager:
            theme_manager.register(self._on_theme_change)
        
        # Interactive bindings
        self.bind("<ButtonPress-1>", self.on_pan_start)
        self.bind("<B1-Motion>", self.on_pan_drag)
        self.bind("<MouseWheel>", self.on_zoom)
        self.bind("<Button-4>", self.on_zoom)    # Linux zoom in
        self.bind("<Button-5>", self.on_zoom)    # Linux zoom out
        self.bind("<Double-Button-1>", self.reset_zoom_pan)
        self.bind("<Configure>", self.on_resize)
        
        self.draw_elements()

    def set_theme_manager(self, theme_manager):
        self._theme_manager = theme_manager
        if theme_manager:
            theme_manager.register(self._on_theme_change)
            self._on_theme_change(theme_manager)

    def _on_theme_change(self, tm):
        self.configure(bg=tm.c("preview_bg"))
        self.fg_color = tm.c("preview_fg")
        self.draw_elements()

    def config(self, cnf=None, **kw):
        return self.configure(cnf, **kw)

    def configure(self, cnf=None, **kw):
        # Handle backward compatibility for tk.Label config options
        text = kw.pop('text', None)
        image = kw.pop('image', None)
        
        if text is not None:
            self.text_content = text
            if text:
                self.orig_image = None
            self.draw_elements()
            
        if image == '':
            self.orig_image = None
            self.draw_elements()
            
        if kw:
            super().configure(cnf, **kw)

    def display_image(self, pil_image):
        if not pil_image:
            self.configure(image='', text="Error processing image")
            return
            
        self.orig_image = pil_image
        self.text_content = ""
        self.zoom_factor = 1.0
        self.pan_x = 0
        self.pan_y = 0
        self.draw_elements()

    def draw_elements(self):
        self.delete("all")
        
        canvas_width = self.winfo_width()
        canvas_height = self.winfo_height()
        if canvas_width <= 1: canvas_width = 600
        if canvas_height <= 1: canvas_height = 700
        
        if self.orig_image:
            img_w, img_h = self.orig_image.size
            
            # Compute fitting scale factor
            scale_fit = min(canvas_width / img_w, canvas_height / img_h)
            scale = scale_fit * self.zoom_factor
            
            w = int(img_w * scale)
            h = int(img_h * scale)
            
            if w < 1: w = 1
            if h < 1: h = 1
            
            try:
                # Resize the image and create PhotoImage
                resized_img = self.orig_image.resize((w, h), Image.Resampling.LANCZOS)
                self.preview_image_tk = ImageTk.PhotoImage(resized_img)
                
                # Draw centered with current pan offsets
                cx = canvas_width / 2 + self.pan_x
                cy = canvas_height / 2 + self.pan_y
                self.create_image(cx, cy, anchor=tk.CENTER, image=self.preview_image_tk)
            except Exception as e:
                self.create_text(
                    canvas_width / 2, canvas_height / 2,
                    text=f"Error rendering image: {e}",
                    fill=self.fg_color, justify=tk.CENTER,
                    font=("Segoe UI", 10)
                )
        else:
            # Draw helper/error text
            self.create_text(
                canvas_width / 2, canvas_height / 2,
                text=self.text_content,
                fill=self.fg_color, justify=tk.CENTER,
                font=("Segoe UI", 10)
            )

    def on_pan_start(self, event):
        self._pan_start_x = event.x
        self._pan_start_y = event.y
        self._orig_pan_x = self.pan_x
        self._orig_pan_y = self.pan_y

    def on_pan_drag(self, event):
        if not self.orig_image:
            return
        dx = event.x - self._pan_start_x
        dy = event.y - self._pan_start_y
        self.pan_x = self._orig_pan_x + dx
        self.pan_y = self._orig_pan_y + dy
        self.draw_elements()

    def on_zoom(self, event):
        if not self.orig_image:
            return
            
        if event.num == 4 or event.delta > 0:
            factor = 1.15
        elif event.num == 5 or event.delta < 0:
            factor = 0.85
        else:
            return
            
        new_zoom = self.zoom_factor * factor
        if 0.1 <= new_zoom <= 20.0:
            self.zoom_factor = new_zoom
            
            canvas_width = self.winfo_width()
            canvas_height = self.winfo_height()
            if canvas_width <= 1: canvas_width = 600
            if canvas_height <= 1: canvas_height = 700
            
            # Zoom to cursor coordinates logic
            cx = canvas_width / 2 + self.pan_x
            cy = canvas_height / 2 + self.pan_y
            
            dx = event.x - cx
            dy = event.y - cy
            
            self.pan_x -= dx * (factor - 1)
            self.pan_y -= dy * (factor - 1)
            
            self.draw_elements()

    def reset_zoom_pan(self, event=None):
        self.zoom_factor = 1.0
        self.pan_x = 0
        self.pan_y = 0
        self.draw_elements()

    def on_resize(self, event):
        self.draw_elements()