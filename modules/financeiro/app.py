"""Tela inicial: explica a lógica do app antes de ir pro dia a dia."""

import streamlit as st

import database
import ui

st.set_page_config(page_title="Controle Financeiro", page_icon="💰", layout="wide")
database.inicializar_banco()
ui.aplicar_tema()

ui.titulo_pagina("como funciona")

ui.eyebrow("a distinção que mais confunde")
st.subheader("Contas fixas x Gastos")
c1, c2 = st.columns(2)
with c1:
    st.markdown("**Contas fixas**")
    st.caption(
        "Casa, ajuda aos irmãos, psicóloga, outra obrigação. Configuradas **uma vez** em "
        "Dashboard → configurações. Descontadas automaticamente todo mês — você nunca lança "
        "isso na aba Gastos."
    )
with c2:
    st.markdown("**Gastos**")
    st.caption(
        "O variável do dia a dia: mercado, transporte, lazer, farmácia. É isso que você "
        "lança na aba Gastos, e é isso que reduz seu saldo diário disponível."
    )
st.warning(
    "Lançar uma conta fixa como 'gasto' faz o valor sair duas vezes (uma automática, "
    "uma manual) e derruba seu saldo sem motivo real."
)

st.divider()

ui.eyebrow("o ciclo")
st.subheader("Do salário ao dinheiro livre")
st.markdown(
    "Assim que o salário 'entra' (no dia útil configurado), o app já desconta, "
    "automaticamente e antes de qualquer gasto seu:\n\n"
    "1. **Contas fixas** — Casa, ajuda, psicóloga, outra obrigação.\n"
    "2. **Fatura do cartão** — calculada sozinha a partir das compras parceladas.\n"
    "3. **Aporte para a reserva** — o valor que você define.\n\n"
    "O que sobra é o **dinheiro livre do mês**, dividido pelos dias até o próximo "
    "pagamento — isso é o que aparece em *Dia do Pagamento*, no Dashboard. Não importa "
    "se você paga as contas fixas fisicamente no dia 6, no dia 8 ou no dia 15: o valor já "
    "sai da conta de 'livre para gastar' desde o primeiro dia do ciclo. Não tem cronologia "
    "pra se preocupar aqui."
)

st.divider()

ui.eyebrow("cada aba")
st.subheader("O que cada tela faz")
st.markdown(
    "- **Dashboard** — visão geral do mês, Dia do Pagamento, gráficos e insights.\n"
    "- **Gastos** — lançamento rápido do variável do dia a dia.\n"
    "- **Cartão** — compras parceladas, fatura calculada, alerta de limite.\n"
    "- **Planejamento** — orçamento por categoria vs. realizado.\n"
    "- **Reserva** — meta de emergência, aportes e retiradas.\n"
)

st.divider()
st.caption("Use o menu à esquerda para navegar entre as telas.")
