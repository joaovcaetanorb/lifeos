"""Prototipo de tela: drum machine / step sequencer.

Janela separada do loop sampler (main.py) - nao compartilha o motor de
audio, so a estetica (Knob, IconButton, paleta de cores). Os sons de
kick/snare/hat/perc sao sintetizados na hora (sem precisar carregar
sample), so pra dar pra sentir o groove/swing tocando de verdade.

O agendamento dos steps usa root.after() (timer da GUI), nao um clock
sample-accurate dentro do callback de audio como o plano completo
(Fase 2) pede - e uma simplificacao aceitavel para um prototipo visual,
com alguns milissegundos de jitter perceptiveis em BPMs muito altos.
"""

import json
import os
import queue
import tkinter as tk
from tkinter import filedialog, messagebox

import numpy as np
import sounddevice as sd
import soundfile as sf

from main import (
    CREAM, CREAM_DARK, INK, GRAY_TXT, ORANGE, FONT_UI, FONT_UI_BOLD,
    BG_COLOR, WAVE_COLOR, START_COLOR, END_COLOR, Knob, IconButton,
)

SR = 44100
ROWS = ["KICK", "SNARE", "HAT", "PERC"]
STEPS = 16


def _make_kick():
    dur = 0.18
    t = np.arange(int(SR * dur)) / SR
    freq = 150 * np.exp(-t * 18) + 45
    phase = 2 * np.pi * np.cumsum(freq) / SR
    env = np.exp(-t * 14)
    return (np.sin(phase) * env * 0.95).astype("float32")


def _make_snare():
    dur = 0.15
    n = int(SR * dur)
    t = np.arange(n) / SR
    noise = np.random.uniform(-1, 1, n)
    tone = np.sin(2 * np.pi * 180 * t) * np.exp(-t * 30) * 0.5
    return (noise * np.exp(-t * 22) * 0.8 + tone).astype("float32")


def _make_hat():
    dur = 0.06
    n = int(SR * dur)
    t = np.arange(n) / SR
    noise = np.random.uniform(-1, 1, n)
    return (noise * np.exp(-t * 60) * 0.7).astype("float32")


def _make_perc():
    dur = 0.12
    t = np.arange(int(SR * dur)) / SR
    freq = 500 * np.exp(-t * 10) + 250
    phase = 2 * np.pi * np.cumsum(freq) / SR
    env = np.exp(-t * 18)
    return (np.sin(phase) * env * 0.8).astype("float32")


def _make_click(accent=False):
    dur = 0.03
    n = int(SR * dur)
    t = np.arange(n) / SR
    freq = 1500 if accent else 1000
    return (np.sin(2 * np.pi * freq * t) * np.exp(-t * 80) * 0.6).astype("float32")


SOUND_FACTORY = {"KICK": _make_kick, "SNARE": _make_snare, "HAT": _make_hat, "PERC": _make_perc}

DEFAULT_PATTERN = {
    "KICK": {0, 4, 8, 12},
    "SNARE": {4, 12},
    "HAT": {0, 2, 4, 6, 8, 10, 12, 14},
    "PERC": set(),
}

SELECT_COLOR = "#1E88E5"
PARAM_RANGES = {"volume": (0.2, 1.5), "offset": (0, 45), "rate": (0.5, 2.0)}
PARAM_LABELS = {"volume": "VOLUME", "offset": "NUDGE", "rate": "VELOC."}
PARAM_ORDER = ["volume", "offset", "rate"]
GROUP_OFF_COLORS = ["#E4DEC9", "#D6CEB2", "#C6BC9C", "#B7AD8B"]
ROW_SELECT_COLOR = "#FFD9A0"


