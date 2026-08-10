"""Colagem: mosaico das capas mais escutadas num período, pronto pra
postar (post quadrado ou stories vertical)."""

from datetime import date

import streamlit as st

import calculations as calc
import colagem
import database
import ui
import utils

st.set_page_config(page_title="Colagem | Música", page_icon="🎵", layout="wide")
database.inicializar_banco()
ui.aplicar_tema()


def _periodo_selecionado() -> tuple[str, str, str]:
    """Retorna (data_inicio_iso, data_fim_iso, rótulo pro nome do arquivo)."""
    hoje = date.today()
    atalho = st.radio(
        "Período", ["Este mês", "Este ano", "Todos os tempos", "Personalizado"],
        horizontal=True, label_visibility="collapsed", key="colagem_periodo",
    )

    if atalho == "Este mês":
        inicio = hoje.replace(day=1)
        return inicio.isoformat(), hoje.isoformat(), hoje.strftime("%Y-%m")
    if atalho == "Este ano":
        inicio = date(hoje.year, 1, 1)
        return inicio.isoformat(), hoje.isoformat(), str(hoje.year)
    if atalho == "Todos os tempos":
        return "0000-01-01", "9999-12-31", "todos_os_tempos"

    c1, c2 = st.columns(2)
    inicio = c1.date_input("De", value=date(hoje.year, 1, 1), format="DD/MM/YYYY", key="colagem_data_inicio")
    fim = c2.date_input("Até", value=hoje, format="DD/MM/YYYY", key="colagem_data_fim")
    return inicio.isoformat(), fim.isoformat(), f"{inicio.isoformat()}_a_{fim.isoformat()}"


def render() -> None:
    ui.titulo_pagina("colagem")
    st.caption(
        "Mosaico com as capas mais escutadas no período — igual à paradinha que a galera "
        "posta, no formato certo pra Instagram."
    )

    st.divider()
    fonte = st.radio(
        "Fonte", ["Diário (avaliado)", "Histórico Spotify (tocado de verdade)"],
        horizontal=True, key="colagem_fonte",
    )
    data_inicio, data_fim, rotulo = _periodo_selecionado()

    c1, c2 = st.columns(2)
    lado_grade = c1.selectbox("Tamanho da grade", [3, 4, 5], format_func=lambda n: f"{n}x{n}", key="colagem_grade")
    formato = c2.radio("Formato", ["Post (quadrado)", "Stories (vertical)"], key="colagem_formato")
    formato_arquivo = "stories" if formato.startswith("Stories") else "post"

    if st.button("gerar colagem", use_container_width=True):
        if fonte.startswith("Diário"):
            top = calc.top_albuns_periodo(data_inicio, data_fim, lado_grade * lado_grade)
            aviso_vazio = "Nenhuma escuta registrada nesse período ainda."
        else:
            top = calc.top_albuns_historico(data_inicio, data_fim, lado_grade * lado_grade)
            aviso_vazio = "Nenhuma faixa tocada sincronizada nesse período ainda (conecta e sincroniza na página Spotify)."

        if top.empty:
            st.warning(aviso_vazio)
            st.session_state["colagem_bytes"] = None
        else:
            imagem_bytes = colagem.gerar_colagem(top.to_dict("records"), lado_grade, formato_arquivo)
            st.session_state["colagem_bytes"] = imagem_bytes
            st.session_state["colagem_arquivo"] = f"colagem_{rotulo}_{lado_grade}x{lado_grade}_{formato_arquivo}.png"
            st.session_state["colagem_qtd"] = len(top)

    if st.session_state.get("colagem_bytes"):
        st.caption(f"{st.session_state['colagem_qtd']} álbum(ns) na colagem.")
        largura_exibicao = 320 if formato_arquivo == "stories" else 460
        st.image(st.session_state["colagem_bytes"], width=largura_exibicao)
        st.download_button(
            "baixar colagem (PNG)",
            data=st.session_state["colagem_bytes"],
            file_name=st.session_state["colagem_arquivo"],
            mime="image/png",
        )


render()
