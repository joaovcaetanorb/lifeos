"""Dashboard Geral: uma tela só com um resumo de cada área da vida.

Diferente dos outros módulos, este não tem uma tela "como funciona" separada
das telas de uso — a própria home É o resumo, pra caber no princípio de
"entendido em menos de 30 segundos".
"""

from datetime import date
from pathlib import Path

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

# Todos os módulos rodam no mesmo processo/disco (ver app.py da raiz), então
# dá pra ler o arquivo de capa direto do disco do módulo dono — sem duplicar
# a imagem nem o módulo virar "dono" dela. Só leitura, nunca escreve aqui.
_MODULES_DIR = Path(__file__).resolve().parent.parent


def _capa_absoluta(modulo: str, capa_path: str) -> str | None:
    if not capa_path:
        return None
    caminho = _MODULES_DIR / modulo / "database" / capa_path
    return str(caminho) if caminho.exists() else None


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
        st.caption(f"Gasto no ciclo atual: {utils.formatar_moeda(resumo['gasto_mes'])}")
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
            prazo_txt = f" · prazo {tarefa['prazo']}" if tarefa["prazo"] else ""
            st.caption(f"Próxima tarefa: {tarefa['descricao']} ({tarefa['projeto_nome']}{prazo_txt})")
        progresso_txt = f"{resumo['progresso_medio']:.0f}%" if resumo["progresso_medio"] is not None else "—"
        st.caption(
            f"progresso médio: {progresso_txt} · total investido: "
            f"{utils.formatar_moeda(resumo['total_investido'])}"
        )


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
        if resumo["percentual_medio"] is not None:
            st.caption(f"cumprimento médio (30 dias): {resumo['percentual_medio']:.0f}%")


def _linha_capa_e_texto(capa_caminho: str | None):
    """Duas colunas (capa pequena + texto) quando há capa, senão só uma
    coluna de texto ocupando a largura toda. Retorna o container/coluna de
    texto, pra ser usado como `with`."""
    if capa_caminho:
        col_capa, col_texto = st.columns([1, 5])
        with col_capa:
            st.markdown('<div class="card-capa">', unsafe_allow_html=True)
            st.image(capa_caminho, width=90)
            st.markdown("</div>", unsafe_allow_html=True)
        return col_texto
    return st.container()


def _card_livros() -> None:
    with st.container(border=True, key="card_livros"):
        st.markdown("**📚 Livros**")
        resumo = calc.resumo_livros()
        if resumo is None:
            st.caption("Módulo ainda não usado.")
            return
        if resumo["lendo_agora"] == 0:
            ui.destaque_grande("Nenhum livro em andamento")
        else:
            principal = resumo["livros_lendo"][0]
            capa = _capa_absoluta("livros", principal["capa_path"])
            col_texto = _linha_capa_e_texto(capa)
            with col_texto:
                ui.destaque_grande(principal["nome"])
                detalhes = principal["autor"]
                if principal["genero"]:
                    detalhes += f" · {principal['genero']}"
                if principal["ano"]:
                    detalhes += f" · {principal['ano']}"
                st.caption(detalhes)
                if resumo["lendo_agora"] > 1:
                    outros = ", ".join(l["nome"] for l in resumo["livros_lendo"][1:])
                    st.caption(f"também lendo: {outros}")
        st.caption(f"{resumo['lidos_ano']} livro(s) concluído(s) em {date.today().year}")


def _card_musica() -> None:
    with st.container(border=True, key="card_musica"):
        st.markdown("**🎵 Música**")
        resumo = calc.resumo_musica()
        if resumo is None:
            st.caption("Módulo ainda não usado.")
            return
        album = resumo["ultimo_album"]
        if not album:
            ui.destaque_grande("Nenhum álbum registrado ainda")
        else:
            capa = _capa_absoluta("musica", album["capa_path"])
            col_texto = _linha_capa_e_texto(capa)
            with col_texto:
                ui.destaque_grande(f"{album['nome']} — {album['artista']}")
                detalhes = []
                if album["genero"]:
                    detalhes.append(album["genero"])
                if album["ano"]:
                    detalhes.append(str(album["ano"]))
                if detalhes:
                    st.caption(" · ".join(detalhes))
        st.caption(f"{resumo['albuns_mes']} álbum(ns) ouvido(s) este mês")


def _card_humor() -> None:
    with st.container(border=True, key="card_humor"):
        st.markdown("**🙂 Humor**")
        resumo = calc.resumo_humor()
        if resumo is None:
            st.caption("Módulo ainda não usado.")
            return
        if not resumo["registrado_hoje"]:
            ui.destaque_grande("Ainda sem registro hoje")
            return
        ui.destaque_grande(f"{resumo['nota_hoje']}/10")
        st.caption(", ".join(resumo["tags_hoje"]) if resumo["tags_hoje"] else "sem tags")
        if resumo["nota_livre_hoje"]:
            st.caption(resumo["nota_livre_hoje"])


def _secao_saudacao() -> None:
    if not groq_client.disponivel():
        return
    saudacao = models.obter_saudacao_mais_recente()
    humor_hoje = calc.resumo_humor()

    # Além do refresh diário (24h), a saudação também precisa ser refeita
    # se um registro de humor mais novo chegou depois dela — senão o
    # banner pode dizer "dia positivo" logo acima de um card de Humor que
    # acabou de virar negativo, e o usuário lê isso como "não atualizou".
    humor_mais_novo = (
        humor_hoje is not None
        and humor_hoje["registrado_hoje"]
        and humor_hoje["criado_em"] is not None
        and (saudacao is None or humor_hoje["criado_em"] > saudacao["gerado_em"])
    )
    desatualizada = saudacao is None or utils.horas_desde(saudacao["gerado_em"]) >= 24 or humor_mais_novo
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

    _card_financeiro()
    _card_humor()
    _card_habitos()
    _card_projetos()
    _card_livros()
    _card_musica()


render()
