"""Endpoints REST do módulo revisão (/api/revisao/...). Mesmo padrão de
webapp/momentos/router.py."""

import math

import pandas as pd
from fastapi import APIRouter
from pydantic import BaseModel

from . import calculations as calc
from . import repo as models

router = APIRouter(prefix="/api/revisao", tags=["revisao"])


def _limpar_nan(v):
    if isinstance(v, float) and math.isnan(v):
        return None
    return v


def _df_records(df: pd.DataFrame) -> list[dict]:
    if df.empty:
        return []
    return [{k: _limpar_nan(v) for k, v in r.items()} for r in df.to_dict("records")]


@router.get("/resumo")
def resumo(inicio: str, fim: str):
    return calc.resumo_com_comparacao(inicio, fim)


@router.get("/entrada")
def obter_entrada(semana_inicio: str):
    return models.obter_por_semana(semana_inicio)


class EntradaIn(BaseModel):
    semana_inicio: str
    semana_fim: str
    o_que_funcionou: str = ""
    o_que_travou: str = ""
    ajuste_proxima_semana: str = ""


@router.put("/entrada")
def salvar_entrada(body: EntradaIn):
    return models.upsert_revisao(
        body.semana_inicio,
        body.semana_fim,
        body.o_que_funcionou,
        body.o_que_travou,
        body.ajuste_proxima_semana,
    )


@router.get("/historico")
def historico(limite: int = 12):
    return _df_records(models.listar_revisoes(limite))
