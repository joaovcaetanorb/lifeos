"""Relatório de humor em PDF — mesmo estilo visual 'ledger/terminal' do
resto do app (e dos relatórios dos módulos financeiro, projetos e hábitos).
"""

import calendar
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


def _meses_periodo(data_inicio: str, data_fim: str) -> list[tuple[int, int]]:
    """(ano, mês) de cada mês tocado pelo período do relatório — um
    relatório de 90 dias pode cruzar 3-4 meses, então o calendário vira
    uma grade por mês."""
    inicio, fim = date.fromisoformat(data_inicio), date.fromisoformat(data_fim)
    meses = []
    ano, mes = inicio.year, inicio.month
    while (ano, mes) <= (fim.year, fim.month):
        meses.append((ano, mes))
        ano, mes = (ano + 1, 1) if mes == 12 else (ano, mes + 1)
    return meses


def _grafico_calendario_mes(ano: int, mes: int) -> Image | None:
    """Mesma lógica do calendário por mês da página (um retângulo por dia,
    dividido em faixas cronológicas quando há mais de um registro) — só
    que desenhado com matplotlib pra virar imagem estática do PDF."""
    primeiro_dia_semana, dias_no_mes = calendar.monthrange(ano, mes)
    data_inicio = date(ano, mes, 1).isoformat()
    data_fim = date(ano, mes, dias_no_mes).isoformat()
    df = calc.registros_periodo(data_inicio, data_fim)
    if df.empty:
        return None

    registros_por_dia = {
        dia: grupo.sort_values("datetime") for dia, grupo in df.groupby(df["datetime"].dt.day)
    }
    dias_semana_labels = ["seg", "ter", "qua", "qui", "sex", "sáb", "dom"]
    n_semanas = (primeiro_dia_semana + dias_no_mes - 1) // 7 + 1

    fig, ax = plt.subplots(figsize=(6.5, 1.15 * n_semanas + 0.6), facecolor=utils.COR_FUNDO)
    ax.set_facecolor(utils.COR_FUNDO)
    ax.set_title(f"calendário de humor — {utils.NOMES_MESES[mes - 1]} de {ano}", fontsize=10, color=utils.COR_TEXTO)

    for dia in range(1, dias_no_mes + 1):
        posicao = primeiro_dia_semana + dia - 1
        semana, coluna = posicao // 7, posicao % 7
        y_topo = n_semanas - 1 - semana  # matplotlib cresce pra cima; inverte pra semana 0 ficar no topo
        registros_dia = registros_por_dia.get(dia)

        if registros_dia is None or registros_dia.empty:
            ax.add_patch(plt.Rectangle(
                (coluna, y_topo), 1, 1, facecolor=utils.COR_FUNDO_ALT, edgecolor=utils.COR_HAIRLINE, linewidth=0.5,
            ))
            cor_numero = utils.COR_TEXTO_MUTED
        else:
            n = len(registros_dia)
            for i, (_, registro) in enumerate(registros_dia.iterrows()):
                altura = 1 / n
                y0 = y_topo + 1 - (i + 1) * altura
                ax.add_patch(plt.Rectangle(
                    (coluna, y0), 1, altura, facecolor=utils.cor_nota(registro["nota"]),
                    edgecolor=utils.COR_FUNDO, linewidth=0.5,
                ))
            cor_numero = utils.COR_TEXTO

        ax.text(coluna + 0.06, y_topo + 0.92, str(dia), fontsize=6, color=cor_numero, ha="left", va="top")

    ax.set_xlim(0, 7)
    ax.set_ylim(0, n_semanas)
    ax.set_xticks([i + 0.5 for i in range(7)])
    ax.set_xticklabels(dias_semana_labels, fontsize=8, color=utils.COR_TEXTO_MUTED)
    ax.set_yticks([])
    ax.tick_params(length=0)
    for spine in ax.spines.values():
        spine.set_visible(False)
    return _fig_para_imagem(fig)


def _grafico_tags(data_inicio: str, data_fim: str) -> Image | None:
    df = calc.tags_mais_frequentes(data_inicio, data_fim)
    if df.empty:
        return None
    df = df.sort_values("total")
    fig, ax = plt.subplots(figsize=(6.5, max(2, 0.4 * len(df))), facecolor=utils.COR_FUNDO)
    _estilo_eixos(ax)
    ax.set_title("tags mais frequentes", fontsize=10)
    cores = [utils.cor_tag(tag) for tag in df["tag"]]
    ax.barh(df["tag"], df["total"], color=cores)
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
        for ano_mes, mes_mes in _meses_periodo(data_inicio, data_fim):
            grafico_calendario = _grafico_calendario_mes(ano_mes, mes_mes)
            if grafico_calendario is not None:
                story.append(grafico_calendario)
                story.append(Spacer(1, 0.15 * cm))
        story.append(Paragraph("vermelho = nota baixa · azul = nota alta", _ESTILO_MUTED))
        story.append(Spacer(1, 0.4 * cm))

        grafico_tags = _grafico_tags(data_inicio, data_fim)
        if grafico_tags is not None:
            story.append(grafico_tags)
            story.append(Paragraph("azul = sentimento positivo · vermelho = negativo", _ESTILO_MUTED))
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
