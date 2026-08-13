"""Endpoints REST do módulo financeiro (/api/financeiro/...)."""

import math
from typing import Optional

import pandas as pd
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from . import calculations as calc
from . import repo as models

router = APIRouter(prefix="/api/financeiro", tags=["financeiro"])


def _limpar_nan(v):
    if isinstance(v, float) and math.isnan(v):
        return None
    return v


def _df_records(df: pd.DataFrame) -> list[dict]:
    if df.empty:
        return []
    return [{k: _limpar_nan(v) for k, v in r.items()} for r in df.to_dict("records")]


def _periodo_mes(mes: Optional[str]) -> tuple[str, str]:
    return calc.intervalo_mes(mes or calc.mes_atual())


# ---------------------------------------------------------------------------
# Resumo / config
# ---------------------------------------------------------------------------

@router.get("/resumo")
def resumo(mes: Optional[str] = None):
    return calc.resumo_geral(mes)


@router.get("/config")
def obter_config():
    return models.get_config()


class ConfigIn(BaseModel):
    salario: float
    vale_alimentacao: float


@router.put("/config")
def atualizar_config(body: ConfigIn):
    if body.salario < 0 or body.vale_alimentacao < 0:
        raise HTTPException(400, "Salário e vale-alimentação não podem ser negativos.")
    models.atualizar_config(body.salario, body.vale_alimentacao)
    return models.get_config()


# ---------------------------------------------------------------------------
# Contas fixas
# ---------------------------------------------------------------------------

@router.get("/contas-fixas")
def listar_contas_fixas(somente_ativas: bool = False):
    return _df_records(models.listar_contas_fixas(somente_ativas))


class ContaFixaIn(BaseModel):
    descricao: str
    valor: float


@router.post("/contas-fixas", status_code=201)
def criar_conta_fixa(body: ContaFixaIn):
    if not body.descricao.strip():
        raise HTTPException(400, "Informe uma descrição para a conta fixa.")
    if body.valor <= 0:
        raise HTTPException(400, "O valor precisa ser maior que zero.")
    cid = models.inserir_conta_fixa(body.descricao.strip(), body.valor)
    return {"id": cid}


class ContaFixaUpdateIn(BaseModel):
    descricao: str
    valor: float
    ativo: bool


@router.patch("/contas-fixas/{conta_id}")
def atualizar_conta_fixa(conta_id: int, body: ContaFixaUpdateIn):
    if models.obter_conta_fixa(conta_id) is None:
        raise HTTPException(404, "Conta fixa não encontrada.")
    if not body.descricao.strip():
        raise HTTPException(400, "Informe uma descrição para a conta fixa.")
    if body.valor <= 0:
        raise HTTPException(400, "O valor precisa ser maior que zero.")
    models.atualizar_conta_fixa(conta_id, body.descricao.strip(), body.valor, body.ativo)
    return {"ok": True}


@router.delete("/contas-fixas/{conta_id}", status_code=204)
def excluir_conta_fixa(conta_id: int):
    if models.obter_conta_fixa(conta_id) is None:
        raise HTTPException(404, "Conta fixa não encontrada.")
    models.excluir_conta_fixa(conta_id)


# ---------------------------------------------------------------------------
# Gastos
# ---------------------------------------------------------------------------

@router.get("/gastos")
def listar_gastos(mes: Optional[str] = None, inicio: Optional[str] = None, fim: Optional[str] = None):
    if not (inicio and fim):
        inicio, fim = _periodo_mes(mes)
    return _df_records(models.listar_gastos(data_inicio=inicio, data_fim=fim))


class GastoIn(BaseModel):
    data: str
    descricao: str
    valor: float
    categoria: str
    forma_pagamento: str


@router.post("/gastos", status_code=201)
def criar_gasto(body: GastoIn):
    if not body.descricao.strip():
        raise HTTPException(400, "Informe uma descrição para o gasto.")
    if body.valor <= 0:
        raise HTTPException(400, "O valor precisa ser maior que zero.")
    if body.forma_pagamento not in calc.FORMAS_PAGAMENTO:
        raise HTTPException(400, f"Forma de pagamento precisa ser uma de: {', '.join(calc.FORMAS_PAGAMENTO)}.")
    gid = models.inserir_gasto(
        body.data, body.descricao.strip(), body.valor, body.categoria, body.forma_pagamento,
    )
    return {"id": gid}


