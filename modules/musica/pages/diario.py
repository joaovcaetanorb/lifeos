"""Diário: registrar uma escuta nova e ver a linha do tempo de tudo já ouvido."""

from datetime import date
from pathlib import Path

import streamlit as st

import calculations as calc
import database
import models
import spotify_client
import ui
import utils

st.set_page_config(page_title="Diário | Música", page_icon="🎵", layout="wide")
database.inicializar_banco()
ui.aplicar_tema()


def _salvar_capa(album_id: int, arquivo) -> str:
    database.UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    extensao = Path(arquivo.name).suffix
    caminho = database.UPLOADS_DIR / f"{album_id}{extensao}"
    caminho.write_bytes(arquivo.getbuffer())
    return str(caminho.relative_to(database.DB_DIR))


def _salvar_capa_de_bytes(album_id: int, conteudo: bytes) -> str:
    database.UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    caminho = database.UPLOADS_DIR / f"{album_id}.jpg"
    caminho.write_bytes(conteudo)
    return str(caminho.relative_to(database.DB_DIR))


def _secao_busca_spotify() -> dict:
    """Busca opcional no Spotify pra pré-preencher os campos do álbum novo.
    Retorna o resultado escolhido (vazio se nada foi escolhido/buscado)."""
    if not spotify_client.disponivel():
        return {}

    st.caption("buscar no Spotify (opcional — preenche os campos abaixo)")
    c1, c2 = st.columns([4, 1])
    query = c1.text_input(
        "Buscar álbum", key="spotify_query_escuta", label_visibility="collapsed",
        placeholder="Ex.: OK Computer Radiohead",
    )
    if c2.button("buscar", key="spotify_buscar_escuta"):
        st.session_state["spotify_resultados_escuta"] = spotify_client.buscar_albuns(query)

    resultados = st.session_state.get("spotify_resultados_escuta", [])
    if resultados:
        for i, r in enumerate(resultados):
            col_capa, col_info, col_btn = st.columns([1, 5, 1])
            with col_capa:
                if r["capa_url"]:
                    st.image(r["capa_url"], width=50)
            with col_info:
                st.caption(f"{r['nome']} — {r['artista']} ({r['ano'] or '?'})")
            with col_btn:
                if st.button("usar", key=f"spotify_usar_escuta_{i}"):
                    st.session_state["spotify_escolha_escuta"] = r
                    st.session_state["spotify_resultados_escuta"] = []
                    st.rerun()

    escolha = st.session_state.get("spotify_escolha_escuta", {})
    if escolha:
        col_msg, col_limpar = st.columns([5, 1])
        col_msg.success(f"selecionado: {escolha['nome']} — {escolha['artista']}")
        if col_limpar.button("limpar", key="spotify_limpar_escuta"):
            st.session_state["spotify_escolha_escuta"] = {}
            st.rerun()
    return escolha


def _resumo() -> None:
    resumo = calc.resumo_geral()
    nota_txt = utils.formatar_nota(resumo["nota_media_geral"])
    st.caption(
        f"{resumo['total_albuns']} álbum(ns) · {resumo['total_escutas']} escuta(s) · média geral {nota_txt}"
    )


