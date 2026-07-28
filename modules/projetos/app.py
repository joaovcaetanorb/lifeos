"""Tela inicial: explica a lógica do app antes de ir pro dia a dia."""

import streamlit as st

import database
import ui

st.set_page_config(page_title="Projetos", page_icon="🎯", layout="wide")
database.inicializar_banco()
ui.aplicar_tema()

ui.titulo_pagina("como funciona")

ui.eyebrow("a ideia")
st.subheader("Metas viram projetos concretos")
st.markdown(
    "Cada meta que você tem — uma viagem, um instrumento, um curso, uma reforma — vira um "
    "**projeto** com orçamento, um checklist do que precisa ser feito e um histórico de "
    "quanto você já guardou pra ele. Nada de anotar isso espalhado; cada projeto tem um lugar "
    "só dele."
)

st.divider()

ui.eyebrow("os três números")
st.subheader("O que cada projeto acompanha")
c1, c2, c3 = st.columns(3)
with c1:
    st.markdown("**Orçamento**")
    st.caption("Quanto o projeto custa no total, definido uma vez ao criar (pode editar depois).")
with c2:
    st.markdown("**Progresso financeiro**")
    st.caption("Quanto você já guardou (aportes) sobre o orçamento total — em %.")
with c3:
    st.markdown("**Checklist**")
    st.caption("As etapas concretas do projeto, marcadas conforme forem concluídas.")

st.divider()

ui.eyebrow("aportes")
st.subheader("Como o dinheiro entra no projeto")
st.markdown(
    "Você registra **aportes** (valor + data) sempre que separa dinheiro pra esse projeto — "
    "o valor acumulado é a soma de todos os aportes, não um número que você digita direto. "
    "Isso mantém um histórico de quando e quanto você guardou."
)

st.divider()
st.caption("Use o menu à esquerda para ver e gerenciar seus projetos.")
