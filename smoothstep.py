#!/usr/bin/env python3
"""
SmoothStep — Z Anti-Aliasing GCode Post-Processor
By Fromel 3D. Based on GCodeZAA by Theaninova.
"""

import tkinter as tk
from tkinter import filedialog, scrolledtext
import threading
import os
import sys
import json
import math

def _setup_path():
    base = sys._MEIPASS if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__))
    if base not in sys.path:
        sys.path.insert(0, base)

_setup_path()

from gcodezaa.process import process_gcode

PREFS_FILE     = os.path.expanduser("~/.smoothstep_prefs.json")
DEFAULT_MODELS = os.path.expanduser("~/Desktop")

BG         = "#0D1B2A"
BG2        = "#112236"
BG3        = "#1A3050"
BORDER     = "#2A4A6A"
ACCENT     = "#4A9EFF"
ACCENT_DIM = "#2A6ECC"
TEXT       = "#E8F0FF"
TEXT_DIM   = "#7A9CC0"
TEXT_HINT  = "#4A6A8A"
SUCCESS    = "#3DCFAA"
ERROR      = "#FF6B6B"
FONT       = "Helvetica"

LOGO_PATHS = [
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "Fromel3DLogo-8.1.png"),
    os.path.expanduser("~/Desktop/GCodeZAA/Fromel3DLogo-8.1.png"),
]
if getattr(sys, 'frozen', False):
    LOGO_PATHS.insert(0, os.path.join(sys._MEIPASS, "Fromel3DLogo-8.1.png"))


def load_prefs():
    try:
        with open(PREFS_FILE) as f:
            return json.load(f)
    except Exception:
        return {}


