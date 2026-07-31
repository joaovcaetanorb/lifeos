"""Cadastro de gastos — a tela para usar todo dia (lançar em menos de 30s)."""

from datetime import date, datetime

import streamlit as st

import calculations as calc
import database
import models
import ui
import utils

st.set_page_config(page_title="Gastos | Controle Financeiro", page_icon="💰", layout="wide")
database.inicializar_banco()
ui.aplicar_tema()
ui.mostrar_toast_pendente()


def _formulario_novo_gasto() -> None:
    ui.eyebrow("novo lançamento")
    st.subheader("Lançar gasto")
    st.caption(
        "Use aqui só o variável do dia a dia (mercado, transporte, lazer...). "
        "Contas fixas (Casa, ajuda, psicóloga) já são descontadas automaticamente "
        "no Dia do Pagamento — não lance elas aqui, senão o valor sai duas vezes."
    )
    with st.form("form_novo_gasto", clear_on_submit=True):
        c1, c2, c3 = st.columns([1, 2, 1])
        data_gasto = c1.date_input("Data", value=date.today(), format="DD/MM/YYYY")
        descricao = c2.text_input("Descrição", placeholder="Ex.: Mercado, Uber, Cinema...")
        valor = c3.number_input("Valor (R$)", min_value=0.0, step=1.0, format="%.2f")

        c4, c5, c6 = st.columns([2, 2, 1])
        categoria = c4.selectbox("Categoria", utils.CATEGORIAS_GASTO)
        forma_pagamento = c5.selectbox("Forma de pagamento", utils.FORMAS_PAGAMENTO)
        hora_gasto = c6.time_input("Hora", value=datetime.now().time())

        enviado = st.form_submit_button("salvar gasto", use_container_width=True)
        if enviado:
            if not descricao:
                st.warning("Informe uma descrição para o gasto.")
            elif valor <= 0:
                st.warning("Informe um valor maior que zero.")
            else:
                models.inserir_gasto(
                    data_gasto.isoformat(), descricao, valor, categoria, forma_pagamento,
                    hora_gasto.strftime("%H:%M"),
                )
                ui.marcar_toast(f"Gasto de {utils.formatar_moeda(valor)} em {categoria} salvo.")
                st.rerun()


def _formulario_renda_extra() -> None:
    ui.eyebrow("renda extra")
    st.subheader("Registrar renda extra ocasional")
    st.caption(
        "Freela, bico, venda avulsa — qualquer entrada de dinheiro que não seja o "
        "salário fixo. Soma direto no 'dinheiro livre' do Dia do Pagamento, a partir "
        "da data que você informar aqui (mesma lógica de um gasto: cai no ciclo pela data)."
    )
    with st.form("form_renda_extra", clear_on_submit=True):
        c1, c2, c3 = st.columns([1, 2, 1])
        data_receita = c1.date_input("Data", value=date.today(), format="DD/MM/YYYY", key="data_renda_extra")
        descricao = c2.text_input("Descrição", placeholder="Ex.: Freela de fim de semana")
        valor = c3.number_input("Valor (R$)", min_value=0.0, step=1.0, format="%.2f", key="valor_renda_extra")

        if st.form_submit_button("salvar renda extra", use_container_width=True):
            if not descricao:
                st.warning("Informe uma descrição para a renda extra.")
            elif valor <= 0:
                st.warning("Informe um valor maior que zero.")
            else:
                models.inserir_receita_extra(data_receita.isoformat(), descricao, valor)
                ui.marcar_toast(f"Renda extra de {utils.formatar_moeda(valor)} registrada.")
                st.rerun()


def _tabela_renda_extra(mes_ref: str) -> None:
    inicio, fim = calc.intervalo_ciclo(mes_ref)
    receitas = models.listar_receitas_extras(data_inicio=inicio, data_fim=fim)
    if receitas.empty:
        st.caption("Nenhuma renda extra lançada neste ciclo.")
        return

    total = receitas["valor"].sum()
    st.caption(f"Total de renda extra no ciclo: {utils.formatar_moeda(total)}")

    exibicao = receitas[["data", "descricao", "valor"]].copy()
    exibicao["valor"] = exibicao["valor"].map(utils.formatar_moeda)
    exibicao.columns = ["Data", "Descrição", "Valor"]
    st.dataframe(exibicao, use_container_width=True, hide_index=True)

    with st.expander("Excluir uma renda extra"):
        opcoes = {
            int(row["id"]): f"{row['data']} — {row['descricao']} — {utils.formatar_moeda(row['valor'])}"
            for _, row in receitas.iterrows()
        }
        receita_id = st.selectbox(
            "Selecione o lançamento", list(opcoes.keys()), format_func=lambda i: opcoes[i],
            key="sel_receita_extra",
        )
        if st.button("excluir selecionada", key="del_receita_extra"):
            models.excluir_receita_extra(receita_id)
            ui.marcar_toast("Renda extra excluída.", icone="🗑️")
            st.rerun()


def _selecionar_mes(hoje: date) -> str:
    opcoes = [calc.mes_referencia_atual(utils.somar_meses(hoje, -i)) for i in range(6)]
    rotulos = {m: utils.nome_mes(m) for m in opcoes}
    return st.selectbox("Mês", opcoes, format_func=lambda m: rotulos[m])


def _tabela_e_exclusao(mes_ref: str) -> None:
    inicio, fim = calc.intervalo_ciclo(mes_ref)
    gastos = models.listar_gastos(data_inicio=inicio, data_fim=fim)

    total = gastos["valor"].sum() if not gastos.empty else 0.0
    col1, col2 = st.columns(2)
    col1.metric("Total no mês", utils.formatar_moeda(total))
    col2.metric("Lançamentos", len(gastos))

    if gastos.empty:
        st.caption("Nenhum gasto lançado neste mês.")
        return

    exibicao = gastos[["data", "hora", "descricao", "valor", "categoria", "forma_pagamento"]].copy()
    exibicao["valor"] = exibicao["valor"].map(utils.formatar_moeda)
    exibicao.columns = ["Data", "Hora", "Descrição", "Valor", "Categoria", "Forma de pagamento"]
    st.dataframe(exibicao, use_container_width=True, hide_index=True)

    with st.expander("Excluir um lançamento"):
        opcoes = {
            int(row["id"]): f"{row['data']} — {row['descricao']} — {utils.formatar_moeda(row['valor'])}"
            for _, row in gastos.iterrows()
        }
        gasto_id = st.selectbox("Selecione o lançamento", list(opcoes.keys()), format_func=lambda i: opcoes[i])
        if st.button("excluir selecionado"):
            models.excluir_gasto(gasto_id)
            ui.marcar_toast("Lançamento excluído.", icone="🗑️")
            st.rerun()


def render() -> None:
    hoje = date.today()
    ui.titulo_pagina("gastos")

    _formulario_novo_gasto()
    st.divider()
    _formulario_renda_extra()
    st.divider()

    ui.eyebrow("histórico")
    st.subheader("Lançamentos")
    mes_ref = _selecionar_mes(hoje)
    _tabela_e_exclusao(mes_ref)

    st.markdown("**Renda extra do ciclo**")
    _tabela_renda_extra(mes_ref)


render()
