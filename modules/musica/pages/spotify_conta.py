"""Conta Spotify: login de verdade (Authorization Code) pra puxar
histórico real de faixas tocadas e top artistas/faixas da conta — separado
do Diário, que continua sendo só o que o usuário escolhe avaliar/resenhar.
"""

import streamlit as st

import database
import models
import spotify_client
import ui
import utils

st.set_page_config(page_title="Spotify | Música", page_icon="🎵", layout="wide")
database.inicializar_banco()
ui.aplicar_tema()
ui.mostrar_toast_pendente()

_PERIODOS = {"short_term": "4 semanas", "medium_term": "6 meses", "long_term": "geral"}


def _formatar_tocado_em(tocado_em: str) -> str:
    """'2026-08-10T14:23:45.000Z' -> '10/08/2026 14:23'."""
    if not tocado_em or len(tocado_em) < 16:
        return ""
    data = utils.formatar_data_br(tocado_em[:10])
    hora = tocado_em[11:16]
    return f"{data} {hora}"


def _processar_callback_oauth() -> None:
    """Se a Spotify acabou de redirecionar de volta com ?code=..., troca
    pelo token e limpa a URL — sem isso o `code` (que só serve uma vez)
    ficaria na barra de endereço e um F5 tentaria reusá-lo."""
    code = st.query_params.get("code")
    if not code:
        return
    if spotify_client.completar_conexao(code):
        ui.marcar_toast("Conta Spotify conectada.")
    else:
        st.session_state["_spotify_erro_conexao"] = True
    st.query_params.clear()
    st.rerun()


def _botao_conectar() -> None:
    url = spotify_client.url_autorizacao()
    if url is None:
        st.warning(
            "Faltam credenciais do Spotify configuradas (SPOTIFY_CLIENT_ID/SECRET/REDIRECT_URI "
            "em secrets.toml)."
        )
        return
    st.markdown(
        f'''<a href="{url}" style="
            display: inline-flex; align-items: center; gap: 0.5rem;
            background: #1DB954; color: #0D0F0C; font-weight: 700;
            padding: 0.65rem 1.5rem; border-radius: 999px; text-decoration: none;
            font-family: 'JetBrains Mono', monospace; font-size: 0.9rem;
        ">♫ Entrar com Spotify</a>''',
        unsafe_allow_html=True,
    )


def _secao_desconectada() -> None:
    st.caption(
        "Conecta sua conta de verdade (login na Spotify, não as credenciais do app) pra "
        "puxar o histórico real de faixas tocadas e seus top artistas/faixas. Isso é "
        "separado do Diário — não vira escuta registrada sozinho."
    )
    if st.session_state.pop("_spotify_erro_conexao", False):
        st.warning("Não consegui completar a conexão com o Spotify. Tenta de novo.")
    _botao_conectar()


def _sincronizar_automaticamente() -> None:
    """Uma sincronização por sessão ao abrir a página — sem isso o
    histórico só cresce quando alguém lembra de clicar "sincronizar
    agora", e a API só devolve as últimas 50 faixas (o que não for
    salvo a tempo, se perde)."""
    if st.session_state.get("_spotify_sync_automatica_feita"):
        return
    st.session_state["_spotify_sync_automatica_feita"] = True
    spotify_client.sincronizar_historico()


def _secao_historico() -> None:
    ui.eyebrow("histórico")
    st.subheader("Últimas faixas tocadas")

    c1, c2 = st.columns([5, 1])
    if c2.button("sincronizar agora", use_container_width=True):
        novas = spotify_client.sincronizar_historico()
        ui.marcar_toast(f"{novas} faixa(s) nova(s) sincronizada(s)." if novas else "Nada novo desde a última vez.")
        st.rerun()

    historico = models.listar_historico(50)
    if historico.empty:
        c1.caption("Nenhuma faixa sincronizada ainda.")
        return

    for _, faixa in historico.iterrows():
        col_capa, col_texto = st.columns([1, 6])
        with col_capa:
            if faixa["capa_url"]:
                st.image(faixa["capa_url"], width=64)
        with col_texto:
            st.markdown(f"**{faixa['faixa_nome']}** — {faixa['artista_nome']}")
            st.caption(f"{faixa['album_nome']} · {_formatar_tocado_em(faixa['tocado_em'])}")
        st.divider()


def _secao_top() -> None:
    ui.eyebrow("segundo o spotify")
    st.subheader("Top artistas e faixas")
    periodo = st.radio(
        "Período", list(_PERIODOS.keys()), format_func=lambda p: _PERIODOS[p],
        horizontal=True, label_visibility="collapsed", key="spotify_top_periodo",
    )

    col_artistas, col_faixas = st.columns(2)
    with col_artistas:
        st.markdown("**Artistas**")
        artistas = spotify_client.top_artistas_conta(periodo)
        if not artistas:
            st.caption("Nada por aqui ainda.")
        for i, artista in enumerate(artistas, start=1):
            c1, c2 = st.columns([1, 5])
            if artista["capa_url"]:
                c1.image(artista["capa_url"], width=48)
            c2.write(f"{i}. {artista['nome']}")

    with col_faixas:
        st.markdown("**Faixas**")
        faixas = spotify_client.top_faixas_conta(periodo)
        if not faixas:
            st.caption("Nada por aqui ainda.")
        for i, faixa in enumerate(faixas, start=1):
            c1, c2 = st.columns([1, 5])
            if faixa["capa_url"]:
                c1.image(faixa["capa_url"], width=48)
            c2.write(f"{i}. {faixa['nome']} — {faixa['artista']}")


def _secao_desconectar() -> None:
    with st.expander("desconectar conta"):
        confirmar = st.checkbox("confirmar desconexão", key="confirmar_desconectar_spotify")
        if st.button("desconectar", disabled=not confirmar):
            spotify_client.desconectar()
            st.session_state.pop("_spotify_sync_automatica_feita", None)
            ui.marcar_toast("Conta Spotify desconectada.", icone="🔌")
            st.rerun()


def render() -> None:
    ui.titulo_pagina("spotify")
    _processar_callback_oauth()

    if not spotify_client.conta_conectada():
        _secao_desconectada()
        return

    _sincronizar_automaticamente()
    _secao_historico()
    st.divider()
    _secao_top()
    st.divider()
    _secao_desconectar()


render()
