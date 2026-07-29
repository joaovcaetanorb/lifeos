"""Relatório de humor em PDF — mesmo estilo visual 'ledger/terminal' do
resto do app (e dos relatórios dos módulos financeiro, projetos e hábitos).
"""

import io
from datetime import date, timedelta

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import HRFlowable, Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

import calculations as calc
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
_ESTILO_MUTED = ParagraphStyle("muted", fontName="Courier", fontSize=8.5, textColor=_COR_MUTED, leading=12)
_ESTILO_NOTA = ParagraphStyle("nota", fontName="Courier-Bold", fontSize=40, leading=52, textColor=_COR_ACENTO,
                               alignment=1)
_ESTILO_VEREDITO = ParagraphStyle("veredito", fontName="Courier-Bold", fontSize=12, leading=16, textColor=_COR_TEXTO,
                                  alignment=1, spaceBefore=4, spaceAfter=10)


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


def _grafico_evolucao(dias: int, hoje: date) -> Image | None:
    df = calc.evolucao_diaria(dias, hoje)
    if df["nota"].dropna().empty:
        return None
    fig, ax = plt.subplots(figsize=(6.5, 3), facecolor=utils.COR_FUNDO)
    _estilo_eixos(ax)
    ax.set_title(f"evolução do humor (últimos {dias} dias)", fontsize=10)
    ax.bar(df["data"], df["nota"], color=utils.COR_REALIZADO)
    ax.plot(df["data"], df["media_movel_7d"], color=utils.COR_ACENTO, linewidth=2)
    ax.set_ylim(0, 10)
    return _fig_para_imagem(fig)


def _grafico_tags(data_inicio: str, data_fim: str) -> Image | None:
    df = calc.tags_mais_frequentes(data_inicio, data_fim)
    if df.empty:
        return None
    df = df.sort_values("total")
    fig, ax = plt.subplots(figsize=(6.5, max(2, 0.4 * len(df))), facecolor=utils.COR_FUNDO)
    _estilo_eixos(ax)
    ax.set_title("tags mais frequentes", fontsize=10)
    ax.barh(df["tag"], df["total"], color=utils.COR_ACENTO)
    return _fig_para_imagem(fig)


def gerar_pdf_relatorio(dias: int = 30) -> bytes:
    """Monta o relatório do período (resumo, gráficos, histórico e a nota
    final) e devolve os bytes do PDF."""
    hoje = date.today()
    data_inicio = (hoje - timedelta(days=dias - 1)).isoformat()
    data_fim = hoje.isoformat()
    resumo = calc.resumo_periodo(data_inicio, data_fim)

    story = []
    story.append(Paragraph("HUMOR", _ESTILO_EYEBROW))
    story.append(Paragraph(f"$ relatório — últimos {dias} dias", _ESTILO_TITULO))
    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph(f"gerado em {hoje.strftime('%d/%m/%Y')}", _ESTILO_MUTED))
    story.append(Spacer(1, 0.5 * cm))
    story.append(HRFlowable(width="100%", color=_COR_HAIRLINE, thickness=1))
    story.append(Spacer(1, 0.4 * cm))

    nota_media_txt = f"{resumo['nota_media']:.1f}" if resumo["nota_media"] is not None else "—"
    dados_resumo = [
        ["registros no período", str(resumo["total_registros"])],
        ["nota média", nota_media_txt],
        ["tag mais frequente", resumo["tag_destaque"] or "—"],
    ]
    tabela = Table(dados_resumo, colWidths=[8 * cm, 8 * cm])
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

    if resumo["total_registros"] > 0:
        story.append(Paragraph("GRÁFICOS", _ESTILO_EYEBROW))
        story.append(Paragraph("evolução e padrões", _ESTILO_SUBTITULO))
        grafico_evolucao = _grafico_evolucao(dias, hoje)
        if grafico_evolucao is not None:
            story.append(grafico_evolucao)
            story.append(Spacer(1, 0.3 * cm))
        grafico_tags = _grafico_tags(data_inicio, data_fim)
        if grafico_tags is not None:
            story.append(grafico_tags)
        story.append(Spacer(1, 0.5 * cm))

        story.append(Paragraph("HISTÓRICO DO PERÍODO", _ESTILO_EYEBROW))
        registros = models.listar_registros(data_inicio, data_fim)
        dados_tabela = [["data", "nota", "tags"]]
        for _, r in registros.iterrows():
            tags_txt = ", ".join(utils.texto_para_tags(r["tags"])) or "—"
            dados_tabela.append([f"{utils.formatar_data_br(r['data'])} {r['hora']}".strip(), f"{r['nota']}/10", tags_txt])
        tabela_registros = Table(dados_tabela, colWidths=[4 * cm, 2 * cm, 10 * cm])
        tabela_registros.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), "Courier"),
            ("FONTNAME", (0, 0), (-1, 0), "Courier-Bold"),
            ("TEXTCOLOR", (0, 0), (-1, 0), _COR_MUTED),
            ("TEXTCOLOR", (0, 1), (-1, -1), _COR_TEXTO),
            ("FONTSIZE", (0, 0), (-1, -1), 8.5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LINEBELOW", (0, 0), (-1, -1), 0.5, _COR_HAIRLINE),
        ]))
        story.append(tabela_registros)
        story.append(Spacer(1, 0.5 * cm))

    story.append(HRFlowable(width="100%", color=_COR_HAIRLINE, thickness=1))
    story.append(Spacer(1, 0.4 * cm))
    story.append(Paragraph("VEREDITO", _ESTILO_EYEBROW))
    story.append(Paragraph(f"{nota_media_txt} / 10", _ESTILO_NOTA))
    story.append(Spacer(1, 0.4 * cm))
    story.append(Paragraph(calc.veredito_humor(resumo["nota_media"]), _ESTILO_VEREDITO))

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        topMargin=1.5 * cm, bottomMargin=1.5 * cm, leftMargin=1.5 * cm, rightMargin=1.5 * cm,
    )
    doc.build(story, onFirstPage=_fundo_pagina, onLaterPages=_fundo_pagina)
    buffer.seek(0)
    return buffer.getvalue()
