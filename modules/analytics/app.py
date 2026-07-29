"""Tela inicial: explica a lógica do app antes de ir pro dia a dia."""

import streamlit as st

import database
import ui

st.set_page_config(page_title="Analytics", page_icon="📈", layout="wide")
database.inicializar_banco()
ui.aplicar_tema()

ui.titulo_pagina("como funciona")

ui.eyebrow("a diferença pro Geral")
st.subheader("Tendências, não o momento atual")
st.markdown(
    "O **Geral** (dashboard da home) mostra como você está *hoje* — um resumo rápido, "
    "sem gráfico de evolução. O **Analytics** é o oposto: aqui a pergunta é **'como eu "
    "evoluí?'**, olhando pra trás, cruzando meses e módulos diferentes. Os dois nunca "
    "mostram a mesma coisa de propósito."
)

st.divider()

ui.eyebrow("três seções")
st.subheader("O que tem aqui")
st.markdown(
    "- **Gráficos** — tendências de cada módulo, com filtro de período (mês, ano, "
    "todos os tempos ou personalizado).\n"
    "- **Perguntas** — escolha uma pergunta pronta ou escreva a sua. A resposta é "
    "gerada por IA (Groq), sempre baseada só nos números reais dos seus módulos — "
    "nunca inventada.\n"
    "- **Sugestões** — sem você perguntar nada, a IA olha os dados e aponta padrões "
    "que podem valer a pena notar. Atualiza sozinha a cada um dia, não a cada "
    "recarregamento da página."
)

st.divider()

ui.eyebrow("privacidade")
st.subheader("O que vai pra IA")
st.markdown(
    "Só números agregados (ex.: 'gasto médio em julho: R$ 1.200') — nunca a lista "
    "bruta de gastos, reviews ou anotações. Se você nunca configurar a chave do Groq, "
    "essa parte simplesmente não aparece; os gráficos continuam funcionando normalmente."
)

st.divider()
st.caption("Use o menu à esquerda para ir pro Analytics.")
