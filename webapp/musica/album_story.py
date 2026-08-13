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


def _bloco_faixa_favorita(draw: ImageDraw.ImageDraw, y: float, faixa: str, cor_accent: str) -> float:
    """Faixa favorita costuma vir como uma lista "Música A, Música B, ..."
    (checklist da tracklist no formulário do diário) — cada música vira uma
    pill (mesmo componente de kit.chip usado nos destaques do relatório de
    período), em vez de texto corrido: fica claro que é uma LISTA. Sempre
    mostra TODAS as faixas (sem cortar em "+N") — prioridade é a lista
    completa; é a review que cede espaço se sobrar pouco, não o contrário."""
    itens = [t.strip() for t in faixa.split(",") if t.strip()]
    titulo = "faixas favoritas" if len(itens) > 1 else "faixa favorita"
    y0 = y
    y += kit.modulo_cabecalho(draw, MARGEM, y, titulo)
    fonte = kit.jbm(25, bold=True)
    y_texto = y + 14

    altura_ocupada = kit.linha_chips_centralizada(draw, y_texto, itens, fonte, gap=12,
                                                   cor_borda=cor_accent, cor_texto=cor_accent)
    y_fim = y_texto + altura_ocupada
    draw.rectangle([MARGEM, y0, LARGURA - MARGEM, y_fim + 22], outline=HAIR, width=2)
    return y_fim + 22 + 36


def gerar_album_story(escuta: dict, incluir_review: bool = True, incluir_faixa_favorita: bool = True,
                       cor_hex: str | None = None, usar_cor_capa: bool = False) -> bytes:
    """cor_hex (manual) tem prioridade sobre usar_cor_capa (automática, via
    colagem.cor_dominante); sem nenhum dos dois, mantém o verde padrão do
    app — a personalização é sempre opt-in, nunca muda o comportamento
    default de quem não mexeu nessas opções."""
    capa = colagem.tile_capa({"album_id": escuta.get("album_id")}, LADO_CAPA)

    personalizado = bool(cor_hex) or usar_cor_capa
    if cor_hex:
        cor_accent = cor_hex
    elif usar_cor_capa:
        cor_accent = colagem.cor_dominante(capa)
    else:
        cor_accent = ACCENT_BRIGHT

    imagem = kit.fundo(cor_accent if personalizado else None)
    draw = ImageDraw.Draw(imagem)

    y = kit.bloco_topbar(imagem, draw, "LIFEOS · MÓDULO MÚSICA", date.today().strftime("%d/%m/%Y"))

    kit.eyebrow(draw, MARGEM, y, "diário — avaliação", INK_MUTED, 22)
    y += 44

    # artista em destaque — o "protagonista" do card, tratamento igual ao
    # "ARTISTA #1" do relatório de período, só que como herói da tela
    kit.texto_rastreado_centralizado(draw, LARGURA / 2, y, "ARTISTA", kit.cp(20), cor_accent, tracking=3)
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

    x_capa = int(LARGURA / 2 - LADO_CAPA / 2)
    imagem.paste(capa, (x_capa, int(y)))
    draw.rectangle([x_capa, y, x_capa + LADO_CAPA, y + LADO_CAPA], outline=HAIR, width=2)
    y += LADO_CAPA + 36

    if escuta.get("nota") is not None:
        y += kit.linha_estrelas(imagem, draw, LARGURA / 2, y, float(escuta["nota"]), 5, raio=24, gap=15, cor_cheia=cor_accent)
        y += 18
        nota_fmt = str(escuta["nota"]).rstrip("0").rstrip(".") if isinstance(escuta["nota"], float) else str(escuta["nota"])
        kit.texto_rastreado_centralizado(draw, LARGURA / 2, y, f"{nota_fmt} DE 5", kit.cp(20), INK_MUTED, tracking=2.5)
        y += 44
    else:
        kit.texto_rastreado_centralizado(draw, LARGURA / 2, y, "SEM NOTA", kit.cp(20), INK_DIM, tracking=2.5)
        y += 44

    # espaço mínimo pra abrir o bloco da review — cabeçalho + 1 linha
    # truncada cabem em ~150px; como LIMITE_CONTEUDO já deixa 92px de folga
    # antes da linha real do rodapé, 60px de sobra aqui ainda garante que o
    # pior caso (1 linha só) não encosta no rodapé. Um valor alto demais
    # aqui (110) já fez a review sumir por só 5px de diferença — real bug
    # visto em produção com a review "Banger!!!" de A. Vandal.
    ESPACO_MINIMO_BLOCO = 60

    review = (escuta.get("review") or "").strip()
    tem_review_a_mostrar = incluir_review and bool(review)

    # faixa favorita tem prioridade sobre a review: sempre mostra a lista
    # completa (o usuário prefere assim); é a review que cede espaço/some
    # se sobrar pouco depois dela, não o contrário.
    faixa_favorita = (escuta.get("faixa_favorita") or "").strip()
    if incluir_faixa_favorita and faixa_favorita:
        y += 16
        y = _bloco_faixa_favorita(draw, y, faixa_favorita, cor_accent)

    if tem_review_a_mostrar and (LIMITE_CONTEUDO - y) > ESPACO_MINIMO_BLOCO:
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
