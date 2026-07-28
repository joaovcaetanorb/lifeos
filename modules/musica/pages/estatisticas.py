"""Estatísticas: poucos números que importam sobre a jornada musical."""

import plotly.graph_objects as go
import streamlit as st

import calculations as calc
import database
import ui
import utils

st.set_page_config(page_title="Estatísticas | Música", page_icon="🎵", layout="wide")
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


def _secao_resumo_ano() -> None:
    resumo = calc.resumo_ano_atual()
    ui.eyebrow(f"resumo de {resumo['ano']}")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Álbuns novos", resumo["albuns_novos"])
    c2.metric("Escutas", resumo["escutas"])
    c3.metric("Nota média", utils.formatar_nota(resumo["nota_media"]))
    c4.metric("Artista destaque", resumo["artista_destaque"] or "—")


def _grafico_escutas_por_mes() -> None:
    ui.eyebrow("atividade")
    st.subheader("Escutas por mês")
    df = calc.escutas_por_mes(12)
    if df["total"].sum() == 0:
        st.caption("Nenhuma escuta registrada nos últimos 12 meses.")
        return
    fig = go.Figure()
    fig.add_trace(go.Bar(x=df["mes_nome"], y=df["total"], marker_color=utils.COR_ACENTO))
    st.plotly_chart(_grid_style(fig), use_container_width=True)


def _grafico_distribuicao_notas() -> None:
    ui.eyebrow("avaliações")
    st.subheader("Distribuição de notas")
    df = calc.distribuicao_notas()
    if df["total"].sum() == 0:
        st.caption("Nenhuma escuta avaliada ainda.")
        return
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=[utils.formatar_nota(n) for n in df["nota"]], y=df["total"], marker_color=utils.COR_ACENTO,
    ))
    st.plotly_chart(_grid_style(fig), use_container_width=True)


def _grafico_top_artistas() -> None:
    ui.eyebrow("recorrência")
    st.subheader("Artistas mais escutados")
    df = calc.top_artistas(8)
    if df.empty:
        st.caption("Nenhuma escuta registrada ainda.")
        return
    df = df.sort_values("total")
    fig = go.Figure()
    fig.add_trace(go.Bar(x=df["total"], y=df["artista_nome"], orientation="h", marker_color=utils.COR_ACENTO))
    st.plotly_chart(_grid_style(fig), use_container_width=True)


def render() -> None:
    ui.titulo_pagina("estatísticas")

    _secao_resumo_ano()
    st.divider()
    _grafico_escutas_por_mes()
    st.divider()
    _grafico_distribuicao_notas()
    st.divider()
    _grafico_top_artistas()


render()
