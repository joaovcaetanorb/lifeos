"""Relatório de projetos em PDF — mesmo estilo visual 'ledger/terminal' do
resto do app (e do relatório do módulo financeiro).

Dois modos: lista de projetos filtrada por status, ou um projeto específico
com detalhe completo (checklist, aportes, gráfico de evolução).
"""

import io
from datetime import date

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from PIL import Image as PILImage

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import HRFlowable, Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

import calculations as calc
import database
import models
import utils

plt.rcParams["font.family"] = "monospace"

_COR_FUNDO = colors.HexColor(utils.COR_FUNDO)
_COR_TEXTO = colors.HexColor(utils.COR_TEXTO)
_COR_MUTED = colors.HexColor(utils.COR_TEXTO_MUTED)
_COR_ACENTO = colors.HexColor(utils.COR_ACENTO)
_COR_HAIRLINE = colors.HexColor(utils.COR_HAIRLINE)

_ESTILO_EYEBROW = ParagraphStyle("eyebrow", fontName="Courier", fontSize=8, leading=10, textColor=_COR_MUTED,
                                 spaceAfter=2)
_ESTILO_TITULO = ParagraphStyle("titulo", fontName="Courier-Bold", fontSize=22, leading=30, textColor=_COR_TEXTO,
                                 spaceAfter=4)
_ESTILO_SUBTITULO = ParagraphStyle("subtitulo", fontName="Courier-Bold", fontSize=13, leading=18, textColor=_COR_TEXTO,
                                   spaceBefore=12, spaceAfter=6)
_ESTILO_CORPO = ParagraphStyle("corpo", fontName="Courier", fontSize=9.5, textColor=_COR_TEXTO, leading=14)
_ESTILO_MUTED = ParagraphStyle("muted", fontName="Courier", fontSize=8.5, textColor=_COR_MUTED, leading=12)
_ESTILO_MUTED_RECUADO = ParagraphStyle("muted_recuado", parent=_ESTILO_MUTED, leftIndent=14)


def _fundo_pagina(canvas_obj, doc) -> None:
    canvas_obj.saveState()
    canvas_obj.setFillColor(_COR_FUNDO)
    canvas_obj.rect(0, 0, doc.pagesize[0], doc.pagesize[1], fill=1, stroke=0)
    canvas_obj.restoreState()


def _estilo_eixos(ax) -> None:
    ax.set_facecolor(utils.COR_FUNDO)
    ax.tick_params(colors=utils.COR_TEXTO_MUTED, labelsize=8)
    for spine in ax.spines.values():
        spine.set_color(utils.COR_HAIRLINE)
    ax.title.set_color(utils.COR_TEXTO)


def _fig_para_imagem(fig, largura_cm: float = 16.5) -> Image:
    buf = io.BytesIO()
    fig.tight_layout()
    fig.savefig(buf, format="png", dpi=160, facecolor=fig.get_facecolor())
    plt.close(fig)
    buf.seek(0)
    proporcao = fig.get_size_inches()[1] / fig.get_size_inches()[0]
    largura = largura_cm * cm
    return Image(buf, width=largura, height=largura * proporcao)


def _cabecalho(story: list, eyebrow: str, titulo: str) -> None:
    story.append(Paragraph(eyebrow, _ESTILO_EYEBROW))
    story.append(Paragraph(f"$ {titulo}", _ESTILO_TITULO))
    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph(f"gerado em {date.today().strftime('%d/%m/%Y')}", _ESTILO_MUTED))
    story.append(Spacer(1, 0.5 * cm))
    story.append(HRFlowable(width="100%", color=_COR_HAIRLINE, thickness=1))
    story.append(Spacer(1, 0.4 * cm))


def _thumbnail(foto_path: str, largura_cm: float = 2.5, largura_px: int = 400) -> Image | None:
    """Miniatura de tamanho padronizado: redimensiona de verdade (não só a
    exibição) antes de embutir no PDF, senão uma foto de câmera de alguns MB
    infla o arquivo inteiro mesmo aparecendo pequena na página."""
    if not foto_path:
        return None
    caminho = database.DB_DIR / foto_path
    if not caminho.exists():
        return None
    with PILImage.open(caminho) as img:
        img = img.convert("RGB")
        proporcao = img.height / img.width
        img = img.resize((largura_px, max(1, int(largura_px * proporcao))))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=80)
        buf.seek(0)
    largura = largura_cm * cm
    return Image(buf, width=largura, height=largura * proporcao)


