"""Tela inicial: explica a lógica do app antes de ir pro dia a dia."""

import streamlit as st

import database
import ui

st.set_page_config(page_title="Hábitos", page_icon="✅", layout="wide")
database.inicializar_banco()
ui.aplicar_tema()

ui.titulo_pagina("como funciona")

ui.eyebrow("a ideia")
st.subheader("Marcar o que foi cumprido, dia a dia")
st.markdown(
    "Cada hábito que você quer acompanhar (exercitar, ler, meditar, dormir cedo...) vira um "
    "item nessa lista. Todo dia você só marca um checkbox: fez ou não fez. Sem nota, sem "
    "escala — o objetivo é ser rápido o suficiente pra realmente usar todo dia."
)

st.divider()

ui.eyebrow("o que isso vira")
st.subheader("Streak e percentual cumprido")
c1, c2 = st.columns(2)
with c1:
    st.markdown("**Streak atual**")
    st.caption(
        "Quantos dias seguidos você vem cumprindo o hábito, contando até hoje (ou até ontem, "
        "se hoje ainda não foi marcado — a streak só quebra à meia-noite, não assim que o dia "
        "começa)."
    )
with c2:
    st.markdown("**% cumprido (30 dias)**")
    st.caption(
        "De quantos dos últimos 30 dias você cumpriu o hábito. Mostra o ritmo real, sem um dia "
        "isolado bom ou ruim pesar demais."
    )

st.divider()
st.caption("Use o menu à esquerda para ver e marcar seus hábitos.")
