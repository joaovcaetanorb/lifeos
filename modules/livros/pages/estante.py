"""Estante: catálogo com o histórico de leituras de cada livro."""

from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st

import calculations as calc
import database
import models
import ui
import utils

st.set_page_config(page_title="Estante | Livros", page_icon="📚", layout="wide")
database.inicializar_banco()
ui.aplicar_tema()


def _ano_valido(valor) -> int | None:
    """pandas lê ano_publicacao NULL como NaN (float) — e NaN é 'truthy'
    em Python, então int(NaN) estoura. Normaliza pra None nesse caso."""
    if valor is None or pd.isna(valor):
        return None
    return int(valor)


def _salvar_capa(livro_id: int, arquivo) -> str:
    database.UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    extensao = Path(arquivo.name).suffix
    caminho = database.UPLOADS_DIR / f"{livro_id}{extensao}"
    caminho.write_bytes(arquivo.getbuffer())
    return str(caminho.relative_to(database.DB_DIR))


def _resumo() -> None:
    resumo = calc.resumo_geral()
    nota_txt = utils.formatar_nota(resumo["nota_media_geral"])
    st.caption(
        f"{resumo['total_livros']} livro(s) · {resumo['total_leituras']} leitura(s) · média geral {nota_txt}"
    )


def _popover_leitura(leitura: dict) -> None:
    leitura_id = int(leitura["id"])
    with st.popover("✎"):
        with st.form(f"form_editar_leitura_estante_{leitura_id}"):
            data_val = st.date_input(
                "Data", value=date.fromisoformat(leitura["data"]), format="DD/MM/YYYY",
            )
            status_val = st.selectbox(
                "Status", utils.ESTADOS_LEITURA, index=utils.ESTADOS_LEITURA.index(leitura["status"]),
                key=f"status_editar_estante_{leitura_id}",
            )
            sem_nota = st.checkbox(
                "sem nota", value=utils.nota_ausente(leitura["nota"]), key=f"sem_nota_estante_{leitura_id}",
            )
            nota_atual = 4.0 if utils.nota_ausente(leitura["nota"]) else float(leitura["nota"])
            nota_val = st.select_slider(
                "Nota", options=utils.OPCOES_NOTA, value=nota_atual, format_func=utils.formatar_nota,
                key=f"nota_estante_{leitura_id}",
            )
            review = st.text_area("Review", value=leitura["review"])

            c1, c2 = st.columns(2)
            salvar = c1.form_submit_button("salvar")
            excluir = c2.form_submit_button("excluir")

        if salvar:
            models.atualizar_leitura(
                leitura_id, data_val.isoformat(), status_val, None if sem_nota else nota_val, review.strip(),
            )
            st.rerun()
        if excluir:
            models.excluir_leitura(leitura_id)
            st.rerun()


def _linha_leitura(leitura: dict) -> None:
    col_texto, col_acao = st.columns([8, 1])
    with col_texto:
        ui.nota_destaque(utils.formatar_nota(leitura["nota"]))
        st.caption(f"{utils.formatar_data_br(leitura['data'])} · {leitura['status']}")
        if leitura["review"]:
            st.caption(leitura["review"])
    with col_acao:
        _popover_leitura(leitura)


def _secao_leituras(livro_id: int) -> None:
    leituras = models.listar_leituras(livro_id)
    if leituras.empty:
        st.caption("Nenhuma leitura registrada ainda pra esse livro.")
    else:
        for _, leitura in leituras.iterrows():
            _linha_leitura(dict(leitura))
            st.divider()

    with st.form(f"form_nova_leitura_{livro_id}", clear_on_submit=True):
        st.caption("registrar nova leitura")
        c1, c2 = st.columns(2)
        data_leitura = c1.date_input("Data", value=date.today(), format="DD/MM/YYYY")
        status = c2.selectbox("Status", utils.ESTADOS_LEITURA, key=f"status_nova_{livro_id}")
        sem_nota = st.checkbox("ainda sem nota", key=f"sem_nota_nova_{livro_id}")
        nota = st.select_slider(
            "Nota", options=utils.OPCOES_NOTA, value=4.0, format_func=utils.formatar_nota,
            key=f"nota_nova_{livro_id}",
        )
        review = st.text_area("Review (opcional)")

        if st.form_submit_button("registrar leitura"):
            models.inserir_leitura(
                livro_id, data_leitura.isoformat(), status, None if sem_nota else nota, review.strip(),
            )
            st.rerun()


