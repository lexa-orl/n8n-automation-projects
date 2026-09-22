"""
Simple Tkinter GUI annotator:
- Choose input folder
- Browse images (list on left)
- Display original / result / alpha
- Simple brush to mark FG/BG scribbles and save to annotations folder
- Reprocess current image (regenerate trimap using scribbles + mask)

This is intentionally minimal and focuses on annotating problem images and reprocessing a single file.
"""

import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk, ImageDraw
from pathlib import Path
import os
import subprocess
import threading
import sys


class Annotator(tk.Frame):
    def __init__(self, master):
        super().__init__(master)
        self.master = master
        self.pack(fill='both', expand=True)
        self.input_folder = None
        self.files = []
        self.current_index = 0
        self.mode = 'fg'  # 'fg' or 'bg'

        self.create_ui()

    def create_ui(self):
        top = tk.Frame(self)
        top.pack(side='top', fill='x')

        tk.Button(top, text='Select Folder', command=self.select_folder).pack(side='left')
        tk.Button(top, text='Reprocess Current', command=self.reprocess_current).pack(side='left')
        tk.Button(top, text='Open Output Folder', command=self.open_output).pack(side='left')

        self.mode_btn = tk.Button(top, text='Mode: FG', command=self.toggle_mode)
        self.mode_btn.pack(side='left')

        left = tk.Frame(self)
        left.pack(side='left', fill='y')
        self.listbox = tk.Listbox(left, width=40)
        self.listbox.pack(fill='y', expand=True)
        self.listbox.bind('<<ListboxSelect>>', self.on_select)

        right = tk.Frame(self)
        right.pack(side='left', fill='both', expand=True)
        self.canvas = tk.Canvas(right, bg='black')
        self.canvas.pack(fill='both', expand=True)

        self.canvas.bind('<B1-Motion>', self.on_paint)
        self.canvas.bind('<ButtonRelease-1>', self.on_release)

        self.brush_size = 15
        self.scribble = None

    def select_folder(self):
        path = filedialog.askdirectory()
        if not path:
            return
        self.input_folder = Path(path)
        self.files = [p for p in self.input_folder.rglob('*') if p.suffix.lower() in ('.jpg', '.jpeg', '.png')]
        self.files.sort()
        self.listbox.delete(0, 'end')
        for f in self.files:
            self.listbox.insert('end', str(f.relative_to(self.input_folder)))
        if self.files:
            self.listbox.selection_set(0)
            self.load_image(0)

    def on_select(self, evt):
        sel = self.listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        self.load_image(idx)

    def load_image(self, idx):
        self.current_index = idx
        path = self.files[idx]
        self.original = Image.open(path).convert('RGBA')
        self.display_image(self.original)
        # ensure annotations folder exists
        ann_dir = self.input_folder.parent / (self.input_folder.name + '_annotations') / path.relative_to(self.input_folder).parent
        ann_dir.mkdir(parents=True, exist_ok=True)
        self.mask_fg_path = ann_dir / (path.stem + '_fg.png')
        self.mask_bg_path = ann_dir / (path.stem + '_bg.png')
        # load or create scribble image
        if self.mask_fg_path.exists():
            self.scribble_fg = Image.open(self.mask_fg_path).convert('L')
        else:
            self.scribble_fg = Image.new('L', self.original.size, 0)
        if self.mask_bg_path.exists():
            self.scribble_bg = Image.open(self.mask_bg_path).convert('L')
        else:
            self.scribble_bg = Image.new('L', self.original.size, 0)

        self.scribble = Image.new('RGBA', self.original.size, (0,0,0,0))

    def display_image(self, pil_img):
        self.tkimg = ImageTk.PhotoImage(pil_img.resize((800, 800), Image.LANCZOS))
        self.canvas.delete('all')
        self.canvas.create_image(0, 0, anchor='nw', image=self.tkimg)
        self.canvas.config(scrollregion=self.canvas.bbox('all'))

    def toggle_mode(self):
        self.mode = 'bg' if self.mode == 'fg' else 'fg'
        self.mode_btn.config(text=f"Mode: {'FG' if self.mode=='fg' else 'BG'}")

    def on_paint(self, event):
        if not hasattr(self, 'original'):
            return
        # map canvas coords to image coords (assumes 800x800 display)
        x = int(event.x * self.original.width / 800)
        y = int(event.y * self.original.height / 800)
        draw = ImageDraw.Draw(self.scribble)
        color = (255,0,0,128) if self.mode == 'fg' else (0,0,255,128)
        draw.ellipse((x-self.brush_size, y-self.brush_size, x+self.brush_size, y+self.brush_size), fill=color)
        # update scribble mask
        mask_draw = ImageDraw.Draw(self.scribble_fg if self.mode=='fg' else self.scribble_bg)
        mask_draw.ellipse((x-self.brush_size, y-self.brush_size, x+self.brush_size, y+self.brush_size), fill=255)
        # update display overlay
        overlay = Image.alpha_composite(self.original, self.scribble)
        self.display_image(overlay)

    def on_release(self, event):
        # save masks
        path = self.files[self.current_index]
        self.mask_fg_path.parent.mkdir(parents=True, exist_ok=True)
        self.scribble_fg.save(self.mask_fg_path)
        self.scribble_bg.save(self.mask_bg_path)

    def reprocess_current(self):
        # call remove_bg_v3.py for single file (creates/updates trimap)
        path = self.files[self.current_index]
        cmd = [sys.executable, str(Path(__file__).parent / 'remove_bg_v3.py'), '--input', str(path.parent), '--erode', '5', '--dilate', '5']
        def run():
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            out, err = proc.communicate()
            if proc.returncode != 0:
                messagebox.showerror('Error', err)
            else:
                messagebox.showinfo('Done', 'Reprocessed current folder. Trimap and results updated.')
        threading.Thread(target=run).start()

    def open_output(self):
        if not self.input_folder:
            return
        out = self.input_folder.parent / (self.input_folder.name + '_v3_ready')
        if out.exists():
            os.startfile(out)
        else:
            messagebox.showinfo('Info', 'Output folder not found yet')


def main():
    root = tk.Tk()
    root.title('RemBG Annotator')
    app = Annotator(root)
    root.geometry('1200x900')
    root.mainloop()


if __name__ == '__main__':
    main()
