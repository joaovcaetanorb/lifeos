"""Pad sampler: chopar um audio e distribuir pedacos em 16 pads, tocaveis pelo teclado.

Tela separada do Loop Sampler (main.py) e do Drum Machine (drum_prototype.py) -
reaproveita a estetica e os padroes ja validados (waveform com zoom/drag do
main.py, fila de comandos + mixer de vozes do drum_prototype.py) mas e um
modulo proprio, com seu proprio motor de audio (nao compartilha stream com
os outros dois).

Fluxo: carregar/gravar um audio -> chopar um trecho na waveform -> "Atribuir
ao pad selecionado" grava aquele trecho (ja com pitch aplicado) no pad -> o
pad toca pelo mouse ou pela tecla mapeada, no modo escolhido (oneshot / hold
/ loop).
"""

import queue
import sys
import tkinter as tk
from tkinter import filedialog, messagebox

import numpy as np
import sounddevice as sd
import soundfile as sf

from main import (
    CREAM, CREAM_DARK, INK, GRAY_TXT, ORANGE, FONT_UI, FONT_UI_BOLD,
    BG_COLOR, GRID_COLOR, GRID_COLOR_MID, WAVE_COLOR, START_COLOR, END_COLOR,
    Knob, IconButton,
)

if sys.platform == "win32":
    try:
        import pyaudiowpatch as pyaudio
    except ImportError:
        pyaudio = None
else:
    pyaudio = None

SR = 44100
PAD_KEYS = ["1", "2", "3", "4", "q", "w", "e", "r", "a", "s", "d", "f", "z", "x", "c", "v"]
MODES = ["oneshot", "hold", "loop"]
MODE_LABELS = {"oneshot": "ONE-SHOT", "hold": "HOLD", "loop": "LOOP"}
SELECT_COLOR = "#1E88E5"
FADE_SAMPLES = int(0.005 * SR)


def _resample_rate(data, orig_sr, target_sr):
    if orig_sr == target_sr:
        return data.astype("float32")
    n = len(data)
    new_n = max(1, int(n * target_sr / orig_sr))
    positions = np.linspace(0, n - 1, new_n)
    if data.ndim == 1:
        return np.interp(positions, np.arange(n), data).astype("float32")
    out = np.empty((new_n, data.shape[1]), dtype="float32")
    for ch in range(data.shape[1]):
        out[:, ch] = np.interp(positions, np.arange(n), data[:, ch])
    return out


def _resample_pitch(chunk, rate):
    n = len(chunk)
    new_n = max(1, int(n / rate))
    positions = np.linspace(0, n - 1, new_n)
    src_idx = np.arange(n)
    out = np.empty((new_n, chunk.shape[1]), dtype="float32")
    for ch in range(chunk.shape[1]):
        out[:, ch] = np.interp(positions, src_idx, chunk[:, ch])
    return out


