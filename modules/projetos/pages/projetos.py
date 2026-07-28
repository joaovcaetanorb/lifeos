"""Projetos: lista, criação, checklist e aportes de cada meta."""

from datetime import date
from pathlib import Path

import streamlit as st

import calculations as calc
import database
import models
import relatorio
import ui
import utils

st.set_page_config(page_title="Projetos | Projetos", page_icon="🎯", layout="wide")
database.inicializar_banco()
ui.aplicar_tema()


def _salvar_foto(projeto_id: int, arquivo) -> str:
    """Salva a foto enviada em database/uploads/<id><extensão> e retorna o
    caminho relativo a DB_DIR (o que é guardado em projetos.foto_path)."""
    database.UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    extensao = Path(arquivo.name).suffix
    caminho = database.UPLOADS_DIR / f"{projeto_id}{extensao}"
    caminho.write_bytes(arquivo.getbuffer())
    return str(caminho.relative_to(database.DB_DIR))


def _salvar_foto_item(item_id: int, arquivo) -> str:
    """Mesma lógica de _salvar_foto, com prefixo 'item_' pra não colidir com
    o nome de arquivo da foto de capa do projeto (ids de tabelas diferentes)."""
    database.UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    extensao = Path(arquivo.name).suffix
    caminho = database.UPLOADS_DIR / f"item_{item_id}{extensao}"
    caminho.write_bytes(arquivo.getbuffer())
    return str(caminho.relative_to(database.DB_DIR))


def _resumo() -> None:
    resumo = calc.resumo_geral()
    st.caption(
        f"{resumo['projetos_ativos']} projeto(s) ativo(s) · "
        f"{utils.formatar_moeda(resumo['total_investido'])} investidos no total"
    )


def _formulario_novo_projeto() -> None:
    with st.expander("+ novo projeto"):
        with st.form("form_novo_projeto", clear_on_submit=True):
            nome = st.text_input("Nome")
            descricao = st.text_input("Descrição (opcional)")
            orcamento = st.number_input("Orçamento (R$)", min_value=0.0, step=50.0, format="%.2f")
            observacoes = st.text_area("Observações (opcional)")
            foto = st.file_uploader("Foto (opcional)", type=["png", "jpg", "jpeg"])

            if st.form_submit_button("criar projeto", use_container_width=True):
                if not nome.strip():
                    st.warning("Informe um nome para o projeto.")
                else:
                    projeto_id = models.inserir_projeto(
                        nome.strip(), descricao.strip(), orcamento, observacoes.strip()
                    )
                    if foto is not None:
                        caminho = _salvar_foto(projeto_id, foto)
                        models.atualizar_projeto(
                            projeto_id, nome.strip(), descricao.strip(), orcamento,
                            observacoes.strip(), "Ativo", foto_path=caminho,
                        )
                    st.success(f"Projeto '{nome}' criado.")
                    st.rerun()


def _toggle_item(item_id: int) -> None:
    novo_valor = st.session_state[f"chk_{item_id}"]
    models.marcar_item_checklist(item_id, novo_valor)


def _rotulo_item(item: dict) -> str:
    """Anexa indicadores curtos ao título do item (prazo, link, foto, notas)
    sem precisar abrir os detalhes pra saber que eles existem."""
    extras = []
    if item["prazo"]:
        prefixo = "atrasado" if calc.item_vencido(item["prazo"], bool(item["concluido"])) else "até"
        extras.append(f"{prefixo} {utils.formatar_data_br(item['prazo'])}")
    if item["link"]:
        extras.append("🔗")
    if item["foto_path"]:
        extras.append("🖼")
    if item["notas"]:
        extras.append("📝")
    if not extras:
        return item["descricao"]
    return f"{item['descricao']}   ({' · '.join(extras)})"


def _popover_item(item: dict) -> None:
    item_id = int(item["id"])
    with st.popover("✎", use_container_width=False):
        if item["foto_path"]:
            caminho_foto = database.DB_DIR / item["foto_path"]
            if caminho_foto.exists():
                st.image(str(caminho_foto), use_column_width=True)

        with st.form(f"form_item_detalhe_{item_id}"):
            notas = st.text_area("Notas", value=item["notas"])
            sem_prazo = st.checkbox("sem prazo definido", value=not bool(item["prazo"]))
            valor_prazo_atual = date.fromisoformat(item["prazo"]) if item["prazo"] else date.today()
            prazo_input = st.date_input("Prazo", value=valor_prazo_atual, format="DD/MM/YYYY")
            link = st.text_input("Link", value=item["link"], placeholder="https://...")
            nova_foto = st.file_uploader("Foto (opcional)", type=["png", "jpg", "jpeg"], key=f"foto_item_{item_id}")

            c1, c2 = st.columns(2)
            salvar = c1.form_submit_button("salvar")
            excluir = c2.form_submit_button("excluir item")

        if salvar:
            prazo_final = "" if sem_prazo else prazo_input.isoformat()
            caminho = _salvar_foto_item(item_id, nova_foto) if nova_foto is not None else None
            models.atualizar_detalhes_item_checklist(
                item_id, notas.strip(), prazo_final, link.strip(), foto_path=caminho
            )
            st.rerun()
        if excluir:
            models.excluir_item_checklist(item_id)
            st.rerun()


