"""Monta um card vertical (1080x1920, Stories) pra UMA escuta do diário —
capa grande, nota em estrelas e, opcionalmente, a review escrita. Mesmo kit
visual de relatorio_stories.py (via story_kit.py), reaproveita o recorte de
capa quadrada de colagem.tile_capa em vez de duplicar a lógica de abrir/
cortar a imagem."""

import io
from datetime import date, datetime

from PIL import ImageDraw

from . import colagem
from . import story_kit as kit

LARGURA, ALTURA, MARGEM, LARGURA_UTIL = kit.LARGURA, kit.ALTURA, kit.MARGEM, kit.LARGURA_UTIL
INK, INK_MUTED, INK_DIM, ACCENT, ACCENT_BRIGHT, HAIR = (
    kit.INK, kit.INK_MUTED, kit.INK_DIM, kit.ACCENT, kit.ACCENT_BRIGHT, kit.HAIR,
)
LADO_CAPA = 860


def _data_br(iso: str) -> str:
    try:
        return datetime.strptime(iso, "%Y-%m-%d").strftime("%d/%m/%Y")
    except (ValueError, TypeError):
        return iso or ""


def gerar_album_story(escuta: dict, incluir_review: bool = True) -> bytes:
    imagem = kit.fundo()
    draw = ImageDraw.Draw(imagem)

    y = kit.bloco_topbar(imagem, draw, "LIFEOS · MÓDULO MÚSICA", date.today().strftime("%d/%m/%Y"))

    kit.eyebrow(draw, MARGEM, y, "diário — avaliação", INK_MUTED, 22)
    y += 40
    fonte_titulo, texto_titulo = kit.fonte_ajustada(draw, escuta["album_nome"], True, 60, LARGURA_UTIL)
    y += kit.centralizado(draw, y, texto_titulo, fonte_titulo, INK) + 14
    fonte_artista, texto_artista = kit.fonte_ajustada(draw, escuta["artista_nome"], False, 34, LARGURA_UTIL, tamanho_minimo=22)
    y += kit.centralizado(draw, y, texto_artista, fonte_artista, INK_MUTED) + 36

    capa = colagem.tile_capa({"album_id": escuta.get("album_id")}, LADO_CAPA)
    x_capa = int(LARGURA / 2 - LADO_CAPA / 2)
    imagem.paste(capa, (x_capa, int(y)))
    draw.rectangle([x_capa, y, x_capa + LADO_CAPA, y + LADO_CAPA], outline=HAIR, width=2)
    y += LADO_CAPA + 40

    if escuta.get("nota") is not None:
        y += kit.linha_estrelas(imagem, draw, LARGURA / 2, y, float(escuta["nota"]), 5, raio=26, gap=16)
        y += 20
        nota_fmt = str(escuta["nota"]).rstrip("0").rstrip(".") if isinstance(escuta["nota"], float) else str(escuta["nota"])
        kit.texto_rastreado_centralizado(draw, LARGURA / 2, y, f"{nota_fmt} DE 5", kit.cp(20), INK_MUTED, tracking=2.5)
        y += 50
    else:
        kit.texto_rastreado_centralizado(draw, LARGURA / 2, y, "SEM NOTA", kit.cp(20), INK_DIM, tracking=2.5)
        y += 50

    review = (escuta.get("review") or "").strip()
    if incluir_review and review:
        y += 20
        y0 = y
        y += kit.modulo_cabecalho(draw, MARGEM, y, "review")
        espaco_disponivel = (ALTURA - 200) - y  # deixa espaço pro rodapé
        fonte_review = kit.jbm(30)
        altura_por_linha = kit.altura_linha(fonte_review) + 10
        max_linhas = max(2, int(espaco_disponivel / altura_por_linha) - 1)
        y_texto = y + 30
        y_fim = kit.paragrafo_centralizado(draw, y_texto, review, fonte_review, INK, LARGURA_UTIL - 80, max_linhas=max_linhas)
        draw.rectangle([MARGEM, y0, LARGURA - MARGEM, y_fim + 24], outline=HAIR, width=2)
        y = y_fim + 24 + 40

    rodape_y = ALTURA - 96
    draw.line([(MARGEM, rodape_y - 32), (LARGURA - MARGEM, rodape_y - 32)], fill=HAIR, width=2)
    kit.texto_rastreado_centralizado(draw, LARGURA / 2, rodape_y, f"OUVIDO EM {_data_br(escuta.get('data'))}", kit.cp(20), INK_DIM, tracking=2.5)

    imagem = kit.aplicar_scanlines(imagem)

    buf = io.BytesIO()
    imagem.save(buf, format="PNG")
    buf.seek(0)
    return buf.getvalue()
