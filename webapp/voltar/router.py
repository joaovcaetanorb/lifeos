"""Endpoints REST do módulo voltar (/api/voltar...)."""

import math
from typing import Optional

import pandas as pd
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from . import calculations as calc
from . import repo as models

router = APIRouter(prefix="/api/voltar", tags=["voltar"])


def _limpar_nan(v):
    if isinstance(v, float) and math.isnan(v):
        return None
    return v


def _df_records(df: pd.DataFrame) -> list[dict]:
    if df.empty:
        return []
    return [{k: _limpar_nan(v) for k, v in r.items()} for r in df.to_dict("records")]


@router.get("/painel")
def obter_painel():
    return calc.painel()


@router.get("/registros")
def listar_registros(inicio: Optional[str] = None, fim: Optional[str] = None, limite: int = 30):
    return _df_records(models.listar_registros(inicio, fim, limite))


class RegistroIn(BaseModel):
    data: str
    hora_dormir: Optional[str] = None  # "HH:MM" — que horas foi deitar na noite anterior
    agua: Optional[bool] = None
    academia: Optional[str] = None  # 'sim' | 'nao' | 'nao_era_dia'
    leitura: Optional[bool] = None
    cigarros: Optional[int] = None
    responsabilidades: Optional[bool] = None
    coisa_boa_texto: str = ""
    coisa_boa_categoria: Optional[str] = None
    dinheiro: Optional[str] = None  # 'dentro' | 'fora'
    maconha: Optional[str] = None  # 'nao_usei' | 'usei_cuidei' | 'usei_sem_cuidar'


_ACADEMIA_VALIDOS = {None, "sim", "nao", "nao_era_dia"}
_DINHEIRO_VALIDOS = {None, "dentro", "fora"}
_MACONHA_VALIDOS = {None, "nao_usei", "usei_cuidei", "usei_sem_cuidar"}


@router.post("")
def salvar_registro(body: RegistroIn):
    if not body.data:
        raise HTTPException(400, "Informe a data.")
    if body.academia not in _ACADEMIA_VALIDOS:
        raise HTTPException(400, "Academia precisa ser sim, não ou 'não era dia'.")
    if body.dinheiro not in _DINHEIRO_VALIDOS:
        raise HTTPException(400, "Dinheiro precisa ser 'dentro' ou 'fora' do planejado.")
    if body.maconha not in _MACONHA_VALIDOS:
        raise HTTPException(400, "Maconha precisa ser 'não usei', 'usei e cuidei antes' ou 'usei antes de cuidar'.")
    if body.coisa_boa_categoria and body.coisa_boa_categoria not in models.CATEGORIAS_COISA_BOA:
        raise HTTPException(400, "Categoria de coisa boa inválida.")

    registro = models.upsert_registro(
        body.data, body.hora_dormir, body.agua, body.academia, body.leitura, body.cigarros,
        body.responsabilidades, body.coisa_boa_texto.strip(), body.coisa_boa_categoria, body.dinheiro,
        body.maconha,
    )
    return registro


@router.get("/categorias-coisa-boa")
def categorias_coisa_boa():
    return models.CATEGORIAS_COISA_BOA
