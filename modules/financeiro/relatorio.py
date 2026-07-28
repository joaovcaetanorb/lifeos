"""Relatório mensal em PDF — mesmo estilo visual 'ledger/terminal' do app.

Usa matplotlib pros gráficos (kaleido não está instalado, e matplotlib já é
uma dependência disponível) e reportlab pro layout do documento.
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


def _grafico_categoria(mes_ref: str) -> Image:
    df = calc.gasto_por_categoria(mes_ref)
    fig, ax = plt.subplots(figsize=(6.5, 3), facecolor=utils.COR_FUNDO)
    _estilo_eixos(ax)
    ax.set_title("gastos por categoria", fontsize=10)
    if not df.empty:
        df = df.sort_values("valor")
        cores = [utils.CATEGORIA_CORES.get(c, utils.COR_ACENTO) for c in df["categoria"]]
        ax.barh(df["categoria"], df["valor"], color=cores)
    return _fig_para_imagem(fig)


def _grafico_evolucao_mensal(hoje: date) -> Image:
    df = calc.evolucao_mensal(6, hoje)
    fig, ax = plt.subplots(figsize=(6.5, 3), facecolor=utils.COR_FUNDO)
    _estilo_eixos(ax)
    ax.set_title("evolução mensal", fontsize=10)
    ax.bar(df["mes_nome"], df["valor"], color=utils.COR_ACENTO)
    return _fig_para_imagem(fig)


def _grafico_orcamento(mes_ref: str) -> Image:
    df = calc.planejamento_vs_realizado(mes_ref)
    fig, ax = plt.subplots(figsize=(6.5, 3), facecolor=utils.COR_FUNDO)
    _estilo_eixos(ax)
    ax.set_title("planejado x realizado", fontsize=10)
    if not df.empty:
        posicoes = range(len(df))
        largura = 0.35
        ax.bar([i - largura / 2 for i in posicoes], df["valor_planejado"], width=largura,
               color=utils.COR_PLANEJADO, label="planejado")
        ax.bar([i + largura / 2 for i in posicoes], df["valor_realizado"], width=largura,
               color=utils.COR_REALIZADO, label="realizado")
        ax.set_xticks(list(posicoes))
        ax.set_xticklabels(df["categoria"], rotation=30, ha="right", fontsize=7)
        legenda = ax.legend(facecolor=utils.COR_FUNDO, labelcolor=utils.COR_TEXTO, fontsize=8, frameon=False)
    return _fig_para_imagem(fig)


def _grafico_reserva() -> Image:
    df = calc.evolucao_reserva()
    fig, ax = plt.subplots(figsize=(6.5, 3), facecolor=utils.COR_FUNDO)
    _estilo_eixos(ax)
    ax.set_title("evolução da reserva", fontsize=10)
    if not df.empty:
        ax.plot(df["data"], df["saldo_acumulado"], color=utils.COR_ACENTO, marker="o", markersize=4)
        config = models.get_config()
        if config["reserva_meta"] > 0:
            ax.axhline(config["reserva_meta"], color=utils.COR_TEXTO_MUTED, linestyle="--", linewidth=1)
        fig.autofmt_xdate(rotation=30)
    return _fig_para_imagem(fig)


def _grafico_hora(mes_ref: str) -> Image | None:
    df = calc.gasto_por_hora_mes(mes_ref)
    if df.empty or df["valor"].sum() == 0:
        return None
    fig, ax = plt.subplots(figsize=(6.5, 3), facecolor=utils.COR_FUNDO)
    _estilo_eixos(ax)
    ax.set_title("gastos por horário", fontsize=10)
    ax.bar(df["hora"], df["valor"], color=utils.COR_ACENTO)
    ax.set_xticks(range(0, 24, 2))
    ax.set_xticklabels(df["hora"][::2], rotation=0, fontsize=7)
    return _fig_para_imagem(fig)


def gerar_pdf_mensal(mes_referencia: str) -> bytes:
    """Monta o relatório do mês (resumo, gráficos, insights e nota) e devolve os bytes do PDF."""
    inicio_ciclo, _ = calc.intervalo_ciclo(mes_referencia)
    hoje = date.fromisoformat(inicio_ciclo)
    config = models.get_config()

    fatura = calc.fatura_do_mes(mes_referencia)
    gasto_mes = calc.gasto_total_mes(mes_referencia)
    comprometido = calc.total_comprometido_cartao(hoje)
    comparativo = calc.comparativo_mes_anterior(hoje)
    insights = calc.gerar_insights(hoje)
    nota_info = calc.nota_do_mes(mes_referencia)

    story = []
    story.append(Paragraph("ANÁLISE", _ESTILO_EYEBROW))
    story.append(Paragraph(f"$ relatório — {utils.nome_mes(mes_referencia)}", _ESTILO_TITULO))
    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph(f"gerado em {date.today().strftime('%d/%m/%Y')}", _ESTILO_MUTED))
    story.append(Spacer(1, 0.5 * cm))
    story.append(HRFlowable(width="100%", color=_COR_HAIRLINE, thickness=1))
    story.append(Spacer(1, 0.4 * cm))

    dados_resumo = [
        ["salário", utils.formatar_moeda(config["salario"])],
        ["vale alimentação", utils.formatar_moeda(config["vale_alimentacao"])],
        ["gastos do mês", utils.formatar_moeda(gasto_mes)],
        ["fatura do cartão", utils.formatar_moeda(fatura)],
        ["comprometido no cartão", utils.formatar_moeda(comprometido)],
        ["reserva atual", utils.formatar_moeda(calc.saldo_reserva())],
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

    if comparativo["mes_anterior"] > 0:
        if comparativo["maior"]:
            texto_comp = f"Gastou {utils.formatar_moeda(abs(comparativo['diferenca']))} a mais que no mês anterior."
        else:
            texto_comp = f"Gastou {utils.formatar_moeda(abs(comparativo['diferenca']))} a menos que no mês anterior."
        story.append(Paragraph(texto_comp, _ESTILO_CORPO))
        story.append(Spacer(1, 0.3 * cm))

    story.append(Paragraph("GRÁFICOS", _ESTILO_EYEBROW))
    story.append(Paragraph("visão do mês", _ESTILO_SUBTITULO))
    story.append(_grafico_categoria(mes_referencia))
    story.append(Spacer(1, 0.3 * cm))
    story.append(_grafico_evolucao_mensal(hoje))
    story.append(Spacer(1, 0.3 * cm))
    story.append(_grafico_orcamento(mes_referencia))
    story.append(Spacer(1, 0.3 * cm))
    story.append(_grafico_reserva())
    story.append(Spacer(1, 0.3 * cm))

    grafico_hora = _grafico_hora(mes_referencia)
    if grafico_hora is not None:
        story.append(grafico_hora)
    else:
        story.append(Paragraph(
            "gastos por horário: sem dados suficientes ainda — informe a hora ao lançar um gasto.",
            _ESTILO_MUTED,
        ))
    story.append(Spacer(1, 0.5 * cm))

    if insights:
        story.append(Paragraph("LEITURA AUTOMÁTICA", _ESTILO_EYEBROW))
        story.append(Paragraph("inteligência financeira", _ESTILO_SUBTITULO))
        for texto in insights:
            story.append(Paragraph(f"- {texto}", _ESTILO_CORPO))
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
