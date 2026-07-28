"""Estilo visual compartilhado: tema 'ledger/terminal' monoespaçado.

Chamado por toda página logo após st.set_page_config(). Mantém CSS num só
lugar em vez de repetir a mesma string em 5 arquivos.
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

/* rótulo de seção estilo "eyebrow" de ledger */
.ledger-eyebrow {
    font-family: 'Courier Prime', monospace;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    font-size: 0.75rem;
    opacity: 0.55;
    margin-bottom: 0.25rem;
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
    """Título de página no estilo prompt de terminal: '$ dashboard'."""
    st.title(f"$ {nome}")


def eyebrow(texto: str) -> None:
    st.markdown(f'<div class="ledger-eyebrow">{texto}</div>', unsafe_allow_html=True)


def explicacao(texto: str) -> None:
    """Nota curta de 'como ler este gráfico', recolhida por padrão."""
    with st.expander("? como ler este gráfico"):
        st.caption(texto)
