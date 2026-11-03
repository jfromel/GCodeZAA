#!/usr/bin/env python3
"""
GCodeZAA UI — Night mode Mac app.
Run with: /opt/homebrew/bin/python3.11 ~/Desktop/GCodeZAA/zaa_app.py
"""

import tkinter as tk
from tkinter import filedialog, scrolledtext
import subprocess
import threading
import os

PYTHON = "/Users/johnfromel/Library/Caches/pypoetry/virtualenvs/gcodezaa-urSMRtnC-py3.11/bin/python"
SCRIPT_DIR = "/Users/johnfromel/Desktop/GCodeZAA"
DEFAULT_MODELS = "/Users/johnfromel/Desktop/modelsSTL"

# Night mode palette
BG          = "#0D1B2A"   # deep navy background
BG2         = "#112236"   # slightly lighter surface
BG3         = "#1A3050"   # input/card background
BORDER      = "#2A4A6A"   # subtle border
ACCENT      = "#4A9EFF"   # electric blue accent
ACCENT_DIM  = "#2A6ECC"   # darker accent for hover
TEXT        = "#E8F0FF"   # primary text
TEXT_DIM    = "#7A9CC0"   # muted text
TEXT_HINT   = "#4A6A8A"   # placeholder/hint
SUCCESS     = "#3DCFAA"   # green for done
ERROR       = "#FF6B6B"   # red for errors
FONT        = "Helvetica"


class CanvasButton(tk.Canvas):
    """A properly colored button that macOS can't override."""
    def __init__(self, parent, text, command, bg_color, fg_color, hover_color,
                 height=44, font_size=13, **kwargs):
        super().__init__(parent, height=height, highlightthickness=0,
                         bg=BG, **kwargs)
        self.command = command
        self.bg_color = bg_color
        self.fg_color = fg_color
        self.hover_color = hover_color
        self.text = text
        self.font_size = font_size
        self.height = height
        self._hovered = False
        self._disabled = False

        self.bind("<Configure>", self._draw)
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Button-1>", self._on_click)

    def _draw(self, event=None):
        self.delete("all")
        w = self.winfo_width()
        h = self.height
        color = self.hover_color if self._hovered and not self._disabled else self.bg_color
        if self._disabled:
            color = BG3
        self.create_rectangle(0, 0, w, h, fill=color, outline=BORDER, width=1)
        fg = TEXT_DIM if self._disabled else self.fg_color
        self.create_text(w // 2, h // 2, text=self.text,
                         fill=fg, font=(FONT, self.font_size, "bold"))

    def _on_enter(self, e):
        self._hovered = True
        self._draw()

    def _on_leave(self, e):
        self._hovered = False
        self._draw()

    def _on_click(self, e):
        if not self._disabled:
            self.command()

    def set_text(self, text):
        self.text = text
        self._draw()

    def set_disabled(self, val):
        self._disabled = val
        self._draw()

    def set_colors(self, bg, hover):
        self.bg_color = bg
        self.hover_color = hover
        self._draw()


class ZAAApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("GCodeZAA")
        self.geometry("640x820")
        self.resizable(True, True)
        self.configure(bg=BG)

        self.gcode_path = tk.StringVar()
        self.models_path = tk.StringVar(value=DEFAULT_MODELS)
        self.output_path = tk.StringVar()
        self.resolution = tk.DoubleVar(value=0.1)
        self.outer_walls = tk.BooleanVar(value=True)
        self.inner_walls = tk.BooleanVar(value=True)
        self.top_surface = tk.BooleanVar(value=True)
        self.ironing = tk.BooleanVar(value=False)
        self.obj_name = tk.StringVar()
        self.pos_x = tk.StringVar()
        self.pos_y = tk.StringVar()

        self._build_ui()

    def _build_ui(self):
        # Header
        hdr = tk.Frame(self, bg=BG2, height=56)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        tk.Label(hdr, text="GCODE", font=(FONT, 15, "bold"),
                 bg=BG2, fg=ACCENT).pack(side="left", padx=(20, 0), pady=14)
        tk.Label(hdr, text="ZAA", font=(FONT, 15, "bold"),
                 bg=BG2, fg=TEXT).pack(side="left", pady=14)
        tk.Label(hdr, text="  //  Z Anti-Aliasing Post-Processor",
                 font=(FONT, 11), bg=BG2, fg=TEXT_DIM).pack(side="left", pady=14)

        # Divider
        tk.Frame(self, bg=BORDER, height=1).pack(fill="x")

        # Scrollable area
        canvas = tk.Canvas(self, bg=BG, highlightthickness=0)
        scrollbar = tk.Scrollbar(self, orient="vertical", command=canvas.yview,
                                  bg=BG, troughcolor=BG2)
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        main = tk.Frame(canvas, bg=BG)
        cw = canvas.create_window((0, 0), window=main, anchor="nw")

        main.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(cw, width=e.width))

        # mousewheel scroll
        canvas.bind_all("<MouseWheel>", lambda e: canvas.yview_scroll(-1 * (e.delta // 120), "units"))

        # --- FILES ---
        self._section(main, "Files")
        self._file_row(main, "GCode file", self.gcode_path, self._pick_gcode)
        self._file_row(main, "Models folder", self.models_path, self._pick_models, is_dir=True)
        self._file_row(main, "Output file  (blank = overwrite input)", self.output_path, self._pick_output, save=True)

        # --- Z CONTOURING ---
        self._section(main, "Z Contouring")

        self._label(main, "Resolution (mm)  —  lower = smoother, slower")
        rf = tk.Frame(main, bg=BG)
        rf.pack(fill="x", padx=20, pady=(0, 12))
        self.res_label = tk.Label(rf, text="0.10", font=(FONT, 13, "bold"),
                                   bg=BG, fg=ACCENT, width=5, anchor="e")
        self.res_label.pack(side="right")
        tk.Label(rf, text="mm", font=(FONT, 11),
                 bg=BG, fg=TEXT_DIM).pack(side="right", padx=(0, 4))
        tk.Scale(rf, from_=0.05, to=1.0, resolution=0.05, orient="horizontal",
                 variable=self.resolution, bg=BG, fg=TEXT, highlightthickness=0,
                 troughcolor=BG3, activebackground=ACCENT, sliderrelief="flat",
                 showvalue=False, command=self._update_res_label,
                 bd=0).pack(side="left", fill="x", expand=True)

        toggles = [
            ("Contour outer walls", self.outer_walls),
            ("Contour inner walls", self.inner_walls),
            ("Contour top surface", self.top_surface),
            ("Contour ironing lines", self.ironing),
        ]
        for label, var in toggles:
            tk.Checkbutton(main, text=label, variable=var,
                           font=(FONT, 12), bg=BG, fg=TEXT,
                           selectcolor=BG3, activebackground=BG,
                           activeforeground=ACCENT,
                           cursor="hand2", anchor="w").pack(fill="x", padx=20, pady=3)

        # --- OBJECT PLACEMENT ---
        self._section(main, "Object placement  (optional — OrcaSlicer auto-detects)")

        opf = tk.Frame(main, bg=BG)
        opf.pack(fill="x", padx=20, pady=(0, 8))
        tk.Label(opf, text="Object name:", font=(FONT, 12),
                 bg=BG, fg=TEXT_DIM).pack(side="left", padx=(0, 10))
        tk.Entry(opf, textvariable=self.obj_name, width=28,
                 font=(FONT, 12), relief="flat", bg=BG3, fg=TEXT,
                 insertbackground=ACCENT,
                 highlightthickness=1, highlightbackground=BORDER,
                 highlightcolor=ACCENT).pack(side="left", ipady=6, ipadx=6)

        ppf = tk.Frame(main, bg=BG)
        ppf.pack(fill="x", padx=20, pady=(0, 16))
        tk.Label(ppf, text="Position X:", font=(FONT, 12),
                 bg=BG, fg=TEXT_DIM).pack(side="left", padx=(0, 6))
        tk.Entry(ppf, textvariable=self.pos_x, width=8,
                 font=(FONT, 12), relief="flat", bg=BG3, fg=TEXT,
                 insertbackground=ACCENT,
                 highlightthickness=1, highlightbackground=BORDER,
                 highlightcolor=ACCENT).pack(side="left", ipady=6, ipadx=6, padx=(0, 14))
        tk.Label(ppf, text="Y:", font=(FONT, 12),
                 bg=BG, fg=TEXT_DIM).pack(side="left", padx=(0, 6))
        tk.Entry(ppf, textvariable=self.pos_y, width=8,
                 font=(FONT, 12), relief="flat", bg=BG3, fg=TEXT,
                 insertbackground=ACCENT,
                 highlightthickness=1, highlightbackground=BORDER,
                 highlightcolor=ACCENT).pack(side="left", ipady=6, ipadx=6)

        # Run button
        self.run_btn = CanvasButton(
            main, text="RUN ZAA", command=self._run,
            bg_color=ACCENT, fg_color="#FFFFFF",
            hover_color=ACCENT_DIM, height=50, font_size=14
        )
        self.run_btn.pack(fill="x", padx=20, pady=(4, 8))

        # Log
        self._section(main, "Log")
        self.log = scrolledtext.ScrolledText(
            main, height=10, font=(FONT, 11),
            bg=BG2, fg=TEXT, insertbackground=ACCENT,
            relief="flat", highlightthickness=1,
            highlightbackground=BORDER, state="disabled"
        )
        self.log.pack(fill="x", padx=20, pady=(0, 20))

    def _section(self, parent, title):
        f = tk.Frame(parent, bg=BG)
        f.pack(fill="x", padx=20, pady=(16, 8))
        tk.Label(f, text=title.upper(), font=(FONT, 9, "bold"),
                 fg=ACCENT, bg=BG).pack(side="left")
        tk.Frame(f, height=1, bg=BORDER).pack(side="left", fill="x",
                                               expand=True, padx=10, pady=6)

    def _label(self, parent, text):
        tk.Label(parent, text=text, font=(FONT, 12),
                 fg=TEXT_DIM, bg=BG).pack(anchor="w", padx=20, pady=(0, 4))

    def _file_row(self, parent, label, var, command, is_dir=False, save=False):
        self._label(parent, label)
        f = tk.Frame(parent, bg=BG)
        f.pack(fill="x", padx=20, pady=(0, 10))
        tk.Entry(f, textvariable=var, font=(FONT, 12), relief="flat",
                 bg=BG3, fg=TEXT, insertbackground=ACCENT,
                 highlightthickness=1, highlightbackground=BORDER,
                 highlightcolor=ACCENT).pack(side="left", fill="x", expand=True,
                                              ipady=6, ipadx=8, padx=(0, 8))
        btn = CanvasButton(f, text="Browse", command=command,
                           bg_color=BG3, fg_color=TEXT_DIM,
                           hover_color=BORDER, height=34, font_size=11)
        btn.pack(side="left", ipadx=10)
        btn.config(width=72)

    def _update_res_label(self, val):
        self.res_label.config(text=f"{float(val):.2f}")

    def _pick_gcode(self):
        initialdir = os.path.expanduser("~/Desktop/modelsGcode")
        if not os.path.exists(initialdir):
            initialdir = os.path.expanduser("~/Desktop")
        path = filedialog.askopenfilename(
            title="Select GCode file",
            filetypes=[("GCode files", "*.gcode"), ("All files", "*.*")],
            initialdir=initialdir
        )
        if path:
            self.gcode_path.set(path)
            self._log(f"GCode: {path}")

    def _pick_models(self):
        path = filedialog.askdirectory(
            title="Select models folder",
            initialdir=os.path.expanduser("~/Desktop")
        )
        if path:
            self.models_path.set(path)
            self._log(f"Models: {path}")

    def _pick_output(self):
        initial = self.gcode_path.get()
        initialdir = os.path.dirname(initial) if initial else os.path.expanduser("~/Desktop")
        if not os.path.exists(initialdir):
            initialdir = os.path.expanduser("~/Desktop")
        initialfile = ""
        if initial:
            name, ext = os.path.splitext(os.path.basename(initial))
            initialfile = f"{name}_ZAA{ext}"
        path = filedialog.asksaveasfilename(
            title="Save output GCode as",
            filetypes=[("GCode files", "*.gcode"), ("All files", "*.*")],
            initialdir=initialdir,
            initialfile=initialfile,
            defaultextension=".gcode"
        )
        if path:
            self.output_path.set(path)
            self._log(f"Output: {path}")

    def _log(self, text, color=None):
        self.log.config(state="normal")
        if color:
            tag = f"color_{color}"
            self.log.tag_configure(tag, foreground=color)
            self.log.insert("end", text + "\n", tag)
        else:
            self.log.insert("end", text + "\n")
        self.log.see("end")
        self.log.config(state="disabled")

    def _run(self):
        gcode = self.gcode_path.get().strip()
        models = self.models_path.get().strip()

        if not gcode:
            self._log("ERROR: No gcode file selected.", ERROR)
            return
        if not os.path.exists(gcode):
            self._log(f"ERROR: GCode file not found: {gcode}", ERROR)
            return
        if not models:
            self._log("ERROR: No models folder selected.", ERROR)
            return
        if not os.path.exists(models):
            self._log(f"ERROR: Models folder not found: {models}", ERROR)
            return

        output = self.output_path.get().strip() or gcode
        cmd = [PYTHON, "-m", "gcodezaa", gcode, "-m", models, "-o", output]

        name = self.obj_name.get().strip()
        px = self.pos_x.get().strip()
        py = self.pos_y.get().strip()
        if name:
            cmd += ["-n", name]
        if px and py:
            cmd += ["-p", f"{px},{py}"]

        self.run_btn.set_text("PROCESSING...")
        self.run_btn.set_disabled(True)
        self.run_btn.set_colors(BG3, BG3)

        self._log("─" * 44, TEXT_HINT)
        self._log(f"GCode:      {os.path.basename(gcode)}", ACCENT)
        self._log(f"Output:     {os.path.basename(output)}")
        self._log(f"Models:     {models}")
        self._log(f"Resolution: {self.resolution.get():.2f}mm")
        self._log("Processing…  this may take a minute", TEXT_DIM)

        def worker():
            try:
                result = subprocess.run(cmd, cwd=SCRIPT_DIR,
                                        capture_output=True, text=True)
                if result.stdout:
                    self.after(0, lambda: self._log(result.stdout.strip()))
                if result.stderr:
                    self.after(0, lambda: self._log(result.stderr.strip(), TEXT_DIM))
                if result.returncode == 0:
                    size = os.path.getsize(output) / (1024 * 1024)
                    self.after(0, lambda: self._log(
                        f"✓  Done!  {os.path.basename(output)}  ({size:.1f} MB)", SUCCESS))
                else:
                    self.after(0, lambda: self._log(
                        f"✗  Failed (exit code {result.returncode})", ERROR))
            except Exception as e:
                self.after(0, lambda: self._log(f"✗  Error: {e}", ERROR))
            finally:
                self.after(0, self._reset_btn)

        threading.Thread(target=worker, daemon=True).start()

    def _reset_btn(self):
        self.run_btn.set_text("RUN ZAA")
        self.run_btn.set_disabled(False)
        self.run_btn.set_colors(ACCENT, ACCENT_DIM)


if __name__ == "__main__":
    app = ZAAApp()
    app.mainloop()
