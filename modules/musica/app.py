"""Tela inicial: explica a lógica do app antes de ir pro dia a dia."""

import streamlit as st

import database
import ui

st.set_page_config(page_title="Música", page_icon="🎵", layout="wide")
database.inicializar_banco()
ui.aplicar_tema()

ui.titulo_pagina("como funciona")

ui.eyebrow("a ideia")
st.subheader("Um diário musical, não um player")
st.markdown(
    "Aqui você não ouve música — você registra o que ouviu. Cada **escuta** é uma entrada de "
    "diário: um álbum, uma data, uma nota, o que você achou. Com o tempo isso vira uma linha "
    "do tempo da sua relação com a música, não só uma lista de álbuns."
)

st.divider()

ui.eyebrow("o que muda tudo")
st.subheader("Reescutar faz parte do produto")
st.markdown(
    "Um álbum pode ter **várias escutas** ao longo dos anos. Você pode ouvir algo em 2020, dar "
    "3 estrelas, e reouvir em 2026 e sentir outra coisa completamente — registre as duas. "
    "O álbum é só o catálogo (nome, artista, ano); a opinião mora na escuta, não no álbum."
)

st.divider()

ui.eyebrow("cada aba")
st.subheader("O que cada tela faz")
c1, c2 = st.columns(2)
with c1:
    st.markdown("**Diário**")
    st.caption("Registrar uma escuta nova e ver a linha do tempo de tudo que você já ouviu.")
with c2:
    st.markdown("**Álbuns**")
    st.caption("Catálogo dos álbuns cadastrados, cada um com o histórico de todas as suas escutas.")

st.divider()
st.caption("Use o menu à esquerda para navegar entre as telas.")
