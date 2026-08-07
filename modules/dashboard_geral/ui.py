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

/* esconde o chrome padrão do Streamlit (menu hambúrguer, rodapé "Made with
   Streamlit", botão Deploy) — não combina com a identidade "ledger" própria
   do app */
#MainMenu, footer, [data-testid="stDeployButton"], [data-testid="stToolbar"] {
    visibility: hidden !important;
}

/* hover/foco nos botões: transição sutil pro verde de destaque, sem sombra
   (mantém o visual chapado/terminal) */
.stButton > button {
    transition: border-color 0.15s ease, color 0.15s ease;
}
.stButton > button:hover {
    border-color: #3FA66B !important;
    color: #3FA66B !important;
}
.stButton > button:focus-visible {
    outline: 2px solid #3FA66B;
    outline-offset: 1px;
}

/* scrollbar fina e quadrada, verde sobre escuro — o scrollbar padrão do
   navegador quebra a ilusão de terminal */
::-webkit-scrollbar { width: 10px; height: 10px; }
::-webkit-scrollbar-track { background: #0D0F0C; }
::-webkit-scrollbar-thumb { background: #2A2D23; border-radius: 0; }
::-webkit-scrollbar-thumb:hover { background: #3FA66B; }

/* cabeçalho do expander no mesmo tratamento visual do .ledger-eyebrow, e
   mais contraste na borda dos containers contra o fundo secundário */
[data-testid="stExpander"] summary {
    font-family: 'Courier Prime', monospace;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    font-size: 0.85rem;
}
[data-testid="stVerticalBlockBorderWrapper"] {
    border-color: #2A2D23 !important;
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