def _bloco_item_checklist(story: list, item, estilo_titulo: ParagraphStyle) -> None:
    marca = "[x]" if item["concluido"] else "[ ]"
    vencido = calc.item_vencido(item["prazo"], bool(item["concluido"]))
    prazo_txt = f" — prazo: {utils.formatar_data_br(item['prazo'])}" if item["prazo"] else ""
    if vencido:
        prazo_txt += " (atrasado)"
    story.append(Paragraph(f"{marca} {item['descricao']}{prazo_txt}", estilo_titulo))
    if item["notas"]:
        story.append(Paragraph(item["notas"], _ESTILO_MUTED_RECUADO))
    if item["link"]:
        story.append(Paragraph(item["link"], _ESTILO_MUTED_RECUADO))
    thumb = _thumbnail(item["foto_path"], largura_cm=2.5)
    if thumb is not None:
        story.append(Spacer(1, 0.1 * cm))
        story.append(thumb)
        story.append(Spacer(1, 0.1 * cm))


def _build(story: list) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        topMargin=1.5 * cm, bottomMargin=1.5 * cm, leftMargin=1.5 * cm, rightMargin=1.5 * cm,
    )
    doc.build(story, onFirstPage=_fundo_pagina, onLaterPages=_fundo_pagina)
    buffer.seek(0)
    return buffer.getvalue()


# ---------------------------------------------------------------------------
# Relatório de lista (filtrado por status)
# ---------------------------------------------------------------------------

def _grafico_progresso(projetos_com_progresso: list[dict]) -> Image | None:
    com_orcamento = [p for p in projetos_com_progresso if p["progresso_financeiro"] is not None]
    if not com_orcamento:
        return None
    fig, ax = plt.subplots(figsize=(6.5, max(2, 0.5 * len(com_orcamento))), facecolor=utils.COR_FUNDO)
    _estilo_eixos(ax)
    ax.set_title("progresso financeiro por projeto", fontsize=10)
    nomes = [p["nome"] for p in com_orcamento]
    valores = [p["progresso_financeiro"] for p in com_orcamento]
    ax.barh(nomes, valores, color=utils.COR_ACENTO)
    ax.set_xlim(0, 100)
    return _fig_para_imagem(fig)


def gerar_pdf_lista(filtro_status: str | None) -> bytes:
    """filtro_status: 'Ativo' | 'Pausado' | 'Concluído' | None (todos)."""
    projetos_df = models.listar_projetos(status=filtro_status)
    rotulo_filtro = filtro_status if filtro_status else "todos os projetos"

    story = []
    _cabecalho(story, "PROJETOS", f"relatório — {rotulo_filtro}")

    if projetos_df.empty:
        story.append(Paragraph("Nenhum projeto nessa categoria ainda.", _ESTILO_CORPO))
        return _build(story)

    projetos = []
    for _, row in projetos_df.iterrows():
        pid = int(row["id"])
        projetos.append({
            "id": pid,
            "nome": row["nome"],
            "descricao": row["descricao"],
            "observacoes": row["observacoes"],
            "foto_path": row["foto_path"],
            "status": row["status"],
            "orcamento": row["orcamento"],
            "valor_acumulado": calc.valor_acumulado(pid),
            "progresso_financeiro": calc.progresso_financeiro(pid, row["orcamento"]),
            "progresso_checklist": calc.progresso_checklist(pid),
        })

    dados_resumo = [["projeto", "status", "orçamento", "acumulado", "financeiro", "checklist"]]
    for p in projetos:
        dados_resumo.append([
            p["nome"],
            p["status"],
            utils.formatar_moeda(p["orcamento"]),
            utils.formatar_moeda(p["valor_acumulado"]),
            f"{p['progresso_financeiro']:.0f}%" if p["progresso_financeiro"] is not None else "—",
            f"{p['progresso_checklist']:.0f}%" if p["progresso_checklist"] is not None else "—",
        ])
    tabela = Table(dados_resumo, colWidths=[4.5 * cm, 2.3 * cm, 2.6 * cm, 2.6 * cm, 2.3 * cm, 2.3 * cm])
    tabela.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "Courier"),
        ("FONTNAME", (0, 0), (-1, 0), "Courier-Bold"),
        ("TEXTCOLOR", (0, 0), (-1, 0), _COR_MUTED),
        ("TEXTCOLOR", (0, 1), (-1, -1), _COR_TEXTO),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LINEBELOW", (0, 0), (-1, -1), 0.5, _COR_HAIRLINE),
    ]))
    story.append(tabela)
    story.append(Spacer(1, 0.5 * cm))

    grafico = _grafico_progresso(projetos)
    if grafico is not None:
        story.append(grafico)
        story.append(Spacer(1, 0.5 * cm))

    story.append(Paragraph("DETALHES", _ESTILO_EYEBROW))
    for p in projetos:
        story.append(Paragraph(p["nome"], _ESTILO_SUBTITULO))

        capa = _thumbnail(p["foto_path"], largura_cm=2.5)
        if capa is not None:
            story.append(capa)
            story.append(Spacer(1, 0.15 * cm))

        if p["descricao"]:
            story.append(Paragraph(p["descricao"], _ESTILO_CORPO))
        if p["observacoes"]:
            story.append(Paragraph(p["observacoes"], _ESTILO_MUTED))

        itens = models.listar_checklist(p["id"])
        for _, item in itens.iterrows():
            _bloco_item_checklist(story, item, _ESTILO_MUTED)
        story.append(Spacer(1, 0.3 * cm))

    return _build(story)


