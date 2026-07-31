"""Estilo visual compartilhado: tema 'ledger/terminal' monoespaçado.

Cópia do tema dos outros módulos (cada módulo do LifeOS roda como app
independente, mas mantém a mesma identidade visual). Chamado por toda
página logo após st.set_page_config().
"""

import streamlit as st

_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&family=Courier+Prime:wght@400;700&display=swap');

html, body, [class*="css"] {
    font-family: 'JetBrains Mono', ui-monospace, 'Courier New', monospace !important;
}

/* ledger: cantos retos em vez do arredondado padrão de SaaS */
button, input, textarea, select,
[data-testid="stMetric"], [data-testid="stExpander"], [data-testid="stForm"],
[data-testid="stDataFrame"], [data-testid="stAlert"], .stButton > button,
[data-baseweb="select"] > div {
    border-radius: 2px !important;
}

/* métricas: label pequeno em caixa alta espaçada, valor com números tabulares */
[data-testid="stMetricLabel"] {
    font-family: 'Courier Prime', monospace !important;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    font-size: 0.72rem !important;
    opacity: 0.7;
}
[data-testid="stMetricValue"] {
    font-variant-numeric: tabular-nums;
    font-weight: 700;
}

/* navegação lateral: indicador de página ativa como traço, não pílula */
[data-testid="stSidebarNavLink"] {
    border-radius: 0 !important;
    border-left: 2px solid transparent;
}
[data-testid="stSidebarNavLink"][aria-current="page"] {
    border-left: 2px solid #3FA66B;
    background: rgba(63, 166, 107, 0.10) !important;
}

hr { opacity: 0.35; }

/* capas em miniatura não precisam do botão de tela cheia do Streamlit
   (some junto com hover e quebra o layout em imagens pequenas) */
button[title="View fullscreen"] {
    display: none;
}

/* rótulo de seção estilo "eyebrow" de ledger */
.ledger-eyebrow {
    font-family: 'Courier Prime', monospace;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    font-size: 0.75rem;
    opacity: 0.55;
    margin-bottom: 0.25rem;
}

/* nota em estrelas: destaque maior que o resto da linha muted */
.nota-destaque {
    font-family: 'Courier Prime', monospace;
    font-weight: 700;
    font-size: 1.2rem;
    color: #3FA66B;
    letter-spacing: 0.02em;
    margin: 0.1rem 0 0.2rem 0;
}

/* celular: menos padding lateral, números menores */
@media (max-width: 640px) {
    [data-testid="stAppViewContainer"] .block-container {
        padding-left: 1rem !important;
        padding-right: 1rem !important;
        padding-top: 2rem !important;
    }
    [data-testid="stMetricValue"] { font-size: 1.25rem !important; }
    [data-testid="stMetricLabel"] { font-size: 0.65rem !important; }
}
</style>
"""


def aplicar_tema() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)


def titulo_pagina(nome: str) -> None:
    """Título de página no estilo prompt de terminal: '$ diario'."""
    st.title(f"$ {nome}")


def eyebrow(texto: str) -> None:
    st.markdown(f'<div class="ledger-eyebrow">{texto}</div>', unsafe_allow_html=True)


def nota_destaque(texto: str) -> None:
    st.markdown(f'<div class="nota-destaque">{texto}</div>', unsafe_allow_html=True)


_CHAVE_TOAST = "_toast_pendente"


def marcar_toast(mensagem: str, icone: str = "✅") -> None:
    """Guarda uma mensagem de confirmação pra mostrar depois de um st.rerun().

    st.success() chamado logo antes de st.rerun() não sobrevive ao rerun (o
    script é cortado antes do navegador renderizar) — por isso a mensagem
    passa pelo session_state e só vira st.toast() no topo da próxima
    execução, via mostrar_toast_pendente()."""
    st.session_state[_CHAVE_TOAST] = (mensagem, icone)


def mostrar_toast_pendente() -> None:
    """Chamar uma vez, no topo de cada página, antes de qualquer outra
    renderização — mostra (e consome) o toast deixado por marcar_toast()."""
    pendente = st.session_state.pop(_CHAVE_TOAST, None)
    if pendente:
        mensagem, icone = pendente
        st.toast(mensagem, icon=icone)
