"""Dashboard Geral: uma tela só com um resumo de cada área da vida.

Diferente dos outros módulos, este não tem uma tela "como funciona" separada
das telas de uso — a própria home É o resumo, pra caber no princípio de
"entendido em menos de 30 segundos".
"""

from datetime import date

import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import calculations as calc
import ui
import utils

st.set_page_config(page_title="Dashboard Geral", page_icon="🧭", layout="wide")
ui.aplicar_tema()

CHART_LAYOUT = dict(
    margin=dict(l=10, r=10, t=30, b=10),
    height=280,
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="JetBrains Mono, monospace", color=utils.COR_TEXTO_MUTED),
)


def _grid_style(fig: go.Figure) -> go.Figure:
    fig.update_xaxes(showgrid=True, gridcolor=utils.COR_HAIRLINE, zeroline=False)
    fig.update_yaxes(showgrid=False, zeroline=False)
    fig.update_layout(**CHART_LAYOUT)
    return fig


def _card_financeiro() -> None:
    with st.container(border=True, key="card_financeiro"):
        st.markdown("**💰 Financeiro**")
        resumo = calc.resumo_financeiro()
        if resumo is None:
            st.caption("Módulo ainda não usado.")
            return
        st.metric("Saldo até o pagamento", utils.formatar_moeda(resumo["saldo_restante"]))
        st.caption(
            f"Gasto no ciclo: {utils.formatar_moeda(resumo['gasto_mes'])} · "
            f"faltam {resumo['dias_restantes']} dia(s) para "
            f"{resumo['proximo_pagamento'].strftime('%d/%m')}"
        )
        if not resumo["controle_ativo"]:
            st.caption("Controle ainda não ativo — valores zerados até a data configurada.")


def _card_projetos() -> None:
    with st.container(border=True, key="card_projetos"):
        st.markdown("**🎯 Projetos**")
        resumo = calc.resumo_projetos()
        if resumo is None:
            st.caption("Módulo ainda não usado.")
            return
        if resumo["ativos"] == 0:
            st.metric("Projetos ativos", 0)
            st.caption("Nenhum projeto ativo no momento.")
            return
        st.metric("Projetos ativos", resumo["ativos"])
        progresso_txt = f"{resumo['progresso_medio']:.0f}%" if resumo["progresso_medio"] is not None else "—"
        st.caption(
            f"{utils.formatar_moeda(resumo['total_investido'])} investidos no total · "
            f"progresso médio: {progresso_txt}"
        )


def _card_habitos() -> None:
    with st.container(border=True, key="card_habitos"):
        st.markdown("**✅ Hábitos**")
        resumo = calc.resumo_habitos()
        if resumo is None:
            st.caption("Módulo ainda não usado.")
            return
        if resumo["ativos"] == 0:
            st.metric("Hábitos ativos", 0)
            st.caption("Nenhum hábito cadastrado ainda.")
            return
        st.metric("Hábitos ativos", resumo["ativos"])
        st.caption(f"cumprimento médio (30 dias): {resumo['percentual_medio']:.0f}%")


def _card_livros() -> None:
    with st.container(border=True, key="card_livros"):
        st.markdown("**📚 Livros**")
        resumo = calc.resumo_livros()
        if resumo is None:
            st.caption("Módulo ainda não usado.")
            return
        if resumo["lendo_agora"] == 0:
            st.metric("Lendo agora", "—")
        else:
            st.metric("Lendo agora", resumo["titulos_lendo"][0])
            if resumo["lendo_agora"] > 1:
                st.caption("também: " + ", ".join(resumo["titulos_lendo"][1:]))
        st.caption(f"{resumo['lidos_ano']} livro(s) concluído(s) em {date.today().year}")


def _card_musica() -> None:
    with st.container(border=True, key="card_musica"):
        st.markdown("**🎵 Música**")
        resumo = calc.resumo_musica()
        if resumo is None:
            st.caption("Módulo ainda não usado.")
            return
        st.metric("Álbuns este mês", resumo["albuns_mes"])
        if resumo["ultimo_album"]:
            st.caption(f"Último álbum: {resumo['ultimo_album']}")
        else:
            st.caption("Nenhum álbum registrado ainda.")


def _grafico_evolucao_gastos() -> None:
    st.markdown("**Evolução de gastos (Financeiro)**")
    df = calc.evolucao_gastos(6)
    if df.empty or df["valor"].sum() == 0:
        st.caption("Sem dados suficientes ainda.")
        return
    fig = px.bar(df, x="mes_nome", y="valor", text=df["valor"].map(utils.formatar_moeda))
    fig.update_traces(marker_color=utils.COR_REALIZADO, textposition="outside", cliponaxis=False)
    fig.update_layout(xaxis_title=None, yaxis_title=None)
    st.plotly_chart(_grid_style(fig), use_container_width=True)


def _grafico_progresso_projetos() -> None:
    st.markdown("**Progresso dos projetos ativos**")
    df = calc.progresso_projetos_ativos()
    if df.empty:
        st.caption("Nenhum projeto ativo com orçamento definido.")
        return
    fig = px.bar(
        df, x="progresso", y="nome", orientation="h",
        text=df["progresso"].map(lambda v: f"{v:.0f}%"),
    )
    fig.update_traces(marker_color=utils.COR_ACENTO, textposition="outside", cliponaxis=False)
    fig.update_layout(xaxis_title=None, yaxis_title=None, xaxis_range=[0, 100])
    st.plotly_chart(_grid_style(fig), use_container_width=True)


def render() -> None:
    ui.titulo_pagina("dashboard geral")
    ui.eyebrow(date.today().strftime("%d/%m/%Y"))
    st.caption("Um resumo rápido de cada área — abra o módulo correspondente para ver os detalhes.")

    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        _card_financeiro()
    with c2:
        _card_projetos()
    with c3:
        _card_habitos()
    with c4:
        _card_livros()
    with c5:
        _card_musica()

    st.divider()

    col_a, col_b = st.columns(2)
    with col_a:
        _grafico_evolucao_gastos()
    with col_b:
        _grafico_progresso_projetos()


render()
