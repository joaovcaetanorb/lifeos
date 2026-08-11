"""Constantes e funções auxiliares. Port de modules/habitos/utils.py."""

import calendar
from datetime import date


def formatar_data_br(data_iso: str) -> str:
    if not data_iso:
        return ""
    ano, mes, dia = data_iso.split("-")
    return f"{dia}/{mes}"


def hoje_iso() -> str:
    return date.today().isoformat()


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
