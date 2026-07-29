"""Constantes e funções auxiliares usadas em todo o app.

Não acessa banco de dados nem contém regra de negócio — isso fica em
calculations.py. Aqui só formatação, datas e constantes de domínio.
"""

import calendar
from datetime import date, datetime

# Tema visual "ledger/terminal": mesmo esquema de cores dos demais módulos.
COR_FUNDO = "#0D0F0C"
COR_FUNDO_ALT = "#16190F"
COR_TEXTO = "#E8E6DC"
COR_TEXTO_MUTED = "#898781"
COR_HAIRLINE = "#2A2D23"
COR_ACENTO = "#3FA66B"
COR_REALIZADO = "#3987e5"

# Perguntas pré-definidas mostradas como botões — vocabulário fixo (não
# texto livre) porque cada uma tem um foco temático específico que ajuda o
# prompt a saber que parte do contexto priorizar na resposta.
PERGUNTAS_PREDEFINIDAS = [
    "Como evoluí nos últimos meses?",
    "Meu humor mudou?",
    "Estou economizando mais?",
    "Quanto avancei nos meus projetos?",
    "Quais hábitos eu tenho mais dificuldade?",
    "Quais gêneros ou artistas eu mais ouvi?",
]


def formatar_moeda(valor: float) -> str:
    return f"R$ {valor:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")


def nome_mes(mes_referencia: str) -> str:
    """'2026-07' -> 'Julho/2026'."""
    nomes = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho",
             "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
    ano, mes = mes_referencia.split("-")
    return f"{nomes[int(mes) - 1]}/{ano}"


def nome_mes_curto(periodo: str) -> str:
    """'2026-07' -> 'jul/26'."""
    nomes = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
    ano, mes = periodo.split("-")
    return f"{nomes[int(mes) - 1]}/{ano[-2:]}"


def somar_meses(data_: date, meses: int) -> date:
    """Soma N meses a uma data, ajustando o dia se o mês destino for mais curto."""
    mes_total = data_.month - 1 + meses
    ano = data_.year + mes_total // 12
    mes = mes_total % 12 + 1
    ultimo_dia = calendar.monthrange(ano, mes)[1]
    dia = min(data_.day, ultimo_dia)
    return date(ano, mes, dia)


def horas_desde(timestamp_iso: str) -> float:
    """Horas decorridas desde um timestamp 'YYYY-MM-DD HH:MM:SS' gravado
    via CURRENT_TIMESTAMP do SQLite — que é sempre UTC, por isso compara
    com utcnow() e não now() (senão o fuso horário local desvia a conta)."""
    gerado_em = datetime.fromisoformat(timestamp_iso)
    return (datetime.utcnow() - gerado_em).total_seconds() / 3600
