"""Monta um card vertical (1080x1920, Stories) pra UMA escuta do diário —
artista em destaque, álbum com tratamento tipográfico próprio, capa, nota em
estrelas e, opcionalmente, faixa favorita e review escrita. Mesmo kit visual
de relatorio_stories.py (via story_kit.py), reaproveita o recorte de capa
quadrada de colagem.tile_capa em vez de duplicar a lógica de abrir/cortar a
imagem."""

import io
from datetime import date, datetime

from PIL import ImageDraw

from . import colagem
from . import story_kit as kit

LARGURA, ALTURA, MARGEM, LARGURA_UTIL = kit.LARGURA, kit.ALTURA, kit.MARGEM, kit.LARGURA_UTIL
INK, INK_MUTED, INK_DIM, ACCENT_BRIGHT, HAIR = (
    kit.INK, kit.INK_MUTED, kit.INK_DIM, kit.ACCENT_BRIGHT, kit.HAIR,
)
LADO_CAPA = 760


def _data_br(iso: str) -> str:
    try:
        return datetime.strptime(iso, "%Y-%m-%d").strftime("%d/%m/%Y")
    except (ValueError, TypeError):
        return iso or ""


# y máximo que qualquer bloco de conteúdo pode ocupar — deixa uma folga
# confortável antes da linha do rodapé (ALTURA - 96), pra nunca colidir com
# "OUVIDO EM ..." mesmo quando faixa favorita + review são longas juntas.
LIMITE_CONTEUDO = ALTURA - 220


def _bloco_faixa_favorita(draw: ImageDraw.ImageDraw, y: float, faixa: str, limite_y: float) -> float:
    """Faixa favorita costuma vir como uma lista "Música A, Música B, ..."
    (checklist da tracklist no formulário do diário) — quebra em linhas em
    vez de truncar numa só, senão só a primeira música sobrevive. Trunca a
    lista (com "…") se não houver espaço pra ela toda antes de limite_y."""
    y0 = y
    y += kit.modulo_cabecalho(draw, MARGEM, y, "faixa favorita")
    itens = [t.strip() for t in faixa.split(",") if t.strip()]
    fonte = kit.jbm(34, bold=True)
    altura_por_linha = kit.altura_linha(fonte) + 8
    y_texto = y + 14
    max_linhas = max(1, int((limite_y - y_texto) / altura_por_linha))
    if len(itens) > 1 or max_linhas < 1:
        y_fim = kit.paragrafo_centralizado(draw, y_texto, "\n".join(itens), fonte, ACCENT_BRIGHT,
                                            LARGURA_UTIL - 80, max_linhas=max_linhas, gap=8)
    else:
        y_fim = y_texto + kit.centralizado(draw, y_texto, itens[0] if itens else faixa, fonte, ACCENT_BRIGHT)
    draw.rectangle([MARGEM, y0, LARGURA - MARGEM, y_fim + 22], outline=HAIR, width=2)
    return y_fim + 22 + 36


def gerar_album_story(escuta: dict, incluir_review: bool = True, incluir_faixa_favorita: bool = True) -> bytes:
    imagem = kit.fundo()
    draw = ImageDraw.Draw(imagem)

    y = kit.bloco_topbar(imagem, draw, "LIFEOS · MÓDULO MÚSICA", date.today().strftime("%d/%m/%Y"))

    kit.eyebrow(draw, MARGEM, y, "diário — avaliação", INK_MUTED, 22)
    y += 44

    # artista em destaque — o "protagonista" do card, tratamento igual ao
    # "ARTISTA #1" do relatório de período, só que como herói da tela
    kit.texto_rastreado_centralizado(draw, LARGURA / 2, y, "ARTISTA", kit.cp(20), ACCENT_BRIGHT, tracking=3)
    y += 34
    fonte_artista, texto_artista = kit.fonte_ajustada(draw, escuta["artista_nome"], True, 76, LARGURA_UTIL, tamanho_minimo=36)
    y += kit.centralizado(draw, y, texto_artista, fonte_artista, INK) + 30

    # álbum — tratamento tipográfico diferente do artista (fonte "eyebrow"
    # rastreada, não a mono grande) pra criar hierarquia visual entre os dois
    kit.texto_rastreado_centralizado(draw, LARGURA / 2, y, "ÁLBUM", kit.cp(18), INK_DIM, tracking=3)
    y += 30
    fonte_album, texto_album = kit.fonte_ajustada_generica(draw, escuta["album_nome"].upper(), kit.cp, True, 34,
                                                            LARGURA_UTIL - 80, tamanho_minimo=18, tracking=1.5)
    kit.texto_rastreado_centralizado(draw, LARGURA / 2, y, texto_album, fonte_album, INK_MUTED, tracking=1.5)
    y += kit.altura_linha(fonte_album) + 40

    capa = colagem.tile_capa({"album_id": escuta.get("album_id")}, LADO_CAPA)
    x_capa = int(LARGURA / 2 - LADO_CAPA / 2)
    imagem.paste(capa, (x_capa, int(y)))
    draw.rectangle([x_capa, y, x_capa + LADO_CAPA, y + LADO_CAPA], outline=HAIR, width=2)
    y += LADO_CAPA + 36

    if escuta.get("nota") is not None:
        y += kit.linha_estrelas(imagem, draw, LARGURA / 2, y, float(escuta["nota"]), 5, raio=24, gap=15)
        y += 18
        nota_fmt = str(escuta["nota"]).rstrip("0").rstrip(".") if isinstance(escuta["nota"], float) else str(escuta["nota"])
        kit.texto_rastreado_centralizado(draw, LARGURA / 2, y, f"{nota_fmt} DE 5", kit.cp(20), INK_MUTED, tracking=2.5)
        y += 44
    else:
        kit.texto_rastreado_centralizado(draw, LARGURA / 2, y, "SEM NOTA", kit.cp(20), INK_DIM, tracking=2.5)
        y += 44

    # espaço mínimo pra valer a pena abrir um bloco novo (cabeçalho + 1
    # linha de conteúdo + respiro) — abaixo disso, pula o bloco em vez de
    # espremer ele e invadir o rodapé.
    ESPACO_MINIMO_BLOCO = 110

    faixa_favorita = (escuta.get("faixa_favorita") or "").strip()
    if incluir_faixa_favorita and faixa_favorita and (LIMITE_CONTEUDO - y) > ESPACO_MINIMO_BLOCO:
        y += 16
        y = _bloco_faixa_favorita(draw, y, faixa_favorita, LIMITE_CONTEUDO)

    review = (escuta.get("review") or "").strip()
    if incluir_review and review and (LIMITE_CONTEUDO - y) > ESPACO_MINIMO_BLOCO:
        y += 4
        y0 = y
        y += kit.modulo_cabecalho(draw, MARGEM, y, "review")
        fonte_review = kit.jbm(30)
        altura_por_linha = kit.altura_linha(fonte_review) + 10
        y_texto = y + 30
        max_linhas = max(1, int((LIMITE_CONTEUDO - y_texto) / altura_por_linha))
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