def save_prefs(data):
    try:
        with open(PREFS_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass


def draw_logo(canvas, bg=BG2):
    """Draw Fromel3D PNG logo onto canvas, scaled to fit."""
    from PIL import Image, ImageTk
    w = canvas.winfo_width() or canvas.winfo_reqwidth()
    h = canvas.winfo_height() or canvas.winfo_reqheight()
    if w < 2 or h < 2:
        return
    for path in LOGO_PATHS:
        if os.path.exists(path):
            try:
                img = Image.open(path)
                ratio = min(w / img.width, h / img.height)
                nw, nh = int(img.width * ratio), int(img.height * ratio)
                img = img.resize((nw, nh), Image.LANCZOS)
                photo = ImageTk.PhotoImage(img)
                canvas._logo = photo
                canvas.delete("all")
                canvas.create_image(0, h // 2, image=photo, anchor="w")
                return
            except Exception:
                pass
    canvas.create_text(8, h // 2, text="FROMEL 3D",
                       font=(FONT, 14, "bold"), fill=TEXT, anchor="w")


class CanvasButton(tk.Canvas):
    def __init__(self, parent, text, command, bg_color, fg_color, hover_color,
                 height=44, font_size=13, **kwargs):
        super().__init__(parent, height=height, highlightthickness=0, bg=BG, **kwargs)
        self.command     = command
        self.bg_color    = bg_color
        self.fg_color    = fg_color
        self.hover_color = hover_color
        self.text        = text
        self.font_size   = font_size
        self.btn_height  = height
        self._hovered    = False
        self._disabled   = False
        self.bind("<Configure>", self._draw)
        self.bind("<Enter>",    lambda e: self._set_hover(True))
        self.bind("<Leave>",    lambda e: self._set_hover(False))
        self.bind("<Button-1>", lambda e: self.command() if not self._disabled else None)

    def _set_hover(self, val):
        self._hovered = val
        self._draw()

    def _draw(self, event=None):
        self.delete("all")
        w = self.winfo_width()
        h = self.btn_height
        color = BG3 if self._disabled else (self.hover_color if self._hovered else self.bg_color)
        self.create_rectangle(0, 0, w, h, fill=color, outline=BORDER, width=1)
        fg = TEXT_HINT if self._disabled else self.fg_color
        self.create_text(w // 2, h // 2, text=self.text,
                         fill=fg, font=(FONT, self.font_size, "bold"))

    def set_text(self, t):       self.text = t;                               self._draw()
    def set_disabled(self, v):   self._disabled = v;                          self._draw()
    def set_colors(self, bg, h): self.bg_color = bg; self.hover_color = h;    self._draw()


class SmoothStep(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("SmoothStep")
        self.geometry("660x920")
        self.resizable(True, True)
        self.configure(bg=BG)

        prefs = load_prefs()
        self.gcode_path  = tk.StringVar(value=prefs.get("gcode_path", ""))
        self.models_path = tk.StringVar(value=prefs.get("models_path", DEFAULT_MODELS))
        self.output_path = tk.StringVar(value=prefs.get("output_path", ""))
        self.resolution  = tk.DoubleVar(value=prefs.get("resolution", 0.1))
        self.outer_walls = tk.BooleanVar(value=prefs.get("outer_walls", True))
        self.inner_walls = tk.BooleanVar(value=prefs.get("inner_walls", True))
        self.top_surface = tk.BooleanVar(value=prefs.get("top_surface", True))
        self.ironing          = tk.BooleanVar(value=prefs.get("ironing", False))
        self.bottom_surface   = tk.BooleanVar(value=prefs.get("bottom_surface", False))
        self.support_interface = tk.BooleanVar(value=prefs.get("support_interface", False))
        self.min_z            = tk.DoubleVar(value=prefs.get("min_z", 0.02))
        self.bottom_min_z     = tk.DoubleVar(value=prefs.get("bottom_min_z", 0.02))
        self.support_min_z    = tk.DoubleVar(value=prefs.get("support_min_z", 0.1))
        self.obj_name    = tk.StringVar(value=prefs.get("obj_name", ""))
        self.pos_x       = tk.StringVar(value=prefs.get("pos_x", ""))
        self.pos_y       = tk.StringVar(value=prefs.get("pos_y", ""))

        self._pulse_active = False
        self._pulse_chars  = ["⠋","⠙","⠹","⠸","⠼","⠴","⠦","⠧","⠇","⠏"]
        self._pulse_idx    = 0

        self._build_ui()
        self._set_icon()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _set_icon(self):
        icon_paths = [
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "smoothstep_icon.png"),
            os.path.expanduser("~/Desktop/GCodeZAA/smoothstep_icon.png"),
        ]
        if getattr(sys, 'frozen', False):
            icon_paths.insert(0, os.path.join(sys._MEIPASS, "smoothstep_icon.png"))
        for path in icon_paths:
            if os.path.exists(path):
                try:
                    from PIL import Image, ImageTk
                    img = Image.open(path).resize((256, 256))
                    self._icon_img = ImageTk.PhotoImage(img)
                    self.iconphoto(True, self._icon_img)
                    return
                except Exception:
                    pass

    def _on_close(self):
        save_prefs({
            "gcode_path":  self.gcode_path.get(),
            "models_path": self.models_path.get(),
            "output_path": self.output_path.get(),
            "resolution":  self.resolution.get(),
            "outer_walls": self.outer_walls.get(),
            "inner_walls": self.inner_walls.get(),
            "top_surface": self.top_surface.get(),
            "ironing":           self.ironing.get(),
            "bottom_surface":    self.bottom_surface.get(),
            "support_interface": self.support_interface.get(),
            "min_z":             self.min_z.get(),
            "bottom_min_z":      self.bottom_min_z.get(),
            "support_min_z":     self.support_min_z.get(),
            "obj_name":    self.obj_name.get(),
            "pos_x":       self.pos_x.get(),
            "pos_y":       self.pos_y.get(),
        })
        self.destroy()

    def _build_ui(self):
        # ── HEADER ──────────────────────────────────────────────
        hdr = tk.Frame(self, bg=BG2, height=90)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)

        logo_canvas = tk.Canvas(hdr, width=320, height=84,
                                bg=BG2, highlightthickness=0)
        logo_canvas.pack(side="left", padx=(14, 0), pady=3)
        logo_canvas.bind("<Configure>", lambda e: draw_logo(logo_canvas, BG2))
        self.after(60, lambda: draw_logo(logo_canvas, BG2))

        tk.Frame(hdr, bg=BORDER, width=1).pack(side="left", fill="y", padx=14, pady=10)

        name_frame = tk.Frame(hdr, bg=BG2)
        name_frame.pack(side="left")
        tk.Label(name_frame, text="SMOOTH", font=(FONT, 15, "bold"),
                 bg=BG2, fg=ACCENT).pack(side="left")
        tk.Label(name_frame, text="STEP", font=(FONT, 15, "bold"),
                 bg=BG2, fg=TEXT).pack(side="left")
        tk.Label(hdr, text="Z Anti-Aliasing Post-Processor",
                 font=(FONT, 10), bg=BG2, fg=TEXT_DIM).pack(side="left", padx=(8, 0))

        tk.Frame(self, bg=BORDER, height=1).pack(fill="x")

        # ── SCROLLABLE BODY ─────────────────────────────────────
        outer = tk.Frame(self, bg=BG)
        outer.pack(fill="both", expand=True)
        canvas = tk.Canvas(outer, bg=BG, highlightthickness=0)
        sb = tk.Scrollbar(outer, orient="vertical", command=canvas.yview,
                          bg=BG2, troughcolor=BG2)
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        main = tk.Frame(canvas, bg=BG)
        cw = canvas.create_window((0, 0), window=main, anchor="nw")
        main.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(cw, width=e.width))
        canvas.bind_all("<MouseWheel>",
                        lambda e: canvas.yview_scroll(-1*(e.delta//120), "units"))

        # FILES
        self._section(main, "Files")
        self._file_row(main, "GCode file", self.gcode_path, self._pick_gcode)
        self._file_row(main, "Models folder (STL directory)",
                       self.models_path, self._pick_models, is_dir=True)
        self._file_row(main, "Output file  (blank = overwrite input)",
                       self.output_path, self._pick_output, save=True)

        # Z CONTOURING
        self._section(main, "Z Contouring")
        self._label(main, "Resolution (mm)  —  lower = smoother, slower")
        rf = tk.Frame(main, bg=BG)
        rf.pack(fill="x", padx=20, pady=(0, 12))
        self.res_label = tk.Label(rf, text=f"{self.resolution.get():.2f}",
                                   font=(FONT, 13, "bold"), bg=BG, fg=ACCENT,
                                   width=5, anchor="e")
        self.res_label.pack(side="right")
        tk.Label(rf, text="mm", font=(FONT, 11), bg=BG,
                 fg=TEXT_DIM).pack(side="right", padx=(0, 4))
        tk.Scale(rf, from_=0.05, to=1.0, resolution=0.05, orient="horizontal",
                 variable=self.resolution, bg=BG, fg=TEXT, highlightthickness=0,
                 troughcolor=BG3, activebackground=ACCENT, sliderrelief="flat",
                 showvalue=False, command=self._update_res_label, bd=0
                 ).pack(side="left", fill="x", expand=True)

        for label, var in [
            ("Contour outer walls", self.outer_walls),
            ("Contour inner walls", self.inner_walls),
            ("Contour top surface", self.top_surface),
            ("Contour ironing lines", self.ironing),
            ("Contour bottom surface", self.bottom_surface),
            ("Contour support interface", self.support_interface),
        ]:
            tk.Checkbutton(main, text=label, variable=var,
                           font=(FONT, 12), bg=BG, fg=TEXT,
                           selectcolor=BG3, activebackground=BG,
                           activeforeground=ACCENT, cursor="hand2",
                           anchor="w").pack(fill="x", padx=20, pady=3)

        # MIN Z HEIGHTS
        self._label(main, "Minimum Z offset (mm)")
        for label, var in [
            ("Top / walls", self.min_z),
            ("Bottom surface", self.bottom_min_z),
            ("Support interface", self.support_min_z),
        ]:
            zf = tk.Frame(main, bg=BG)
            zf.pack(fill="x", padx=20, pady=(0, 4))
            tk.Label(zf, text=label, font=(FONT, 11), bg=BG,
                     fg=TEXT_DIM, width=16, anchor="w").pack(side="left")
            tk.Entry(zf, textvariable=var, width=8,
                     font=(FONT, 12), relief="flat", bg=BG3, fg=TEXT,
                     insertbackground=ACCENT, highlightthickness=1,
                     highlightbackground=BORDER, highlightcolor=ACCENT
                     ).pack(side="left", ipady=4, ipadx=6)
            tk.Label(zf, text="mm", font=(FONT, 11), bg=BG,
                     fg=TEXT_DIM).pack(side="left", padx=(4, 0))

        # OBJECT PLACEMENT
        self._section(main, "Object placement  (optional — OrcaSlicer auto-detects)")
        opf = tk.Frame(main, bg=BG)
        opf.pack(fill="x", padx=20, pady=(0, 8))
        tk.Label(opf, text="Object name:", font=(FONT, 12), bg=BG,
                 fg=TEXT_DIM).pack(side="left", padx=(0, 10))
        tk.Entry(opf, textvariable=self.obj_name, width=28,
                 font=(FONT, 12), relief="flat", bg=BG3, fg=TEXT,
                 insertbackground=ACCENT, highlightthickness=1,
                 highlightbackground=BORDER, highlightcolor=ACCENT
                 ).pack(side="left", ipady=6, ipadx=6)

        ppf = tk.Frame(main, bg=BG)
        ppf.pack(fill="x", padx=20, pady=(0, 16))
        for lbl, var, px in [("Position X:", self.pos_x, (0, 14)),
                              ("Y:", self.pos_y, (0, 0))]:
            tk.Label(ppf, text=lbl, font=(FONT, 12), bg=BG,
                     fg=TEXT_DIM).pack(side="left", padx=(0, 6))
            tk.Entry(ppf, textvariable=var, width=8,
                     font=(FONT, 12), relief="flat", bg=BG3, fg=TEXT,
                     insertbackground=ACCENT, highlightthickness=1,
                     highlightbackground=BORDER, highlightcolor=ACCENT
                     ).pack(side="left", ipady=6, ipadx=6, padx=px)

        # Progress bar
        pb_frame = tk.Frame(main, bg=BG)
        pb_frame.pack(fill="x", padx=20, pady=(0, 4))
        pb_bg = tk.Frame(pb_frame, bg=BG3, height=4)
        pb_bg.pack(fill="x")
        self.progress_bar = tk.Frame(pb_bg, bg=ACCENT, height=4)
        self.progress_bar.place(x=0, y=0, relheight=1, relwidth=0)

        # Run button
        self.run_btn = CanvasButton(
            main, text="RUN  //  SMOOTH STEP", command=self._run,
            bg_color=ACCENT, fg_color="#FFFFFF",
            hover_color=ACCENT_DIM, height=52, font_size=14
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
        self.log.pack(fill="x", padx=20, pady=(0, 8))

        # ── FOOTER ──────────────────────────────────────────────
        tk.Frame(main, bg=BORDER, height=1).pack(fill="x", padx=20, pady=(12, 0))

        footer = tk.Frame(main, bg=BG)
        footer.pack(fill="x", pady=(12, 0))

        # Centered logo
        footer_logo = tk.Canvas(footer, width=320, height=80,
                                bg=BG, highlightthickness=0)
        footer_logo.pack(anchor="center")
        footer_logo.bind("<Configure>", lambda e: draw_logo(footer_logo, BG))
        self.after(120, lambda: draw_logo(footer_logo, BG))

        # Credits
        credits_frame = tk.Frame(footer, bg=BG)
        credits_frame.pack(anchor="center", pady=(8, 4))

        tk.Label(credits_frame,
                 text="SmoothStep by Fromel 3D  //  Powered by GCodeZAA (Theaninova)  //  AGPL-3.0",
                 font=(FONT, 9), bg=BG, fg=TEXT_HINT).pack()

        # Clickable links
        links_frame = tk.Frame(footer, bg=BG)
        links_frame.pack(anchor="center", pady=(0, 4))

        def make_link(parent, text, url):
            lbl = tk.Label(parent, text=text, font=(FONT, 9, "underline"),
                           bg=BG, fg=ACCENT, cursor="hand2")
            lbl.pack(side="left", padx=6)
            lbl.bind("<Button-1>", lambda e: self._open_url(url))
            return lbl

        make_link(links_frame, "GCodeZAA on GitHub",
                  "https://github.com/Theaninova/GCodeZAA")
        tk.Label(links_frame, text="//", font=(FONT, 9),
                 bg=BG, fg=TEXT_HINT).pack(side="left")
        make_link(links_frame, "Non-Planar FFF Research Paper",
                  "https://arxiv.org/abs/1609.03032")

        tk.Label(footer,
                 text="Licensed under AGPL-3.0  —  Use freely, share improvements",
                 font=(FONT, 8), bg=BG, fg=TEXT_HINT).pack(pady=(0, 16))

    def _open_url(self, url):
        import subprocess
        subprocess.Popen(["open", url])

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
                 highlightcolor=ACCENT
                 ).pack(side="left", fill="x", expand=True,
                        ipady=6, ipadx=8, padx=(0, 8))
        btn = CanvasButton(f, text="Browse", command=command,
                           bg_color=BG3, fg_color=TEXT_DIM,
                           hover_color=BORDER, height=34, font_size=11)
        btn.pack(side="left")
        btn.config(width=72)

    def _update_res_label(self, val):
        self.res_label.config(text=f"{float(val):.2f}")

    def _pick_gcode(self):
        d = self.gcode_path.get()
        initialdir = os.path.dirname(d) if d and os.path.exists(os.path.dirname(d)) \
                     else os.path.expanduser("~/Desktop")
        path = filedialog.askopenfilename(
            title="Select GCode file",
            filetypes=[("GCode files", "*.gcode"), ("All files", "*.*")],
            initialdir=initialdir
        )
        if path:
            self.gcode_path.set(path)
            self._log(f"GCode: {path}", ACCENT)

    def _pick_models(self):
        path = filedialog.askdirectory(
            title="Select models folder",
            initialdir=os.path.expanduser("~/Desktop")
        )
        if path:
            self.models_path.set(path)
            self._log(f"Models: {path}", ACCENT)

    def _pick_output(self):
        initial = self.gcode_path.get()
        initialdir = os.path.dirname(initial) if initial else os.path.expanduser("~/Desktop")
        initialfile = ""
        if initial:
            name, ext = os.path.splitext(os.path.basename(initial))
            initialfile = f"{name}_ZAA{ext}"
        path = filedialog.asksaveasfilename(
            title="Save output as",
            filetypes=[("GCode files", "*.gcode"), ("All files", "*.*")],
            initialdir=initialdir, initialfile=initialfile,
            defaultextension=".gcode"
        )
        if path:
            self.output_path.set(path)
            self._log(f"Output: {path}", ACCENT)

    def _log(self, text, color=None):
        self.log.config(state="normal")
        if color:
            tag = f"c_{color}"
            self.log.tag_configure(tag, foreground=color)
            self.log.insert("end", text + "\n", tag)
        else:
            self.log.insert("end", text + "\n")
        self.log.see("end")
        self.log.config(state="disabled")

    def _start_pulse(self):
        self._pulse_active = True
        self._pulse_idx    = 0
        self._pulse_bar_w  = 0
        self._animate_pulse()

    def _animate_pulse(self):
        if not self._pulse_active:
            return
        self._pulse_idx   = (self._pulse_idx + 1) % len(self._pulse_chars)
        self._pulse_bar_w = (self._pulse_bar_w + 2) % 102
        frac = self._pulse_bar_w / 100.0
        if frac > 1.0:
            frac = 2.0 - frac
        self.progress_bar.place(relwidth=frac)
        self.run_btn.set_text(f"PROCESSING  {self._pulse_chars[self._pulse_idx]}")
        self.after(80, self._animate_pulse)

    def _stop_pulse(self):
        self._pulse_active = False
        self.progress_bar.place(relwidth=0)

    def _run(self):
        gcode  = self.gcode_path.get().strip()
        models = self.models_path.get().strip()

        if not gcode:
            self._log("ERROR: No gcode file selected.", ERROR); return
        if not os.path.exists(gcode):
            self._log(f"ERROR: GCode not found: {gcode}", ERROR); return
        if not models:
            self._log("ERROR: No models folder selected.", ERROR); return
        if not os.path.exists(models):
            self._log(f"ERROR: Models folder not found: {models}", ERROR); return

        output     = self.output_path.get().strip() or gcode
        name       = self.obj_name.get().strip()
        px         = self.pos_x.get().strip()
        py         = self.pos_y.get().strip()
        resolution = self.resolution.get()

        plate_model = (name, float(px), float(py)) if name and px and py else None

        self.run_btn.set_disabled(True)
        self.run_btn.set_colors(BG3, BG3)
        self._start_pulse()

        self._log("─" * 44, TEXT_HINT)
        self._log(f"GCode:      {os.path.basename(gcode)}", ACCENT)
        self._log(f"Output:     {os.path.basename(output)}")
        self._log(f"Models:     {models}")
        self._log(f"Resolution: {resolution:.2f}mm")
        self._log("Processing…  this may take a minute", TEXT_DIM)

        def worker():
            try:
                with open(gcode, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                settings = {
                    "outer_walls": self.outer_walls.get(),
                    "inner_walls": self.inner_walls.get(),
                    "top_surface": self.top_surface.get(),
                    "ironing": self.ironing.get(),
                    "bottom_surface": self.bottom_surface.get(),
                    "support_interface": self.support_interface.get(),
                    "min_z": self.min_z.get(),
                    "bottom_min_z": self.bottom_min_z.get(),
                    "support_interface_min_z": self.support_min_z.get(),
                }
                result = process_gcode(lines, models, plate_model, settings=settings)
                with open(output, "w", encoding="utf-8") as f:
                    f.writelines(result)
                size = os.path.getsize(output) / (1024 * 1024)
                self.after(0, lambda: self._log(
                    f"✓  Done!  {os.path.basename(output)}  ({size:.1f} MB)", SUCCESS))
            except Exception as e:
                self.after(0, lambda: self._log(f"✗  Error: {e}", ERROR))
            finally:
                self.after(0, self._reset_btn)

        threading.Thread(target=worker, daemon=True).start()

    def _reset_btn(self):
        self._stop_pulse()
        self.run_btn.set_text("RUN  //  SMOOTH STEP")
        self.run_btn.set_disabled(False)
        self.run_btn.set_colors(ACCENT, ACCENT_DIM)


if __name__ == "__main__":
    app = SmoothStep()
    app.mainloop()