def _secao_checklist(pid: int) -> None:
    itens = models.listar_checklist(pid)
    if itens.empty:
        st.caption("Nenhum item ainda.")
    else:
        for _, item in itens.iterrows():
            item_dict = dict(item)
            item_id = int(item_dict["id"])
            col_chk, col_pop = st.columns([8, 1])
            with col_chk:
                st.checkbox(
                    _rotulo_item(item_dict), value=bool(item_dict["concluido"]),
                    key=f"chk_{item_id}", on_change=_toggle_item, args=(item_id,),
                )
            with col_pop:
                _popover_item(item_dict)

    with st.form(f"form_add_item_{pid}", clear_on_submit=True):
        nova_descricao = st.text_input("Novo item", placeholder="Ex.: comprar passagem")
        if st.form_submit_button("adicionar item"):
            if nova_descricao.strip():
                models.inserir_item_checklist(pid, nova_descricao.strip())
                st.rerun()


def _secao_aportes(pid: int) -> None:
    with st.form(f"form_aporte_{pid}", clear_on_submit=True):
        c1, c2 = st.columns(2)
        data_aporte = c1.date_input("Data", value=date.today(), format="DD/MM/YYYY", key=f"data_aporte_{pid}")
        valor = c2.number_input("Valor (R$)", min_value=0.0, step=10.0, format="%.2f", key=f"valor_aporte_{pid}")
        observacao = st.text_input("Observação (opcional)", key=f"obs_aporte_{pid}")

        if st.form_submit_button("registrar aporte"):
            if valor <= 0:
                st.warning("Informe um valor maior que zero.")
            else:
                models.inserir_aporte(pid, data_aporte.isoformat(), valor, observacao)
                st.success(f"Aporte de {utils.formatar_moeda(valor)} registrado.")
                st.rerun()

    aportes = models.listar_aportes(pid)
    if aportes.empty:
        st.caption("Nenhum aporte registrado ainda.")
        return

    exibicao = aportes[["data", "valor", "observacao"]].copy()
    exibicao["valor"] = exibicao["valor"].map(utils.formatar_moeda)
    exibicao.columns = ["Data", "Valor", "Observação"]
    st.dataframe(exibicao, use_container_width=True, hide_index=True)

    st.caption("excluir um aporte")
    opcoes = {
        int(row["id"]): f"{row['data']} — {utils.formatar_moeda(row['valor'])}"
        for _, row in aportes.iterrows()
    }
    aporte_id = st.selectbox(
        "Selecione o aporte", list(opcoes.keys()), format_func=lambda i: opcoes[i],
        key=f"sel_aporte_{pid}", label_visibility="collapsed",
    )
    if st.button("excluir aporte selecionado", key=f"del_aporte_{pid}"):
        models.excluir_aporte(aporte_id)
        st.rerun()


def _secao_editar(projeto: dict) -> None:
    pid = int(projeto["id"])
    with st.form(f"form_editar_{pid}"):
        nome = st.text_input("Nome", value=projeto["nome"])
        descricao = st.text_input("Descrição", value=projeto["descricao"])
        orcamento = st.number_input(
            "Orçamento (R$)", min_value=0.0, step=50.0, format="%.2f", value=float(projeto["orcamento"])
        )
        observacoes = st.text_area("Observações", value=projeto["observacoes"])
        status = st.selectbox(
            "Status", utils.STATUS_PROJETO, index=utils.STATUS_PROJETO.index(projeto["status"])
        )
        nova_foto = st.file_uploader("Substituir foto (opcional)", type=["png", "jpg", "jpeg"], key=f"foto_{pid}")

        if st.form_submit_button("salvar alterações"):
            caminho = _salvar_foto(pid, nova_foto) if nova_foto is not None else None
            models.atualizar_projeto(
                pid, nome.strip(), descricao.strip(), orcamento, observacoes.strip(), status, foto_path=caminho
            )
            st.success("Projeto atualizado.")
            st.rerun()

    st.divider()
    confirmar = st.checkbox("confirmar exclusão deste projeto", key=f"confirmar_exclusao_{pid}")
    if st.button("excluir projeto", key=f"del_projeto_{pid}", disabled=not confirmar):
        models.excluir_projeto(pid)
        st.success("Projeto excluído.")
        st.rerun()


