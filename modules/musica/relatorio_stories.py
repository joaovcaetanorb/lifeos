"""Monta um card vertical (1080x1920, proporção de Stories) com o resumo do
consumo real de música no período — pra baixar e postar. Mesma família
visual do resto do app (ledger/terminal, fundo escuro, verde de destaque),
desenhada com Pillow em vez de HTML porque o destino é uma imagem, não uma
página.

Usa a fonte monoespaçada que o matplotlib já traz embutida (DejaVuSansMono)
em vez de depender de uma fonte TrueType própria no repo ou instalada no
servidor — `matplotlib` já é dependência obrigatória do projeto (gráficos
de Estatísticas), então o caminho sempre existe, inclusive no Streamlit
Cloud.
"""

import io
import os
from datetime import date

import matplotlib
from PIL import Image, ImageColor, ImageDraw, ImageFont

import utils

LARGURA, ALTURA = 1080, 1920
MARGEM = 90
LARGURA_UTIL = LARGURA - 2 * MARGEM
MARGEM_TOPO_MINIMA = 130
ALTURA_RODAPE = 140

_FONTS_DIR = os.path.join(matplotlib.get_data_path(), "fonts", "ttf")
_FONTE_REGULAR = os.path.join(_FONTS_DIR, "DejaVuSansMono.ttf")
_FONTE_BOLD = os.path.join(_FONTS_DIR, "DejaVuSansMono-Bold.ttf")


