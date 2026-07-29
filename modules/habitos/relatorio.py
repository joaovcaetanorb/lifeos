"""Relatório de hábitos em PDF — mesmo estilo visual 'ledger/terminal' do
resto do app (e dos relatórios dos módulos financeiro e projetos).
"""

import io
from datetime import date

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
_ESTILO_CORPO = ParagraphStyle("corpo", fontName="Courier", fontSize=9.5, textColor=_COR_TEXTO, leading=14)
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


def _grafico_progresso(dias: int, hoje: date) -> Image | None:
    df = calc.progresso_por_habito(dias, hoje)
    if df.empty:
        return None
    fig, ax = plt.subplots(figsize=(6.5, max(2, 0.5 * len(df))), facecolor=utils.COR_FUNDO)
    _estilo_eixos(ax)
    ax.set_title(f"% cumprido por hábito (últimos {dias} dias)", fontsize=10)
    ax.barh(df["nome"], df["percentual"], color=utils.COR_ACENTO)
    ax.set_xlim(0, 100)
    return _fig_para_imagem(fig)


def _grafico_evolucao(hoje: date) -> Image | None:
    df = calc.evolucao_semanal(8, hoje)
    if df.empty or df["percentual"].sum() == 0:
        return None
    fig, ax = plt.subplots(figsize=(6.5, 3), facecolor=utils.COR_FUNDO)
    _estilo_eixos(ax)
    ax.set_title("evolução semanal (todos os hábitos)", fontsize=10)
    ax.bar(df["semana"], df["percentual"], color=utils.COR_REALIZADO)
    ax.set_ylim(0, 100)
    return _fig_para_imagem(fig)


def gerar_pdf_relatorio(dias: int = 30) -> bytes:
    """Monta o relatório do período (resumo, gráficos, detalhe por hábito
    e a nota final) e devolve os bytes do PDF."""
    hoje = date.today()
    resumo = calc.resumo_geral(hoje)
    nota_info = calc.nota_periodo(dias, hoje)

    story = []
    story.append(Paragraph("HÁBITOS", _ESTILO_EYEBROW))
    story.append(Paragraph(f"$ relatório — últimos {dias} dias", _ESTILO_TITULO))
    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph(f"gerado em {hoje.strftime('%d/%m/%Y')}", _ESTILO_MUTED))
    story.append(Spacer(1, 0.5 * cm))
    story.append(HRFlowable(width="100%", color=_COR_HAIRLINE, thickness=1))
    story.append(Spacer(1, 0.4 * cm))

    media_txt = f"{resumo['percentual_medio']:.0f}%" if resumo["percentual_medio"] is not None else "—"
    dados_resumo = [
        ["hábitos ativos", str(resumo["ativos"])],
        ["cumprimento médio", media_txt],
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

    if resumo["ativos"] > 0:
        story.append(Paragraph("GRÁFICOS", _ESTILO_EYEBROW))
        story.append(Paragraph("progresso do período", _ESTILO_SUBTITULO))
        grafico_progresso = _grafico_progresso(dias, hoje)
        if grafico_progresso is not None:
            story.append(grafico_progresso)
            story.append(Spacer(1, 0.3 * cm))
        grafico_evolucao = _grafico_evolucao(hoje)
        if grafico_evolucao is not None:
            story.append(grafico_evolucao)
        story.append(Spacer(1, 0.5 * cm))

        story.append(Paragraph("DETALHE POR HÁBITO", _ESTILO_EYEBROW))
        habitos = models.listar_habitos()
        dados_tabela = [["hábito", "streak atual", f"% ({dias}d)"]]
        for _, h in habitos.iterrows():
            r = calc.resumo_habito(int(h["id"]), hoje)
            dados_tabela.append([h["nome"], f"{r['streak']} dia(s)", f"{r['percentual_30d']:.0f}%"])
        tabela_habitos = Table(dados_tabela, colWidths=[8 * cm, 4 * cm, 4 * cm])
        tabela_habitos.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), "Courier"),
            ("FONTNAME", (0, 0), (-1, 0), "Courier-Bold"),
            ("TEXTCOLOR", (0, 0), (-1, 0), _COR_MUTED),
            ("TEXTCOLOR", (0, 1), (-1, -1), _COR_TEXTO),
            ("FONTSIZE", (0, 0), (-1, -1), 8.5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LINEBELOW", (0, 0), (-1, -1), 0.5, _COR_HAIRLINE),
        ]))
        story.append(tabela_habitos)
        story.append(Spacer(1, 0.5 * cm))

    story.append(HRFlowable(width="100%", color=_COR_HAIRLINE, thickness=1))
    story.append(Spacer(1, 0.4 * cm))
    story.append(Paragraph("VEREDITO", _ESTILO_EYEBROW))
    story.append(Paragraph(f"{nota_info['nota']:.1f} / 10", _ESTILO_NOTA))
    story.append(Spacer(1, 0.4 * cm))
    story.append(Paragraph(nota_info["veredito"], _ESTILO_VEREDITO))
    for detalhe in nota_info["detalhes"]:
        story.append(Paragraph(f"- {detalhe}", _ESTILO_MUTED))

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        topMargin=1.5 * cm, bottomMargin=1.5 * cm, leftMargin=1.5 * cm, rightMargin=1.5 * cm,
    )
    doc.build(story, onFirstPage=_fundo_pagina, onLaterPages=_fundo_pagina)
    buffer.seek(0)
    return buffer.getvalue()