def _group_off_color(col):
    return GROUP_OFF_COLORS[(col // 4) % len(GROUP_OFF_COLORS)]


def _default_cell():
    return {"on": False, "offset": 0.0, "volume": 1.0, "rate": 1.0}


def _resample_rate(data, orig_sr, target_sr):
    if orig_sr == target_sr:
        return data.astype("float32")
    n = len(data)
    new_n = max(1, int(n * target_sr / orig_sr))
    positions = np.linspace(0, n - 1, new_n)
    return np.interp(positions, np.arange(n), data).astype("float32")


class SampleEditorDialog:
    """Editor de som por pad: carregar WAV proprio, chopar na waveform, ajustar pitch."""

    def __init__(self, parent, row, on_apply):
        self.row = row
        self.on_apply = on_apply
        self.data = None
        self.duration = 0.0
        self.start = 0.0
        self.end = 0.0
        self.drag_target = None
        self.reversed = False

        self.top = tk.Toplevel(parent)
        self.top.title(f"Editar som — {row}")
        self.top.configure(bg=CREAM)
        self.top.resizable(False, False)
        self.top.protocol("WM_DELETE_WINDOW", self.top.destroy)

        outer = tk.Frame(self.top, bg=CREAM, highlightthickness=3, highlightbackground=INK)
        outer.pack(padx=10, pady=10)

        tk.Label(outer, text=f"Som do pad: {row}", font=FONT_UI_BOLD, bg=CREAM, fg=INK).pack(pady=(12, 4))
        self._make_button(outer, "Carregar áudio", self.load_file).pack(pady=4)
        self.info_label = tk.Label(
            outer, text="usando som sintetizado padrão", font=FONT_UI, bg=CREAM, fg=GRAY_TXT,
        )
        self.info_label.pack(pady=(0, 6))

        self.canvas_w, self.canvas_h = 420, 120
        self.canvas = tk.Canvas(
            outer, width=self.canvas_w, height=self.canvas_h,
            bg=BG_COLOR, highlightthickness=2, highlightbackground=INK,
        )
        self.canvas.pack(padx=12, pady=6)
        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        tk.Label(
            outer, text="arraste as linhas vermelhas pra cortar (início/fim)",
            font=("Consolas", 7), bg=CREAM, fg=GRAY_TXT,
        ).pack()

        knobs_row = tk.Frame(outer, bg=CREAM)
        knobs_row.pack(pady=8)
        self.pitch_knob = Knob(knobs_row, "PITCH", -24, 24, value=0, resolution=1, command=lambda v: None, size=44)
        self.pitch_knob.pack(side="left", padx=8)
        self.volume_knob = Knob(knobs_row, "VOLUME", 0.2, 1.5, value=1.0, resolution=0.05, command=lambda v: None, size=44)
        self.volume_knob.pack(side="left", padx=8)
        self.decay_knob = Knob(knobs_row, "TAMANHO", 5, 300, value=5, resolution=5, command=lambda v: None, size=44)
        self.decay_knob.pack(side="left", padx=8)

        self.reverse_btn = tk.Button(
            outer, text="🔁 Reverter: OFF", font=FONT_UI, relief="flat", bd=0, takefocus=0,
            bg=CREAM_DARK, fg=INK, padx=10, pady=4, command=self.toggle_reverse,
        )
        self.reverse_btn.pack(pady=(0, 8))

        btn_row = tk.Frame(outer, bg=CREAM)
        btn_row.pack(pady=(4, 12))
        self._make_button(btn_row, "▶ Ouvir", self.preview).grid(row=0, column=0, padx=6)
        self._make_button(btn_row, "Usar este som", self.apply, accent=True).grid(row=0, column=1, padx=6)
        self._make_button(btn_row, "Cancelar", self.top.destroy).grid(row=0, column=2, padx=6)

        self.top.update_idletasks()
        w, h = self.top.winfo_width(), self.top.winfo_height()
        px = parent.winfo_rootx() + (parent.winfo_width() - w) // 2
        py = parent.winfo_rooty() + (parent.winfo_height() - h) // 2
        self.top.geometry(f"+{max(0, px)}+{max(0, py)}")

        self.top.transient(parent)
        self.top.grab_set()
        self.top.focus_set()

    @staticmethod
    def _make_button(parent, text, command, accent=False):
        kwargs = dict(text=text, command=command, relief="flat", bd=0, font=FONT_UI_BOLD, padx=10, pady=4, cursor="hand2")
        if accent:
            kwargs.update(bg=ORANGE, fg="white", activebackground="#e64f18", activeforeground="white")
        else:
            kwargs.update(bg=CREAM_DARK, fg=INK, activebackground=CREAM, activeforeground=INK)
        return tk.Button(parent, **kwargs)

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
        mono = data.mean(axis=1)
        mono = _resample_rate(mono, sr, SR)
        self.data = mono
        self.duration = len(mono) / SR
        self.start = 0.0
        self.end = self.duration
        name = path.replace("\\", "/").rsplit("/", 1)[-1]
        self.info_label.config(text=f"{name} — {self.duration:.2f}s")
        self._compute_envelope()
        self._draw_waveform()

    def _compute_envelope(self):
        width = self.canvas_w
        n = len(self.data)
        edges = np.linspace(0, n, width + 1).astype(int)
        mins = np.empty(width, dtype="float32")
        maxs = np.empty(width, dtype="float32")
        for i in range(width):
            a, b = edges[i], max(edges[i] + 1, edges[i + 1])
            chunk = self.data[a:b]
            mins[i] = chunk.min()
            maxs[i] = chunk.max()
        self.env_min, self.env_max = mins, maxs

    def _draw_waveform(self):
        self.canvas.delete("all")
        mid = self.canvas_h / 2
        half = self.canvas_h / 2 - 4
        for x in range(self.canvas_w):
            y1 = mid - self.env_max[x] * half
            y2 = mid - self.env_min[x] * half
            self.canvas.create_line(x, y1, x, y2, fill=WAVE_COLOR)
        self._draw_markers()

    def _draw_markers(self):
        self.canvas.delete("marker")
        if self.duration <= 0:
            return
        sx = (self.start / self.duration) * self.canvas_w
        ex = (self.end / self.duration) * self.canvas_w
        self.canvas.create_line(sx, 0, sx, self.canvas_h, fill=START_COLOR, width=2, tags="marker")
        self.canvas.create_line(ex, 0, ex, self.canvas_h, fill=END_COLOR, width=2, dash=(4, 2), tags="marker")

    def on_press(self, event):
        if self.duration <= 0:
            return
        sx = (self.start / self.duration) * self.canvas_w
        ex = (self.end / self.duration) * self.canvas_w
        self.drag_target = "start" if abs(event.x - sx) <= abs(event.x - ex) else "end"

    def on_drag(self, event):
        if self.duration <= 0 or self.drag_target is None:
            return
        t = max(0, min(self.canvas_w, event.x)) / self.canvas_w * self.duration
        if self.drag_target == "start":
            self.start = min(t, self.end - 0.01)
        else:
            self.end = max(t, self.start + 0.01)
        self._draw_waveform()

    def toggle_reverse(self):
        self.reversed = not self.reversed
        self.reverse_btn.config(
            text=f"🔁 Reverter: {'ON' if self.reversed else 'OFF'}",
            bg=ORANGE if self.reversed else CREAM_DARK,
            fg="white" if self.reversed else INK,
        )

    def _render(self):
        chunk = self.data[int(self.start * SR):int(self.end * SR)].copy()
        semitones = self.pitch_knob.get()
        if semitones != 0:
            rate = 2 ** (semitones / 12)
            n = len(chunk)
            new_n = max(1, int(n / rate))
            positions = np.linspace(0, n - 1, new_n)
            chunk = np.interp(positions, np.arange(n), chunk).astype("float32")

        decay_ms = self.decay_knob.get()
        fade = min(int(decay_ms / 1000 * SR), len(chunk) - 1)
        if fade > 0:
            ramp = np.linspace(1.0, 0.0, fade, dtype="float32")
            chunk[-fade:] *= ramp

        volume = self.volume_knob.get()
        if volume != 1.0:
            chunk = chunk * volume

        if self.reversed:
            chunk = chunk[::-1].copy()

        return chunk.astype("float32")

    def preview(self):
        if self.data is None:
            messagebox.showinfo("Nada carregado", "Carregue um áudio primeiro.")
            return
        sd.play(self._render(), SR)

    def apply(self):
        if self.data is None:
            messagebox.showinfo("Nada carregado", "Carregue um áudio antes de usar.")
            return
        self.on_apply(self._render())
        self.top.destroy()


class DrumProto:
    def __init__(self, root, container=None):
        self.root = root
        parent = container if container is not None else root
        if container is None:
            self.root.title("Drum Machine - Prototipo")

        self.sounds = {row: factory() for row, factory in SOUND_FACTORY.items()}
        self.custom_sound_rows = set()
        self.metro_click = _make_click(False)
        self.metro_click_accent = _make_click(True)
        self.metronome_on = False

        self.cell_data = {row: [_default_cell() for _ in range(STEPS)] for row in ROWS}
        for row in ROWS:
            for c in DEFAULT_PATTERN[row]:
                self.cell_data[row][c]["on"] = True
        self.cells = {row: [] for row in ROWS}
        self.row_labels = {}
        self.rows_selected = set()
        self.bar_rects = []
        self.ticks = []
        self.selected = ("KICK", 0)
        self.edit_param = "volume"
        self.editor_collapsed = False

        self.playing = False
        self.current_step = 0
        self._after_id = None
        self.voices = []
        self.cmd_queue = queue.Queue()

        self.stream = sd.OutputStream(samplerate=SR, channels=1, dtype="float32", blocksize=256, callback=self._audio_callback)
        self.stream.start()

        self.root.bind_all("<space>", self._on_space)

        outer = tk.Frame(parent, bg=CREAM, highlightthickness=3, highlightbackground=INK)
        outer.pack(padx=14, pady=14)

        cell = 34
        grid_w = cell * STEPS

        header = tk.Canvas(outer, width=grid_w + 140, height=54, bg=CREAM, highlightthickness=0)
        header.pack(pady=(12, 4), padx=12)
        self._draw_screw(header, 16, 27)
        self._draw_screw(header, grid_w + 124, 27)
        header.create_text(36, 12, text="LOOP//1", anchor="nw", font=("Arial", 18, "bold"), fill=INK)
        header.create_text(36, 36, text="drum machine — prototipo", anchor="nw", font=("Consolas", 8), fill=GRAY_TXT)
        bx0, bx1 = grid_w + 124 - 120, grid_w + 124 - 4
        header.create_rectangle(bx0, 16, bx1, 38, outline=ORANGE, width=2)
        header.create_text((bx0 + bx1) / 2, 27, text="MODE: SEQ", font=("Consolas", 8, "bold"), fill=ORANGE)

        transport_bar = tk.Frame(outer, bg=CREAM)
        transport_bar.pack(pady=(0, 10))
        IconButton(transport_bar, "play", "PLAY", self.play, accent=True, size=40).grid(row=0, column=0, padx=8)
        IconButton(transport_bar, "stop", "STOP", self.stop, size=40).grid(row=0, column=1, padx=8)
        self.bpm_knob = Knob(transport_bar, "BPM", 60, 180, value=92, resolution=1, command=lambda v: None, size=44)
        self.bpm_knob.grid(row=0, column=2, padx=14)
        self.swing_knob = Knob(transport_bar, "SWING", 50, 75, value=50, resolution=1, command=lambda v: None, size=44)
        self.swing_knob.grid(row=0, column=3, padx=14)
        self.metro_btn = tk.Button(
            transport_bar, text="Metrônomo: OFF", font=FONT_UI, relief="flat", bd=0, takefocus=0,
            bg=CREAM_DARK, fg=INK, padx=10, pady=4, command=self.toggle_metronome,
        )
        self.metro_btn.grid(row=0, column=4, padx=(14, 0))
        tk.Label(
            transport_bar, text="espaço\n= play/pause", font=("Consolas", 7), bg=CREAM, fg=GRAY_TXT, justify="center",
        ).grid(row=0, column=5, padx=(14, 0))

        kit_row = tk.Frame(outer, bg=CREAM)
        kit_row.pack(pady=(0, 6))
        self._make_button(kit_row, "💾 Salvar", self.save_pattern).grid(row=0, column=0, padx=6)
        self._make_button(kit_row, "📂 Carregar padrão", self.load_pattern).grid(row=0, column=1, padx=6)

        grid_frame = tk.Frame(outer, bg=CREAM)
        grid_frame.pack(padx=12)

        label_col = tk.Frame(grid_frame, bg=CREAM)
        label_col.grid(row=0, column=0, rowspan=len(ROWS) + 1, sticky="n")
        tk.Label(label_col, text="", bg=CREAM, height=1).pack()
        for row in ROWS:
            lbl = tk.Button(
                label_col, text=row, bg=CREAM, fg=INK, font=FONT_UI_BOLD, width=7, anchor="w",
                relief="flat", bd=0, takefocus=0, command=lambda r=row: self.toggle_row_selection(r),
            )
            lbl.bind("<Button-3>", lambda e, r=row: self.open_sample_editor(r))
            lbl.pack(pady=1)
            self.row_labels[row] = lbl

        steps_col = tk.Frame(grid_frame, bg=CREAM)
        steps_col.grid(row=0, column=1)

        self.playhead_canvas = tk.Canvas(steps_col, width=grid_w, height=10, bg=CREAM, highlightthickness=0)
        self.playhead_canvas.pack(pady=(0, 2))
        for c in range(STEPS):
            tick_id = self.playhead_canvas.create_rectangle(
                c * cell + 2, 1, c * cell + cell - 2, 8, fill=CREAM_DARK, outline="",
            )
            self.ticks.append(tick_id)

        self.cell_px = cell
        for row in ROWS:
            row_frame = tk.Frame(steps_col, bg=CREAM)
            row_frame.pack(pady=1)
            for c in range(STEPS):
                accent = (c % 4 == 0)
                btn = tk.Button(
                    row_frame, width=2, height=1, relief="flat", bd=1, takefocus=0,
                    highlightthickness=2, highlightbackground=(INK if accent else CREAM_DARK),
                    command=lambda r=row, c=c: self.toggle_cell(r, c),
                )
                btn.bind("<Button-3>", lambda e, r=row, c=c: self.select_cell(r, c))
                btn.grid(row=0, column=c, padx=1)
                self.cells[row].append(btn)
        self._refresh_all_cells()

        tk.Frame(outer, bg=INK, height=2).pack(fill="x", padx=12, pady=(12, 0))

        editor = tk.Frame(outer, bg=CREAM_DARK, highlightthickness=2, highlightbackground=INK)
        editor.pack(padx=12, pady=12, fill="x")

        editor_header = tk.Frame(editor, bg=CREAM_DARK)
        editor_header.pack(fill="x", padx=10, pady=(8, 4))
        self.collapse_btn = tk.Button(
            editor_header, text="▾", font=FONT_UI_BOLD, relief="flat", bd=0, takefocus=0,
            bg=CREAM_DARK, fg=INK, command=self.toggle_editor_collapsed, width=2,
        )
        self.collapse_btn.pack(side="left")
        tk.Label(
            editor_header, text="EDITOR DE NOTA", font=("Consolas", 8, "bold"), bg=CREAM_DARK, fg=GRAY_TXT,
        ).pack(side="left", padx=(4, 0))
        self.note_label = tk.Label(editor_header, text="", font=FONT_UI_BOLD, bg=CREAM_DARK, fg=INK)
        self.note_label.pack(side="left", padx=(14, 0))

        self.param_buttons = {}
        tabs = tk.Frame(editor_header, bg=CREAM_DARK)
        tabs.pack(side="right")
        for param in PARAM_ORDER:
            btn = tk.Button(
                tabs, text=PARAM_LABELS[param], font=FONT_UI_BOLD, relief="flat", bd=0, takefocus=0,
                padx=8, pady=3, command=lambda p=param: self.set_edit_param(p),
            )
            btn.pack(side="left", padx=2)
            self.param_buttons[param] = btn

        self.bar_h = 64
        self.bar_wrap = tk.Frame(editor, bg=CREAM_DARK)
        self.bar_wrap.pack(padx=10, pady=(0, 10))
        self.bar_canvas = tk.Canvas(
            self.bar_wrap, width=grid_w, height=self.bar_h, bg=CREAM, highlightthickness=1, highlightbackground=INK,
        )
        self.bar_canvas.pack()
        for c in range(STEPS):
            rect_id = self.bar_canvas.create_rectangle(
                c * cell + 3, self.bar_h, c * cell + cell - 3, self.bar_h, fill=CREAM_DARK, outline="",
            )
            self.bar_rects.append(rect_id)
        self.bar_canvas.bind("<ButtonPress-1>", self._on_bar_drag)
        self.bar_canvas.bind("<B1-Motion>", self._on_bar_drag)
        self.hint_label = tk.Label(
            editor, text="clique direito numa célula pra escolher qual linha aparece aqui embaixo",
            font=("Consolas", 7), bg=CREAM_DARK, fg=GRAY_TXT,
        )
        self.hint_label.pack(pady=(0, 8))

        self._style_param_buttons()
        self._style_row_labels()
        self.select_cell(*self.selected)

    @staticmethod
    def _draw_screw(canvas, cx, cy, r=7):
        canvas.create_oval(cx - r, cy - r, cx + r, cy + r, fill=CREAM_DARK, outline=INK, width=1)
        canvas.create_line(cx - r * 0.6, cy, cx + r * 0.6, cy, fill=INK, width=1)

    @staticmethod
    def _make_button(parent, text, command):
        return tk.Button(
            parent, text=text, command=command, relief="flat", bd=0, font=FONT_UI_BOLD,
            padx=10, pady=4, cursor="hand2", bg=CREAM_DARK, fg=INK,
            activebackground=CREAM, activeforeground=INK, takefocus=0,
        )

    def open_sample_editor(self, row):
        SampleEditorDialog(self.root, row, lambda buf, r=row: self._set_row_sound(r, buf))

    def _set_row_sound(self, row, buf):
        self.sounds[row] = buf
        self.custom_sound_rows.add(row)

    def save_pattern(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".json", filetypes=[("Pattern JSON", "*.json")], initialfile="drum_pattern.json",
        )
        if not path:
            return
        base_dir = os.path.dirname(path)
        base_name = os.path.splitext(os.path.basename(path))[0]

        rows_state = {}
        for row in ROWS:
            custom_wav = None
            if row in self.custom_sound_rows:
                custom_wav = f"{base_name}_{row}.wav"
                try:
                    sf.write(os.path.join(base_dir, custom_wav), self.sounds[row], SR)
                except Exception as exc:
                    messagebox.showerror("Erro ao salvar", f"Não consegui salvar o som de {row}:\n{exc}")
                    return
            rows_state[row] = {"cells": self.cell_data[row], "custom_sound_wav": custom_wav}

        state = {
            "version": 1,
            "bpm": self.bpm_knob.get(),
            "swing": self.swing_knob.get(),
            "metronome_on": self.metronome_on,
            "rows": rows_state,
        }
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2)
        except Exception as exc:
            messagebox.showerror("Erro ao salvar", f"Não consegui salvar o padrão:\n{exc}")
            return
        messagebox.showinfo("Salvo", f"Padrão salvo em:\n{path}")

    def load_pattern(self):
        path = filedialog.askopenfilename(filetypes=[("Pattern JSON", "*.json"), ("Todos", "*.*")])
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                state = json.load(f)
        except Exception as exc:
            messagebox.showerror("Erro ao carregar", f"Não consegui ler o padrão:\n{exc}")
            return

        self.bpm_knob.set(state.get("bpm", 92))
        self.swing_knob.set(state.get("swing", 50))
        self.metronome_on = state.get("metronome_on", False)
        self.metro_btn.config(
            text=f"Metrônomo: {'ON' if self.metronome_on else 'OFF'}",
            bg=ORANGE if self.metronome_on else CREAM_DARK,
            fg="white" if self.metronome_on else INK,
        )

        base_dir = os.path.dirname(path)
        self.custom_sound_rows = set()
        for row in ROWS:
            row_state = state.get("rows", {}).get(row)
            if not row_state:
                continue
            cells = row_state.get("cells")
            if cells:
                self.cell_data[row] = cells
            custom_wav = row_state.get("custom_sound_wav")
            if custom_wav:
                wav_path = os.path.join(base_dir, custom_wav)
                try:
                    data, sr = sf.read(wav_path, always_2d=True, dtype="float32")
                    mono = data.mean(axis=1)
                    self.sounds[row] = _resample_rate(mono, sr, SR)
                    self.custom_sound_rows.add(row)
                except Exception as exc:
                    messagebox.showwarning("Aviso", f"Não consegui carregar o som de {row}:\n{exc}")

        self.selected = ("KICK", 0)
        self._refresh_all_cells()
        self._refresh_bar_lane()
        messagebox.showinfo("Carregado", f"Padrão carregado de:\n{path}")

    def toggle_row_selection(self, row):
        if row in self.rows_selected:
            self.rows_selected.discard(row)
        else:
            self.rows_selected.add(row)
        self._style_row_labels()

    def _style_row_labels(self):
        for row, lbl in self.row_labels.items():
            lbl.config(bg=ROW_SELECT_COLOR if row in self.rows_selected else CREAM)

    def toggle_cell(self, row, col):
        targets = self.rows_selected if self.rows_selected else {row}
        new_state = not self.cell_data[row][col]["on"]
        for r in targets:
            self.cell_data[r][col]["on"] = new_state
        self.selected = (row, col)
        self._refresh_all_cells()
        self._refresh_bar_lane()

    def select_cell(self, row, col):
        self.selected = (row, col)
        self._refresh_all_cells()
        self._refresh_bar_lane()

    def toggle_editor_collapsed(self):
        self.editor_collapsed = not self.editor_collapsed
        if self.editor_collapsed:
            self.bar_wrap.pack_forget()
            self.hint_label.pack_forget()
            self.collapse_btn.config(text="▸")
        else:
            self.bar_wrap.pack(padx=10, pady=(0, 10))
            self.hint_label.pack(pady=(0, 8))
            self.collapse_btn.config(text="▾")

    def set_edit_param(self, param):
        self.edit_param = param
        self._style_param_buttons()
        self._refresh_bar_lane()

    def _style_param_buttons(self):
        for param, btn in self.param_buttons.items():
            active = param == self.edit_param
            btn.config(bg=ORANGE if active else CREAM, fg="white" if active else INK)

    def _refresh_all_cells(self):
        for row in ROWS:
            for c in range(STEPS):
                self._style_cell(row, c)

    def _style_cell(self, row, col):
        data = self.cell_data[row][col]
        btn = self.cells[row][col]
        is_selected = self.selected == (row, col)
        accent = (col % 4 == 0)
        btn.config(
            bg=(ORANGE if data["on"] else _group_off_color(col)),
            highlightbackground=(SELECT_COLOR if is_selected else (INK if accent else CREAM_DARK)),
        )

    def _value_to_height(self, param, value):
        lo, hi = PARAM_RANGES[param]
        frac = (value - lo) / (hi - lo)
        frac = max(0.0, min(1.0, frac))
        return max(2, frac * self.bar_h)

    def _height_to_value(self, param, frac):
        lo, hi = PARAM_RANGES[param]
        frac = max(0.0, min(1.0, frac))
        return lo + frac * (hi - lo)

    def _refresh_bar_lane(self):
        row, sel_col = self.selected
        for c in range(STEPS):
            data = self.cell_data[row][c]
            value = data[self.edit_param]
            h = self._value_to_height(self.edit_param, value)
            x0 = c * self.cell_px + 3
            x1 = c * self.cell_px + self.cell_px - 3
            y0 = self.bar_h - h
            color = ORANGE if data["on"] else _group_off_color(c)
            is_selected = c == sel_col
            self.bar_canvas.coords(self.bar_rects[c], x0, y0, x1, self.bar_h)
            self.bar_canvas.itemconfig(
                self.bar_rects[c], fill=color, outline=(SELECT_COLOR if is_selected else ""), width=2,
            )
        value = self.cell_data[row][sel_col][self.edit_param]
        self.note_label.config(text=f"{row} · step {sel_col + 1} · {PARAM_LABELS[self.edit_param]} {value:.2f}")

    def _on_bar_drag(self, event):
        row = self.selected[0]
        col = max(0, min(STEPS - 1, int(event.x // self.cell_px)))
        frac = 1.0 - (event.y / self.bar_h)
        value = self._height_to_value(self.edit_param, frac)
        self.cell_data[row][col][self.edit_param] = value
        self.selected = (row, col)
        self._refresh_all_cells()
        self._refresh_bar_lane()

    def toggle_metronome(self):
        self.metronome_on = not self.metronome_on
        self.metro_btn.config(
            text=f"Metrônomo: {'ON' if self.metronome_on else 'OFF'}",
            bg=ORANGE if self.metronome_on else CREAM_DARK,
            fg="white" if self.metronome_on else INK,
        )

    def _on_space(self, _event):
        self.toggle_play()
        return "break"

    def toggle_play(self):
        if self.playing:
            self.stop()
        else:
            self.play()

    def _prepare_note_buffer(self, row, data):
        buf = self.sounds[row]
        rate = data["rate"]
        if rate != 1.0:
            n = len(buf)
            new_n = max(1, int(n / rate))
            positions = np.linspace(0, n - 1, new_n)
            buf = np.interp(positions, np.arange(n), buf).astype("float32")
        volume = data["volume"]
        if volume != 1.0:
            buf = buf * volume
        return buf.astype("float32")

    def _compute_deltas_ms(self):
        bpm = self.bpm_knob.get()
        swing = self.swing_knob.get() / 100.0
        beat_ms = 60000.0 / bpm
        eighth = beat_ms / 2
        times = []
        for i in range(STEPS):
            pair = i // 2
            base = pair * eighth
            t = base if i % 2 == 0 else base + eighth * swing
            times.append(t)
        bar_len = 4 * beat_ms
        deltas = []
        for i in range(STEPS):
            prev = times[i - 1] if i > 0 else times[-1] - bar_len
            deltas.append(times[i] - prev)
        return deltas

    def _trigger_step(self, i):
        if self.metronome_on and i % 4 == 0:
            self.cmd_queue.put(self.metro_click_accent if i == 0 else self.metro_click)
        for row in ROWS:
            data = self.cell_data[row][i]
            if not data["on"]:
                continue
            buf = self._prepare_note_buffer(row, data)
            delay = data["offset"]
            if delay <= 0:
                self.cmd_queue.put(buf)
            else:
                self.root.after(int(delay), lambda b=buf: self.cmd_queue.put(b))

    def _highlight_step(self, i):
        for c, tick_id in enumerate(self.ticks):
            self.playhead_canvas.itemconfig(tick_id, fill=(ORANGE if c == i else CREAM_DARK))

    def _tick(self):
        if not self.playing:
            return
        self._trigger_step(self.current_step)
        self._highlight_step(self.current_step)
        deltas = self._compute_deltas_ms()
        next_step = (self.current_step + 1) % STEPS
        delay = deltas[next_step]
        self.current_step = next_step
        self._after_id = self.root.after(max(1, int(delay)), self._tick)

    def play(self):
        if self.playing:
            return
        self.playing = True
        self.current_step = 0
        self._tick()

    def stop(self):
        self.playing = False
        if self._after_id is not None:
            self.root.after_cancel(self._after_id)
            self._after_id = None
        self._highlight_step(-1)

    def _audio_callback(self, outdata, frames, time_info, status):
        while True:
            try:
                buf = self.cmd_queue.get_nowait()
            except queue.Empty:
                break
            self.voices.append([buf, 0])

        out = np.zeros(frames, dtype="float32")
        still_alive = []
        for voice in self.voices:
            buf, pos = voice
            take = min(len(buf) - pos, frames)
            out[:take] += buf[pos:pos + take]
            pos += take
            if pos < len(buf):
                voice[1] = pos
                still_alive.append(voice)
        self.voices = still_alive
        np.clip(out, -1.0, 1.0, out=out)
        outdata[:, 0] = out


def main():
    root = tk.Tk()
    DrumProto(root)
    root.mainloop()


if __name__ == "__main__":
    main()