def _fonte(bold: bool, tamanho: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(_FONTE_BOLD if bold else _FONTE_REGULAR, tamanho)


def _largura_texto(draw: ImageDraw.ImageDraw, texto: str, fonte: ImageFont.FreeTypeFont) -> int:
    bbox = draw.textbbox((0, 0), texto, font=fonte)
    return bbox[2] - bbox[0]


def _fonte_ajustada(
    draw: ImageDraw.ImageDraw, texto: str, bold: bool, tamanho_inicial: int,
    largura_maxima: int = LARGURA_UTIL, tamanho_minimo: int = 28,
) -> tuple[ImageFont.FreeTypeFont, str]:
    """Reduz o tamanho da fonte até o texto caber em `largura_maxima`; se
    ainda não couber no tamanho mínimo, trunca com reticências — nomes de
    artista/faixa não têm tamanho previsível, sem isso vazariam da tela."""
    tamanho = tamanho_inicial
    fonte = _fonte(bold, tamanho)
    while tamanho > tamanho_minimo and _largura_texto(draw, texto, fonte) > largura_maxima:
        tamanho -= 4
        fonte = _fonte(bold, tamanho)
    if _largura_texto(draw, texto, fonte) > largura_maxima:
        while texto and _largura_texto(draw, texto + "…", fonte) > largura_maxima:
            texto = texto[:-1]
        texto = f"{texto}…" if texto else "…"
    return fonte, texto


def _centralizado(draw: ImageDraw.ImageDraw, y: int, texto: str, fonte: ImageFont.FreeTypeFont, cor) -> int:
    """Desenha `texto` centralizado horizontalmente na altura `y`; retorna
    a altura ocupada, pra quem chama avançar o cursor vertical."""
    bbox = draw.textbbox((0, 0), texto, font=fonte)
    largura, altura = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = (LARGURA - largura) // 2
    draw.text((x - bbox[0], y - bbox[1]), texto, font=fonte, fill=cor)
    return altura


def _fundo_gradiente() -> Image.Image:
    """Fundo com leve gradiente vertical entre as duas cores de fundo do
    tema — evita a chapa lisa de um card só com COR_FUNDO."""
    topo = ImageColor.getrgb(utils.COR_FUNDO)
    base = ImageColor.getrgb(utils.COR_FUNDO_ALT)
    img = Image.new("RGB", (LARGURA, ALTURA))
    draw = ImageDraw.Draw(img)
    for y in range(ALTURA):
        t = y / ALTURA
        cor = tuple(int(topo[i] + (base[i] - topo[i]) * t) for i in range(3))
        draw.line([(0, y), (LARGURA, y)], fill=cor)
    return img


def _desenhar_conteudo(draw: ImageDraw.ImageDraw, dados: dict, rotulo_periodo: str, cores: tuple) -> int:
    """Desenha o bloco de estatísticas a partir de y=0 e retorna a altura
    total ocupada — quem chama decide onde colar esse bloco (pra
    centralizar verticalmente conforme o conteúdo, já que a quantidade de
    seções varia com os dados disponíveis)."""
    cor_texto, cor_muted, cor_acento, cor_hairline = cores

    def linha(y: int) -> int:
        draw.line([(MARGEM, y), (LARGURA - MARGEM, y)], fill=cor_hairline, width=2)
        return y + 60

    y = 0
    y += _centralizado(draw, y, "$ MEU SPOTIFY", _fonte(True, 34), cor_acento) + 24
    y += _centralizado(draw, y, rotulo_periodo.upper(), _fonte(True, 52), cor_texto) + 60
    y = linha(y) + 10

    y += _centralizado(draw, y, f"{dados['total_faixas']}", _fonte(True, 150), cor_acento) + 14
    y += _centralizado(draw, y, "MÚSICAS OUVIDAS", _fonte(True, 32), cor_muted) + 90

    horas, minutos_resto = divmod(dados["minutos"], 60)
    texto_tempo = f"{horas}h{minutos_resto:02d}" if horas > 0 else f"{minutos_resto}min"
    y += _centralizado(draw, y, texto_tempo, _fonte(True, 110), cor_texto) + 14
    y += _centralizado(draw, y, "TEMPO OUVIDO", _fonte(True, 32), cor_muted) + 50
    y = linha(y) + 10

    if dados["top_artista"]:
        y += _centralizado(draw, y, "ARTISTA #1", _fonte(True, 28), cor_acento) + 18
        fonte, texto = _fonte_ajustada(draw, dados["top_artista"], True, 72)
        y += _centralizado(draw, y, texto, fonte, cor_texto) + 60

    if dados["top_faixa"]:
        y += _centralizado(draw, y, "FAIXA #1", _fonte(True, 28), cor_acento) + 18
        fonte, texto = _fonte_ajustada(draw, dados["top_faixa"], True, 56)
        y += _centralizado(draw, y, texto, fonte, cor_texto) + 10
        fonte, texto = _fonte_ajustada(draw, dados.get("top_faixa_artista") or "", False, 34)
        y += _centralizado(draw, y, texto, fonte, cor_muted) + 60

    y = linha(y)

    if dados["artistas_distintos"]:
        y += _centralizado(
            draw, y, f"{dados['artistas_distintos']} ARTISTAS DIFERENTES", _fonte(False, 32), cor_muted,
        ) + 24
    if dados["hora_favorita"] is not None:
        y += _centralizado(
            draw, y, f"MAIS OUVIDO PERTO DAS {dados['hora_favorita']}H", _fonte(False, 32), cor_muted,
        ) + 24

    return y


def gerar_relatorio_stories(dados: dict, rotulo_periodo: str) -> bytes:
    """dados: dict no formato de `calculations.resumo_periodo_real()`.
    rotulo_periodo: rótulo já formatado do período (ex: "este mês", "2026").
    PNG bytes, 1080x1920."""
    cor_texto = ImageColor.getrgb(utils.COR_TEXTO)
    cor_muted = ImageColor.getrgb(utils.COR_TEXTO_MUTED)
    cor_acento = ImageColor.getrgb(utils.COR_ACENTO)
    cor_hairline = ImageColor.getrgb(utils.COR_HAIRLINE)

    camada = Image.new("RGBA", (LARGURA, ALTURA), (0, 0, 0, 0))
    altura_conteudo = _desenhar_conteudo(
        ImageDraw.Draw(camada), dados, rotulo_periodo, (cor_texto, cor_muted, cor_acento, cor_hairline),
    )

    espaco_disponivel = ALTURA - ALTURA_RODAPE
    offset = max(MARGEM_TOPO_MINIMA, (espaco_disponivel - altura_conteudo) // 2)

    imagem = _fundo_gradiente()
    imagem.paste(camada, (0, offset), camada)

    rodape = f"gerado em {date.today().strftime('%d/%m/%Y')} · LifeOS"
    _centralizado(ImageDraw.Draw(imagem), ALTURA - 90, rodape, _fonte(False, 26), cor_muted)

    buf = io.BytesIO()
    imagem.save(buf, format="PNG")
    buf.seek(0)
    return buf.getvalue()
