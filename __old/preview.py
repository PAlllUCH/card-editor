import tkinter as tk
from PIL import Image, ImageTk

class ImagePreviewWindow(tk.Toplevel):
    def __init__(self, master):
        super().__init__(master)
        self.title("Last Downloaded Image")
        self.geometry("400x550")
        
        self.protocol("WM_DELETE_WINDOW", self.hide_window)
        
        self.label = tk.Label(self, text="Waiting for downloads...", bg="#2d2d2d", fg="white")
        self.label.pack(expand=True, fill=tk.BOTH)
        
        self.configure(bg="#2d2d2d")
        self.withdraw() 
        
    def hide_window(self):
        self.withdraw()
        
    def show_window(self):
        self.deiconify()

    def update_image(self, filepath):
        try:
            if not self.winfo_viewable():
                self.show_window()
                
            img = Image.open(filepath)
            img.thumbnail((380, 500), Image.Resampling.LANCZOS)
            
            self.photo = ImageTk.PhotoImage(img)
            self.label.config(image=self.photo, text="")
        except Exception as e:
            self.label.config(image='', text=f"Could not preview image:\n{e}")