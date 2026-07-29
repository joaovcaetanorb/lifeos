"""Constantes e funções auxiliares usadas em todo o app.

Não acessa banco de dados nem contém regra de negócio — isso fica em
calculations.py. Aqui só formatação e datas.
"""

from datetime import date

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