# ---------------------------------------------------------------------------
# Relatório de um projeto específico
# ---------------------------------------------------------------------------

def _grafico_evolucao_projeto(projeto_id: int) -> Image | None:
    df = calc.evolucao_aportes(projeto_id)
    if df.empty:
        return None
    fig, ax = plt.subplots(figsize=(6.5, 3), facecolor=utils.COR_FUNDO)
    _estilo_eixos(ax)
    ax.set_title("evolução dos aportes", fontsize=10)
    ax.plot(df["data"], df["saldo_acumulado"], color=utils.COR_ACENTO, marker="o", markersize=4)
    fig.autofmt_xdate(rotation=30)
    return _fig_para_imagem(fig)


def gerar_pdf_projeto(projeto_id: int) -> bytes:
    projeto = models.obter_projeto(projeto_id)
    if projeto is None:
        raise ValueError(f"Projeto {projeto_id} não encontrado.")

    valor_acum = calc.valor_acumulado(projeto_id)
    prog_fin = calc.progresso_financeiro(projeto_id, projeto["orcamento"])
    prog_check = calc.progresso_checklist(projeto_id)

    story = []
    _cabecalho(story, "PROJETO", projeto["nome"])

    capa = _thumbnail(projeto["foto_path"], largura_cm=4.5)
    if capa is not None:
        story.append(capa)
        story.append(Spacer(1, 0.4 * cm))

    dados_resumo = [
        ["status", projeto["status"]],
        ["orçamento", utils.formatar_moeda(projeto["orcamento"])],
        ["valor acumulado", utils.formatar_moeda(valor_acum)],
        ["progresso financeiro", f"{prog_fin:.0f}%" if prog_fin is not None else "sem orçamento definido"],
        ["progresso checklist", f"{prog_check:.0f}%" if prog_check is not None else "sem itens"],
    ]
    tabela = Table(dados_resumo, colWidths=[6 * cm, 10 * cm])
    tabela.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "Courier"),
        ("TEXTCOLOR", (0, 0), (0, -1), _COR_MUTED),
        ("TEXTCOLOR", (1, 0), (1, -1), _COR_TEXTO),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LINEBELOW", (0, 0), (-1, -2), 0.5, _COR_HAIRLINE),
    ]))
    story.append(tabela)
    story.append(Spacer(1, 0.5 * cm))

    if projeto["descricao"]:
        story.append(Paragraph(projeto["descricao"], _ESTILO_CORPO))
        story.append(Spacer(1, 0.3 * cm))

    grafico = _grafico_evolucao_projeto(projeto_id)
    if grafico is not None:
        story.append(grafico)
        story.append(Spacer(1, 0.5 * cm))

    story.append(Paragraph("CHECKLIST", _ESTILO_EYEBROW))
    story.append(Paragraph("etapas", _ESTILO_SUBTITULO))
    itens = models.listar_checklist(projeto_id)
    if itens.empty:
        story.append(Paragraph("Nenhum item cadastrado.", _ESTILO_MUTED))
    else:
        for _, item in itens.iterrows():
            _bloco_item_checklist(story, item, _ESTILO_CORPO)
    story.append(Spacer(1, 0.5 * cm))

    story.append(Paragraph("APORTES", _ESTILO_EYEBROW))
    story.append(Paragraph("histórico", _ESTILO_SUBTITULO))
    aportes = models.listar_aportes(projeto_id)
    if aportes.empty:
        story.append(Paragraph("Nenhum aporte registrado.", _ESTILO_MUTED))
    else:
        dados_aportes = [["data", "valor", "observação"]]
        for _, aporte in aportes.iterrows():
            dados_aportes.append([aporte["data"], utils.formatar_moeda(aporte["valor"]), aporte["observacao"] or ""])
        tabela_aportes = Table(dados_aportes, colWidths=[3 * cm, 3 * cm, 10 * cm])
        tabela_aportes.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), "Courier"),
            ("FONTNAME", (0, 0), (-1, 0), "Courier-Bold"),
            ("TEXTCOLOR", (0, 0), (-1, 0), _COR_MUTED),
            ("TEXTCOLOR", (0, 1), (-1, -1), _COR_TEXTO),
            ("FONTSIZE", (0, 0), (-1, -1), 8.5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LINEBELOW", (0, 0), (-1, -1), 0.5, _COR_HAIRLINE),
        ]))
        story.append(tabela_aportes)
    story.append(Spacer(1, 0.5 * cm))

    if projeto["observacoes"]:
        story.append(Paragraph("OBSERVAÇÕES", _ESTILO_EYEBROW))
        story.append(Paragraph(projeto["observacoes"], _ESTILO_CORPO))

    return _build(story)
