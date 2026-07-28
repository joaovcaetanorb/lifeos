"""Controle de cartão de crédito: compras parceladas, fatura calculada e alertas."""

from datetime import date

import plotly.express as px
import streamlit as st

import calculations as calc
import database
import models
import ui
import utils

st.set_page_config(page_title="Cartão | Controle Financeiro", page_icon="💰", layout="wide")
database.inicializar_banco()
ui.aplicar_tema()

CHART_LAYOUT = dict(
    margin=dict(l=10, r=10, t=40, b=10),
    height=320,
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="JetBrains Mono, monospace", color=utils.COR_TEXTO_MUTED),
)

NIVEL_PARA_ALERTA = {
    "ok": st.success,
    "atencao": st.info,
    "alerta": st.warning,
    "critico": st.error,
}


def _grid_style(fig):
    fig.update_xaxes(showgrid=True, gridcolor=utils.COR_HAIRLINE, zeroline=False)
    fig.update_yaxes(showgrid=False, zeroline=False)
    fig.update_layout(**CHART_LAYOUT)
    return fig


def _secao_metricas_e_alerta(hoje: date) -> None:
    mes_ref = calc.mes_referencia_atual(hoje)
    config = models.get_config()

    fatura_atual = calc.fatura_do_mes(mes_ref)
    comprometido = calc.total_comprometido_cartao(hoje)
    projecao = calc.projecao_fatura_atual(hoje)
    limite_info = calc.percentual_limite_cartao(fatura_atual, config["salario"] + config["vale_alimentacao"])

    col1, col2, col3 = st.columns(3)
    col1.metric("Fatura atual", utils.formatar_moeda(fatura_atual))
    col2.metric("Total comprometido (todas as parcelas futuras)", utils.formatar_moeda(comprometido))
    col3.metric("Projeção da fatura atual", utils.formatar_moeda(projecao))

    alerta_fn = NIVEL_PARA_ALERTA[limite_info["nivel"]]
    alerta_fn(
        f"{limite_info['mensagem']} (limite recomendado: {utils.formatar_moeda(limite_info['limite_recomendado'])}, "
        f"30% da renda mensal)"
    )


def _grafico_proximas_faturas(hoje: date) -> None:
    st.markdown("**Próximas faturas (calculadas a partir das compras cadastradas)**")
    df = calc.proximas_faturas(6, hoje)
    fig = px.bar(df, x="mes_nome", y="valor", text=df["valor"].map(utils.formatar_moeda))
    fig.update_traces(marker_color=utils.COR_REALIZADO, textposition="outside", cliponaxis=False)
    fig.update_layout(xaxis_title=None, yaxis_title=None)
    st.plotly_chart(_grid_style(fig), use_container_width=True)


def _formulario_nova_compra() -> None:
    ui.eyebrow("novo lançamento")
    st.subheader("Cadastrar compra no cartão")
    with st.form("form_nova_compra", clear_on_submit=True):
        c1, c2 = st.columns([2, 1])
        descricao = c1.text_input("Descrição", placeholder="Ex.: Notebook, Roupas, Presente...")
        valor_total = c2.number_input("Valor total (R$)", min_value=0.0, step=1.0, format="%.2f")

        c3, c4, c5 = st.columns(3)
        data_compra = c3.date_input("Data da compra", value=date.today(), format="DD/MM/YYYY")
        parcelas = c4.number_input("Nº de parcelas", min_value=1, max_value=48, value=1, step=1)
        categoria = c5.selectbox("Categoria", utils.CATEGORIAS_GASTO)

        if st.form_submit_button("salvar compra", use_container_width=True):
            if not descricao:
                st.warning("Informe uma descrição para a compra.")
            elif valor_total <= 0:
                st.warning("Informe um valor maior que zero.")
            else:
                models.inserir_compra_cartao(descricao, data_compra.isoformat(), valor_total, int(parcelas), categoria)
                st.success(f"Compra de {utils.formatar_moeda(valor_total)} em {int(parcelas)}x salva.")
                st.rerun()


def _tabela_e_exclusao(hoje: date) -> None:
    ui.eyebrow("histórico")
    st.subheader("Compras cadastradas")
    detalhe = calc.detalhe_compras_cartao(hoje)
    if detalhe.empty:
        st.caption("Nenhuma compra cadastrada ainda.")
        return

    exibicao = detalhe[[
        "descricao", "data_compra", "valor_total", "parcelas", "valor_parcela",
        "parcelas_pagas", "parcelas_restantes", "categoria",
    ]].copy()
    exibicao["valor_total"] = exibicao["valor_total"].map(utils.formatar_moeda)
    exibicao["valor_parcela"] = exibicao["valor_parcela"].map(utils.formatar_moeda)
    exibicao["progresso"] = exibicao["parcelas_pagas"].astype(str) + "/" + detalhe["parcelas"].astype(str)
    exibicao = exibicao.drop(columns=["parcelas_pagas", "parcelas_restantes", "parcelas"])
    exibicao.columns = ["Descrição", "Data da compra", "Valor total", "Valor da parcela", "Categoria", "Parcelas pagas"]
    st.dataframe(exibicao, use_container_width=True, hide_index=True)

    with st.expander("Excluir uma compra"):
        opcoes = {
            int(row["id"]): f"{row['descricao']} — {utils.formatar_moeda(row['valor_total'])} ({row['parcelas']}x)"
            for _, row in detalhe.iterrows()
        }
        compra_id = st.selectbox("Selecione a compra", list(opcoes.keys()), format_func=lambda i: opcoes[i])
        st.caption("Remove todas as parcelas futuras dessa compra do cálculo da fatura.")
        if st.button("excluir selecionada"):
            models.excluir_compra_cartao(compra_id)
            st.success("Compra excluída.")
            st.rerun()


def render() -> None:
    hoje = date.today()
    ui.titulo_pagina("cartao")

    _secao_metricas_e_alerta(hoje)
    st.divider()
    _grafico_proximas_faturas(hoje)
    st.divider()
    _formulario_nova_compra()
    st.divider()
    _tabela_e_exclusao(hoje)


render()