def _card_projeto(projeto: dict) -> None:
    pid = int(projeto["id"])
    with st.container(border=True):
        if projeto["foto_path"]:
            col_foto, col_main = st.columns([1, 4])
        else:
            col_foto, col_main = None, st.container()

        if col_foto is not None:
            with col_foto:
                caminho_foto = database.DB_DIR / projeto["foto_path"]
                if caminho_foto.exists():
                    st.image(str(caminho_foto), use_column_width=True)

        with col_main:
            st.subheader(projeto["nome"])
            st.caption(f"status: {projeto['status']}")
            if projeto["descricao"]:
                st.write(projeto["descricao"])

            valor_acum = calc.valor_acumulado(pid)
            prog_fin = calc.progresso_financeiro(pid, projeto["orcamento"])
            prog_check = calc.progresso_checklist(pid)

            c1, c2 = st.columns(2)
            with c1:
                if prog_fin is not None:
                    st.progress(
                        prog_fin / 100,
                        text=f"financeiro: {utils.formatar_moeda(valor_acum)} / "
                             f"{utils.formatar_moeda(projeto['orcamento'])} ({prog_fin:.0f}%)",
                    )
                else:
                    st.caption(f"acumulado: {utils.formatar_moeda(valor_acum)} (sem orçamento definido)")
            with c2:
                if prog_check is not None:
                    st.progress(prog_check / 100, text=f"checklist: {prog_check:.0f}%")
                else:
                    st.caption("checklist: sem itens ainda")

        with st.expander("detalhes e gestão"):
            tab_checklist, tab_aportes, tab_editar = st.tabs(["checklist", "aportes", "editar / excluir"])
            with tab_checklist:
                _secao_checklist(pid)
            with tab_aportes:
                _secao_aportes(pid)
            with tab_editar:
                _secao_editar(projeto)


def _secao_relatorio() -> None:
    with st.expander("relatório em PDF"):
        st.caption(
            "Gera um PDF no mesmo estilo do módulo financeiro — bom pra guardar ou "
            "compartilhar o andamento de um projeto."
        )

        projetos_df = models.listar_projetos()
        opcoes_escopo = ["Todos", "Ativo", "Pausado", "Concluído", "Um projeto específico"]
        escopo = st.selectbox("Escopo do relatório", opcoes_escopo, key="escopo_relatorio_projetos")

        opcoes_projeto = {}
        projeto_especifico_id = None
        if escopo == "Um projeto específico":
            if projetos_df.empty:
                st.caption("Nenhum projeto cadastrado ainda.")
                return
            opcoes_projeto = {int(row["id"]): row["nome"] for _, row in projetos_df.iterrows()}
            projeto_especifico_id = st.selectbox(
                "Projeto", list(opcoes_projeto.keys()), format_func=lambda i: opcoes_projeto[i],
                key="projeto_relatorio_especifico",
            )

        if st.button("gerar relatório", key="gerar_relatorio_projetos"):
            if escopo == "Um projeto específico":
                pdf_bytes = relatorio.gerar_pdf_projeto(projeto_especifico_id)
                nome_arquivo = f"relatorio_{opcoes_projeto[projeto_especifico_id]}.pdf".replace(" ", "_")
            else:
                filtro = None if escopo == "Todos" else escopo
                pdf_bytes = relatorio.gerar_pdf_lista(filtro)
                nome_arquivo = f"relatorio_projetos_{escopo.lower()}.pdf"
            st.session_state["pdf_relatorio_projetos"] = pdf_bytes
            st.session_state["pdf_relatorio_projetos_nome"] = nome_arquivo

        if st.session_state.get("pdf_relatorio_projetos"):
            st.download_button(
                "baixar PDF",
                data=st.session_state["pdf_relatorio_projetos"],
                file_name=st.session_state["pdf_relatorio_projetos_nome"],
                mime="application/pdf",
                key="baixar_relatorio_projetos",
            )


def render() -> None:
    ui.titulo_pagina("projetos")
    _resumo()

    st.divider()
    _formulario_novo_projeto()
    _secao_relatorio()

    st.divider()
    ui.eyebrow("seus projetos")
    filtro = st.radio(
        "status", ["Todos"] + utils.STATUS_PROJETO, horizontal=True, label_visibility="collapsed"
    )
    projetos = models.listar_projetos(status=None if filtro == "Todos" else filtro)

    if projetos.empty:
        st.caption("Nenhum projeto cadastrado ainda.")
    else:
        for _, projeto in projetos.iterrows():
            _card_projeto(dict(projeto))


render()
