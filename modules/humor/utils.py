"""Constantes e funções auxiliares usadas em todo o app.

Não acessa banco de dados nem contém regra de negócio — isso fica em
calculations.py. Aqui só formatação, datas e vocabulário fixo de domínio.
"""

from datetime import date, datetime

# Vocabulário fixo de tags — de propósito, não é texto livre. O objetivo
# declarado é permitir cruzamento automático (ex.: "IA" relacionando
# hábitos x humor x música) mais pra frente, e isso só funciona com um
# vocabulário fechado e contável, não com palavras livres cada dia diferentes.
TAGS_HUMOR = [
    "Animado", "Grato", "Motivado", "Calmo", "Realizado", "Confiante", "Focado",
    "Ansioso", "Cansado", "Irritado", "Triste", "Sobrecarregado", "Frustrado", "Entediado",
]

# As 7 primeiras tags acima são o lado positivo do vocabulário; o resto é
# negativo. Usado só pra colorir (gráfico de tags, badges do histórico) —
# não afeta a nota numérica.
TAGS_POSITIVAS = set(TAGS_HUMOR[:7])

# Tema visual "ledger/terminal": mesmo esquema de cores dos demais módulos.
COR_FUNDO = "#0D0F0C"
COR_FUNDO_ALT = "#16190F"
COR_TEXTO = "#E8E6DC"
COR_TEXTO_MUTED = "#898781"
COR_HAIRLINE = "#2A2D23"
COR_ACENTO = "#3FA66B"
COR_REALIZADO = "#3987e5"

# Par validado (CVD ΔE 19.2, normal-vision ΔE 29.0, contraste >=3:1 no fundo
# escuro do app) via scripts/validate_palette.js da skill de dataviz —
# verde/vermelho (a primeira tentativa) falha separação pra daltonismo
# deutan (ΔE 4.0), por isso azul/vermelho.
COR_TAG_POSITIVO = "#3987e5"
COR_TAG_NEGATIVO = "#e66767"


def formatar_data_br(data_iso: str) -> str:
    """'2026-08-05' -> '05/08'. String vazia retorna vazio."""
    if not data_iso:
        return ""
    ano, mes, dia = data_iso.split("-")
    return f"{dia}/{mes}"


def hoje_iso() -> str:
    return date.today().isoformat()


def agora_hora() -> str:
    return datetime.now().strftime("%H:%M")


def tags_para_texto(tags: list[str]) -> str:
    """['Animado', 'Grato'] -> 'Animado,Grato' (armazenamento em coluna única)."""
    return ",".join(tags)


def texto_para_tags(texto: str) -> list[str]:
    """'Animado,Grato' -> ['Animado', 'Grato']. String vazia -> []."""
    return [t for t in texto.split(",") if t]


def cor_tag(tag: str) -> str:
    return COR_TAG_POSITIVO if tag in TAGS_POSITIVAS else COR_TAG_NEGATIVO


def badge_cor_tag(tag: str) -> str:
    """Nome de cor aceito por st.badge/diretiva markdown (":blue-badge[...]")."""
    return "blue" if tag in TAGS_POSITIVAS else "red"
