"""Álbuns: catálogo com o histórico de escutas de cada um."""

from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st

import calculations as calc
import database
import models
import spotify_client
import ui
import utils

st.set_page_config(page_title="Álbuns | Música", page_icon="🎵", layout="wide")
database.inicializar_banco()
ui.aplicar_tema()


def _ano_valido(valor) -> int | None:
    """pandas lê ano_lancamento NULL como NaN (float) — e NaN é 'truthy'
    em Python, então int(NaN) estoura. Normaliza pra None nesse caso."""
    if valor is None or pd.isna(valor):
        return None
    return int(valor)


def _salvar_capa(album_id: int, arquivo) -> str:
    database.UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    extensao = Path(arquivo.name).suffix
    caminho = database.UPLOADS_DIR / f"{album_id}{extensao}"
    caminho.write_bytes(arquivo.getbuffer())
    return str(caminho.relative_to(database.DB_DIR))


def _resumo() -> None:
    resumo = calc.resumo_geral()
    nota_txt = utils.formatar_nota(resumo["nota_media_geral"])
    st.caption(
        f"{resumo['total_albuns']} álbum(ns) · {resumo['total_escutas']} escuta(s) · média geral {nota_txt}"
    )


def _campo_faixa_favorita(spotify_id: str, valor_atual: str, key: str) -> str:
    """Se o álbum tem spotify_id e o Spotify está disponível, busca a
    tracklist real (cacheada por spotify_id) e mostra uma faixa por
    checkbox pra marcar as favoritas. Senão, cai pro texto livre. Sempre
    retorna a string final (faixas separadas por ', ')."""
    faixas = []
    if spotify_id and spotify_client.disponivel():
        cache_key = f"faixas_{spotify_id}"
        if cache_key not in st.session_state:
            st.session_state[cache_key] = spotify_client.buscar_faixas(spotify_id)
        faixas = st.session_state[cache_key]

    if not faixas:
        return st.text_input("Faixa favorita (opcional)", value=valor_atual, key=key)

    atuais = {f.strip() for f in valor_atual.split(",") if f.strip()}
    st.caption("faixas favoritas (opcional)")
    escolhidas = [
        faixa for i, faixa in enumerate(faixas)
        if st.checkbox(faixa, value=faixa in atuais, key=f"{key}_faixa_{i}")
    ]
    return ", ".join(escolhidas)


def _popover_escuta(escuta: dict, spotify_id: str) -> None:
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
            faixa = _campo_faixa_favorita(
                spotify_id, escuta["faixa_favorita"], f"faixa_favorita_editar_album_{escuta_id}",
            )
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


def _linha_escuta(escuta: dict, spotify_id: str) -> None:
    col_texto, col_acao = st.columns([8, 1])
    with col_texto:
        linha = f"{utils.formatar_data_br(escuta['data'])} · {utils.formatar_nota(escuta['nota'])}"
        if escuta["faixa_favorita"]:
            linha += f" · faixa(s) favorita(s): {escuta['faixa_favorita']}"
        st.markdown(linha)
        if escuta["review"]:
            st.caption(escuta["review"])
    with col_acao:
        _popover_escuta(escuta, spotify_id)


def _secao_escutas(album_id: int, spotify_id: str) -> None:
    escutas = models.listar_escutas(album_id)
    if escutas.empty:
        st.caption("Nenhuma escuta registrada ainda pra esse álbum.")
    else:
        for _, escuta in escutas.iterrows():
            _linha_escuta(dict(escuta), spotify_id)
            st.divider()

    with st.form(f"form_nova_escuta_{album_id}", clear_on_submit=True):
        st.caption("registrar nova escuta")
        c1, c2 = st.columns(2)
        data_escuta = c1.date_input("Data", value=date.today(), format="DD/MM/YYYY")
        sem_nota = c2.checkbox("ainda sem nota")
        nota = st.select_slider("Nota", options=utils.OPCOES_NOTA, value=4.0, format_func=utils.formatar_nota)
        faixa_favorita = _campo_faixa_favorita(spotify_id, "", f"faixa_favorita_nova_album_{album_id}")
        review = st.text_area("Review (opcional)")

        if st.form_submit_button("registrar escuta"):
            models.inserir_escuta(
                album_id, data_escuta.isoformat(), None if sem_nota else nota, review.strip(), faixa_favorita.strip(),
            )
            st.rerun()


def _secao_editar(album: dict) -> None:
    album_id = int(album["id"])
    with st.form(f"form_editar_album_{album_id}"):
        nome = st.text_input("Álbum", value=album["nome"])
        ano = st.number_input(
            "Ano de lançamento", min_value=0, max_value=2100, step=1,
            value=_ano_valido(album["ano_lancamento"]) or 0,
        )
        genero = st.text_input("Gênero", value=album["genero"])
        nova_capa = st.file_uploader("Substituir capa (opcional)", type=["png", "jpg", "jpeg"], key=f"capa_{album_id}")

        if st.form_submit_button("salvar alterações"):
            caminho = _salvar_capa(album_id, nova_capa) if nova_capa is not None else None
            models.atualizar_album(album_id, nome.strip(), int(ano) if ano else None, genero.strip(), capa_path=caminho)
            st.success("Álbum atualizado.")
            st.rerun()

    st.divider()
    confirmar = st.checkbox("confirmar exclusão deste álbum (apaga todas as escutas dele)", key=f"confirmar_del_{album_id}")
    if st.button("excluir álbum", key=f"del_album_{album_id}", disabled=not confirmar):
        models.excluir_album(album_id)
        st.success("Álbum excluído.")
        st.rerun()


def _card_album(album: dict) -> None:
    album_id = int(album["id"])
    with st.container(border=True):
        col_capa, col_texto = st.columns([1, 5])

        with col_capa:
            if album["capa_path"]:
                caminho_capa = database.DB_DIR / album["capa_path"]
                if caminho_capa.exists():
                    st.image(str(caminho_capa), width=100)

        with col_texto:
            st.subheader(album["nome"])
            ano_valido = _ano_valido(album["ano_lancamento"])
            ano_txt = str(ano_valido) if ano_valido else "ano desconhecido"
            genero_txt = album["genero"] if album["genero"] else "sem gênero"
            st.caption(f"{album['artista_nome']} · {ano_txt} · {genero_txt}")

            nota_media = calc.nota_media_album(album_id)
            total = calc.total_escutas_album(album_id)
            st.caption(f"{utils.formatar_nota(nota_media)} · {total} escuta(s)")

        with st.expander("histórico e gestão"):
            tab_escutas, tab_editar = st.tabs(["escutas", "editar / excluir"])
            with tab_escutas:
                _secao_escutas(album_id, album["spotify_id"])
            with tab_editar:
                _secao_editar(album)


def render() -> None:
    ui.titulo_pagina("álbuns")
    _resumo()

    st.divider()
    busca = st.text_input("Buscar por álbum ou artista", placeholder="Ex.: Radiohead")

    albuns = models.listar_albuns()
    if busca.strip():
        termo = busca.strip().lower()
        albuns = albuns[
            albuns["nome"].str.lower().str.contains(termo) | albuns["artista_nome"].str.lower().str.contains(termo)
        ]

    st.divider()
    if albuns.empty:
        st.caption("Nenhum álbum encontrado.")
    else:
        for _, album in albuns.iterrows():
            _card_album(dict(album))


render()
