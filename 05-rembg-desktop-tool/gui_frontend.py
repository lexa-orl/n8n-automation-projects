import contextlib
import io
import os
import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageTk

import remove_bg_v3


class QueueWriter(io.TextIOBase):
    def __init__(self, output_queue):
        self.output_queue = output_queue

    def write(self, text):
        if text.strip():
            self.output_queue.put(text.rstrip())
        return len(text)

    def flush(self):
        pass


class RembgApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("RemBG Studio")
        self.geometry("1180x760")
        self.minsize(980, 640)
        self.configure(bg="#eef2f6")
        self.output_queue = queue.Queue()
        self.preview_photo = None
        self.processing = False
        self._configure_style()
        self._build_ui()
        self.after(100, self._drain_log)

    def _configure_style(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("App.TFrame", background="#eef2f6")
        style.configure("Card.TFrame", background="#ffffff")
        style.configure("Title.TLabel", background="#ffffff", foreground="#172033", font=("Segoe UI", 22, "bold"))
        style.configure("Subtitle.TLabel", background="#ffffff", foreground="#647084", font=("Segoe UI", 10))
        style.configure("Section.TLabel", background="#ffffff", foreground="#172033", font=("Segoe UI", 11, "bold"))
        style.configure("Field.TLabel", background="#ffffff", foreground="#526074", font=("Segoe UI", 9))
        style.configure("Primary.TButton", background="#2563eb", foreground="#ffffff", padding=(16, 9), font=("Segoe UI", 10, "bold"))
        style.map("Primary.TButton", background=[("active", "#1d4ed8")])
        style.configure("Secondary.TButton", background="#e8eef8", foreground="#1e3a8a", padding=(12, 8), font=("Segoe UI", 9, "bold"))
        style.configure("TEntry", padding=7)
        style.configure("TCombobox", padding=6)

    def _build_ui(self):
        shell = ttk.Frame(self, style="App.TFrame", padding=24)
        shell.pack(fill="both", expand=True)
        header = ttk.Frame(shell, style="Card.TFrame", padding=(28, 22))
        header.pack(fill="x", pady=(0, 18))
        ttk.Label(header, text="RemBG Studio", style="Title.TLabel").pack(anchor="w")
        ttk.Label(header, text="Local batch background removal for product images", style="Subtitle.TLabel").pack(anchor="w", pady=(4, 0))
        body = ttk.Frame(shell, style="App.TFrame")
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=0, minsize=350)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)
        controls = ttk.Frame(body, style="Card.TFrame", padding=22)
        controls.grid(row=0, column=0, sticky="nsew", padx=(0, 16))
        ttk.Label(controls, text="Processing setup", style="Section.TLabel").pack(anchor="w", pady=(0, 16))
        self.input_var = tk.StringVar()
        self.output_var = tk.StringVar()
        self.model_var = tk.StringVar(value="u2net")
        self.max_side_var = tk.StringVar(value="1600")
        self.erode_var = tk.StringVar(value="5")
        self.dilate_var = tk.StringVar(value="5")
        self._path_field(controls, "Input folder", self.input_var, self._choose_input)
        self._path_field(controls, "Output folder (optional)", self.output_var, self._choose_output)
        ttk.Label(controls, text="Model", style="Field.TLabel").pack(anchor="w", pady=(14, 4))
        ttk.Combobox(controls, textvariable=self.model_var, values=("u2net", "isnet-general-use", "u2net_human_seg"), state="readonly").pack(fill="x")
        grid = ttk.Frame(controls, style="Card.TFrame")
        grid.pack(fill="x", pady=(14, 0))
        for column in range(2):
            grid.columnconfigure(column, weight=1)
        self._numeric_field(grid, "Max side", self.max_side_var, 0, 0)
        self._numeric_field(grid, "Erode radius", self.erode_var, 0, 1)
        self._numeric_field(grid, "Dilate radius", self.dilate_var, 1, 0)
        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(controls, textvariable=self.status_var, style="Subtitle.TLabel").pack(anchor="w", pady=(22, 12))
        self.start_button = ttk.Button(controls, text="Start processing", style="Primary.TButton", command=self._start)
        self.start_button.pack(fill="x")
        ttk.Button(controls, text="Open output folder", style="Secondary.TButton", command=self._open_output).pack(fill="x", pady=(10, 0))
        preview = ttk.Frame(body, style="Card.TFrame", padding=22)
        preview.grid(row=0, column=1, sticky="nsew")
        preview.rowconfigure(1, weight=1)
        preview.columnconfigure(0, weight=1)
        ttk.Label(preview, text="Preview and activity", style="Section.TLabel").grid(row=0, column=0, sticky="w")
        self.preview = tk.Label(preview, text="Processed image preview\nwill appear here", bg="#f5f7fb", fg="#8290a5", font=("Segoe UI", 12), compound="center")
        self.preview.grid(row=1, column=0, sticky="nsew", pady=(14, 14))
        self.log = tk.Text(preview, height=8, bg="#111827", fg="#dbeafe", insertbackground="#ffffff", relief="flat", padx=12, pady=10, font=("Consolas", 9), state="disabled")
        self.log.grid(row=2, column=0, sticky="ew")

    def _path_field(self, parent, label, variable, command):
        ttk.Label(parent, text=label, style="Field.TLabel").pack(anchor="w", pady=(0, 4))
        row = ttk.Frame(parent, style="Card.TFrame")
        row.pack(fill="x")
        row.columnconfigure(0, weight=1)
        ttk.Entry(row, textvariable=variable).grid(row=0, column=0, sticky="ew")
        ttk.Button(row, text="Browse", style="Secondary.TButton", command=command).grid(row=0, column=1, padx=(8, 0))

    def _numeric_field(self, parent, label, variable, row, column):
        cell = ttk.Frame(parent, style="Card.TFrame")
        cell.grid(row=row, column=column, sticky="ew", padx=(0 if column == 0 else 8, 8 if column == 0 else 0), pady=(0, 10))
        ttk.Label(cell, text=label, style="Field.TLabel").pack(anchor="w", pady=(0, 4))
        ttk.Entry(cell, textvariable=variable).pack(fill="x")

    def _choose_input(self):
        selected = filedialog.askdirectory(title="Select input folder")
        if selected:
            self.input_var.set(selected)
            if not self.output_var.get():
                self.output_var.set(str(Path(selected).parent / f"{Path(selected).name}_v3_ready"))

    def _choose_output(self):
        selected = filedialog.askdirectory(title="Select output folder")
        if selected:
            self.output_var.set(selected)

    def _write_log(self, message):
        self.log.configure(state="normal")
        self.log.insert("end", message + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _drain_log(self):
        while not self.output_queue.empty():
            self._write_log(self.output_queue.get())
        self.after(100, self._drain_log)

    def _start(self):
        if self.processing:
            return
        input_path = Path(self.input_var.get().strip())
        if not input_path.is_dir():
            messagebox.showwarning("Input folder required", "Select a folder containing images first.")
            return
        try:
            max_side = int(self.max_side_var.get())
            erode = int(self.erode_var.get())
            dilate = int(self.dilate_var.get())
        except ValueError:
            messagebox.showwarning("Invalid settings", "Size and radius values must be integers.")
            return
        self.processing = True
        self.start_button.configure(state="disabled")
        self.status_var.set("Processing...")
        self._write_log("Starting background removal...")

        def worker():
            try:
                os.environ["REMBG_MODEL"] = self.model_var.get()
                kwargs = {"out_suffix": "_v3_ready", "erode": erode, "dilate": dilate, "max_side": max_side}
                with contextlib.redirect_stdout(QueueWriter(self.output_queue)):
                    remove_bg_v3.process_folder(input_path.resolve(), **kwargs)
                self.output_queue.put("Completed successfully.")
            except Exception as error:
                self.output_queue.put(f"Error: {error}")
            finally:
                self.after(0, self._finish)

        threading.Thread(target=worker, daemon=True).start()

    def _finish(self):
        self.processing = False
        self.start_button.configure(state="normal")
        self.status_var.set("Ready")
        self._load_preview()

    def _load_preview(self):
        output = Path(self.output_var.get().strip()) if self.output_var.get().strip() else None
        if not output or not output.is_dir():
            return
        images = list(output.rglob("*.png"))
        if not images:
            return
        try:
            image = Image.open(images[0]).convert("RGBA")
            image.thumbnail((720, 470), Image.LANCZOS)
            self.preview_photo = ImageTk.PhotoImage(image)
            self.preview.configure(image=self.preview_photo, text="", bg="#f5f7fb")
        except Exception:
            pass

    def _open_output(self):
        output = self.output_var.get().strip()
        if output and Path(output).exists():
            os.startfile(output)
        else:
            messagebox.showinfo("Output folder", "Run processing first or choose an output folder.")


if __name__ == "__main__":
    RembgApp().mainloop()
