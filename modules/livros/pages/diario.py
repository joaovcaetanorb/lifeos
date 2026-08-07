"""Diário: registrar uma leitura nova e ver a linha do tempo de tudo já lido."""

from datetime import date
from pathlib import Path

import streamlit as st

import calculations as calc
import database
import models
import ui
import utils

st.set_page_config(page_title="Diário | Livros", page_icon="📚", layout="wide")
database.inicializar_banco()
ui.aplicar_tema()
ui.mostrar_toast_pendente()


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


@st.fragment
def _formulario_nova_leitura() -> None:
    with st.expander("+ nova leitura", expanded=True):
        livros = models.listar_livros()
        opcoes = {-1: "+ novo livro"}
        for _, row in livros.iterrows():
            opcoes[int(row["id"])] = f"{row['autor_nome']} — {row['nome']}"

        livro_selecionado = st.selectbox(
            "Livro", list(opcoes.keys()), format_func=lambda i: opcoes[i], key="livro_selecionado_leitura",
        )

        novo_autor = novo_livro = novo_genero = ""
        novo_ano = 0
        nova_capa = None
        if livro_selecionado == -1:
            c1, c2 = st.columns(2)
            novo_autor = c1.text_input("Autor", key="novo_autor_leitura")
            novo_livro = c2.text_input("Livro", key="novo_livro_leitura")
            c3, c4 = st.columns(2)
            novo_ano = c3.number_input(
                "Ano de publicação (opcional)", min_value=0, max_value=2100, step=1, value=0,
                key="novo_ano_leitura",
            )
            novo_genero = c4.text_input("Gênero (opcional)", key="novo_genero_leitura")
            nova_capa = st.file_uploader("Capa (opcional)", type=["png", "jpg", "jpeg"], key="nova_capa_leitura")

        with st.form("form_nova_leitura", clear_on_submit=True):
            c1, c2 = st.columns(2)
            data_leitura = c1.date_input("Data", value=date.today(), format="DD/MM/YYYY")
            status = c2.selectbox("Status", utils.ESTADOS_LEITURA)
            sem_nota = st.checkbox("ainda sem nota")
            nota = st.select_slider("Nota", options=utils.OPCOES_NOTA, value=4.0, format_func=utils.formatar_nota)
            review = st.text_area("Review (opcional)")

            if st.form_submit_button("registrar leitura", use_container_width=True):
                if livro_selecionado == -1:
                    if not novo_autor.strip() or not novo_livro.strip():
                        st.warning("Informe autor e nome do livro.")
                        st.stop()
                    autor_id = models.obter_ou_criar_autor(novo_autor.strip())
                    livro_id = models.obter_ou_criar_livro(
                        novo_livro.strip(), autor_id, int(novo_ano) if novo_ano else None, novo_genero.strip(),
                    )
                    if nova_capa is not None:
                        caminho = _salvar_capa(livro_id, nova_capa)
                        models.atualizar_livro(
                            livro_id, novo_livro.strip(), int(novo_ano) if novo_ano else None,
                            novo_genero.strip(), capa_path=caminho,
                        )
                else:
                    livro_id = livro_selecionado

                models.inserir_leitura(
                    livro_id, data_leitura.isoformat(), status, None if sem_nota else nota, review.strip(),
                )
                ui.marcar_toast("Leitura registrada.")
                st.rerun()


def _popover_leitura(leitura: dict) -> None:
    leitura_id = int(leitura["id"])
    with st.popover("✎"):
        st.caption(f"{leitura['livro_nome']} — {leitura['autor_nome']}")
        with st.form(f"form_editar_leitura_{leitura_id}"):
            data_val = st.date_input(
                "Data", value=date.fromisoformat(leitura["data"]), format="DD/MM/YYYY",
            )
            status_val = st.selectbox(
                "Status", utils.ESTADOS_LEITURA, index=utils.ESTADOS_LEITURA.index(leitura["status"]),
                key=f"status_editar_{leitura_id}",
            )
            sem_nota = st.checkbox(
                "sem nota", value=utils.nota_ausente(leitura["nota"]), key=f"sem_nota_editar_{leitura_id}",
            )
            nota_atual = 4.0 if utils.nota_ausente(leitura["nota"]) else float(leitura["nota"])
            nota_val = st.select_slider(
                "Nota", options=utils.OPCOES_NOTA, value=nota_atual, format_func=utils.formatar_nota,
                key=f"nota_editar_{leitura_id}",
            )
            review = st.text_area("Review", value=leitura["review"])

            c1, c2 = st.columns(2)
            salvar = c1.form_submit_button("salvar", use_container_width=True)
            excluir = c2.form_submit_button("excluir", use_container_width=True)

        if salvar:
            models.atualizar_leitura(
                leitura_id, data_val.isoformat(), status_val, None if sem_nota else nota_val, review.strip(),
            )
            ui.marcar_toast("Leitura atualizada.")
            st.rerun()
        if excluir:
            models.excluir_leitura(leitura_id)
            ui.marcar_toast("Leitura excluída.", icone="🗑️")
            st.rerun()


def _card_leitura(leitura: dict) -> None:
    with st.container(border=True):
        col_capa, col_texto, col_acao = st.columns([1, 6.5, 0.5], gap="small")

        with col_capa:
            if leitura["capa_path"]:
                caminho_capa = database.DB_DIR / leitura["capa_path"]
                if caminho_capa.exists():
                    st.image(str(caminho_capa), width=120)

        with col_texto:
            st.markdown(f"**{leitura['livro_nome']}** — {leitura['autor_nome']}")
            ui.nota_destaque(utils.formatar_nota(leitura["nota"]))
            st.caption(f"{utils.formatar_data_br(leitura['data'])} · {leitura['status']}")
            if leitura["review"]:
                st.write(leitura["review"])

        with col_acao:
            _popover_leitura(leitura)


def render() -> None:
    ui.titulo_pagina("diário")
    _resumo()

    st.divider()
    _formulario_nova_leitura()

    st.divider()
    ui.eyebrow("linha do tempo")
    leituras = models.listar_leituras_com_livro()

    if leituras.empty:
        st.caption("Nenhuma leitura registrada ainda.")
    else:
        for _, leitura in leituras.iterrows():
            _card_leitura(dict(leitura))


render()
