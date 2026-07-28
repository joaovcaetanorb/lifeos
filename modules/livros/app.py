"""Tela inicial: explica a lógica do app antes de ir pro dia a dia."""

import streamlit as st

import database
import ui

st.set_page_config(page_title="Livros", page_icon="📚", layout="wide")
database.inicializar_banco()
ui.aplicar_tema()

ui.titulo_pagina("como funciona")

ui.eyebrow("a ideia")
st.subheader("Um diário de leitura, não uma meta de páginas")
st.markdown(
    "Aqui você registra sua relação com os livros que passam pela sua vida: quando começou, "
    "quando terminou (ou abandonou), o que achou. Cada **leitura** é uma entrada de diário — "
    "com o tempo isso vira um histórico de como sua cabeça mudou lendo as mesmas coisas."
)

st.divider()

ui.eyebrow("o que muda tudo")
st.subheader("Reler faz parte do produto")
st.markdown(
    "Um livro pode ter **várias leituras** ao longo dos anos. Reler algo 10 anos depois e "
    "sentir outra coisa completamente é normal — registre as duas. O livro é só o catálogo "
    "(nome, autor, ano); a opinião mora na leitura, não no livro."
)

st.divider()

ui.eyebrow("status")
st.subheader("Lendo, concluído ou abandonado")
st.markdown(
    "Cada leitura tem um status. Um livro sem nenhuma leitura registrada ainda é simplesmente "
    "**não iniciado** — está na estante, esperando."
)

st.divider()

ui.eyebrow("cada aba")
st.subheader("O que cada tela faz")
c1, c2 = st.columns(2)
with c1:
    st.markdown("**Diário**")
    st.caption("Registrar uma leitura nova e ver a linha do tempo de tudo que você já leu.")
with c2:
    st.markdown("**Estante**")
    st.caption("Catálogo dos livros cadastrados, cada um com o histórico de todas as suas leituras.")

st.divider()
st.caption("Use o menu à esquerda para navegar entre as telas.")
