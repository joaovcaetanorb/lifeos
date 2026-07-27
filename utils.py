"""Constantes e funções auxiliares usadas em todo o app.

Não acessa banco de dados nem contém regra de negócio financeira —
isso fica em calculations.py. Aqui só formatação e datas.
"""

from datetime import date, timedelta
import calendar

# ---------------------------------------------------------------------------
# Constantes de domínio
# ---------------------------------------------------------------------------

CATEGORIAS_GASTO = [
    "Alimentação",
    "Transporte",
    "Lazer",
    "Compras pessoais",
    "Saúde",
    "Casa",
    "Assinaturas",
    "Outros",
]

FORMAS_PAGAMENTO = [
    "Pix",
    "Débito",
    "Crédito",
    "Vale alimentação",
]

TIPOS_MOVIMENTO_RESERVA = ["Aporte", "Retirada"]

# Cor fixa por categoria (mesma cor em todos os gráficos, nunca reciclada
# conforme quais categorias aparecem no período). Passos calibrados para
# superfície escura (tema "ledger/terminal" do app).
CATEGORIA_CORES = {
    "Alimentação": "#3987e5",
    "Transporte": "#d95926",
    "Lazer": "#199e70",
    "Compras pessoais": "#c98500",
    "Saúde": "#d55181",
    "Casa": "#4caf50",
    "Assinaturas": "#9085e9",
    "Outros": "#e66767",
}

COR_PLANEJADO = "#c3c2b7"  # referência/baseline (neutro, tom claro sobre fundo escuro)
COR_REALIZADO = "#3987e5"  # valor real (destaque, mesmo azul do slot 1)

# Tema visual "ledger/terminal": fundo escuro, monoespaçado, acento verde-ledger.
COR_FUNDO = "#0D0F0C"
COR_FUNDO_ALT = "#16190F"
COR_TEXTO = "#E8E6DC"
COR_TEXTO_MUTED = "#898781"
COR_HAIRLINE = "#2A2D23"
COR_ACENTO = "#3FA66B"


# ---------------------------------------------------------------------------
# Formatação
# ---------------------------------------------------------------------------

def formatar_moeda(valor: float) -> str:
    """Formata um número como moeda brasileira: 1234.5 -> 'R$ 1.234,50'."""
    if valor is None:
        valor = 0.0
    texto = f"{valor:,.2f}"
    texto = texto.replace(",", "_").replace(".", ",").replace("_", ".")
    return f"R$ {texto}"


def mes_referencia(data_: date | None = None) -> str:
    """Retorna a referência do mês no formato 'AAAA-MM'."""
    data_ = data_ or date.today()
    return data_.strftime("%Y-%m")


def intervalo_mes(mes_referencia: str) -> tuple[str, str]:
    """'2026-07' -> ('2026-07-01', '2026-07-31'), respeitando o nº de dias do mês."""
    ano, mes = map(int, mes_referencia.split("-"))
    ultimo_dia = calendar.monthrange(ano, mes)[1]
    return f"{mes_referencia}-01", f"{mes_referencia}-{ultimo_dia:02d}"


def nome_mes(mes_referencia_str: str) -> str:
    """'2026-07' -> 'Julho/2026'."""
    ano, mes = mes_referencia_str.split("-")
    nomes = [
        "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
        "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
    ]
    return f"{nomes[int(mes) - 1]}/{ano}"


# ---------------------------------------------------------------------------
# Datas / dias úteis
# ---------------------------------------------------------------------------

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
    """Data do próximo pagamento (n-ésimo dia útil do mês).

    Se o pagamento deste mês já passou, retorna o do mês seguinte.
    """
    hoje = hoje or date.today()
    pagamento_mes_atual = n_esimo_dia_util(hoje.year, hoje.month, n_dia_util)
    if hoje <= pagamento_mes_atual:
        return pagamento_mes_atual

    ano, mes = hoje.year, hoje.month + 1
    if mes > 12:
        ano, mes = ano + 1, 1
    return n_esimo_dia_util(ano, mes, n_dia_util)


def pagamento_anterior(hoje: date | None = None, n_dia_util: int = 5) -> date:
    """Data do último pagamento recebido (início do ciclo financeiro atual).

    É o inverso de proximo_pagamento(): usado pra saber, a partir de hoje,
    quando o ciclo atual (o que este pagamento precisa cobrir) começou.
    """
    hoje = hoje or date.today()
    pagamento_mes_atual = n_esimo_dia_util(hoje.year, hoje.month, n_dia_util)
    if hoje >= pagamento_mes_atual:
        return pagamento_mes_atual

    ano, mes = hoje.year, hoje.month - 1
    if mes < 1:
        ano, mes = ano - 1, 12
    return n_esimo_dia_util(ano, mes, n_dia_util)


def dias_ate(data_alvo: date, hoje: date | None = None) -> int:
    """Dias restantes até uma data (mínimo 1, para evitar divisão por zero)."""
    hoje = hoje or date.today()
    return max((data_alvo - hoje).days, 1)


def somar_meses(data_: date, meses: int) -> date:
    """Soma N meses a uma data, ajustando o dia se o mês destino for mais curto."""
    mes_total = data_.month - 1 + meses
    ano = data_.year + mes_total // 12
    mes = mes_total % 12 + 1
    ultimo_dia = calendar.monthrange(ano, mes)[1]
    dia = min(data_.day, ultimo_dia)
    return date(ano, mes, dia)
