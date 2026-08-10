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

import colagem
import utils

LARGURA, ALTURA = 1080, 1920
MARGEM = 90
LARGURA_UTIL = LARGURA - 2 * MARGEM
MARGEM_TOPO_MINIMA = 110
ALTURA_RODAPE = 130
LADO_MOSAICO = 480

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
    largura_maxima: int = LARGURA_UTIL, tamanho_minimo: int = 26,
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


def _centralizado_x(draw: ImageDraw.ImageDraw, x_centro: int, y: int, texto: str, fonte: ImageFont.FreeTypeFont, cor) -> int:
    """Desenha `texto` centralizado em torno de `x_centro` na altura `y`;
    retorna a altura ocupada, pra quem chama avançar o cursor vertical."""
    bbox = draw.textbbox((0, 0), texto, font=fonte)
    largura, altura = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = x_centro - largura // 2
    draw.text((x - bbox[0], y - bbox[1]), texto, font=fonte, fill=cor)
    return altura


def _centralizado(draw: ImageDraw.ImageDraw, y: int, texto: str, fonte: ImageFont.FreeTypeFont, cor) -> int:
    return _centralizado_x(draw, LARGURA // 2, y, texto, fonte, cor)


_VERDE_SPOTIFY = (29, 185, 84)  # #1DB954 — verde oficial, não o COR_ACENTO do app


def _icone_spotify(diametro: int) -> Image.Image:
    """Selo circular inspirado no ícone do Spotify (círculo verde + 3 ondas
    sonoras brancas, concêntricas a partir do mesmo centro) desenhado com
    primitivas do Pillow — não é o arquivo oficial da marca (não temos
    acesso a ele aqui), só uma referência visual pra deixar claro de onde
    vêm os números do card."""
    escala = 4  # desenha maior e reduz depois, pra anti-aliasing sem depender de libs extras
    tam = diametro * escala
    img = Image.new("RGBA", (tam, tam), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse([0, 0, tam - 1, tam - 1], fill=_VERDE_SPOTIFY)

    centro_x, centro_y = tam / 2, tam * 0.56
    largura_linha = round(tam * 0.052)
    for raio_rel in (0.40, 0.28, 0.16):
        raio = tam * raio_rel
        bbox = [centro_x - raio, centro_y - raio, centro_x + raio, centro_y + raio]
        draw.arc(bbox, start=205, end=335, fill=(255, 255, 255, 255), width=largura_linha)

    return img.resize((diametro, diametro), Image.Resampling.LANCZOS)


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


def _desenhar_conteudo(
    draw: ImageDraw.ImageDraw, camada: Image.Image, dados: dict, rotulo_periodo: str,
    top_albuns: list[dict], cores: tuple,
) -> int:
    """Desenha o bloco de estatísticas a partir de y=0 e retorna a altura
    total ocupada — quem chama decide onde colar esse bloco (pra
    centralizar verticalmente conforme o conteúdo, já que a quantidade de
    seções varia com os dados disponíveis). `camada` é a mesma imagem de
    `draw`, usada só pra colar o mosaico de capas (Image.paste não existe
    em ImageDraw)."""
    cor_texto, cor_muted, cor_acento, cor_hairline = cores

    def linha(y: int) -> int:
        draw.line([(MARGEM, y), (LARGURA - MARGEM, y)], fill=cor_hairline, width=2)
        return y + 44

    y = 0
    icone = _icone_spotify(80)
    camada.paste(icone, ((LARGURA - icone.width) // 2, y), icone)
    y += icone.height + 22
    y += _centralizado(draw, y, "MEU SPOTIFY", _fonte(True, 30), cor_acento) + 18
    y += _centralizado(draw, y, rotulo_periodo.upper(), _fonte(True, 44), cor_texto) + 34

    if top_albuns:
        mosaico = colagem.montar_mosaico(top_albuns, 3, LADO_MOSAICO).convert("RGBA")
        x = (LARGURA - mosaico.width) // 2
        camada.paste(mosaico, (x, y))
        y += mosaico.height + 30

    y = linha(y)

    x_esq, x_dir = LARGURA * 0.27, LARGURA * 0.73
    horas, minutos_resto = divmod(dados["minutos"], 60)
    texto_tempo = f"{horas}h{minutos_resto:02d}" if horas > 0 else f"{minutos_resto}min"
    altura_num = max(
        _centralizado_x(draw, x_esq, y, f"{dados['total_faixas']}", _fonte(True, 92), cor_acento),
        _centralizado_x(draw, x_dir, y, texto_tempo, _fonte(True, 92), cor_texto),
    )
    y += altura_num + 12
    _centralizado_x(draw, x_esq, y, "MÚSICAS", _fonte(True, 24), cor_muted)
    _centralizado_x(draw, x_dir, y, "TEMPO OUVIDO", _fonte(True, 24), cor_muted)
    y += 24 + 20

    y = linha(y)

    if dados["top_artista"]:
        y += _centralizado(draw, y, "ARTISTA #1", _fonte(True, 26), cor_acento) + 14
        fonte, texto = _fonte_ajustada(draw, dados["top_artista"], True, 62)
        y += _centralizado(draw, y, texto, fonte, cor_texto) + 34

    if dados["top_faixa"]:
        y += _centralizado(draw, y, "FAIXA #1", _fonte(True, 26), cor_acento) + 14
        fonte, texto = _fonte_ajustada(draw, dados["top_faixa"], True, 48)
        y += _centralizado(draw, y, texto, fonte, cor_texto) + 8
        fonte, texto = _fonte_ajustada(draw, dados.get("top_faixa_artista") or "", False, 30)
        y += _centralizado(draw, y, texto, fonte, cor_muted) + 34

    y = linha(y)

    detalhe = []
    if dados["artistas_distintos"]:
        detalhe.append(f"{dados['artistas_distintos']} ARTISTAS DIFERENTES")
    if dados["hora_favorita"] is not None:
        detalhe.append(f"PICO ÀS {dados['hora_favorita']}H")
    if dados.get("sequencia_dias", 0) >= 2:
        detalhe.append(f"{dados['sequencia_dias']} DIAS SEGUIDOS")
    if detalhe:
        fonte, texto = _fonte_ajustada(draw, "  ·  ".join(detalhe), False, 28, tamanho_minimo=20)
        y += _centralizado(draw, y, texto, fonte, cor_muted) + 20

    return y


def gerar_relatorio_stories(dados: dict, rotulo_periodo: str, top_albuns: list[dict] | None = None) -> bytes:
    """dados: dict no formato de `calculations.resumo_periodo_real()`.
    rotulo_periodo: rótulo já formatado do período (ex: "este mês", "2026").
    top_albuns: lista no formato de `calculations.top_albuns_historico()`
    (já ordenada, mais tocado primeiro) — vira um mosaico 3x3 no topo do
    card; None ou lista vazia pula o mosaico. PNG bytes, 1080x1920."""
    cor_texto = ImageColor.getrgb(utils.COR_TEXTO)
    cor_muted = ImageColor.getrgb(utils.COR_TEXTO_MUTED)
    cor_acento = ImageColor.getrgb(utils.COR_ACENTO)
    cor_hairline = ImageColor.getrgb(utils.COR_HAIRLINE)

    camada = Image.new("RGBA", (LARGURA, ALTURA), (0, 0, 0, 0))
    altura_conteudo = _desenhar_conteudo(
        ImageDraw.Draw(camada), camada, dados, rotulo_periodo, top_albuns or [],
        (cor_texto, cor_muted, cor_acento, cor_hairline),
    )

    espaco_disponivel = ALTURA - ALTURA_RODAPE
    offset = max(MARGEM_TOPO_MINIMA, (espaco_disponivel - altura_conteudo) // 2)

    imagem = _fundo_gradiente()
    imagem.paste(camada, (0, offset), camada)

    rodape = f"gerado em {date.today().strftime('%d/%m/%Y')}"
    _centralizado(ImageDraw.Draw(imagem), ALTURA - 80, rodape, _fonte(False, 24), cor_muted)

    buf = io.BytesIO()
    imagem.save(buf, format="PNG")
    buf.seek(0)
    return buf.getvalue()