def _formulario_nova_escuta() -> None:
    with st.expander("+ nova escuta", expanded=True):
        albuns = models.listar_albuns()
        opcoes = {-1: "+ novo álbum"}
        for _, row in albuns.iterrows():
            opcoes[int(row["id"])] = f"{row['artista_nome']} — {row['nome']}"

        album_selecionado = st.selectbox(
            "Álbum", list(opcoes.keys()), format_func=lambda i: opcoes[i], key="album_selecionado_escuta",
        )

        novo_artista = novo_album = novo_genero = ""
        novo_ano = 0
        nova_capa = None
        escolha_spotify = {}
        if album_selecionado == -1:
            escolha_spotify = _secao_busca_spotify()
            # sufixo muda o "key" dos campos quando uma nova escolha do Spotify
            # é feita, forçando os widgets a reassumir o value= pré-preenchido
            # (senão o key antigo já teria estado salvo e o value seria ignorado)
            sufixo = escolha_spotify.get("spotify_id", "manual")

            c1, c2 = st.columns(2)
            novo_artista = c1.text_input(
                "Artista", value=escolha_spotify.get("artista", ""), key=f"novo_artista_escuta_{sufixo}",
            )
            novo_album = c2.text_input(
                "Álbum", value=escolha_spotify.get("nome", ""), key=f"novo_album_escuta_{sufixo}",
            )
            c3, c4 = st.columns(2)
            novo_ano = c3.number_input(
                "Ano de lançamento (opcional)", min_value=0, max_value=2100, step=1,
                value=escolha_spotify.get("ano") or 0, key=f"novo_ano_escuta_{sufixo}",
            )
            novo_genero = c4.text_input("Gênero (opcional)", key=f"novo_genero_escuta_{sufixo}")
            nova_capa = st.file_uploader(
                "Capa manual (opcional — substitui a do Spotify, se houver)",
                type=["png", "jpg", "jpeg"], key=f"nova_capa_escuta_{sufixo}",
            )

        with st.form("form_nova_escuta", clear_on_submit=True):
            c1, c2 = st.columns(2)
            data_escuta = c1.date_input("Data", value=date.today(), format="DD/MM/YYYY")
            sem_nota = c2.checkbox("ainda sem nota")
            nota = st.select_slider("Nota", options=utils.OPCOES_NOTA, value=4.0, format_func=utils.formatar_nota)
            faixa_favorita = st.text_input("Faixa favorita (opcional)")
            review = st.text_area("Review (opcional)")

            if st.form_submit_button("registrar escuta", use_container_width=True):
                if album_selecionado == -1:
                    if not novo_artista.strip() or not novo_album.strip():
                        st.warning("Informe artista e nome do álbum.")
                        st.stop()
                    artista_id = models.obter_ou_criar_artista(
                        novo_artista.strip(), spotify_id=escolha_spotify.get("artista_spotify_id", ""),
                    )
                    album_id = models.obter_ou_criar_album(
                        novo_album.strip(), artista_id, int(novo_ano) if novo_ano else None, novo_genero.strip(),
                        spotify_id=escolha_spotify.get("spotify_id", ""),
                        spotify_url=escolha_spotify.get("spotify_url", ""),
                    )

                    caminho = None
                    if nova_capa is not None:
                        caminho = _salvar_capa(album_id, nova_capa)
                    elif escolha_spotify.get("capa_url"):
                        conteudo = spotify_client.baixar_capa(escolha_spotify["capa_url"])
                        if conteudo is not None:
                            caminho = _salvar_capa_de_bytes(album_id, conteudo)

                    if caminho is not None:
                        models.atualizar_album(
                            album_id, novo_album.strip(), int(novo_ano) if novo_ano else None,
                            novo_genero.strip(), capa_path=caminho,
                        )

                    st.session_state["spotify_escolha_escuta"] = {}
                else:
                    album_id = album_selecionado

                models.inserir_escuta(
                    album_id, data_escuta.isoformat(), None if sem_nota else nota,
                    review.strip(), faixa_favorita.strip(),
                )
                st.success("Escuta registrada.")
                st.rerun()


def _popover_escuta(escuta: dict) -> None:
    escuta_id = int(escuta["id"])
    with st.popover("✎"):
        with st.form(f"form_editar_escuta_{escuta_id}"):
            data_val = st.date_input(
                "Data", value=date.fromisoformat(escuta["data"]), format="DD/MM/YYYY",
            )
            sem_nota = st.checkbox("sem nota", value=utils.nota_ausente(escuta["nota"]))
            nota_atual = 4.0 if utils.nota_ausente(escuta["nota"]) else float(escuta["nota"])
            nota_val = st.select_slider(
                "Nota", options=utils.OPCOES_NOTA, value=nota_atual, format_func=utils.formatar_nota,
            )
            faixa = st.text_input("Faixa favorita", value=escuta["faixa_favorita"])
            review = st.text_area("Review", value=escuta["review"])

            c1, c2 = st.columns(2)
            salvar = c1.form_submit_button("salvar")
            excluir = c2.form_submit_button("excluir")

        if salvar:
            models.atualizar_escuta(
                escuta_id, data_val.isoformat(), None if sem_nota else nota_val, review.strip(), faixa.strip(),
            )
            st.rerun()
        if excluir:
            models.excluir_escuta(escuta_id)
            st.rerun()


def _card_escuta(escuta: dict) -> None:
    with st.container(border=True):
        col_capa, col_texto, col_acao = st.columns([1, 7, 1])

        with col_capa:
            if escuta["capa_path"]:
                caminho_capa = database.DB_DIR / escuta["capa_path"]
                if caminho_capa.exists():
                    st.image(str(caminho_capa), width=80)

        with col_texto:
            st.markdown(f"**{escuta['album_nome']}** — {escuta['artista_nome']}")
            linha = f"{utils.formatar_data_br(escuta['data'])} · {utils.formatar_nota(escuta['nota'])}"
            if escuta["faixa_favorita"]:
                linha += f" · faixa favorita: {escuta['faixa_favorita']}"
            st.caption(linha)
            if escuta["review"]:
                st.write(escuta["review"])

        with col_acao:
            _popover_escuta(escuta)


def render() -> None:
    ui.titulo_pagina("diário")
    _resumo()

    st.divider()
    _formulario_nova_escuta()

    st.divider()
    ui.eyebrow("linha do tempo")
    escutas = models.listar_escutas_com_album()

    if escutas.empty:
        st.caption("Nenhuma escuta registrada ainda.")
    else:
        for _, escuta in escutas.iterrows():
            _card_escuta(dict(escuta))


render()
