"""Relatório de hábitos em PDF — usa o tema compartilhado
webapp/core/pdf_theme.py (mesma cara do console novo: LED, prompt "$",
caixas com hairline, KPIs com linha de destaque no topo)."""

import io
from datetime import date

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer

from core import pdf_theme as tema
from . import calculations as calc

plt.rcParams["font.family"] = "monospace"

_LARGURA_UTIL = 18.0  # cm — A4 (21) - margens (1.5*2)
_LARGURA_GRAFICO = _LARGURA_UTIL - 0.8  # desconta o padding da caixa que envolve os gráficos


def _estilo_eixos(ax) -> None:
    ax.set_facecolor(tema.BG)
    ax.tick_params(colors=tema.INK_MUTED, labelsize=8)
    for spine in ax.spines.values():
        spine.set_color(tema.HAIR)
    ax.title.set_color(tema.INK)


def _fig_para_imagem(fig, largura_cm: float = _LARGURA_UTIL) -> Image:
    buf = io.BytesIO()
    fig.tight_layout()
    fig.savefig(buf, format="png", dpi=160, facecolor=fig.get_facecolor())
    plt.close(fig)
    buf.seek(0)
    proporcao = fig.get_size_inches()[1] / fig.get_size_inches()[0]
    largura = largura_cm * cm
    return Image(buf, width=largura, height=largura * proporcao)


def _grafico_progresso(dias: int, hoje: date, registros, habitos) -> Image | None:
    df = calc.progresso_por_habito(dias, hoje, registros, habitos)
    if df.empty:
        return None
    fig, ax = plt.subplots(figsize=(6.5, max(2, 0.5 * len(df))), facecolor=tema.BG)
    _estilo_eixos(ax)
    ax.set_title(f"% cumprido por hábito (últimos {dias} dias)", fontsize=10, color=tema.INK)
    ax.barh(df["nome"], df["percentual"], color=tema.ACCENT)
    ax.set_xlim(0, 100)
    return _fig_para_imagem(fig, _LARGURA_GRAFICO)


def _grafico_evolucao(hoje: date, registros, habitos) -> Image | None:
    df = calc.evolucao_semanal(8, hoje, registros, habitos)
    if df.empty or df["percentual"].sum() == 0:
        return None
    fig, ax = plt.subplots(figsize=(6.5, 3), facecolor=tema.BG)
    _estilo_eixos(ax)
    ax.set_title("evolução semanal (todos os hábitos)", fontsize=10, color=tema.INK)
    ax.bar(df["semana"], df["percentual"], color=tema.ACCENT_BRIGHT)
    ax.set_ylim(0, 100)
    return _fig_para_imagem(fig, _LARGURA_GRAFICO)


def gerar_pdf_relatorio(dias: int = 30) -> bytes:
    s = tema.estilos()
    hoje = date.today()
    habitos = calc.buscar_habitos()
    registros = calc.buscar_registros_todos()
    resumo = calc.resumo_geral(hoje, registros, habitos)
    nota_info = calc.nota_periodo(dias, hoje, registros, habitos)

    story = []
    story += tema.cabecalho("hábitos", f"relatório — últimos {dias} dias", f"gerado em {hoje.strftime('%d/%m/%Y')}")

    media_txt = f"{resumo['percentual_medio']:.0f}%" if resumo["percentual_medio"] is not None else "—"
    story.append(tema.linha_kpis([
        ("hábitos ativos", str(resumo["ativos"])),
        ("cumprimento médio", media_txt),
    ], _LARGURA_UTIL))
    story.append(Spacer(1, 0.55 * cm))

    if resumo["ativos"] > 0:
        story.append(tema.eyebrow("gráficos"))
        story.append(Spacer(1, 0.15 * cm))
        graficos = []
        grafico_progresso = _grafico_progresso(dias, hoje, registros, habitos)
        if grafico_progresso is not None:
            graficos.append(grafico_progresso)
            graficos.append(Spacer(1, 0.3 * cm))
        grafico_evolucao = _grafico_evolucao(hoje, registros, habitos)
        if grafico_evolucao is not None:
            graficos.append(grafico_evolucao)
        if graficos:
            story.append(tema.caixa(graficos, _LARGURA_UTIL))
            story.append(Spacer(1, 0.55 * cm))

        story.append(tema.eyebrow("detalhe por hábito"))
        story.append(Spacer(1, 0.15 * cm))
        linhas = []
        for _, h in habitos.iterrows():
            r = calc.resumo_habito(int(h["id"]), hoje, registros)
            linhas.append([h["nome"], f"{r['streak']} dia(s)", f"{r['percentual_30d']:.0f}%"])
        story.append(tema.tabela_dados(
            ["hábito", "streak atual", f"% ({dias}d)"], linhas, [9.0, 4.5, 4.5],
        ))
        story.append(Spacer(1, 0.55 * cm))

    story.append(tema.hairline())
    story.append(Spacer(1, 0.45 * cm))
    story.append(tema.eyebrow("veredito"))
    conteudo_veredito = [
        Spacer(1, 0.1 * cm),
        Paragraph(f"{nota_info['nota']:.1f} / 10", s["nota"]),
        Spacer(1, 0.1 * cm),
        Paragraph(nota_info["veredito"], s["veredito"]),
    ]
    for detalhe in nota_info["detalhes"]:
        conteudo_veredito.append(Paragraph(f"— {detalhe}", s["muted"]))
    conteudo_veredito.append(Spacer(1, 0.1 * cm))
    story.append(tema.caixa(conteudo_veredito, _LARGURA_UTIL, accent_topo=True))

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        topMargin=1.5 * cm, bottomMargin=1.5 * cm, leftMargin=1.5 * cm, rightMargin=1.5 * cm,
    )
    doc.build(story, onFirstPage=tema.fundo_pagina, onLaterPages=tema.fundo_pagina)
    buffer.seek(0)
    return buffer.getvalue()
