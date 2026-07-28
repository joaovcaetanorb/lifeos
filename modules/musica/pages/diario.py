"""Diário: registrar uma escuta nova e ver a linha do tempo de tudo já ouvido."""

from datetime import date
from pathlib import Path

import streamlit as st

import calculations as calc
import database
import models
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
        if album_selecionado == -1:
            c1, c2 = st.columns(2)
            novo_artista = c1.text_input("Artista", key="novo_artista_escuta")
            novo_album = c2.text_input("Álbum", key="novo_album_escuta")
            c3, c4 = st.columns(2)
            novo_ano = c3.number_input(
                "Ano de lançamento (opcional)", min_value=0, max_value=2100, step=1, value=0,
                key="novo_ano_escuta",
            )
            novo_genero = c4.text_input("Gênero (opcional)", key="novo_genero_escuta")
            nova_capa = st.file_uploader("Capa (opcional)", type=["png", "jpg", "jpeg"], key="nova_capa_escuta")

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
                    artista_id = models.obter_ou_criar_artista(novo_artista.strip())
                    album_id = models.obter_ou_criar_album(
                        novo_album.strip(), artista_id, int(novo_ano) if novo_ano else None, novo_genero.strip(),
                    )
                    if nova_capa is not None:
                        caminho = _salvar_capa(album_id, nova_capa)
                        models.atualizar_album(
                            album_id, novo_album.strip(), int(novo_ano) if novo_ano else None,
                            novo_genero.strip(), capa_path=caminho,
                        )
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
