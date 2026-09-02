"""Janela unica juntando o Loop Sampler e o Drum Machine.

Os dois modulos continuam existindo como arquivos separados
(main.py / drum_prototype.py) - aqui so encaixamos os dois dentro
de um tk.PanedWindow vertical, com um divisor arrastavel entre eles
pra redistribuir o espaco. O desenho de cada um (waveform, grade de
steps) ainda tem tamanho fixo em pixels - arrastar o divisor muda
quanto espaco cada secao GANHA, mas o conteudo em si nao estica
sozinho pra preencher esse espaco extra. Deixar isso responsivo de
verdade e um proximo passo, nao feito aqui ainda.
"""

import tkinter as tk

from main import LoopApp, CREAM, INK
from drum_prototype import DrumProto


def main():
    root = tk.Tk()
    root.title("LOOP//1 Studio")
    root.configure(bg=CREAM)
    root.geometry("760x900")

    paned = tk.PanedWindow(
        root, orient=tk.VERTICAL, sashrelief="raised", sashwidth=8,
        bg=CREAM, bd=0, showhandle=True, handlesize=10, handlepad=20,
    )
    paned.pack(fill="both", expand=True)

    top_frame = tk.Frame(paned, bg=CREAM)
    bottom_frame = tk.Frame(paned, bg=CREAM)
    paned.add(top_frame, minsize=200, stretch="always")
    paned.add(bottom_frame, minsize=200, stretch="always")

    LoopApp(root, container=top_frame)
    DrumProto(root, container=bottom_frame)

    root.mainloop()


if __name__ == "__main__":
    main()