@router.delete("/gastos/{gasto_id}", status_code=204)
def excluir_gasto(gasto_id: int):
    if models.obter_gasto(gasto_id) is None:
        raise HTTPException(404, "Gasto não encontrado.")
    models.excluir_gasto(gasto_id)


# ---------------------------------------------------------------------------
# Receitas extras (freelance)
# ---------------------------------------------------------------------------

@router.get("/receitas-extras")
def listar_receitas_extras(mes: Optional[str] = None, inicio: Optional[str] = None, fim: Optional[str] = None):
    if not (inicio and fim):
        inicio, fim = _periodo_mes(mes)
    return _df_records(models.listar_receitas_extras(data_inicio=inicio, data_fim=fim))


class ReceitaExtraIn(BaseModel):
    data: str
    descricao: str
    valor: float


@router.post("/receitas-extras", status_code=201)
def criar_receita_extra(body: ReceitaExtraIn):
    if not body.descricao.strip():
        raise HTTPException(400, "Informe uma descrição para a renda extra.")
    if body.valor <= 0:
        raise HTTPException(400, "O valor precisa ser maior que zero.")
    rid = models.inserir_receita_extra(body.data, body.descricao.strip(), body.valor)
    return {"id": rid}


@router.delete("/receitas-extras/{receita_id}", status_code=204)
def excluir_receita_extra(receita_id: int):
    if models.obter_receita_extra(receita_id) is None:
        raise HTTPException(404, "Renda extra não encontrada.")
    models.excluir_receita_extra(receita_id)


# ---------------------------------------------------------------------------
# Cofre
# ---------------------------------------------------------------------------

@router.get("/cofre/movimentos")
def listar_movimentos_reserva(inicio: Optional[str] = None, fim: Optional[str] = None):
    return _df_records(models.listar_movimentos_reserva(data_inicio=inicio, data_fim=fim))


class MovimentoReservaIn(BaseModel):
    data: str
    valor: float
    tipo: str
    observacao: str = ""


@router.post("/cofre/movimentos", status_code=201)
def criar_movimento_reserva(body: MovimentoReservaIn):
    if body.tipo not in ("Aporte", "Retirada"):
        raise HTTPException(400, "Tipo precisa ser 'Aporte' ou 'Retirada'.")
    if body.valor <= 0:
        raise HTTPException(400, "O valor precisa ser maior que zero.")
    if body.tipo == "Retirada" and body.valor > calc.saldo_cofre():
        raise HTTPException(400, "Essa retirada deixaria o cofre com saldo negativo.")
    mid = models.inserir_movimento_reserva(body.data, body.valor, body.tipo, body.observacao.strip())
    return {"id": mid}


@router.delete("/cofre/movimentos/{movimento_id}", status_code=204)
def excluir_movimento_reserva(movimento_id: int):
    if models.obter_movimento_reserva(movimento_id) is None:
        raise HTTPException(404, "Movimento não encontrado.")
    models.excluir_movimento_reserva(movimento_id)


# ---------------------------------------------------------------------------
# Gráficos
# ---------------------------------------------------------------------------

@router.get("/graficos/categoria")
def grafico_categoria(mes: Optional[str] = None):
    return _df_records(calc.gasto_por_categoria(mes))


@router.get("/graficos/forma-pagamento")
def grafico_forma_pagamento(mes: Optional[str] = None):
    return _df_records(calc.gasto_por_forma_pagamento(mes))


@router.get("/graficos/evolucao-mensal")
def grafico_evolucao_mensal(n_meses: int = 6):
    return _df_records(calc.evolucao_mensal_gastos(n_meses))


@router.get("/graficos/evolucao-cofre")
def grafico_evolucao_cofre():
    return _df_records(calc.evolucao_cofre())
