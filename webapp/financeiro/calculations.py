"""Lógica de negócio (sem SQL). Mês calendário simples (dia 1 ao último dia
do mês) — sem ciclo de dia útil de pagamento, ao contrário do financeiro
antigo em modules/financeiro/calculations.py."""

import calendar
from datetime import date

import pandas as pd

from . import repo as models

CATEGORIAS_GASTO = [
    "Alimentação", "Transporte", "Lazer", "Compras pessoais",
    "Saúde", "Casa", "Assinaturas", "Outros",
]
FORMAS_PAGAMENTO = ["Dinheiro", "Vale-alimentação", "Cartão de crédito"]
NOMES_MES_CURTO = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]

_SINAL_MOVIMENTO_RESERVA = {"Aporte": 1, "Retirada": -1}


def mes_atual() -> str:
    return date.today().strftime("%Y-%m")


def intervalo_mes(mes: str) -> tuple[str, str]:
    ano, mes_num = (int(p) for p in mes.split("-"))
    ultimo_dia = calendar.monthrange(ano, mes_num)[1]
    inicio = f"{ano:04d}-{mes_num:02d}-01"
    fim = f"{ano:04d}-{mes_num:02d}-{ultimo_dia:02d}"
    return inicio, fim


def saldo_dinheiro(mes: str | None = None) -> dict:
    """Salário + receitas extras do mês − contas fixas ativas − gastos do
    mês pagos em Dinheiro ou Cartão de crédito (vale-alimentação tem bucket
    próprio, ver saldo_vale_alimentacao)."""
    mes = mes or mes_atual()
    inicio, fim = intervalo_mes(mes)
    config = models.get_config() or {"salario": 0.0}

    contas_fixas = models.listar_contas_fixas(somente_ativas=True)
    contas_fixas_total = round(contas_fixas["valor"].sum(), 2) if not contas_fixas.empty else 0.0

    gastos = models.listar_gastos(data_inicio=inicio, data_fim=fim)
    gastos_dinheiro = 0.0
    if not gastos.empty:
        gastos_dinheiro = round(
            gastos[gastos["forma_pagamento"].isin(["Dinheiro", "Cartão de crédito"])]["valor"].sum(), 2
        )

    receitas = models.listar_receitas_extras(data_inicio=inicio, data_fim=fim)
    receitas_total = round(receitas["valor"].sum(), 2) if not receitas.empty else 0.0

    salario = config["salario"]
    saldo = round(salario + receitas_total - contas_fixas_total - gastos_dinheiro, 2)

    return {
        "salario": salario,
        "receitas_extras": receitas_total,
        "contas_fixas": contas_fixas_total,
        "gastos": gastos_dinheiro,
        "saldo": saldo,
    }


def saldo_vale_alimentacao(mes: str | None = None) -> dict:
    """Valor do vale configurado − gastos do mês pagos em Vale-alimentação."""
    mes = mes or mes_atual()
    inicio, fim = intervalo_mes(mes)
    config = models.get_config() or {"vale_alimentacao": 0.0}
    vale_alimentacao = config["vale_alimentacao"]

    gastos = models.listar_gastos(data_inicio=inicio, data_fim=fim)
    gasto_va = 0.0
    if not gastos.empty:
        gasto_va = round(gastos[gastos["forma_pagamento"] == "Vale-alimentação"]["valor"].sum(), 2)

    return {
        "total": vale_alimentacao,
        "gasto": gasto_va,
        "saldo": round(vale_alimentacao - gasto_va, 2),
    }


def saldo_cofre() -> float:
    movimentos = models.listar_movimentos_reserva()
    if movimentos.empty:
        return 0.0
    sinais = movimentos["tipo"].map(_SINAL_MOVIMENTO_RESERVA)
    return round((movimentos["valor"] * sinais).sum(), 2)


def resumo_geral(mes: str | None = None) -> dict:
    mes = mes or mes_atual()
    return {
        "mes": mes,
        "dinheiro": saldo_dinheiro(mes),
        "vale_alimentacao": saldo_vale_alimentacao(mes),
        "cofre": saldo_cofre(),
    }


# ---------------------------------------------------------------------------
# Gráficos
# ---------------------------------------------------------------------------

def gasto_por_categoria(mes: str | None = None) -> pd.DataFrame:
    mes = mes or mes_atual()
    inicio, fim = intervalo_mes(mes)
    gastos = models.listar_gastos(data_inicio=inicio, data_fim=fim)
    if gastos.empty:
        return pd.DataFrame(columns=["categoria", "valor"])
    return (
        gastos.groupby("categoria", as_index=False)["valor"].sum()
        .sort_values("valor", ascending=False)
        .reset_index(drop=True)
    )


def gasto_por_forma_pagamento(mes: str | None = None) -> pd.DataFrame:
    mes = mes or mes_atual()
    inicio, fim = intervalo_mes(mes)
    gastos = models.listar_gastos(data_inicio=inicio, data_fim=fim)
    base = pd.DataFrame({"forma_pagamento": FORMAS_PAGAMENTO})
    if gastos.empty:
        base["valor"] = 0.0
        return base
    agrupado = gastos.groupby("forma_pagamento", as_index=False)["valor"].sum()
    return base.merge(agrupado, on="forma_pagamento", how="left").fillna(0.0)


def _meses_anteriores(n_meses: int, hoje: date | None = None) -> list[str]:
    hoje = hoje or date.today()
    meses = []
    for i in range(n_meses - 1, -1, -1):
        ano, mes_num = hoje.year, hoje.month - i
        while mes_num <= 0:
            mes_num += 12
            ano -= 1
        meses.append(f"{ano:04d}-{mes_num:02d}")
    return meses


def evolucao_mensal_gastos(n_meses: int = 6) -> pd.DataFrame:
    meses = _meses_anteriores(n_meses)
    inicio, _ = intervalo_mes(meses[0])
    _, fim = intervalo_mes(meses[-1])
    gastos = models.listar_gastos(data_inicio=inicio, data_fim=fim)

    linhas = []
    for m in meses:
        total = 0.0
        if not gastos.empty:
            total = gastos[gastos["data"].str.slice(0, 7) == m]["valor"].sum()
        ano, mes_num = (int(p) for p in m.split("-"))
        linhas.append({"mes": m, "mes_nome": f"{NOMES_MES_CURTO[mes_num - 1]}/{ano % 100:02d}", "valor": round(float(total), 2)})
    return pd.DataFrame(linhas)


def evolucao_cofre() -> pd.DataFrame:
    movimentos = models.listar_movimentos_reserva()
    if movimentos.empty:
        return pd.DataFrame(columns=["data", "saldo"])
    df = movimentos.copy()
    df["valor_sinal"] = df["valor"] * df["tipo"].map(_SINAL_MOVIMENTO_RESERVA)
    df = df.sort_values(["data", "id"])
    por_dia = df.groupby("data", as_index=False)["valor_sinal"].sum()
    por_dia["saldo"] = por_dia["valor_sinal"].cumsum().round(2)
    return por_dia[["data", "saldo"]]
