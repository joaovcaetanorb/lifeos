"""Planejamento mensal: orçamento por categoria vs. realizado."""

from datetime import date

import pandas as pd
import plotly.express as px
import streamlit as st

import calculations as calc
import database
import models
import ui
import utils

st.set_page_config(page_title="Planejamento | Controle Financeiro", page_icon="💰", layout="wide")
database.inicializar_banco()
ui.aplicar_tema()
ui.mostrar_toast_pendente()

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


def _selecionar_mes(hoje: date) -> str:
    # Do mês anterior até dezembro do ano corrente — dá pra planejar todos os
    # meses que ainda faltam, não só um par de meses à frente.
    meses_ate_dezembro = 12 - hoje.month
    opcoes = [
        calc.mes_referencia_atual(utils.somar_meses(hoje, i))
        for i in range(-1, meses_ate_dezembro + 1)
    ]
    rotulos = {m: utils.nome_mes(m) for m in opcoes}
    return st.selectbox("Mês de planejamento", opcoes, index=1, format_func=lambda m: rotulos[m])


def _formulario_orcamento(mes_ref: str) -> None:
    ui.eyebrow("orçamento")
    st.subheader("Definir orçamento do mês")
    existentes = models.listar_planejamento(mes_ref).set_index("categoria")["valor_planejado"].to_dict()

    with st.form(f"form_orcamento_{mes_ref}"):
        valores = {}
        colunas = st.columns(4)
        for i, categoria in enumerate(utils.CATEGORIAS_GASTO):
            valor_atual = float(existentes.get(categoria, 0.0))
            valores[categoria] = colunas[i % 4].number_input(
                categoria, min_value=0.0, value=valor_atual, step=10.0, key=f"orc_{mes_ref}_{categoria}",
            )

        if st.form_submit_button("salvar orçamento", use_container_width=True):
            for categoria, valor in valores.items():
                models.upsert_planejamento(mes_ref, categoria, valor)
            ui.marcar_toast("Orçamento salvo.")
            st.rerun()


def _comparativo(mes_ref: str) -> None:
    df = calc.planejamento_vs_realizado(mes_ref)
    if df.empty:
        st.caption("Nada para comparar ainda.")
        return

    total_planejado = df["valor_planejado"].sum()
    total_realizado = df["valor_realizado"].sum()

    c1, c2, c3 = st.columns(3)
    c1.metric("Planejado", utils.formatar_moeda(total_planejado))
    c2.metric("Realizado", utils.formatar_moeda(total_realizado))
    c3.metric("Restante", utils.formatar_moeda(total_planejado - total_realizado))

    st.markdown("**Detalhamento por categoria**")
    for _, linha in df.iterrows():
        if linha["valor_planejado"] == 0 and linha["valor_realizado"] == 0:
            continue

        st.write(
            f"**{linha['categoria']}** — planejado {utils.formatar_moeda(linha['valor_planejado'])}, "
            f"gasto {utils.formatar_moeda(linha['valor_realizado'])}, "
            f"restante {utils.formatar_moeda(linha['valor_restante'])}"
        )

        percentual = linha["percentual_usado"]
        if pd.isna(percentual):
            st.caption("Sem orçamento definido para esta categoria (gasto fora do planejamento).")
            continue

        st.progress(min(percentual / 100, 1.0))
        if percentual >= 100:
            st.error(f"Orçamento de {linha['categoria']} estourado ({percentual:.0f}% usado).")
        elif percentual >= 80:
            st.warning(f"{linha['categoria']} já usou {percentual:.0f}% do orçamento.")

    st.markdown("**Planejado x Realizado**")
    longo = df.melt(
        id_vars="categoria", value_vars=["valor_planejado", "valor_realizado"],
        var_name="tipo", value_name="valor",
    )
    longo["tipo"] = longo["tipo"].map({"valor_planejado": "Planejado", "valor_realizado": "Realizado"})
    fig = px.bar(
        longo, x="categoria", y="valor", color="tipo", barmode="group",
        color_discrete_map={"Planejado": utils.COR_PLANEJADO, "Realizado": utils.COR_REALIZADO},
    )
    fig.update_layout(xaxis_title=None, yaxis_title=None, legend_title=None)
    st.plotly_chart(_grid_style(fig), use_container_width=True)


def render() -> None:
    hoje = date.today()
    ui.titulo_pagina("planejamento")

    mes_ref = _selecionar_mes(hoje)
    _formulario_orcamento(mes_ref)
    st.divider()
    _comparativo(mes_ref)


render()
