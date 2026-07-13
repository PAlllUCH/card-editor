import tkinter as tk
from gui.app_window import MainAppWindow

if __name__ == "__main__":
    root = tk.Tk()
    app = MainAppWindow(root)
    root.mainloop()