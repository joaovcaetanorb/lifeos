"""Primitivas de desenho compartilhadas pelos exportadores tipo Stories do
módulo música (relatorio_stories.py e album_story.py) — mesma paleta/fontes
de webapp/frontend/shared/tokens.css, cartão vertical 1080x1920. Extraído de
relatorio_stories.py pra não duplicar esses ~150 linhas quando o export de
álbum individual (album_story.py) precisou do mesmo kit visual.
"""

import math
import os

from PIL import Image, ImageDraw, ImageFont

LARGURA, ALTURA = 1080, 1920
MARGEM = 72
LARGURA_UTIL = LARGURA - 2 * MARGEM

# Mesma paleta de webapp/frontend/shared/tokens.css — hardcoded aqui (não
# importa utils.py de propósito: aquelas são as cores do tema Streamlit
# antigo, um pouco diferentes das do console novo).
BG = "#0B0D09"
PANEL = "#14170F"
HAIR = "#262920"
HAIR_BRIGHT = "#3a4030"
INK = "#E9E7DC"
INK_MUTED = "#8B8A82"
INK_DIM = "#57564f"
ACCENT = "#2E9E63"
ACCENT_BRIGHT = "#4ADE94"

_FONTS_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend", "shared", "fonts")
_JBM_REGULAR = os.path.join(_FONTS_DIR, "jbm-400.ttf")
_JBM_MEDIUM = os.path.join(_FONTS_DIR, "jbm-500.ttf")
_JBM_BOLD = os.path.join(_FONTS_DIR, "jbm-700.ttf")
_CP_REGULAR = os.path.join(_FONTS_DIR, "cp-400.ttf")
_CP_BOLD = os.path.join(_FONTS_DIR, "cp-700.ttf")


