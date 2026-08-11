"""Monta um card vertical (1080x1920, proporção de Stories) com o resumo do
consumo real de música no período — visual "console/terminal" que espelha
webapp/frontend/shared/tokens.css (mesmas cores, mesma dupla de fontes
JetBrains Mono + Courier Prime, hairlines, scanlines) em vez do cartão
estilo "Spotify Wrapped" que a versão anterior usava — pra bater com a cara
do resto do frontend novo, não a do Streamlit antigo.
"""

import io
import os
from datetime import date

from PIL import Image, ImageDraw, ImageFont

from . import colagem

LARGURA, ALTURA = 1080, 1920
MARGEM = 72
LARGURA_UTIL = LARGURA - 2 * MARGEM
LADO_MOSAICO = 480

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


def _jbm(tamanho: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(_JBM_BOLD if bold else _JBM_REGULAR, tamanho)


def _cp(tamanho: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(_CP_BOLD if bold else _CP_REGULAR, tamanho)


# ---------------------------------------------------------------------------
# texto com tracking manual (letter-spacing) — pros rótulos "eyebrow" em
# caixa alta, que são uma marca registrada da identidade visual do app
# ---------------------------------------------------------------------------

def _largura_rastreada(draw: ImageDraw.ImageDraw, texto: str, fonte: ImageFont.FreeTypeFont, tracking: float = 0) -> float:
    if not texto:
        return 0.0
    total = sum(draw.textlength(ch, font=fonte) for ch in texto)
    return total + tracking * (len(texto) - 1)


def _texto_rastreado(draw: ImageDraw.ImageDraw, xy: tuple, texto: str, fonte: ImageFont.FreeTypeFont, cor, tracking: float = 0) -> float:
    x, y = xy
    for ch in texto:
        draw.text((x, y), ch, font=fonte, fill=cor)
        x += draw.textlength(ch, font=fonte) + tracking
    return x


def _texto_rastreado_centralizado(draw: ImageDraw.ImageDraw, cx: float, y: float, texto: str, fonte: ImageFont.FreeTypeFont, cor, tracking: float = 0) -> None:
    largura = _largura_rastreada(draw, texto, fonte, tracking)
    _texto_rastreado(draw, (cx - largura / 2, y), texto, fonte, cor, tracking)


def _texto_rastreado_direita(draw: ImageDraw.ImageDraw, x_direita: float, y: float, texto: str, fonte: ImageFont.FreeTypeFont, cor, tracking: float = 0) -> None:
    largura = _largura_rastreada(draw, texto, fonte, tracking)
    _texto_rastreado(draw, (x_direita - largura, y), texto, fonte, cor, tracking)


def _altura_linha(fonte: ImageFont.FreeTypeFont) -> int:
    ascent, descent = fonte.getmetrics()
    return ascent + descent


# ---------------------------------------------------------------------------
# texto centralizado simples (sem tracking) — pra números/nomes grandes
# ---------------------------------------------------------------------------

def _centralizado_x(draw: ImageDraw.ImageDraw, cx: float, y: float, texto: str, fonte: ImageFont.FreeTypeFont, cor) -> int:
    bbox = draw.textbbox((0, 0), texto, font=fonte)
    largura, altura = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = cx - largura / 2
    draw.text((x - bbox[0], y - bbox[1]), texto, font=fonte, fill=cor)
    return altura


def _centralizado(draw: ImageDraw.ImageDraw, y: float, texto: str, fonte: ImageFont.FreeTypeFont, cor) -> int:
    return _centralizado_x(draw, LARGURA / 2, y, texto, fonte, cor)


def _largura_texto(draw: ImageDraw.ImageDraw, texto: str, fonte: ImageFont.FreeTypeFont) -> int:
    bbox = draw.textbbox((0, 0), texto, font=fonte)
    return bbox[2] - bbox[0]


def _fonte_ajustada(draw: ImageDraw.ImageDraw, texto: str, bold: bool, tamanho_inicial: int,
                     largura_maxima: int = LARGURA_UTIL, tamanho_minimo: int = 26) -> tuple:
    tamanho = tamanho_inicial
    fonte = _jbm(tamanho, bold)
    while tamanho > tamanho_minimo and _largura_texto(draw, texto, fonte) > largura_maxima:
        tamanho -= 4
        fonte = _jbm(tamanho, bold)
    if _largura_texto(draw, texto, fonte) > largura_maxima:
        while texto and _largura_texto(draw, texto + "…", fonte) > largura_maxima:
            texto = texto[:-1]
        texto = f"{texto}…" if texto else "…"
    return fonte, texto


# ---------------------------------------------------------------------------
# primitivas visuais — LED, eyebrow, painel com hairline, chip
# ---------------------------------------------------------------------------

def _led(draw: ImageDraw.ImageDraw, x: float, y: float, cor=ACCENT, r: int = 6) -> None:
    draw.ellipse([x, y, x + 2 * r, y + 2 * r], fill=cor)


def _eyebrow(draw: ImageDraw.ImageDraw, x: float, y: float, texto: str, cor=INK_MUTED, tamanho: int = 22) -> None:
    fonte = _cp(tamanho)
    _texto_rastreado(draw, (x, y), texto.upper(), fonte, cor, tracking=3)


def _modulo_cabecalho(draw: ImageDraw.ImageDraw, x: float, y: float, texto: str) -> int:
    """LED + eyebrow no canto, igual ao .module-head do frontend. Retorna
    a altura ocupada."""
    r = 5
    _led(draw, x, y + 6, ACCENT, r)
    _eyebrow(draw, x + 2 * r + 14, y, texto, INK_MUTED, 22)
    return 40


def _chip(draw: ImageDraw.ImageDraw, cx_start: float, y: float, texto: str, fonte: ImageFont.FreeTypeFont) -> float:
    """Desenha uma pill (borda fina, cantos retos) começando em cx_start;
    retorna a posição x logo após o chip (pra empilhar chips numa linha)."""
    pad_x, pad_y = 20, 12
    largura = draw.textlength(texto, font=fonte)
    altura = _altura_linha(fonte)
    x1, y1 = cx_start, y
    x2, y2 = x1 + largura + 2 * pad_x, y1 + altura + 2 * pad_y
    draw.rectangle([x1, y1, x2, y2], outline=HAIR_BRIGHT, width=2)
    draw.text((x1 + pad_x, y1 + pad_y - 2), texto, font=fonte, fill=INK_MUTED)
    return x2


def _linha_chips_centralizada(draw: ImageDraw.ImageDraw, y: float, textos: list, fonte: ImageFont.FreeTypeFont, gap: int = 14) -> int:
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

    altura_chip = _altura_linha(fonte) + 2 * pad_y
    y_cursor = y
    for linha in linhas:
        largura_total = sum(draw.textlength(t, font=fonte) + 2 * pad_x for t in linha) + gap * (len(linha) - 1)
        x = LARGURA / 2 - largura_total / 2
        for t in linha:
            x = _chip(draw, x, y_cursor, t, fonte) + gap
        y_cursor += altura_chip + 12
    return y_cursor - y - 12


# ---------------------------------------------------------------------------
# fundo + scanlines
# ---------------------------------------------------------------------------

def _fundo() -> Image.Image:
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


def _aplicar_scanlines(imagem: Image.Image) -> Image.Image:
    """Réplica do .scanlines do frontend: linhas horizontais de 1px bem
    sutis, a cada 3px."""
    overlay = Image.new("RGBA", imagem.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    for y in range(0, ALTURA, 3):
        draw.line([(0, y), (LARGURA, y)], fill=(255, 255, 255, 10))
    return Image.alpha_composite(imagem.convert("RGBA"), overlay).convert("RGB")


# ---------------------------------------------------------------------------
# blocos de conteúdo
# ---------------------------------------------------------------------------

def _bloco_topbar(imagem: Image.Image, draw: ImageDraw.ImageDraw, rotulo_periodo: str) -> int:
    y = MARGEM
    _led(draw, MARGEM, y + 6, ACCENT, 5)
    _eyebrow(draw, MARGEM + 24, y, "LIFEOS · MÓDULO MÚSICA", INK_DIM, 20)
    _texto_rastreado_direita(draw, LARGURA - MARGEM, y, date.today().strftime("%d/%m/%Y"), _cp(20), INK_DIM, tracking=2)
    y += 40
    draw.line([(MARGEM, y), (LARGURA - MARGEM, y)], fill=HAIR, width=2)
    return y + 48


def _bloco_titulo(draw: ImageDraw.ImageDraw, y: float, rotulo_periodo: str) -> float:
    _eyebrow(draw, MARGEM, y, "relatório — segundo o spotify", INK_MUTED, 22)
    y += 40
    fonte_titulo = _jbm(66, bold=True)
    draw.text((MARGEM, y), "$ ", font=fonte_titulo, fill=ACCENT)
    largura_prompt = draw.textlength("$ ", font=fonte_titulo)
    fonte_titulo2, texto_titulo = _fonte_ajustada(draw, rotulo_periodo.lower(), True, 66, LARGURA_UTIL - largura_prompt)
    draw.text((MARGEM + largura_prompt, y), texto_titulo, font=fonte_titulo2, fill=INK)
    y += _altura_linha(fonte_titulo) + 44
    return y


def _bloco_mosaico(imagem: Image.Image, draw: ImageDraw.ImageDraw, y: float, top_albuns: list) -> float:
    if not top_albuns:
        return y
    y0 = y
    y += _modulo_cabecalho(draw, MARGEM, y, "consumo real")
    lado_caixa = LADO_MOSAICO + 48
    x1 = LARGURA / 2 - lado_caixa / 2
    x2 = x1 + lado_caixa
    draw.rectangle([x1, y, x2, y + lado_caixa], outline=HAIR, width=2)
    mosaico = colagem.montar_mosaico(top_albuns, 3, LADO_MOSAICO)
    imagem.paste(mosaico, (int(LARGURA / 2 - LADO_MOSAICO / 2), int(y + 24)))
    y += lado_caixa + 40
    return y


def _bloco_kpis(draw: ImageDraw.ImageDraw, y: float, dados: dict) -> float:
    y += _modulo_cabecalho(draw, MARGEM, y, "atividade")
    gap = 20
    largura_caixa = (LARGURA_UTIL - gap) / 2
    altura_caixa = 280
    horas, minutos_resto = divmod(dados["minutos"], 60)
    texto_tempo = f"{horas}h{minutos_resto:02d}" if horas > 0 else f"{minutos_resto}min"

    caixas = [
        (str(dados["total_faixas"]), "MÚSICAS OUVIDAS"),
        (texto_tempo, "TEMPO OUVIDO"),
    ]
    for i, (valor, rotulo) in enumerate(caixas):
        x1 = MARGEM + i * (largura_caixa + gap)
        x2 = x1 + largura_caixa
        draw.rectangle([x1, y, x2, y + altura_caixa], outline=HAIR, width=2)
        draw.line([(x1, y), (x2, y)], fill=ACCENT, width=4)
        cx = x1 + largura_caixa / 2
        fonte_num, texto_num = _fonte_ajustada(draw, valor, True, 96, largura_caixa - 40, tamanho_minimo=48)
        _centralizado_x(draw, cx, y + 74, texto_num, fonte_num, ACCENT_BRIGHT)
        _texto_rastreado_centralizado(draw, cx, y + altura_caixa - 56, rotulo, _cp(20), INK_MUTED, tracking=2.5)
    return y + altura_caixa + 44


def _bloco_recorrencia(draw: ImageDraw.ImageDraw, y: float, dados: dict) -> float:
    if not dados["top_artista"] and not dados["top_faixa"]:
        return y
    y0 = y
    y += _modulo_cabecalho(draw, MARGEM, y, "recorrência")
    caixa_y0 = y
    conteudo_y = y + 36

    if dados["top_artista"]:
        _texto_rastreado_centralizado(draw, LARGURA / 2, conteudo_y, "ARTISTA #1", _cp(20), ACCENT_BRIGHT, tracking=2.5)
        conteudo_y += 38
        fonte, texto = _fonte_ajustada(draw, dados["top_artista"], True, 58, LARGURA_UTIL - 80)
        conteudo_y += _centralizado(draw, conteudo_y, texto, fonte, INK) + 34

    if dados["top_faixa"]:
        _texto_rastreado_centralizado(draw, LARGURA / 2, conteudo_y, "FAIXA #1", _cp(20), ACCENT_BRIGHT, tracking=2.5)
        conteudo_y += 38
        fonte, texto = _fonte_ajustada(draw, dados["top_faixa"], True, 46, LARGURA_UTIL - 80)
        conteudo_y += _centralizado(draw, conteudo_y, texto, fonte, INK) + 6
        fonte2, texto2 = _fonte_ajustada(draw, dados.get("top_faixa_artista") or "", False, 28, LARGURA_UTIL - 80)
        conteudo_y += _centralizado(draw, conteudo_y, texto2, fonte2, INK_MUTED) + 30

    draw.rectangle([MARGEM, caixa_y0, LARGURA - MARGEM, conteudo_y + 6], outline=HAIR, width=2)
    return conteudo_y + 6 + 44


def _bloco_chips(draw: ImageDraw.ImageDraw, y: float, dados: dict) -> float:
    detalhe = []
    if dados["artistas_distintos"]:
        detalhe.append(f"{dados['artistas_distintos']} ARTISTAS DIFERENTES")
    if dados["hora_favorita"] is not None:
        detalhe.append(f"PICO ÀS {dados['hora_favorita']}H")
    if dados.get("sequencia_dias", 0) >= 2:
        detalhe.append(f"{dados['sequencia_dias']} DIAS SEGUIDOS")
    if not detalhe:
        return y
    y += _linha_chips_centralizada(draw, y, detalhe, _cp(20))
    return y


def gerar_relatorio_stories(dados: dict, rotulo_periodo: str, top_albuns: list | None = None) -> bytes:
    imagem = _fundo()
    draw = ImageDraw.Draw(imagem)

    y = _bloco_topbar(imagem, draw, rotulo_periodo)
    y = _bloco_titulo(draw, y, rotulo_periodo)
    y = _bloco_mosaico(imagem, draw, y, top_albuns or [])
    y = _bloco_kpis(draw, y, dados)
    y = _bloco_recorrencia(draw, y, dados)
    y = _bloco_chips(draw, y, dados)

    rodape_y = ALTURA - 96
    draw.line([(MARGEM, rodape_y - 32), (LARGURA - MARGEM, rodape_y - 32)], fill=HAIR, width=2)
    _texto_rastreado_centralizado(draw, LARGURA / 2, rodape_y, f"GERADO EM {date.today().strftime('%d/%m/%Y')}", _cp(20), INK_DIM, tracking=2.5)

    imagem = _aplicar_scanlines(imagem)

    buf = io.BytesIO()
    imagem.save(buf, format="PNG")
    buf.seek(0)
    return buf.getvalue()
