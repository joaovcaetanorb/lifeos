"""Relatório de humor em PDF — usa o tema compartilhado
webapp/core/pdf_theme.py (mesma cara do console novo: LED, prompt "$",
caixas com hairline, KPIs com linha de destaque no topo)."""

import calendar
import io
from datetime import date, timedelta

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer

from core import pdf_theme as tema
from . import calculations as calc
from . import repo
from . import utils

plt.rcParams["font.family"] = "monospace"

_LARGURA_UTIL = 18.0  # cm — A4 (21) - margens (1.5*2)
_LARGURA_GRAFICO = _LARGURA_UTIL - 0.8


def _fig_para_imagem(fig, largura_cm: float = _LARGURA_UTIL) -> Image:
    buf = io.BytesIO()
    fig.tight_layout()
    fig.savefig(buf, format="png", dpi=160, facecolor=fig.get_facecolor())
    plt.close(fig)
    buf.seek(0)
    proporcao = fig.get_size_inches()[1] / fig.get_size_inches()[0]
    largura = largura_cm * cm
    return Image(buf, width=largura, height=largura * proporcao)


def _meses_periodo(data_inicio: str, data_fim: str) -> list[tuple[int, int]]:
    inicio, fim = date.fromisoformat(data_inicio), date.fromisoformat(data_fim)
    meses = []
    ano, mes = inicio.year, inicio.month
    while (ano, mes) <= (fim.year, fim.month):
        meses.append((ano, mes))
        ano, mes = (ano + 1, 1) if mes == 12 else (ano, mes + 1)
    return meses


def _grafico_calendario_mes(ano: int, mes: int) -> Image | None:
    """Um retângulo por dia, dividido em faixas cronológicas quando há mais
    de um registro no mesmo dia — mesma lógica do calendário da página."""
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

    fig, ax = plt.subplots(figsize=(6.5, 1.15 * n_semanas + 0.6), facecolor=tema.BG)
    ax.set_facecolor(tema.BG)
    ax.set_title(f"calendário de humor — {utils.NOMES_MESES[mes - 1]} de {ano}", fontsize=10, color=tema.INK)

    for dia in range(1, dias_no_mes + 1):
        posicao = primeiro_dia_semana + dia - 1
        semana, coluna = posicao // 7, posicao % 7
        y_topo = n_semanas - 1 - semana
        registros_dia = registros_por_dia.get(dia)

        if registros_dia is None or registros_dia.empty:
            ax.add_patch(plt.Rectangle(
                (coluna, y_topo), 1, 1, facecolor=tema.PANEL, edgecolor=tema.HAIR, linewidth=0.5,
            ))
            cor_numero = tema.INK_MUTED
        else:
            n = len(registros_dia)
            for i, (_, registro) in enumerate(registros_dia.iterrows()):
                altura = 1 / n
                y0 = y_topo + 1 - (i + 1) * altura
                ax.add_patch(plt.Rectangle(
                    (coluna, y0), 1, altura, facecolor=utils.cor_nota(registro["nota"]),
                    edgecolor=tema.BG, linewidth=0.5,
                ))
            cor_numero = tema.INK

        ax.text(coluna + 0.06, y_topo + 0.92, str(dia), fontsize=6, color=cor_numero, ha="left", va="top")

    ax.set_xlim(0, 7)
    ax.set_ylim(0, n_semanas)
    ax.set_xticks([i + 0.5 for i in range(7)])
    ax.set_xticklabels(dias_semana_labels, fontsize=8, color=tema.INK_MUTED)
    ax.set_yticks([])
    ax.tick_params(length=0)
    for spine in ax.spines.values():
        spine.set_visible(False)
    return _fig_para_imagem(fig, _LARGURA_GRAFICO)