def _make_seamless_edges(chunk, sr):
    n = len(chunk)
    fade_len = min(int(0.008 * sr), n // 4)
    if fade_len < 8:
        return chunk
    tail = chunk[-fade_len:]
    head = chunk[:fade_len]
    ramp = np.linspace(0.0, 1.0, fade_len, dtype="float32").reshape(-1, 1)
    blended = tail * (1.0 - ramp) + head * ramp
    looped = chunk[:-fade_len].copy()
    looped[:fade_len] = blended
    return looped


class PadSlot:
    def __init__(self, key):
        self.key = key
        self.buffer = None
        self.mode = "oneshot"
        self.volume = 1.0
        self.label = ""

    @property
    def assigned(self):
        return self.buffer is not None


class PadSamplerApp:
    def __init__(self, root, container=None):
        self.root = root
        parent = container if container is not None else root
        if container is None:
            self.root.title("Pad Sampler - Prototipo")
            self.root.configure(bg=CREAM)

        self.data = None
        self.mono = None
        self.samplerate = SR
        self.duration = 0.0
        self.view_start = 0.0
        self.view_end = 1.0
        self.envelope_mins = None
        self.envelope_maxs = None
        self.drag_anchor_sec = None
        self.drag_mode = None

        self.pads = {key: PadSlot(key) for key in PAD_KEYS}
        self.selected_pad_key = PAD_KEYS[0]
        self.pad_buttons = {}
        self.mode_buttons = {}

        self.recording = False
        self._record_frames = []
        self._record_sr = 44100
        self._record_channels = 2
        self._pa = None
        self._pa_stream = None
        self._sd_record_stream = None

        self.voices = []
        self.cmd_queue = queue.Queue()
        self._held_keys = set()
        self._looping_keys = set()
        self._pressed_keys = set()

        self.canvas_width = 640
        self.canvas_height = 140

        outer = tk.Frame(parent, bg=CREAM, highlightthickness=3, highlightbackground=INK)
        outer.pack(padx=14, pady=14)

        header = tk.Canvas(outer, width=self.canvas_width, height=54, bg=CREAM, highlightthickness=0)
        header.pack(pady=(12, 4), padx=12)
        self._draw_screw(header, 16, 27)
        self._draw_screw(header, self.canvas_width - 16, 27)
        header.create_text(36, 12, text="LOOP//1", anchor="nw", font=("Arial", 18, "bold"), fill=INK)
        header.create_text(36, 36, text="pad sampler — prototipo", anchor="nw", font=("Consolas", 8), fill=GRAY_TXT)
        badge_x0, badge_x1 = self.canvas_width - 150, self.canvas_width - 36
        header.create_rectangle(badge_x0, 16, badge_x1, 38, outline=ORANGE, width=2)
        header.create_text((badge_x0 + badge_x1) / 2, 27, text="MODE: PADS", font=("Consolas", 8, "bold"), fill=ORANGE)

        top_row = tk.Frame(outer, bg=CREAM)
        top_row.pack(pady=(0, 6), padx=12, fill="x")
        self._make_button(top_row, "Carregar áudio", self.load_file).pack(side="left")
        self.record_btn = self._make_button(top_row, "🔴 Gravar do PC", self.toggle_record_pc)
        self.record_btn.pack(side="left", padx=(8, 0))
        self.info_label = tk.Label(top_row, text="Nenhum áudio carregado", bg=CREAM, fg=GRAY_TXT, font=FONT_UI)
        self.info_label.pack(side="left", padx=10)

        self.canvas = tk.Canvas(
            outer, width=self.canvas_width, height=self.canvas_height,
            bg=BG_COLOR, highlightthickness=3, highlightbackground=INK,
        )
        self.canvas.pack(pady=5, padx=12)
        self.draw_grid()
        self.canvas.bind("<ButtonPress-1>", self.on_canvas_press)
        self.canvas.bind("<B1-Motion>", self.on_canvas_drag)
        self.canvas.bind("<Control-MouseWheel>", self.on_mousewheel)
        self.canvas.bind("<Control-Button-4>", lambda e: self.on_mousewheel(e, delta=120))
        self.canvas.bind("<Control-Button-5>", lambda e: self.on_mousewheel(e, delta=-120))
        self.canvas.bind("<Shift-MouseWheel>", self.on_shift_wheel)
        self.canvas.bind("<Shift-Button-4>", lambda e: self.on_shift_wheel(e, delta=120))
        self.canvas.bind("<Shift-Button-5>", lambda e: self.on_shift_wheel(e, delta=-120))

        zoom_bar = tk.Frame(outer, bg=CREAM)
        zoom_bar.pack(pady=(0, 6))
        self._make_button(zoom_bar, "🔎 −", lambda: self.zoom_step(1.4)).grid(row=0, column=0, padx=3)
        self._make_button(zoom_bar, "🔎 +", lambda: self.zoom_step(1 / 1.4)).grid(row=0, column=1, padx=3)
        self._make_button(zoom_bar, "Ver tudo", self.zoom_reset).grid(row=0, column=2, padx=3)

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
        pitch_frame.pack(pady=5)
        self.pitch_knob = Knob(pitch_frame, "PITCH", -24, 24, value=0, resolution=1, command=lambda v: None, size=44)
        self.pitch_knob.pack()

        assign_frame = tk.Frame(outer, bg=CREAM)
        assign_frame.pack(pady=(0, 10))
        self._make_button(assign_frame, "▶ Testar corte", self.preview_staging).pack(side="left", padx=(0, 8))
        self._make_button(
            assign_frame, "➜ Atribuir ao pad selecionado", self.assign_to_selected_pad, accent=True,
        ).pack(side="left")

        tk.Frame(outer, bg=INK, height=2).pack(fill="x", padx=12, pady=(4, 10))

        pad_grid_frame = tk.Frame(outer, bg=CREAM)
        pad_grid_frame.pack(padx=12)
        for i, key in enumerate(PAD_KEYS):
            row, col = divmod(i, 4)
            btn = tk.Button(
                pad_grid_frame, width=7, height=3, relief="flat", bd=1, takefocus=0, font=FONT_UI_BOLD,
            )
            btn.bind("<ButtonPress-1>", lambda e, k=key: self._on_pad_press(k))
            btn.bind("<ButtonRelease-1>", lambda e, k=key: self._on_pad_release(k))
            btn.grid(row=row, column=col, padx=3, pady=3)
            self.pad_buttons[key] = btn

        inspector = tk.Frame(outer, bg=CREAM)
        inspector.pack(pady=(10, 4))
        self.pad_label = tk.Label(inspector, text="", font=FONT_UI_BOLD, bg=CREAM, fg=INK)
        self.pad_label.pack(side="left", padx=(0, 14))
        for mode in MODES:
            btn = tk.Button(
                inspector, text=MODE_LABELS[mode], font=FONT_UI, relief="flat", bd=0, takefocus=0,
                padx=8, pady=3, command=lambda m=mode: self.set_pad_mode(m),
            )
            btn.pack(side="left", padx=2)
            self.mode_buttons[mode] = btn
        self.pad_volume_knob = Knob(
            inspector, "VOL", 0.2, 1.5, value=1.0, resolution=0.05, command=self.on_pad_volume_change, size=40,
        )
        self.pad_volume_knob.pack(side="left", padx=(14, 0))

        tk.Label(
            outer, text="teclas 1234 / qwer / asdf / zxcv tocam os pads (clique também funciona)",
            font=("Consolas", 7), bg=CREAM, fg=GRAY_TXT,
        ).pack(pady=(0, 12))

        self.stream = sd.OutputStream(
            samplerate=SR, channels=2, dtype="float32", blocksize=512, callback=self._audio_callback,
        )
        self.stream.start()

        self.root.bind("<KeyPress>", self._on_keydown)
        self.root.bind("<KeyRelease>", self._on_keyup)

        self._refresh_pad_buttons()
        self.select_pad(self.selected_pad_key)

    # ---------- estilo / widgets utilitarios ----------

    @staticmethod
    def _draw_screw(canvas, cx, cy, r=7):
        canvas.create_oval(cx - r, cy - r, cx + r, cy + r, fill=CREAM_DARK, outline=INK, width=1)
        canvas.create_line(cx - r * 0.6, cy, cx + r * 0.6, cy, fill=INK, width=1)

    @staticmethod
    def _make_button(parent, text, command, accent=False):
        kwargs = dict(
            text=text, command=command, relief="flat", bd=0, font=FONT_UI_BOLD,
            padx=10, pady=4, cursor="hand2", takefocus=0,
        )
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

    # ---------- carregar / gravar ----------

    def load_file(self):
        path = filedialog.askopenfilename(
            filetypes=[("Áudio", "*.wav *.flac *.ogg *.aiff *.aif *.mp3"), ("Todos", "*.*")]
        )
        if not path:
            return
        try:
            data, sr = sf.read(path, always_2d=True, dtype="float32")
        except Exception as exc:
            messagebox.showerror("Erro ao carregar áudio", f"Não consegui ler este arquivo:\n{exc}")
            return
        name = path.replace("\\", "/").rsplit("/", 1)[-1]
        self._use_audio_data(data, sr, name)

    def _use_audio_data(self, data, sr, label):
        if data.ndim == 1:
            data = data.reshape(-1, 1)
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
        self.info_label.config(text=f"{label} — {duration:.2f}s, {sr}Hz")
        self.compute_envelope()
        self.draw_waveform()

    def toggle_record_pc(self):
        if self.recording:
            self._stop_record_pc()
        else:
            self._start_record_pc()

    def _start_record_pc(self):
        self._record_frames = []
        ok = self._start_record_pc_windows() if sys.platform == "win32" else self._start_record_pc_linux()
        if not ok:
            return
        self.recording = True
        self.record_btn.config(text="■ Parar gravação", bg=ORANGE, fg="white")
        self.info_label.config(text="Gravando o que está tocando no PC...")

    def _start_record_pc_windows(self):
        if pyaudio is None:
            messagebox.showerror(
                "Dependência faltando",
                "Instale 'PyAudioWPatch' (pip install PyAudioWPatch) pra gravar do PC no Windows.",
            )
            return False
        try:
            self._pa = pyaudio.PyAudio()
            wasapi_info = self._pa.get_host_api_info_by_type(pyaudio.paWASAPI)
            device = self._pa.get_device_info_by_index(wasapi_info["defaultOutputDevice"])
            if not device.get("isLoopbackDevice", False):
                for loopback in self._pa.get_loopback_device_info_generator():
                    if device["name"] in loopback["name"]:
                        device = loopback
                        break

            sr = int(device["defaultSampleRate"])
            channels = device["maxInputChannels"]

            def callback(in_data, frame_count, time_info, status):
                self._record_frames.append(in_data)
                return (in_data, pyaudio.paContinue)

            self._pa_stream = self._pa.open(
                format=pyaudio.paFloat32, channels=channels, rate=sr, frames_per_buffer=1024,
                input=True, input_device_index=device["index"], stream_callback=callback,
            )
            self._record_sr = sr
            self._record_channels = channels
        except Exception as exc:
            messagebox.showerror("Erro ao gravar do PC", f"Não consegui abrir a captura do sistema:\n{exc}")
            return False
        return True

    def _start_record_pc_linux(self):
        try:
            devices = sd.query_devices()
            target = None
            for i, d in enumerate(devices):
                if d["max_input_channels"] > 0 and "monitor" in d["name"].lower():
                    target = i
                    break
            sr = 44100
            channels = 2

            def callback(indata, frames, time_info, status):
                self._record_frames.append(indata.copy())

            self._sd_record_stream = sd.InputStream(
                samplerate=sr, device=target, channels=channels, dtype="float32", callback=callback,
            )
            self._sd_record_stream.start()
            self._record_sr = sr
            self._record_channels = channels
            if target is None:
                messagebox.showwarning(
                    "Sem monitor encontrado",
                    "Não achei automaticamente um dispositivo 'monitor' (loopback) do PipeWire — "
                    "gravando da entrada padrão. Selecione manualmente o monitor da saída nas "
                    "configurações de som se quiser capturar o que está tocando no PC.",
                )
        except Exception as exc:
            messagebox.showerror("Erro ao gravar do PC", f"Não consegui abrir a captura do sistema:\n{exc}")
            return False
        return True

    def _stop_record_pc(self):
        self.recording = False
        self.record_btn.config(text="🔴 Gravar do PC", bg=CREAM_DARK, fg=INK)

        if sys.platform == "win32":
            if self._pa_stream is not None:
                self._pa_stream.stop_stream()
                self._pa_stream.close()
                self._pa_stream = None
            if self._pa is not None:
                self._pa.terminate()
                self._pa = None
            raw = b"".join(self._record_frames)
            data = np.frombuffer(raw, dtype="float32")
            channels = max(1, self._record_channels)
            data = data[: len(data) - (len(data) % channels)].reshape(-1, channels)
        else:
            if self._sd_record_stream is not None:
                self._sd_record_stream.stop()
                self._sd_record_stream.close()
                self._sd_record_stream = None
            data = (
                np.concatenate(self._record_frames, axis=0)
                if self._record_frames else np.zeros((0, self._record_channels), dtype="float32")
            )

        self._record_frames = []
        if len(data) == 0:
            messagebox.showinfo("Nada gravado", "Não capturei áudio nenhum durante a gravação.")
            return
        self._use_audio_data(data, self._record_sr, "gravado do PC")

    # ---------- waveform: envelope, grade, zoom, drag ----------

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
        self.canvas.create_line(
            end_x, 0, end_x, self.canvas_height, fill=END_COLOR, width=2, tags="marker", dash=(4, 2),
        )
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
        self.draw_markers()

    def _x_to_sec(self, x):
        x = min(max(x, 0), self.canvas_width)
        return self.view_start + (x / self.canvas_width) * (self.view_end - self.view_start)

    def on_bounds_change(self, _evt=None):
        self.draw_markers()

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

    # ---------- pads: atribuir, selecionar, disparar ----------

    def preview_staging(self):
        if self.data is None:
            return
        chunk = self._build_chunk_from_staging()
        if chunk is None:
            return
        self.cmd_queue.put(("start", "__preview__", chunk, "oneshot"))

    def _build_chunk_from_staging(self):
        start = int(self.start_var.get() * self.samplerate)
        end = int(self.end_var.get() * self.samplerate)
        if end - start < 100:
            messagebox.showwarning("Corte inválido", "Marque um trecho maior na waveform.")
            return None
        chunk = self.data[start:end].copy()
        semitones = self.pitch_knob.get()
        if semitones != 0:
            rate = 2 ** (semitones / 12)
            chunk = _resample_pitch(chunk, rate)
        if self.samplerate != SR:
            chunk = _resample_rate(chunk, self.samplerate, SR)
        return _make_seamless_edges(chunk, SR)

    def assign_to_selected_pad(self):
        if self.data is None:
            messagebox.showwarning("Nada carregado", "Carregue ou grave um áudio primeiro.")
            return
        chunk = self._build_chunk_from_staging()
        if chunk is None:
            return
        pad = self.pads[self.selected_pad_key]
        pad.buffer = chunk.astype("float32")
        pad.label = f"{self.start_var.get():.2f}-{self.end_var.get():.2f}s"
        self._refresh_pad_buttons()
        self._refresh_pad_label()

    def select_pad(self, key):
        self.selected_pad_key = key
        pad = self.pads[key]
        self._refresh_pad_buttons()
        self._refresh_pad_label()
        for mode, btn in self.mode_buttons.items():
            active = mode == pad.mode
            btn.config(bg=ORANGE if active else CREAM_DARK, fg="white" if active else INK)
        self.pad_volume_knob.set(pad.volume)

    def _refresh_pad_label(self):
        pad = self.pads[self.selected_pad_key]
        status = pad.label if pad.assigned else "vazio"
        self.pad_label.config(text=f"Pad [{self.selected_pad_key.upper()}] — {status}")

    def _refresh_pad_buttons(self):
        for key, btn in self.pad_buttons.items():
            pad = self.pads[key]
            is_selected = key == self.selected_pad_key
            btn.config(
                text=f"{key.upper()}\n{pad.label if pad.assigned else '—'}",
                bg=ORANGE if pad.assigned else CREAM_DARK,
                fg="white" if pad.assigned else INK,
                highlightthickness=3,
                highlightbackground=(SELECT_COLOR if is_selected else INK),
            )

    def set_pad_mode(self, mode):
        pad = self.pads[self.selected_pad_key]
        pad.mode = mode
        for m, btn in self.mode_buttons.items():
            active = m == mode
            btn.config(bg=ORANGE if active else CREAM_DARK, fg="white" if active else INK)

    def on_pad_volume_change(self, value):
        pad = self.pads[self.selected_pad_key]
        pad.volume = value

    def _on_pad_press(self, key):
        self.select_pad(key)
        self._trigger_key_on(key)

    def _on_pad_release(self, key):
        self._trigger_key_off(key)

    def _on_keydown(self, event):
        key = event.keysym.lower()
        if key not in self.pads or key in self._pressed_keys:
            return
        self._pressed_keys.add(key)
        self.select_pad(key)
        self._trigger_key_on(key)

    def _on_keyup(self, event):
        key = event.keysym.lower()
        if key not in self.pads:
            return
        self._pressed_keys.discard(key)
        self._trigger_key_off(key)

    def _trigger_key_on(self, key):
        pad = self.pads[key]
        if not pad.assigned:
            return
        buf = pad.buffer * pad.volume
        if pad.mode == "hold":
            self.cmd_queue.put(("start", key, buf, "hold"))
            self._held_keys.add(key)
        elif pad.mode == "loop":
            if key in self._looping_keys:
                self.cmd_queue.put(("stop", key))
                self._looping_keys.discard(key)
            else:
                self.cmd_queue.put(("start", key, buf, "loop"))
                self._looping_keys.add(key)
        else:
            self.cmd_queue.put(("start", key, buf, "oneshot"))

    def _trigger_key_off(self, key):
        pad = self.pads.get(key)
        if pad is None:
            return
        if pad.mode == "hold" and key in self._held_keys:
            self.cmd_queue.put(("stop", key))
            self._held_keys.discard(key)

    # ---------- motor de audio ----------

    def _audio_callback(self, outdata, frames, time_info, status):
        while True:
            try:
                cmd = self.cmd_queue.get_nowait()
            except queue.Empty:
                break
            if cmd[0] == "start":
                _, key, buf, mode = cmd
                self.voices.append({"key": key, "mode": mode, "buf": buf, "pos": 0, "stopping": False})
            elif cmd[0] == "stop":
                _, key = cmd
                for v in self.voices:
                    if v["key"] == key and v["mode"] in ("hold", "loop") and not v["stopping"]:
                        n = len(v["buf"])
                        pos = v["pos"]
                        fade_len = min(FADE_SAMPLES, n - pos)
                        if fade_len > 0:
                            tail = v["buf"][pos:pos + fade_len].copy()
                            ramp = np.linspace(1.0, 0.0, fade_len, dtype="float32").reshape(-1, 1)
                            tail *= ramp
                            v["buf"] = np.concatenate([v["buf"][:pos], tail])
                        v["stopping"] = True

        out = np.zeros((frames, 2), dtype="float32")
        still_alive = []
        for v in self.voices:
            buf = v["buf"]
            n = len(buf)
            pos = v["pos"]
            idx = 0
            keep = True
            while idx < frames:
                take = min(n - pos, frames - idx)
                if take <= 0:
                    if v["mode"] == "loop" and not v["stopping"]:
                        pos = 0
                        continue
                    keep = False
                    break
                out[idx:idx + take] += buf[pos:pos + take]
                idx += take
                pos += take
                if pos >= n:
                    if v["mode"] == "loop" and not v["stopping"]:
                        pos = 0
                    else:
                        keep = False
                        break
            v["pos"] = pos
            if keep:
                still_alive.append(v)
        self.voices = still_alive[-64:]

        np.clip(out, -1.0, 1.0, out=out)
        outdata[:] = out


def main():
    root = tk.Tk()
    PadSamplerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
