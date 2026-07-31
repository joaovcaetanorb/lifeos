"""Reserva de emergência: meta, evolução, aportes/retiradas e tempo até a meta."""

from datetime import date

import plotly.graph_objects as go
import streamlit as st

import calculations as calc
import database
import models
import ui
import utils

st.set_page_config(page_title="Reserva | Controle Financeiro", page_icon="💰", layout="wide")
database.inicializar_banco()
ui.aplicar_tema()
ui.mostrar_toast_pendente()

CHART_LAYOUT = dict(
    margin=dict(l=10, r=10, t=40, b=10),
    height=360,
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="JetBrains Mono, monospace", color=utils.COR_TEXTO_MUTED),
)


def _grid_style(fig):
    fig.update_xaxes(showgrid=True, gridcolor=utils.COR_HAIRLINE, zeroline=False)
    fig.update_yaxes(showgrid=False, zeroline=False)
    fig.update_layout(**CHART_LAYOUT)
    return fig


def _secao_metricas() -> None:
    config = models.get_config()
    saldo = calc.saldo_reserva()
    meta = config["reserva_meta"]
    aporte_padrao = config["reserva_aporte_padrao"]

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Valor atual", utils.formatar_moeda(saldo))
    col2.metric("Meta", utils.formatar_moeda(meta))

    percentual = min(saldo / meta * 100, 100) if meta > 0 else 0
    col3.metric("Progresso", f"{percentual:.0f}%")

    meses = calc.tempo_para_meta(meta, aporte_padrao)
    if meses is None:
        tempo_texto = "defina um aporte mensal"
    elif meses == 0:
        tempo_texto = "meta atingida! 🎉"
    else:
        tempo_texto = f"~{meses} meses"
    col4.metric("Tempo até a meta", tempo_texto)

    if meta > 0:
        st.progress(min(saldo / meta, 1.0) if saldo > 0 else 0.0)

    st.caption(
        f"Considerando o aporte mensal padrão de {utils.formatar_moeda(aporte_padrao)} "
        f"(ajustável em Dashboard → Configurações)."
    )


def _grafico_evolucao() -> None:
    ui.eyebrow("evolução")
    st.subheader("Evolução da reserva")
    df = calc.evolucao_reserva()
    if df.empty:
        st.caption("Nenhum movimento cadastrado ainda.")
        return

    config = models.get_config()
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["data"], y=df["saldo_acumulado"], mode="lines+markers",
        line=dict(color=utils.COR_REALIZADO, width=2),
        marker=dict(size=8),
        hovertemplate="%{x}<br>Saldo: %{y:,.2f}<extra></extra>",
    ))
    if config["reserva_meta"] > 0:
        fig.add_hline(
            y=config["reserva_meta"], line_dash="dash", line_color=utils.COR_TEXTO_MUTED,
            annotation_text="Meta", annotation_position="top left",
        )
    fig.update_layout(xaxis_title=None, yaxis_title=None)
    st.plotly_chart(_grid_style(fig), use_container_width=True)


def _formulario_movimento() -> None:
    ui.eyebrow("novo movimento")
    st.subheader("Registrar aporte ou retirada")
    saldo_atual = calc.saldo_reserva()

    with st.form("form_movimento_reserva", clear_on_submit=True):
        c1, c2, c3 = st.columns([1, 1, 1])
        data_mov = c1.date_input("Data", value=date.today(), format="DD/MM/YYYY")
        tipo = c2.selectbox("Tipo", utils.TIPOS_MOVIMENTO_RESERVA)
        valor = c3.number_input("Valor (R$)", min_value=0.0, step=10.0, format="%.2f")

        observacao = st.text_input("Observação (opcional)", placeholder="Ex.: 13º salário, emergência médica...")

        if st.form_submit_button("registrar", use_container_width=True):
            if valor <= 0:
                st.warning("Informe um valor maior que zero.")
            elif tipo == "Retirada" and valor > saldo_atual:
                st.warning(
                    f"Essa retirada deixaria a reserva negativa (saldo atual: {utils.formatar_moeda(saldo_atual)})."
                )
            else:
                models.inserir_movimento_reserva(data_mov.isoformat(), valor, tipo, observacao)
                ui.marcar_toast(f"{tipo} de {utils.formatar_moeda(valor)} registrado.")
                st.rerun()


def _tabela_e_exclusao() -> None:
    ui.eyebrow("histórico")
    st.subheader("Histórico de movimentos")
    movimentos = models.listar_movimentos_reserva()
    if movimentos.empty:
        st.caption("Nenhum movimento cadastrado ainda.")
        return

    exibicao = movimentos[["data", "tipo", "valor", "observacao"]].copy().sort_values("data", ascending=False)
    exibicao["valor"] = exibicao["valor"].map(utils.formatar_moeda)
    exibicao.columns = ["Data", "Tipo", "Valor", "Observação"]
    st.dataframe(exibicao, use_container_width=True, hide_index=True)

    with st.expander("Excluir um movimento"):
        opcoes = {
            int(row["id"]): f"{row['data']} — {row['tipo']} — {utils.formatar_moeda(row['valor'])}"
            for _, row in movimentos.iterrows()
        }
        movimento_id = st.selectbox("Selecione o movimento", list(opcoes.keys()), format_func=lambda i: opcoes[i])
        if st.button("excluir selecionado"):
            models.excluir_movimento_reserva(movimento_id)
            ui.marcar_toast("Movimento excluído.", icone="🗑️")
            st.rerun()


def render() -> None:
    ui.titulo_pagina("reserva")

    _secao_metricas()
    st.divider()
    _grafico_evolucao()
    st.divider()
    _formulario_movimento()
    st.divider()
    _tabela_e_exclusao()


render()
