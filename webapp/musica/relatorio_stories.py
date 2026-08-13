"""Monta um card vertical (1080x1920, proporção de Stories) com o resumo do
consumo real de música no período — visual "console/terminal" que espelha
webapp/frontend/shared/tokens.css (mesmas cores, mesma dupla de fontes
JetBrains Mono + Courier Prime, hairlines, scanlines) em vez do cartão
estilo "Spotify Wrapped" que a versão anterior usava — pra bater com a cara
do resto do frontend novo, não a do Streamlit antigo.

Primitivas de desenho (fontes, texto rastreado, fundo, scanlines, chips...)
moraram aqui originalmente; foram extraídas pra story_kit.py quando
album_story.py (export de uma única escuta do diário) precisou do mesmo kit
visual, pra não duplicar.
"""

import io
from datetime import date

from PIL import ImageDraw

from . import colagem
from . import story_kit as kit

LARGURA, ALTURA, MARGEM, LARGURA_UTIL = kit.LARGURA, kit.ALTURA, kit.MARGEM, kit.LARGURA_UTIL
INK, INK_MUTED, ACCENT, ACCENT_BRIGHT, HAIR = kit.INK, kit.INK_MUTED, kit.ACCENT, kit.ACCENT_BRIGHT, kit.HAIR
LADO_MOSAICO = 480


def _bloco_titulo(draw: ImageDraw.ImageDraw, y: float, rotulo_periodo: str) -> float:
    kit.eyebrow(draw, MARGEM, y, "relatório — segundo o spotify", INK_MUTED, 22)
    y += 40
    fonte_titulo = kit.jbm(66, bold=True)
    draw.text((MARGEM, y), "$ ", font=fonte_titulo, fill=ACCENT)
    largura_prompt = draw.textlength("$ ", font=fonte_titulo)
    fonte_titulo2, texto_titulo = kit.fonte_ajustada(draw, rotulo_periodo.lower(), True, 66, LARGURA_UTIL - largura_prompt)
    draw.text((MARGEM + largura_prompt, y), texto_titulo, font=fonte_titulo2, fill=INK)
    y += kit.altura_linha(fonte_titulo) + 44
    return y


def _bloco_mosaico(imagem, draw: ImageDraw.ImageDraw, y: float, top_albuns: list, lado_grade: int = 3) -> float:
    if not top_albuns:
        return y
    y += kit.modulo_cabecalho(draw, MARGEM, y, "consumo real")
    lado_caixa = LADO_MOSAICO + 48
    x1 = LARGURA / 2 - lado_caixa / 2
    x2 = x1 + lado_caixa
    draw.rectangle([x1, y, x2, y + lado_caixa], outline=HAIR, width=2)
    mosaico = colagem.montar_mosaico(top_albuns, lado_grade, LADO_MOSAICO)
    imagem.paste(mosaico, (int(LARGURA / 2 - LADO_MOSAICO / 2), int(y + 24)))
    y += lado_caixa + 40
    return y


def _bloco_kpis(draw: ImageDraw.ImageDraw, y: float, dados: dict) -> float:
    y += kit.modulo_cabecalho(draw, MARGEM, y, "atividade")
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
        fonte_num, texto_num = kit.fonte_ajustada(draw, valor, True, 96, largura_caixa - 40, tamanho_minimo=48)
        kit.centralizado_x(draw, cx, y + 74, texto_num, fonte_num, ACCENT_BRIGHT)
        kit.texto_rastreado_centralizado(draw, cx, y + altura_caixa - 56, rotulo, kit.cp(20), INK_MUTED, tracking=2.5)
    return y + altura_caixa + 44


def _bloco_recorrencia(draw: ImageDraw.ImageDraw, y: float, dados: dict) -> float:
    if not dados["top_artista"] and not dados["top_faixa"]:
        return y
    y += kit.modulo_cabecalho(draw, MARGEM, y, "recorrência")
    caixa_y0 = y
    conteudo_y = y + 36

    if dados["top_artista"]:
        kit.texto_rastreado_centralizado(draw, LARGURA / 2, conteudo_y, "ARTISTA #1", kit.cp(20), ACCENT_BRIGHT, tracking=2.5)
        conteudo_y += 38
        fonte, texto = kit.fonte_ajustada(draw, dados["top_artista"], True, 58, LARGURA_UTIL - 80)
        conteudo_y += kit.centralizado(draw, conteudo_y, texto, fonte, INK) + 34

    if dados["top_faixa"]:
        kit.texto_rastreado_centralizado(draw, LARGURA / 2, conteudo_y, "FAIXA #1", kit.cp(20), ACCENT_BRIGHT, tracking=2.5)
        conteudo_y += 38
        fonte, texto = kit.fonte_ajustada(draw, dados["top_faixa"], True, 46, LARGURA_UTIL - 80)
        conteudo_y += kit.centralizado(draw, conteudo_y, texto, fonte, INK) + 6
        fonte2, texto2 = kit.fonte_ajustada(draw, dados.get("top_faixa_artista") or "", False, 28, LARGURA_UTIL - 80)
        conteudo_y += kit.centralizado(draw, conteudo_y, texto2, fonte2, INK_MUTED) + 30

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
    y += kit.linha_chips_centralizada(draw, y, detalhe, kit.cp(20))
    return y


def gerar_relatorio_stories(dados: dict, rotulo_periodo: str, top_albuns: list | None = None, lado_grade: int = 3) -> bytes:
    imagem = kit.fundo()
    draw = ImageDraw.Draw(imagem)

    y = kit.bloco_topbar(imagem, draw, "LIFEOS · MÓDULO MÚSICA", date.today().strftime("%d/%m/%Y"))
    y = _bloco_titulo(draw, y, rotulo_periodo)
    y = _bloco_mosaico(imagem, draw, y, top_albuns or [], lado_grade)
    y = _bloco_kpis(draw, y, dados)
    y = _bloco_recorrencia(draw, y, dados)
    y = _bloco_chips(draw, y, dados)

    rodape_y = ALTURA - 96
    draw.line([(MARGEM, rodape_y - 32), (LARGURA - MARGEM, rodape_y - 32)], fill=HAIR, width=2)
    kit.texto_rastreado_centralizado(draw, LARGURA / 2, rodape_y, f"GERADO EM {date.today().strftime('%d/%m/%Y')}", kit.cp(20), kit.INK_DIM, tracking=2.5)

    imagem = kit.aplicar_scanlines(imagem)

    buf = io.BytesIO()
    imagem.save(buf, format="PNG")
    buf.seek(0)
    return buf.getvalue()
