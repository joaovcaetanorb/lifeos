"""Constantes e funções auxiliares. Port de modules/musica/utils.py,
verbatim — não tem dependência de Streamlit nem de banco."""

import calendar
from datetime import date

NOTA_MINIMA = 0.5
NOTA_MAXIMA = 5.0
NOTA_PASSO = 0.5
OPCOES_NOTA = [round(NOTA_MINIMA + i * NOTA_PASSO, 1) for i in range(int((NOTA_MAXIMA - NOTA_MINIMA) / NOTA_PASSO) + 1)]

COR_FUNDO = "#0D0F0C"
COR_FUNDO_ALT = "#16190F"
COR_TEXTO = "#E8E6DC"
COR_TEXTO_MUTED = "#898781"
COR_HAIRLINE = "#2A2D23"
COR_ACENTO = "#3FA66B"


def nota_ausente(nota: float | None) -> bool:
    return nota is None or nota != nota


def formatar_nota(nota: float | None) -> str:
    if nota_ausente(nota):
        return "sem nota"
    return f"★ {nota:g}"


def formatar_data_br(data_iso: str) -> str:
    if not data_iso:
        return ""
    ano, mes, dia = data_iso.split("-")
    return f"{dia}/{mes}/{ano}"


def somar_meses(data_: date, meses: int) -> date:
    mes_total = data_.month - 1 + meses
    ano = data_.year + mes_total // 12
    mes = mes_total % 12 + 1
    ultimo_dia = calendar.monthrange(ano, mes)[1]
    dia = min(data_.day, ultimo_dia)
    return date(ano, mes, dia)


def nome_mes_curto(periodo: str) -> str:
    nomes = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
    ano, mes = periodo.split("-")
    return f"{nomes[int(mes) - 1]}/{ano[-2:]}"
