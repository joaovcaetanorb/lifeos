import math
import tkinter as tk
from tkinter import filedialog, messagebox

import numpy as np
import sounddevice as sd
import soundfile as sf

BG_COLOR = "#050a05"
GRID_COLOR = "#123a12"
GRID_COLOR_MID = "#1f5c1f"
WAVE_COLOR = "#39FF14"
START_COLOR = "#FF1744"
END_COLOR = "#FF1744"
PLAYHEAD_COLOR = "#FFFFFF"
KNOB_ACCENT = "#FF5A1F"

CREAM = "#EEE8D9"
CREAM_DARK = "#DDD6C0"
INK = "#1A1A18"
GRAY_TXT = "#78766E"
ORANGE = "#FF5A1F"
FONT_UI = ("Consolas", 9)
FONT_UI_BOLD = ("Consolas", 10, "bold")


class Knob(tk.Frame):
    def __init__(self, parent, label, from_, to, value=0, resolution=1, command=None, size=56):
        super().__init__(parent)
        self.from_ = from_
        self.to = to
        self.resolution = resolution
        self.value = value
        self.command = command
        self.size = size
        self.label_text = label

        self.configure(bg=CREAM)
        self.canvas = tk.Canvas(self, width=size, height=size, highlightthickness=0, bg=CREAM)
        self.canvas.pack()
        self.value_label = tk.Label(self, text="", font=("Consolas", 8), bg=CREAM, fg=INK)
        self.value_label.pack()

        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self._redraw()

    def _fmt(self, v):
        if self.resolution == int(self.resolution) and float(v).is_integer():
            return f"{self.label_text} {int(v):+d}" if self.from_ < 0 < self.to else f"{self.label_text} {int(v)}"
        return f"{self.label_text} {v:+.2f}" if self.from_ < 0 < self.to else f"{self.label_text} {v:.2f}"

    def _redraw(self):
        c = self.canvas
        c.delete("all")
        s = self.size
        pad = 4
        c.create_oval(pad, pad, s - pad, s - pad, outline=INK, width=2)
        span = self.to - self.from_
        frac = 0.5 if span == 0 else (self.value - self.from_) / span
        angle_deg = -135 + frac * 270
        angle = math.radians(angle_deg)
        cx, cy = s / 2, s / 2
        r = (s - 2 * pad) / 2 * 0.75
        x2 = cx + r * math.sin(angle)
        y2 = cy - r * math.cos(angle)
        c.create_line(cx, cy, x2, y2, fill=KNOB_ACCENT, width=3)
        c.create_oval(cx - 2, cy - 2, cx + 2, cy + 2, fill=INK)
        self.value_label.config(text=self._fmt(self.value))

    def _on_press(self, event):
        self._drag_start_y = event.y
        self._drag_start_val = self.value

    def _on_drag(self, event):
        dy = self._drag_start_y - event.y
        span = self.to - self.from_
        sensitivity = span / 150.0
        new_val = self._drag_start_val + dy * sensitivity
        new_val = max(self.from_, min(self.to, new_val))
        if self.resolution:
            new_val = round(new_val / self.resolution) * self.resolution
        if new_val != self.value:
            self.value = new_val
            self._redraw()
            if self.command:
                self.command(self.value)

    def get(self):
        return self.value

    def set(self, value):
        self.value = value
        self._redraw()


class IconButton(tk.Canvas):
    def __init__(self, parent, kind, label, command, size=52, accent=False):
        super().__init__(parent, width=size, height=size + 16, highlightthickness=0, bg=CREAM)
        self.kind = kind
        self.label = label
        self.command = command
        self.size = size
        self.accent = accent
        self.bind("<ButtonPress-1>", lambda e: self._flash())
        self._draw()

    def _flash(self):
        self.command()
        self._draw(pressed=True)
        self.after(90, lambda: self._draw(pressed=False))

    def _draw(self, pressed=False):
        self.delete("all")
        s = self.size
        cx, cy, r = s / 2, s / 2, s / 2 - 5
        outline = ORANGE if self.accent else INK
        fill = CREAM_DARK if pressed else CREAM
        self.create_oval(cx - r, cy - r, cx + r, cy + r, outline=outline, width=3, fill=fill)
        glyph = INK if not self.accent else ORANGE
        if self.kind == "play":
            self.create_polygon(cx - 6, cy - 9, cx - 6, cy + 9, cx + 10, cy, fill=glyph)
        elif self.kind == "stop":
            self.create_rectangle(cx - 7, cy - 7, cx + 7, cy + 7, fill=glyph)
        self.create_text(cx, s + 8, text=self.label, font=("Consolas", 8), fill=GRAY_TXT)


class LoopApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Loop Sampler - MVP")
        self.root.configure(bg=CREAM)

        self.data = None
        self.mono = None
        self.samplerate = 44100
        self.duration = 0.0
        self.view_start = 0.0
        self.view_end = 1.0
        self.loop_buffer = None
        self.pos = 0
        self.stream = None
        self.envelope_mins = None
        self.envelope_maxs = None
        self.drag_anchor_sec = None
        self.drag_mode = None
        self.bar_buttons = {}

        self.canvas_width = 640
        self.canvas_height = 160

        outer = tk.Frame(root, bg=CREAM, highlightthickness=3, highlightbackground=INK)
        outer.pack(padx=14, pady=14)

        header = tk.Canvas(outer, width=self.canvas_width, height=54, bg=CREAM, highlightthickness=0)
        header.pack(pady=(12, 4), padx=12)
        self._draw_screw(header, 16, 27)
        self._draw_screw(header, self.canvas_width - 16, 27)
        header.create_text(36, 12, text="LOOP//1", anchor="nw", font=("Arial", 18, "bold"), fill=INK)
        header.create_text(36, 36, text="personal sampler — concept", anchor="nw", font=("Consolas", 8), fill=GRAY_TXT)
        badge_x0, badge_x1 = self.canvas_width - 156, self.canvas_width - 36
        header.create_rectangle(badge_x0, 16, badge_x1, 38, outline=ORANGE, width=2)
        header.create_text((badge_x0 + badge_x1) / 2, 27, text="MODE: LOOP", font=("Consolas", 8, "bold"), fill=ORANGE)

        top_row = tk.Frame(outer, bg=CREAM)
        top_row.pack(pady=(0, 6), padx=12, fill="x")
        self._make_button(top_row, "Carregar áudio", self.load_file).pack(side="left")
        self.info_label = tk.Label(top_row, text="Nenhum arquivo carregado", bg=CREAM, fg=GRAY_TXT, font=FONT_UI)
        self.info_label.pack(side="left", padx=10)

        self.canvas = tk.Canvas(
            outer, width=self.canvas_width, height=self.canvas_height,
            bg=BG_COLOR, highlightthickness=3, highlightbackground=INK,
        )
        self.canvas.pack(pady=5, padx=12)
        self.draw_grid()
        self.root.after(40, self._update_playhead)
        self.canvas.bind("<ButtonPress-1>", self.on_canvas_press)
        self.canvas.bind("<B1-Motion>", self.on_canvas_drag)
        self.canvas.bind("<Control-MouseWheel>", self.on_mousewheel)
        self.canvas.bind("<Control-Button-4>", lambda e: self.on_mousewheel(e, delta=120))
        self.canvas.bind("<Control-Button-5>", lambda e: self.on_mousewheel(e, delta=-120))
        self.canvas.bind("<Shift-MouseWheel>", self.on_shift_wheel)
        self.canvas.bind("<Shift-Button-4>", lambda e: self.on_shift_wheel(e, delta=120))
        self.canvas.bind("<Shift-Button-5>", lambda e: self.on_shift_wheel(e, delta=-120))

        zoom_bar = tk.Frame(outer, bg=CREAM)
        zoom_bar.pack(pady=(0, 8))
        self._make_button(zoom_bar, "🔎 −", lambda: self.zoom_step(1.4), width=6).grid(row=0, column=0, padx=3)
        self._make_button(zoom_bar, "🔎 +", lambda: self.zoom_step(1 / 1.4), width=6).grid(row=0, column=1, padx=3)
        self._make_button(zoom_bar, "Ver tudo", self.zoom_reset, width=10).grid(row=0, column=2, padx=3)

        bounds = tk.Frame(outer, bg=CREAM)
        bounds.pack(pady=5, padx=12, fill="x")

        tk.Label(bounds, text="Início (s)", bg=CREAM, fg=INK, font=FONT_UI).grid(row=0, column=0, sticky="w")
        self.start_var = tk.DoubleVar(value=0.0)
        self.start_scale = self._make_scale(bounds, self.start_var, 0, 1, 0.01, self.on_bounds_change)
        self.start_scale.grid(row=0, column=1)

        tk.Label(bounds, text="Fim (s)", bg=CREAM, fg=INK, font=FONT_UI).grid(row=1, column=0, sticky="w")
        self.end_var = tk.DoubleVar(value=1.0)
        self.end_scale = self._make_scale(bounds, self.end_var, 0, 1, 0.01, self.on_bounds_change)
        self.end_scale.grid(row=1, column=1)

        pitch_frame = tk.Frame(outer, bg=CREAM)
        pitch_frame.pack(pady=5, padx=12)
        self.pitch_knob = Knob(
            pitch_frame, "PITCH", -24, 24, value=0, resolution=0.1, command=self.on_pitch_change,
        )
        self.pitch_knob.pack()

        bpm_frame = tk.Frame(outer, bg=CREAM)
        bpm_frame.pack(pady=5, padx=12, fill="x")
        tk.Label(bpm_frame, text="Compassos no loop:", bg=CREAM, fg=INK, font=FONT_UI).grid(row=0, column=0, sticky="w")
        self.bars_var = tk.IntVar(value=4)
        for i, bars in enumerate([1, 2, 4, 8]):
            btn = tk.Button(
                bpm_frame, text=str(bars), width=3, relief="flat", bd=0, font=FONT_UI_BOLD,
                command=lambda b=bars: self.set_bars(b),
            )
            btn.grid(row=0, column=1 + i, padx=2)
            self.bar_buttons[bars] = btn
        self._style_bar_buttons()
        self.bpm_label = tk.Label(bpm_frame, text="BPM: -", font=FONT_UI_BOLD, bg=CREAM, fg=ORANGE)
        self.bpm_label.grid(row=0, column=5, padx=(15, 0))

        sync_frame = tk.Frame(outer, bg=CREAM)
        sync_frame.pack(pady=5, padx=12, fill="x")
        tk.Label(sync_frame, text="BPM do projeto:", bg=CREAM, fg=INK, font=FONT_UI).grid(row=0, column=0, sticky="w")
        self.target_bpm_var = tk.StringVar(value="90")
        tk.Entry(
            sync_frame, textvariable=self.target_bpm_var, width=6, font=FONT_UI,
            bg="white", fg=INK, relief="solid", bd=1, insertbackground=INK,
        ).grid(row=0, column=1, padx=(4, 10))
        self._make_button(sync_frame, "Sincronizar pitch", self.sync_to_bpm, accent=True).grid(row=0, column=2)
        self.sync_result_label = tk.Label(sync_frame, text="", font=FONT_UI, bg=CREAM, fg=INK)
        self.sync_result_label.grid(row=0, column=3, padx=(10, 0))

        buttons = tk.Frame(outer, bg=CREAM)
        buttons.pack(pady=(10, 4))
        IconButton(buttons, "play", "PLAY", self.play_loop, accent=True).grid(row=0, column=0, padx=10)
        IconButton(buttons, "stop", "STOP", self.stop).grid(row=0, column=1, padx=10)

        export_frame = tk.Frame(outer, bg=CREAM)
        export_frame.pack(pady=(4, 14))
        self._make_button(export_frame, "💾 Exportar WAV", self.export_wav).pack()

    @staticmethod
    def _draw_screw(canvas, cx, cy, r=7):
        canvas.create_oval(cx - r, cy - r, cx + r, cy + r, fill=CREAM_DARK, outline=INK, width=1)
        canvas.create_line(cx - r * 0.6, cy, cx + r * 0.6, cy, fill=INK, width=1)

    @staticmethod
    def _make_button(parent, text, command, width=None, accent=False):
        kwargs = dict(
            text=text, command=command, relief="flat", bd=0, font=FONT_UI_BOLD,
            padx=10, pady=4, cursor="hand2",
        )
        if width:
            kwargs["width"] = width
        if accent:
            kwargs.update(bg=ORANGE, fg="white", activebackground="#e64f18", activeforeground="white")
        else:
            kwargs.update(bg=CREAM_DARK, fg=INK, activebackground=CREAM, activeforeground=INK)
        return tk.Button(parent, **kwargs)

    @staticmethod
    def _make_scale(parent, variable, from_, to, resolution, command):
        return tk.Scale(
            parent, from_=from_, to=to, resolution=resolution, orient=tk.HORIZONTAL,
            variable=variable, length=320, command=command,
            bg=CREAM, fg=INK, troughcolor=CREAM_DARK, highlightthickness=0,
            activebackground=ORANGE, font=FONT_UI, bd=0,
        )

    def set_bars(self, bars):
        self.bars_var.set(bars)
        self._style_bar_buttons()
        self.update_bpm_label()

    def _style_bar_buttons(self):
        for bars, btn in self.bar_buttons.items():
            if bars == self.bars_var.get():
                btn.config(bg=ORANGE, fg="white", activebackground=ORANGE, activeforeground="white")
            else:
                btn.config(bg=CREAM_DARK, fg=INK, activebackground=CREAM, activeforeground=INK)

    def load_file(self):
        path = filedialog.askopenfilename(
            filetypes=[("Áudio", "*.wav *.flac *.ogg *.aiff *.aif *.mp3"), ("Todos", "*.*")]
        )
        if not path:
            return
        self.stop()
        try:
            data, sr = sf.read(path, always_2d=True, dtype="float32")
        except Exception as exc:
            messagebox.showerror(
                "Erro ao carregar áudio",
                f"Não consegui ler este arquivo:\n{exc}",
            )
            return
        self.data = data
        self.mono = data.mean(axis=1)
        self.samplerate = sr
        duration = len(data) / sr
        self.duration = duration
        self.view_start = 0.0
        self.view_end = duration

        self.start_scale.config(to=duration)
        self.end_scale.config(to=duration)
        self.start_var.set(0.0)
        self.end_var.set(duration)

        name = path.replace("\\", "/").rsplit("/", 1)[-1]
        self.info_label.config(text=f"{name} — {duration:.2f}s, {sr}Hz")

        self.compute_envelope()
        self.draw_waveform()
        self.update_loop_buffer()
        self.update_bpm_label()

    def compute_envelope(self):
        width = self.canvas_width
        if self.mono is None:
            self.envelope_mins = None
            self.envelope_maxs = None
            return
        start_sample = int(self.view_start * self.samplerate)
        end_sample = max(start_sample + 1, int(self.view_end * self.samplerate))
        segment = self.mono[start_sample:end_sample]
        n = len(segment)
        if n == 0:
            self.envelope_mins = np.zeros(width, dtype="float32")
            self.envelope_maxs = np.zeros(width, dtype="float32")
            return
        edges = np.linspace(0, n, width + 1).astype(int)
        mins = np.empty(width, dtype="float32")
        maxs = np.empty(width, dtype="float32")
        for i in range(width):
            a, b = edges[i], max(edges[i] + 1, edges[i + 1])
            chunk = segment[a:b]
            mins[i] = chunk.min()
            maxs[i] = chunk.max()
        self.envelope_mins = mins
        self.envelope_maxs = maxs

    def draw_grid(self, cols=10, rows=4):
        self.canvas.delete("grid")
        view_span = self.view_end - self.view_start
        for i in range(1, cols):
            x = i * self.canvas_width / cols
            self.canvas.create_line(x, 0, x, self.canvas_height, fill=GRID_COLOR, tags="grid")
            if self.duration > 0:
                sec = self.view_start + (x / self.canvas_width) * view_span
                self.canvas.create_text(
                    x + 2, self.canvas_height - 8, text=f"{sec:.2f}s", fill=GRID_COLOR_MID,
                    font=("Courier", 7), anchor="w", tags="grid",
                )
        for i in range(1, rows):
            y = i * self.canvas_height / rows
            color = GRID_COLOR_MID if i == rows // 2 else GRID_COLOR
            self.canvas.create_line(0, y, self.canvas_width, y, fill=color, tags="grid")
        self.canvas.tag_lower("grid")

    def draw_waveform(self):
        self.canvas.delete("wave")
        self.draw_grid()
        if self.envelope_mins is None:
            return
        mid = self.canvas_height / 2
        half = self.canvas_height / 2 - 4
        for x in range(self.canvas_width):
            y1 = mid - self.envelope_maxs[x] * half
            y2 = mid - self.envelope_mins[x] * half
            self.canvas.create_line(x, y1, x, y2, fill=WAVE_COLOR, tags="wave")
        self.draw_markers()

    def draw_markers(self):
        self.canvas.delete("marker")
        if self.duration <= 0:
            return
        view_span = self.view_end - self.view_start
        start_x = ((self.start_var.get() - self.view_start) / view_span) * self.canvas_width
        end_x = ((self.end_var.get() - self.view_start) / view_span) * self.canvas_width
        self.canvas.create_line(start_x, 0, start_x, self.canvas_height, fill=START_COLOR, width=2, tags="marker")
        self.canvas.create_line(end_x, 0, end_x, self.canvas_height, fill=END_COLOR, width=2, tags="marker", dash=(4, 2))
        self.canvas.create_rectangle(
            start_x, 0, end_x, self.canvas_height, outline="", fill=WAVE_COLOR, stipple="gray12", tags="marker",
        )

    def on_canvas_press(self, event):
        if self.duration <= 0:
            return
        view_span = self.view_end - self.view_start
        start_x = ((self.start_var.get() - self.view_start) / view_span) * self.canvas_width
        end_x = ((self.end_var.get() - self.view_start) / view_span) * self.canvas_width
        threshold = 8
        if abs(event.x - start_x) <= threshold:
            self.drag_mode = "start"
        elif abs(event.x - end_x) <= threshold:
            self.drag_mode = "end"
        else:
            self.drag_mode = "new"
            self.drag_anchor_sec = self._x_to_sec(event.x)
            self.start_var.set(self.drag_anchor_sec)
            self.end_var.set(self.drag_anchor_sec)

    def on_canvas_drag(self, event):
        if self.duration <= 0 or self.drag_mode is None:
            return
        current_sec = self._x_to_sec(event.x)
        min_gap = 0.01
        if self.drag_mode == "start":
            new_start = max(0.0, min(current_sec, self.end_var.get() - min_gap))
            self.start_var.set(new_start)
        elif self.drag_mode == "end":
            new_end = min(self.duration, max(current_sec, self.start_var.get() + min_gap))
            self.end_var.set(new_end)
        else:
            if self.drag_anchor_sec is None:
                return
            lo, hi = sorted((self.drag_anchor_sec, current_sec))
            self.start_var.set(lo)
            self.end_var.set(hi)
        self.update_loop_buffer()
        self.draw_markers()
        self.update_bpm_label()

    def _x_to_sec(self, x):
        x = min(max(x, 0), self.canvas_width)
        return self.view_start + (x / self.canvas_width) * (self.view_end - self.view_start)

    def on_bounds_change(self, _evt=None):
        self.update_loop_buffer()
        self.draw_markers()
        self.update_bpm_label()

    def on_pitch_change(self, _value):
        self.update_loop_buffer()

    def update_bpm_label(self):
        duration = self.end_var.get() - self.start_var.get()
        if duration <= 0:
            self.bpm_label.config(text="BPM: -")
            return
        bars = self.bars_var.get()
        beats = bars * 4  # assume 4/4
        bpm = beats * 60.0 / duration
        self.bpm_label.config(text=f"BPM: {bpm:.1f}")

    def sync_to_bpm(self):
        duration = self.end_var.get() - self.start_var.get()
        if duration <= 0:
            return
        try:
            target_bpm = float(self.target_bpm_var.get())
        except ValueError:
            messagebox.showerror("BPM inválido", "Digite um número válido de BPM.")
            return
        if target_bpm <= 0:
            return

        bars = self.bars_var.get()
        beats = bars * 4
        current_bpm = beats * 60.0 / duration
        rate = target_bpm / current_bpm
        semitones = 12 * math.log2(rate)

        if not (self.pitch_knob.from_ <= semitones <= self.pitch_knob.to):
            self.sync_result_label.config(
                text=f"fora do alcance do knob ({semitones:+.2f} st)", fg="#FF1744",
            )
            semitones = max(self.pitch_knob.from_, min(self.pitch_knob.to, semitones))
        else:
            self.sync_result_label.config(text=f"ok ({semitones:+.2f} st)", fg=INK)

        self.pitch_knob.set(round(semitones, 1))
        self.update_loop_buffer()

    def refresh_view(self):
        self.compute_envelope()
        self.draw_waveform()

    def zoom_step(self, factor, center_sec=None):
        if self.duration <= 0:
            return
        if center_sec is None:
            center_sec = (self.view_start + self.view_end) / 2
        cur_width = self.view_end - self.view_start
        min_width = min(self.duration, 0.05)
        new_width = max(min_width, min(cur_width * factor, self.duration))
        ratio = (center_sec - self.view_start) / cur_width if cur_width > 0 else 0.5
        new_start = center_sec - ratio * new_width
        new_end = new_start + new_width
        if new_start < 0:
            new_end -= new_start
            new_start = 0
        if new_end > self.duration:
            new_start -= (new_end - self.duration)
            new_end = self.duration
        self.view_start = max(0.0, new_start)
        self.view_end = new_end
        self.refresh_view()

    def zoom_reset(self):
        if self.duration <= 0:
            return
        self.view_start = 0.0
        self.view_end = self.duration
        self.refresh_view()

    def on_mousewheel(self, event, delta=None):
        if self.duration <= 0:
            return
        delta = event.delta if delta is None else delta
        factor = 0.8 if delta > 0 else 1.25
        center_sec = self._x_to_sec(event.x)
        self.zoom_step(factor, center_sec)

    def pan_view(self, direction):
        if self.duration <= 0:
            return
        cur_width = self.view_end - self.view_start
        step = cur_width * 0.2 * direction
        new_start = self.view_start + step
        new_end = self.view_end + step
        if new_start < 0:
            new_end -= new_start
            new_start = 0
        if new_end > self.duration:
            new_start -= (new_end - self.duration)
            new_end = self.duration
        self.view_start = max(0.0, new_start)
        self.view_end = min(self.duration, new_end)
        self.refresh_view()

    def on_shift_wheel(self, event, delta=None):
        if self.duration <= 0:
            return
        delta = event.delta if delta is None else delta
        direction = -1 if delta > 0 else 1
        self.pan_view(direction)

    def update_loop_buffer(self):
        if self.data is None:
            return
        start = int(self.start_var.get() * self.samplerate)
        end = int(self.end_var.get() * self.samplerate)
        if end - start < 100:
            return

        chunk = self.data[start:end].copy()

        semitones = self.pitch_knob.get()
        if semitones != 0:
            rate = 2 ** (semitones / 12)
            chunk = self._resample_pitch(chunk, rate)

        self.loop_buffer = self._make_seamless_loop(chunk)
        self.pos = 0

    def _resample_pitch(self, chunk, rate):
        n = len(chunk)
        new_n = max(1, int(n / rate))
        positions = np.linspace(0, n - 1, new_n)
        src_idx = np.arange(n)
        out = np.empty((new_n, chunk.shape[1]), dtype="float32")
        for ch in range(chunk.shape[1]):
            out[:, ch] = np.interp(positions, src_idx, chunk[:, ch])
        return out

    def _make_seamless_loop(self, chunk):
        n = len(chunk)
        fade_len = min(int(0.008 * self.samplerate), n // 4)
        if fade_len < 8:
            return chunk
        tail = chunk[-fade_len:]
        head = chunk[:fade_len]
        ramp = np.linspace(0.0, 1.0, fade_len, dtype="float32").reshape(-1, 1)
        blended = tail * (1.0 - ramp) + head * ramp
        looped = chunk[:-fade_len].copy()
        looped[:fade_len] = blended
        return looped

    def play_loop(self):
        if self.loop_buffer is None or self.stream is not None:
            return

        self.pos = 0
        channels = self.loop_buffer.shape[1]

        def callback(outdata, frames, time_info, status):
            buf = self.loop_buffer
            n = len(buf)
            pos = self.pos
            idx = 0
            while idx < frames:
                take = min(n - pos, frames - idx)
                outdata[idx:idx + take] = buf[pos:pos + take]
                idx += take
                pos += take
                if pos >= n:
                    pos = 0
            self.pos = pos

        self.stream = sd.OutputStream(
            samplerate=self.samplerate, channels=channels, dtype="float32", callback=callback,
        )
        self.stream.start()

    def stop(self):
        if self.stream is not None:
            self.stream.stop()
            self.stream.close()
            self.stream = None

    def export_wav(self):
        if self.loop_buffer is None:
            messagebox.showwarning("Nada pra exportar", "Carregue um áudio e marque um loop primeiro.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".wav",
            filetypes=[("WAV", "*.wav")],
            initialfile="loop.wav",
        )
        if not path:
            return
        try:
            sf.write(path, self.loop_buffer, self.samplerate)
        except Exception as exc:
            messagebox.showerror("Erro ao exportar", f"Não consegui salvar o arquivo:\n{exc}")
            return
        messagebox.showinfo("Exportado", f"Loop salvo em:\n{path}")

    def _update_playhead(self):
        self.canvas.delete("playhead")
        if self.stream is not None and self.loop_buffer is not None and len(self.loop_buffer) > 0:
            fraction = self.pos / len(self.loop_buffer)
            t = self.start_var.get() + fraction * (self.end_var.get() - self.start_var.get())
            view_span = self.view_end - self.view_start
            if view_span > 0 and self.view_start <= t <= self.view_end:
                x = ((t - self.view_start) / view_span) * self.canvas_width
                self.canvas.create_line(
                    x, 0, x, self.canvas_height, fill=PLAYHEAD_COLOR, width=2, tags="playhead",
                )
        self.root.after(40, self._update_playhead)


def main():
    root = tk.Tk()
    LoopApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
