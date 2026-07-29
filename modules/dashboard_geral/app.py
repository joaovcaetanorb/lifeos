"""Dashboard Geral: uma tela só com um resumo de cada área da vida.

Diferente dos outros módulos, este não tem uma tela "como funciona" separada
das telas de uso — a própria home É o resumo, pra caber no princípio de
"entendido em menos de 30 segundos".
"""

from datetime import date

import streamlit as st

import calculations as calc
import database
import groq_client
import models
import ui
import utils

st.set_page_config(page_title="Dashboard Geral", page_icon="🧭", layout="wide")
database.inicializar_banco()
ui.aplicar_tema()


def _card_financeiro() -> None:
    with st.container(border=True, key="card_financeiro"):
        st.markdown("**💰 Financeiro**")
        resumo = calc.resumo_financeiro()
        if resumo is None:
            st.caption("Módulo ainda não usado.")
            return
        st.metric("Pode gastar hoje", utils.formatar_moeda(resumo["por_dia"]))
        st.caption(
            f"Saldo até o pagamento: {utils.formatar_moeda(resumo['saldo_restante'])} · "
            f"faltam {resumo['dias_restantes']} dia(s) para "
            f"{resumo['proximo_pagamento'].strftime('%d/%m')}"
        )
        if not resumo["controle_ativo"]:
            st.caption("Controle ainda não ativo — valores zerados até a data configurada.")


def _card_projetos() -> None:
    with st.container(border=True, key="card_projetos"):
        st.markdown("**🎯 Projetos**")
        resumo = calc.resumo_projetos()
        if resumo is None:
            st.caption("Módulo ainda não usado.")
            return
        if resumo["ativos"] == 0:
            st.metric("Projetos ativos", 0)
            st.caption("Nenhum projeto ativo no momento.")
            return
        st.metric("Projetos ativos", resumo["ativos"])
        tarefa = calc.proxima_tarefa_projeto()
        if tarefa is not None:
            st.caption(f"Próxima tarefa: {tarefa['descricao']} ({tarefa['projeto_nome']})")
        else:
            progresso_txt = f"{resumo['progresso_medio']:.0f}%" if resumo["progresso_medio"] is not None else "—"
            st.caption(f"progresso médio: {progresso_txt}")


def _card_habitos() -> None:
    with st.container(border=True, key="card_habitos"):
        st.markdown("**✅ Hábitos**")
        resumo = calc.resumo_habitos()
        if resumo is None:
            st.caption("Módulo ainda não usado.")
            return
        if resumo["ativos"] == 0:
            st.metric("Hábitos ativos", 0)
            st.caption("Nenhum hábito cadastrado ainda.")
            return
        st.metric("Hábitos ativos", resumo["ativos"])
        faltantes = calc.habitos_faltantes_hoje()
        if not faltantes:
            st.caption("Tudo cumprido hoje ✓")
        else:
            st.caption(f"Faltam hoje: {', '.join(faltantes)}")


def _card_livros() -> None:
    with st.container(border=True, key="card_livros"):
        st.markdown("**📚 Livros**")
        resumo = calc.resumo_livros()
        if resumo is None:
            st.caption("Módulo ainda não usado.")
            return
        if resumo["lendo_agora"] == 0:
            st.metric("Lendo agora", "—")
        else:
            st.metric("Lendo agora", resumo["titulos_lendo"][0])
            if resumo["lendo_agora"] > 1:
                st.caption("também: " + ", ".join(resumo["titulos_lendo"][1:]))
        st.caption(f"{resumo['lidos_ano']} livro(s) concluído(s) em {date.today().year}")


def _card_musica() -> None:
    with st.container(border=True, key="card_musica"):
        st.markdown("**🎵 Música**")
        resumo = calc.resumo_musica()
        if resumo is None:
            st.caption("Módulo ainda não usado.")
            return
        st.metric("Álbuns este mês", resumo["albuns_mes"])
        if resumo["ultimo_album"]:
            st.caption(f"Último álbum: {resumo['ultimo_album']}")
        else:
            st.caption("Nenhum álbum registrado ainda.")


def _card_humor() -> None:
    with st.container(border=True, key="card_humor"):
        st.markdown("**🙂 Humor**")
        resumo = calc.resumo_humor()
        if resumo is None:
            st.caption("Módulo ainda não usado.")
            return
        if not resumo["registrado_hoje"]:
            st.metric("Humor hoje", "—")
            st.caption("Ainda sem registro hoje.")
            return
        st.metric("Humor hoje", f"{resumo['nota_hoje']}/10")
        st.caption(", ".join(resumo["tags_hoje"]) if resumo["tags_hoje"] else "sem tags")


def _secao_saudacao() -> None:
    if not groq_client.disponivel():
        return
    saudacao = models.obter_saudacao_mais_recente()
    desatualizada = saudacao is None or utils.horas_desde(saudacao["gerado_em"]) >= 24
    if desatualizada:
        contexto = calc.contexto_hoje()
        texto = groq_client.gerar_saudacao(contexto)
        if texto:
            models.salvar_saudacao(texto)
            saudacao = models.obter_saudacao_mais_recente()
    if saudacao:
        st.info(saudacao["texto"])


def render() -> None:
    ui.titulo_pagina("dashboard geral")
    ui.eyebrow(date.today().strftime("%d/%m/%Y"))
    st.caption("Um resumo rápido de cada área — abra o módulo correspondente para ver os detalhes.")

    _secao_saudacao()

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    with c1:
        _card_financeiro()
    with c2:
        _card_projetos()
    with c3:
        _card_habitos()
    with c4:
        _card_humor()
    with c5:
        _card_livros()
    with c6:
        _card_musica()


render()