def _grafico_tags(data_inicio: str, data_fim: str) -> Image | None:
    df = calc.tags_mais_frequentes(data_inicio, data_fim)
    if df.empty:
        return None
    df = df.sort_values("total")
    fig, ax = plt.subplots(figsize=(6.5, max(2, 0.4 * len(df))), facecolor=tema.BG)
    ax.set_facecolor(tema.BG)
    ax.tick_params(colors=tema.INK_MUTED, labelsize=8)
    for spine in ax.spines.values():
        spine.set_color(tema.HAIR)
    ax.set_title("tags mais frequentes", fontsize=10, color=tema.INK)
    cores = [utils.cor_tag(tag) for tag in df["tag"]]
    ax.barh(df["tag"], df["total"], color=cores)
    return _fig_para_imagem(fig, _LARGURA_GRAFICO)


def gerar_pdf_relatorio(dias: int = 30) -> bytes:
    s = tema.estilos()
    hoje = date.today()
    data_inicio = (hoje - timedelta(days=dias - 1)).isoformat()
    data_fim = hoje.isoformat()
    resumo = calc.resumo_periodo(data_inicio, data_fim)

    story = []
    story += tema.cabecalho("humor", f"relatório — últimos {dias} dias", f"gerado em {hoje.strftime('%d/%m/%Y')}")

    nota_media_txt = f"{resumo['nota_media']:.1f}" if resumo["nota_media"] is not None else "—"
    story.append(tema.linha_kpis([
        ("registros no período", str(resumo["total_registros"])),
        ("nota média", nota_media_txt),
        ("tag em destaque", resumo["tag_destaque"] or "—"),
    ], _LARGURA_UTIL))
    story.append(Spacer(1, 0.55 * cm))

    if resumo["total_registros"] > 0:
        story.append(tema.eyebrow("gráficos"))
        story.append(Spacer(1, 0.15 * cm))
        graficos = []
        for ano_mes, mes_mes in _meses_periodo(data_inicio, data_fim):
            grafico_calendario = _grafico_calendario_mes(ano_mes, mes_mes)
            if grafico_calendario is not None:
                graficos.append(grafico_calendario)
        if graficos:
            # cada mês na sua própria caixa (não empilhados numa Table só) —
            # um calendário de 6 semanas já é uma imagem alta; juntar vários
            # meses numa única célula de Table pode passar da altura da
            # página, e Table não quebra o conteúdo de uma célula entre
            # páginas (LayoutError).
            for grafico in graficos:
                story.append(tema.caixa([grafico], _LARGURA_UTIL))
                story.append(Spacer(1, 0.25 * cm))
            story.append(Paragraph("vermelho = nota baixa · azul = nota alta", s["muted"]))
            story.append(Spacer(1, 0.55 * cm))

        grafico_tags = _grafico_tags(data_inicio, data_fim)
        if grafico_tags is not None:
            story.append(tema.caixa([
                grafico_tags,
                Paragraph("azul = sentimento positivo · vermelho = negativo", s["muted"]),
            ], _LARGURA_UTIL))
            story.append(Spacer(1, 0.55 * cm))

        story.append(tema.eyebrow("histórico do período"))
        story.append(Spacer(1, 0.15 * cm))
        registros = repo.listar_registros(data_inicio, data_fim)
        linhas = []
        for _, r in registros.iterrows():
            tags_txt = ", ".join(utils.texto_para_tags(r["tags"])) or "—"
            linhas.append([f"{utils.formatar_data_br(r['data'])} {r['hora']}".strip(), f"{r['nota']}/10", tags_txt])
        story.append(tema.tabela_dados(["data", "nota", "tags"], linhas, [4.0, 2.5, 11.5]))
        story.append(Spacer(1, 0.55 * cm))

    story.append(tema.hairline())
    story.append(Spacer(1, 0.45 * cm))
    story.append(tema.eyebrow("veredito"))
    story.append(Paragraph(f"{nota_media_txt} / 10", s["nota"]))
    story.append(Spacer(1, 0.1 * cm))
    story.append(Paragraph(calc.veredito_humor(resumo["nota_media"]), s["veredito"]))

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        topMargin=1.5 * cm, bottomMargin=1.5 * cm, leftMargin=1.5 * cm, rightMargin=1.5 * cm,
    )
    doc.build(story, onFirstPage=tema.fundo_pagina, onLaterPages=tema.fundo_pagina)
    buffer.seek(0)
    return buffer.getvalue()