def _secao_editar(livro: dict) -> None:
    livro_id = int(livro["id"])
    with st.form(f"form_editar_livro_{livro_id}"):
        nome = st.text_input("Livro", value=livro["nome"])
        ano = st.number_input(
            "Ano de publicação", min_value=0, max_value=2100, step=1,
            value=_ano_valido(livro["ano_publicacao"]) or 0,
        )
        genero = st.text_input("Gênero", value=livro["genero"])
        nova_capa = st.file_uploader("Substituir capa (opcional)", type=["png", "jpg", "jpeg"], key=f"capa_{livro_id}")

        if st.form_submit_button("salvar alterações"):
            caminho = _salvar_capa(livro_id, nova_capa) if nova_capa is not None else None
            models.atualizar_livro(livro_id, nome.strip(), int(ano) if ano else None, genero.strip(), capa_path=caminho)
            st.success("Livro atualizado.")
            st.rerun()

    st.divider()
    confirmar = st.checkbox("confirmar exclusão deste livro (apaga todas as leituras dele)", key=f"confirmar_del_{livro_id}")
    if st.button("excluir livro", key=f"del_livro_{livro_id}", disabled=not confirmar):
        models.excluir_livro(livro_id)
        st.success("Livro excluído.")
        st.rerun()


def _toggle_favorito_livro(livro_id: int) -> None:
    models.favoritar_livro(livro_id, st.session_state[f"favorito_livro_{livro_id}"])


def _card_livro(livro: dict, status_atual: str) -> None:
    livro_id = int(livro["id"])
    with st.container(border=True):
        col_capa, col_texto, col_favorito = st.columns([1, 5, 1])

        with col_capa:
            if livro["capa_path"]:
                caminho_capa = database.DB_DIR / livro["capa_path"]
                if caminho_capa.exists():
                    st.image(str(caminho_capa), width=140)

        with col_texto:
            st.subheader(livro["nome"])
            ano_valido = _ano_valido(livro["ano_publicacao"])
            ano_txt = str(ano_valido) if ano_valido else "ano desconhecido"
            genero_txt = livro["genero"] if livro["genero"] else "sem gênero"
            st.caption(f"{livro['autor_nome']} · {ano_txt} · {genero_txt}")

            nota_media = calc.nota_media_livro(livro_id)
            total = calc.total_leituras_livro(livro_id)
            ui.nota_destaque(f"{status_atual} · {utils.formatar_nota(nota_media)} ({total} leitura(s))")

        with col_favorito:
            st.checkbox(
                "★ favorito", value=bool(livro["favorito"]), key=f"favorito_livro_{livro_id}",
                on_change=_toggle_favorito_livro, args=(livro_id,),
            )

        with st.expander("histórico e gestão"):
            tab_leituras, tab_editar = st.tabs(["leituras", "editar / excluir"])
            with tab_leituras:
                _secao_leituras(livro_id)
            with tab_editar:
                _secao_editar(livro)


def _secao_melhores_avaliados() -> None:
    top = calc.top_livros_avaliados(5)
    if top.empty:
        return
    ui.eyebrow("destaque")
    st.subheader("Melhores avaliados")
    cols = st.columns(len(top))
    for col, (_, livro) in zip(cols, top.iterrows()):
        with col:
            if livro["capa_path"]:
                caminho_capa = database.DB_DIR / livro["capa_path"]
                if caminho_capa.exists():
                    st.image(str(caminho_capa), use_container_width=True)
            st.caption(f"**{livro['livro_nome']}**  \n{livro['autor_nome']}  \n{utils.formatar_nota(livro['nota_media'])}")


FILTRO_STATUS_OPCOES = ["Todos", "Lendo", "Concluído", "Abandonado", "Não iniciado"]


def render() -> None:
    ui.titulo_pagina("estante")
    _resumo()

    st.divider()
    _secao_melhores_avaliados()

    st.divider()
    filtro_status = st.radio(
        "Status", FILTRO_STATUS_OPCOES, horizontal=True, label_visibility="collapsed", key="estante_filtro_status",
    )
    c1, c2 = st.columns([4, 1])
    busca = c1.text_input(
        "Buscar por livro ou autor", placeholder="Ex.: Machado de Assis", label_visibility="collapsed",
    )
    so_favoritos = c2.checkbox("★ só favoritos")

    livros = models.listar_livros()
    status_todos = calc.status_por_livro()
    livros = livros.assign(
        status_atual=livros["id"].map(lambda lid: status_todos.get(lid, "Não iniciado"))
    )

    if filtro_status != "Todos":
        livros = livros[livros["status_atual"] == filtro_status]
    if so_favoritos:
        livros = livros[livros["favorito"] == 1]
    if busca.strip():
        termo = busca.strip().lower()
        livros = livros[
            livros["nome"].str.lower().str.contains(termo) | livros["autor_nome"].str.lower().str.contains(termo)
        ]

    st.divider()
    if livros.empty:
        st.caption("Nenhum livro encontrado.")
    else:
        for _, livro in livros.iterrows():
            _card_livro(dict(livro), livro["status_atual"])


render()