def jbm(tamanho: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(_JBM_BOLD if bold else _JBM_REGULAR, tamanho)


def cp(tamanho: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(_CP_BOLD if bold else _CP_REGULAR, tamanho)


# ---------------------------------------------------------------------------
# texto com tracking manual (letter-spacing) — pros rótulos "eyebrow" em
# caixa alta, que são uma marca registrada da identidade visual do app
# ---------------------------------------------------------------------------

def largura_rastreada(draw: ImageDraw.ImageDraw, texto: str, fonte: ImageFont.FreeTypeFont, tracking: float = 0) -> float:
    if not texto:
        return 0.0
    total = sum(draw.textlength(ch, font=fonte) for ch in texto)
    return total + tracking * (len(texto) - 1)


def texto_rastreado(draw: ImageDraw.ImageDraw, xy: tuple, texto: str, fonte: ImageFont.FreeTypeFont, cor, tracking: float = 0) -> float:
    x, y = xy
    for ch in texto:
        draw.text((x, y), ch, font=fonte, fill=cor)
        x += draw.textlength(ch, font=fonte) + tracking
    return x


def texto_rastreado_centralizado(draw: ImageDraw.ImageDraw, cx: float, y: float, texto: str, fonte: ImageFont.FreeTypeFont, cor, tracking: float = 0) -> None:
    largura = largura_rastreada(draw, texto, fonte, tracking)
    texto_rastreado(draw, (cx - largura / 2, y), texto, fonte, cor, tracking)


def texto_rastreado_direita(draw: ImageDraw.ImageDraw, x_direita: float, y: float, texto: str, fonte: ImageFont.FreeTypeFont, cor, tracking: float = 0) -> None:
    largura = largura_rastreada(draw, texto, fonte, tracking)
    texto_rastreado(draw, (x_direita - largura, y), texto, fonte, cor, tracking)


def altura_linha(fonte: ImageFont.FreeTypeFont) -> int:
    ascent, descent = fonte.getmetrics()
    return ascent + descent


# ---------------------------------------------------------------------------
# texto centralizado simples (sem tracking) — pra números/nomes grandes
# ---------------------------------------------------------------------------

def centralizado_x(draw: ImageDraw.ImageDraw, cx: float, y: float, texto: str, fonte: ImageFont.FreeTypeFont, cor) -> int:
    bbox = draw.textbbox((0, 0), texto, font=fonte)
    largura, altura = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = cx - largura / 2
    draw.text((x - bbox[0], y - bbox[1]), texto, font=fonte, fill=cor)
    return altura


def centralizado(draw: ImageDraw.ImageDraw, y: float, texto: str, fonte: ImageFont.FreeTypeFont, cor) -> int:
    return centralizado_x(draw, LARGURA / 2, y, texto, fonte, cor)


def largura_texto(draw: ImageDraw.ImageDraw, texto: str, fonte: ImageFont.FreeTypeFont) -> int:
    bbox = draw.textbbox((0, 0), texto, font=fonte)
    return bbox[2] - bbox[0]


def fonte_ajustada(draw: ImageDraw.ImageDraw, texto: str, bold: bool, tamanho_inicial: int,
                    largura_maxima: int = LARGURA_UTIL, tamanho_minimo: int = 26) -> tuple:
    tamanho = tamanho_inicial
    fonte = jbm(tamanho, bold)
    while tamanho > tamanho_minimo and largura_texto(draw, texto, fonte) > largura_maxima:
        tamanho -= 4
        fonte = jbm(tamanho, bold)
    if largura_texto(draw, texto, fonte) > largura_maxima:
        while texto and largura_texto(draw, texto + "…", fonte) > largura_maxima:
            texto = texto[:-1]
        texto = f"{texto}…" if texto else "…"
    return fonte, texto


def quebrar_paragrafo(draw: ImageDraw.ImageDraw, texto: str, fonte: ImageFont.FreeTypeFont, largura_maxima: int) -> list[str]:
    """Quebra um texto livre (review) em linhas que cabem em largura_maxima,
    respeitando quebras de parágrafo (\\n) já existentes no texto."""
    linhas = []
    for paragrafo in texto.splitlines() or [""]:
        palavras = paragrafo.split()
        if not palavras:
            linhas.append("")
            continue
        atual = palavras[0]
        for palavra in palavras[1:]:
            candidata = f"{atual} {palavra}"
            if largura_texto(draw, candidata, fonte) <= largura_maxima:
                atual = candidata
            else:
                linhas.append(atual)
                atual = palavra
        linhas.append(atual)
    return linhas


def paragrafo_centralizado(draw: ImageDraw.ImageDraw, y: float, texto: str, fonte: ImageFont.FreeTypeFont, cor,
                            largura_maxima: int = LARGURA_UTIL, max_linhas: int | None = None, gap: int = 10) -> float:
    """Desenha um parágrafo com quebra automática, cada linha centralizada.
    Retorna o y logo após a última linha desenhada."""
    linhas = quebrar_paragrafo(draw, texto, fonte, largura_maxima)
    if max_linhas is not None and len(linhas) > max_linhas:
        linhas = linhas[:max_linhas]
        ultima = linhas[-1]
        while linhas and largura_texto(draw, ultima + "…", fonte) > largura_maxima:
            ultima = ultima[:-1]
        linhas[-1] = f"{ultima}…"
    altura = altura_linha(fonte)
    for linha in linhas:
        centralizado(draw, y, linha, fonte, cor)
        y += altura + gap
    return y


# ---------------------------------------------------------------------------
# primitivas visuais — LED, eyebrow, painel com hairline, chip, estrelas
# ---------------------------------------------------------------------------

def led(draw: ImageDraw.ImageDraw, x: float, y: float, cor=ACCENT, r: int = 6) -> None:
    draw.ellipse([x, y, x + 2 * r, y + 2 * r], fill=cor)


def eyebrow(draw: ImageDraw.ImageDraw, x: float, y: float, texto: str, cor=INK_MUTED, tamanho: int = 22) -> None:
    fonte = cp(tamanho)
    texto_rastreado(draw, (x, y), texto.upper(), fonte, cor, tracking=3)


def modulo_cabecalho(draw: ImageDraw.ImageDraw, x: float, y: float, texto: str) -> int:
    """LED + eyebrow no canto, igual ao .module-head do frontend. Retorna
    a altura ocupada."""
    r = 5
    led(draw, x, y + 6, ACCENT, r)
    eyebrow(draw, x + 2 * r + 14, y, texto, INK_MUTED, 22)
    return 40


def chip(draw: ImageDraw.ImageDraw, cx_start: float, y: float, texto: str, fonte: ImageFont.FreeTypeFont) -> float:
    """Desenha uma pill (borda fina, cantos retos) começando em cx_start;
    retorna a posição x logo após o chip (pra empilhar chips numa linha)."""
    pad_x, pad_y = 20, 12
    largura = draw.textlength(texto, font=fonte)
    altura = altura_linha(fonte)
    x1, y1 = cx_start, y
    x2, y2 = x1 + largura + 2 * pad_x, y1 + altura + 2 * pad_y
    draw.rectangle([x1, y1, x2, y2], outline=HAIR_BRIGHT, width=2)
    draw.text((x1 + pad_x, y1 + pad_y - 2), texto, font=fonte, fill=INK_MUTED)
    return x2


def linha_chips_centralizada(draw: ImageDraw.ImageDraw, y: float, textos: list, fonte: ImageFont.FreeTypeFont, gap: int = 14) -> int:
    """Quebra os chips em linhas que cabem em LARGURA_UTIL, cada linha
    centralizada. Retorna a altura total ocupada."""
    pad_x, pad_y = 20, 12
    linha_atual, linhas = [], []
    largura_linha = 0
    for t in textos:
        largura_chip = draw.textlength(t, font=fonte) + 2 * pad_x
        acrescimo = largura_chip + (gap if linha_atual else 0)
        if linha_atual and largura_linha + acrescimo > LARGURA_UTIL:
            linhas.append(linha_atual)
            linha_atual, largura_linha = [], 0
            acrescimo = largura_chip
        linha_atual.append(t)
        largura_linha += acrescimo
    if linha_atual:
        linhas.append(linha_atual)

    altura_chip = altura_linha(fonte) + 2 * pad_y
    y_cursor = y
    for linha in linhas:
        largura_total = sum(draw.textlength(t, font=fonte) + 2 * pad_x for t in linha) + gap * (len(linha) - 1)
        x = LARGURA / 2 - largura_total / 2
        for t in linha:
            x = chip(draw, x, y_cursor, t, fonte) + gap
        y_cursor += altura_chip + 12
    return y_cursor - y - 12


def estrela_polygon(cx: float, cy: float, raio_ext: float, raio_int_frac: float = 0.42) -> list[tuple]:
    """Pontos de uma estrela de 5 pontas centrada em (cx, cy), pra desenhar
    com ImageDraw.polygon. raio_int_frac controla o quão "pontuda" ela é."""
    raio_int = raio_ext * raio_int_frac
    pontos = []
    for i in range(10):
        raio = raio_ext if i % 2 == 0 else raio_int
        angulo = math.pi / 2 + i * math.pi / 5  # ponta pra cima
        pontos.append((cx + raio * math.cos(angulo), cy - raio * math.sin(angulo)))
    return pontos


def linha_estrelas(imagem: Image.Image, draw: ImageDraw.ImageDraw, cx: float, y: float, nota: float, maximo: int = 5,
                    raio: float = 22, gap: float = 14, cor_cheia=ACCENT_BRIGHT, cor_vazia=HAIR_BRIGHT) -> float:
    """Desenha `maximo` estrelas centralizadas em cx, preenchidas
    proporcionalmente a `nota` (aceita fração — ex.: 4.5 preenche a 5ª
    estrela até a metade). Retorna a altura ocupada (2 * raio)."""
    largura_estrela = 2 * raio + gap
    largura_total = largura_estrela * maximo - gap
    x0 = cx - largura_total / 2
    for i in range(maximo):
        ex = x0 + i * largura_estrela + raio
        ey = y + raio
        pct = max(0.0, min(1.0, nota - i))
        draw.polygon(estrela_polygon(ex, ey, raio), fill=cor_vazia)
        if pct <= 0:
            continue
        if pct >= 1:
            draw.polygon(estrela_polygon(ex, ey, raio), fill=cor_cheia)
        else:
            # meia estrela (ou fração): desenha a cheia numa camada separada
            # e recorta só a fatia esquerda proporcional a pct via máscara.
            camada = Image.new("RGBA", imagem.size, (0, 0, 0, 0))
            ImageDraw.Draw(camada).polygon(estrela_polygon(ex, ey, raio), fill=cor_cheia)
            mascara = Image.new("L", imagem.size, 0)
            largura_fatia = int(2 * raio * pct)
            ImageDraw.Draw(mascara).rectangle([ex - raio, ey - raio, ex - raio + largura_fatia, ey + raio], fill=255)
            imagem.paste(camada, (0, 0), Image.composite(camada.split()[3], Image.new("L", imagem.size, 0), mascara))
    return 2 * raio


# ---------------------------------------------------------------------------
# fundo + scanlines
# ---------------------------------------------------------------------------

def fundo() -> Image.Image:
    """Fundo quase-preto com leve gradiente vertical (bg -> panel), igual
    ao body do frontend — evita a chapa lisa de uma cor só."""
    topo = tuple(int(BG[i:i + 2], 16) for i in (1, 3, 5))
    base = tuple(int(PANEL[i:i + 2], 16) for i in (1, 3, 5))
    img = Image.new("RGB", (LARGURA, ALTURA))
    draw = ImageDraw.Draw(img)
    for y in range(ALTURA):
        t = (y / ALTURA) ** 1.6  # a maior parte fica escura, só clareia perto do rodapé
        cor = tuple(int(topo[i] + (base[i] - topo[i]) * t * 0.35) for i in range(3))
        draw.line([(0, y), (LARGURA, y)], fill=cor)
    return img


def aplicar_scanlines(imagem: Image.Image) -> Image.Image:
    """Réplica do .scanlines do frontend: linhas horizontais de 1px bem
    sutis, a cada 3px."""
    overlay = Image.new("RGBA", imagem.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    for y in range(0, ALTURA, 3):
        draw.line([(0, y), (LARGURA, y)], fill=(255, 255, 255, 10))
    return Image.alpha_composite(imagem.convert("RGBA"), overlay).convert("RGB")


def bloco_topbar(imagem: Image.Image, draw: ImageDraw.ImageDraw, modulo_label: str, data_texto: str) -> int:
    """LED + 'LIFEOS · MÓDULO X' + data no canto direito + hairline —
    cabeçalho comum a todo cartão Stories do app. Retorna o y seguinte."""
    y = MARGEM
    led(draw, MARGEM, y + 6, ACCENT, 5)
    eyebrow(draw, MARGEM + 24, y, modulo_label, INK_DIM, 20)
    texto_rastreado_direita(draw, LARGURA - MARGEM, y, data_texto, cp(20), INK_DIM, tracking=2)
    y += 40
    draw.line([(MARGEM, y), (LARGURA - MARGEM, y)], fill=HAIR, width=2)
    return y + 48
