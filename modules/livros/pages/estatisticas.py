"""Estatísticas: poucos números que importam sobre a jornada de leitura,
filtráveis por período."""

from datetime import date

import plotly.graph_objects as go
import streamlit as st

import calculations as calc
import database
import models
import ui
import utils

st.set_page_config(page_title="Estatísticas | Livros", page_icon="📚", layout="wide")
database.inicializar_banco()
ui.aplicar_tema()

CHART_LAYOUT = dict(
    margin=dict(l=10, r=10, t=40, b=10),
    height=340,
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="JetBrains Mono, monospace", color=utils.COR_TEXTO_MUTED),
)


def _grid_style(fig):
    fig.update_xaxes(showgrid=True, gridcolor=utils.COR_HAIRLINE, zeroline=False)
    fig.update_yaxes(showgrid=False, zeroline=False)
    fig.update_layout(**CHART_LAYOUT)
    return fig


def _periodo_selecionado() -> tuple[str, str, str]:
    """Retorna (data_inicio_iso, data_fim_iso, rótulo pra exibição)."""
    hoje = date.today()
    atalho = st.radio(
        "Período", ["Este mês", "Este ano", "Todos os tempos", "Personalizado"],
        horizontal=True, label_visibility="collapsed", key="stats_periodo",
    )

    if atalho == "Este mês":
        inicio = hoje.replace(day=1)
        return inicio.isoformat(), hoje.isoformat(), "este mês"
    if atalho == "Este ano":
        inicio = date(hoje.year, 1, 1)
        return inicio.isoformat(), hoje.isoformat(), str(hoje.year)
    if atalho == "Todos os tempos":
        intervalo = models.intervalo_datas_leituras()
        if intervalo is None:
            return hoje.isoformat(), hoje.isoformat(), "todos os tempos"
        return intervalo[0], intervalo[1], "todos os tempos"

    c1, c2 = st.columns(2)
    inicio = c1.date_input("De", value=date(hoje.year, 1, 1), format="DD/MM/YYYY", key="stats_data_inicio")
    fim = c2.date_input("Até", value=hoje, format="DD/MM/YYYY", key="stats_data_fim")
    return inicio.isoformat(), fim.isoformat(), "período personalizado"


def _secao_resumo(data_inicio: str, data_fim: str, rotulo: str) -> None:
    resumo = calc.resumo_periodo(data_inicio, data_fim)
    ui.eyebrow(f"resumo — {rotulo}")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Livros concluídos", resumo["livros_concluidos"])
    c2.metric("Leituras registradas", resumo["leituras"])
    c3.metric("Nota média", utils.formatar_nota(resumo["nota_media"]))
    c4.metric("Autor destaque", resumo["autor_destaque"] or "—")


def _grafico_concluidos_por_mes(data_inicio: str, data_fim: str) -> None:
    ui.eyebrow("ritmo de leitura")
    st.subheader("Livros concluídos por mês")
    df = calc.livros_concluidos_por_mes(data_inicio, data_fim)
    if df["total"].sum() == 0:
        st.caption("Nenhum livro concluído nesse período.")
        return
    fig = go.Figure()
    fig.add_trace(go.Bar(x=df["mes_nome"], y=df["total"], marker_color=utils.COR_ACENTO))
    st.plotly_chart(_grid_style(fig), use_container_width=True)


def _grafico_distribuicao_notas(data_inicio: str, data_fim: str) -> None:
    ui.eyebrow("avaliações")
    st.subheader("Distribuição de notas")
    df = calc.distribuicao_notas(data_inicio, data_fim)
    if df["total"].sum() == 0:
        st.caption("Nenhuma leitura avaliada nesse período.")
        return
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=[utils.formatar_nota(n) for n in df["nota"]], y=df["total"], marker_color=utils.COR_ACENTO,
    ))
    st.plotly_chart(_grid_style(fig), use_container_width=True)


def _grafico_top_autores(data_inicio: str, data_fim: str) -> None:
    ui.eyebrow("recorrência")
    st.subheader("Autores mais lidos")
    df = calc.top_autores(data_inicio, data_fim, 8)
    if df.empty:
        st.caption("Nenhuma leitura registrada nesse período.")
        return
    df = df.sort_values("total")
    fig = go.Figure()
    fig.add_trace(go.Bar(x=df["total"], y=df["autor_nome"], orientation="h", marker_color=utils.COR_ACENTO))
    st.plotly_chart(_grid_style(fig), use_container_width=True)


def render() -> None:
    ui.titulo_pagina("estatísticas")

    data_inicio, data_fim, rotulo = _periodo_selecionado()
    st.divider()

    _secao_resumo(data_inicio, data_fim, rotulo)
    st.divider()
    _grafico_concluidos_por_mes(data_inicio, data_fim)
    st.divider()
    _grafico_distribuicao_notas(data_inicio, data_fim)
    st.divider()
    _grafico_top_autores(data_inicio, data_fim)


render()
