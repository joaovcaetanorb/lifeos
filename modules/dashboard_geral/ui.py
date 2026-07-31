"""Estilo visual compartilhado: tema 'ledger/terminal' monoespaçado.

Mesmo tema dos demais módulos do LifeOS, para manter identidade visual
consistente entre eles.
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

/* cards de resumo: mesma altura entre si, texto sempre encostado no topo,
   mesmo quando um card tem mais linhas de legenda que os outros */
[data-testid="stHorizontalBlock"] {
    align-items: stretch;
}
[class*="st-key-card_"] {
    height: 100%;
}

/* título grande dentro de um card do Dashboard Geral: precisa quebrar
   linha (nomes de livro/álbum longos), diferente do st.metric (que corta
   com reticências em vez de quebrar) */
.card-destaque {
    font-family: 'Courier Prime', monospace;
    font-weight: 700;
    font-size: 1.3rem;
    line-height: 1.3;
    margin: 0.1rem 0 0.3rem 0;
    overflow-wrap: break-word;
}

/* capa (livro/álbum) dentro de um card: cantos retos, igual ao resto do tema */
.card-capa img {
    border-radius: 2px !important;
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


def destaque_grande(texto: str) -> None:
    """Título grande dentro de um card — ao contrário de st.metric, quebra
    linha em vez de cortar com reticências (importante pra nomes longos de
    livro/álbum)."""
    st.markdown(f'<div class="card-destaque">{texto}</div>', unsafe_allow_html=True)
