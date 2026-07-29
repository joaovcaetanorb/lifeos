"""Tela inicial: explica a lógica do app antes de ir pro dia a dia."""

import streamlit as st

import database
import ui

st.set_page_config(page_title="Humor", page_icon="🙂", layout="wide")
database.inicializar_banco()
ui.aplicar_tema()

ui.titulo_pagina("como funciona")

ui.eyebrow("o registro")
st.subheader("Nota + tags, rápido")
st.markdown(
    "Cada registro tem três partes:\n\n"
    "1. **Nota de 1 a 10** — como você está, de forma geral.\n"
    "2. **Tags** — escolhidas de uma lista fixa (Animado, Ansioso, Cansado...), "
    "não texto livre. É rápido (só tocar) e, com o tempo, dá pra contar e cruzar "
    "com outros módulos (ex.: 'nos dias que treinei, quantas vezes marquei "
    "'Ansioso'?').\n"
    "3. **Nota livre (opcional)** — pra escrever o que quiser sobre o dia, sem "
    "estrutura nenhuma. Isso não entra em nenhuma conta, é só pra você reler depois."
)

st.divider()

ui.eyebrow("mais de um registro por dia")
st.subheader("Sem limite diário")
st.markdown(
    "Diferente de Hábitos (um check por dia), aqui você pode registrar quantas "
    "vezes quiser no mesmo dia — humor muda de manhã pra tarde, e travar em um "
    "registro por dia esconderia justamente essas variações."
)

st.divider()

ui.eyebrow("pra que serve")
st.subheader("Não é só um gráfico bonito")
st.markdown(
    "A ideia por trás desse módulo é que, com o tempo, dê pra olhar o humor junto "
    "com outros módulos do LifeOS — hábitos cumpridos, o que você andou ouvindo, "
    "o ritmo de leitura — e ver padrões que não são óbvios no dia a dia. Por isso "
    "as tags são de uma lista fixa: número e categoria dá pra cruzar automaticamente; "
    "texto livre não."
)

st.divider()
st.caption("Use o menu à esquerda para ir pro registro do dia.")
