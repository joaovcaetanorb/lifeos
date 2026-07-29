"""Constantes e funções auxiliares usadas pelo Dashboard Geral.

Inclui a mesma lógica de dia útil/ciclo de pagamento do módulo Financeiro
(duplicada aqui de propósito, como já acontece com formatar_moeda entre os
outros módulos — cada módulo do LifeOS é uma aplicação independente).
"""

import calendar
from datetime import date, timedelta

# Tema visual "ledger/terminal": mesmo esquema de cores dos demais módulos.
COR_FUNDO = "#0D0F0C"
COR_FUNDO_ALT = "#16190F"
COR_TEXTO = "#E8E6DC"
COR_TEXTO_MUTED = "#898781"
COR_HAIRLINE = "#2A2D23"
COR_ACENTO = "#3FA66B"
COR_REALIZADO = "#3987e5"


def formatar_moeda(valor: float) -> str:
    """Formata um número como moeda brasileira: 1234.5 -> 'R$ 1.234,50'."""
    if valor is None:
        valor = 0.0
    texto = f"{valor:,.2f}"
    texto = texto.replace(",", "_").replace(".", ",").replace("_", ".")
    return f"R$ {texto}"


def somar_meses(data_: date, meses: int) -> date:
    """Soma N meses a uma data, ajustando o dia se o mês destino for mais curto."""
    mes_total = data_.month - 1 + meses
    ano = data_.year + mes_total // 12
    mes = mes_total % 12 + 1
    ultimo_dia = calendar.monthrange(ano, mes)[1]
    dia = min(data_.day, ultimo_dia)
    return date(ano, mes, dia)


def eh_dia_util(data_: date) -> bool:
    """Considera apenas fins de semana (feriados não são tratados nesta versão)."""
    return data_.weekday() < 5  # 0=segunda ... 4=sexta


def n_esimo_dia_util(ano: int, mes: int, n: int) -> date:
    """Retorna a data do n-ésimo dia útil de um mês/ano (ex.: 5º dia útil)."""
    dia = date(ano, mes, 1)
    contador = 0
    while True:
        if eh_dia_util(dia):
            contador += 1
            if contador == n:
                return dia
        dia += timedelta(days=1)


def proximo_pagamento(hoje: date | None = None, n_dia_util: int = 5) -> date:
    """Data do próximo pagamento (n-ésimo dia útil do mês)."""
    hoje = hoje or date.today()
    pagamento_mes_atual = n_esimo_dia_util(hoje.year, hoje.month, n_dia_util)
    if hoje <= pagamento_mes_atual:
        return pagamento_mes_atual

    ano, mes = hoje.year, hoje.month + 1
    if mes > 12:
        ano, mes = ano + 1, 1
    return n_esimo_dia_util(ano, mes, n_dia_util)


def pagamento_anterior(hoje: date | None = None, n_dia_util: int = 5) -> date:
    """Data do último pagamento recebido (início do ciclo financeiro atual)."""
    hoje = hoje or date.today()
    pagamento_mes_atual = n_esimo_dia_util(hoje.year, hoje.month, n_dia_util)
    if hoje >= pagamento_mes_atual:
        return pagamento_mes_atual

    ano, mes = hoje.year, hoje.month - 1
    if mes < 1:
        ano, mes = ano - 1, 12
    return n_esimo_dia_util(ano, mes, n_dia_util)


def mes_referencia(data_: date | None = None, dia_util_pagamento: int = 5) -> str:
    """Rótulo 'AAAA-MM' do ciclo financeiro (pagamento-a-pagamento) ao qual a
    data pertence — nomeado pelo mês em que o ciclo COMEÇA."""
    data_ = data_ or date.today()
    inicio_ciclo = pagamento_anterior(data_, dia_util_pagamento)
    return inicio_ciclo.strftime("%Y-%m")


def intervalo_mes(mes_referencia_str: str, dia_util_pagamento: int = 5) -> tuple[str, str]:
    """'2026-08' -> (data do pagamento de agosto, véspera do pagamento de setembro)."""
    ano, mes = map(int, mes_referencia_str.split("-"))
    inicio = n_esimo_dia_util(ano, mes, dia_util_pagamento)
    ano_fim, mes_fim = (ano, mes + 1) if mes < 12 else (ano + 1, 1)
    fim = n_esimo_dia_util(ano_fim, mes_fim, dia_util_pagamento) - timedelta(days=1)
    return inicio.isoformat(), fim.isoformat()


def nome_mes(mes_referencia_str: str) -> str:
    """'2026-07' -> 'Julho/2026'."""
    ano, mes = mes_referencia_str.split("-")
    nomes = [
        "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
        "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
    ]
    return f"{nomes[int(mes) - 1]}/{ano}"


def dias_ate(data_alvo: date, hoje: date | None = None) -> int:
    """Dias restantes até uma data (mínimo 1, para evitar divisão por zero)."""
    hoje = hoje or date.today()
    return max((data_alvo - hoje).days, 1)
