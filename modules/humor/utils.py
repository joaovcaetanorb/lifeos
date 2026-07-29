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

# Tema visual "ledger/terminal": mesmo esquema de cores dos demais módulos.
COR_FUNDO = "#0D0F0C"
COR_FUNDO_ALT = "#16190F"
COR_TEXTO = "#E8E6DC"
COR_TEXTO_MUTED = "#898781"
COR_HAIRLINE = "#2A2D23"
COR_ACENTO = "#3FA66B"
COR_REALIZADO = "#3987e5"


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
