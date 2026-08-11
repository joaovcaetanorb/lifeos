"""Endpoints REST do módulo momentos (/api/momentos...). GET existe só por
completude/debug — a Timeline lê via import direto (ver
webapp/timeline/calculations.py), não por HTTP."""

import math
from typing import Optional

import pandas as pd
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from . import repo as models

router = APIRouter(prefix="/api/momentos", tags=["momentos"])


def _limpar_nan(v):
    if isinstance(v, float) and math.isnan(v):
        return None
    return v


def _df_records(df: pd.DataFrame) -> list[dict]:
    if df.empty:
        return []
    return [{k: _limpar_nan(v) for k, v in r.items()} for r in df.to_dict("records")]


@router.get("")
def listar_momentos(inicio: Optional[str] = None, fim: Optional[str] = None):
    return _df_records(models.listar_momentos(inicio, fim))


class MomentoIn(BaseModel):
    texto: str
    categoria: str


@router.post("", status_code=201)
def criar_momento(body: MomentoIn):
    if not body.texto.strip():
        raise HTTPException(400, "Escreve alguma coisa.")
    if body.categoria not in models.CATEGORIAS_MOMENTO:
        raise HTTPException(400, f"Categoria precisa ser uma de: {', '.join(models.CATEGORIAS_MOMENTO)}.")
    mid = models.inserir_momento(body.texto.strip(), body.categoria)
    return {"id": mid}


@router.delete("/{momento_id}", status_code=204)
def excluir_momento(momento_id: int):
    if models.obter_momento(momento_id) is None:
        raise HTTPException(404, "Momento não encontrado.")
    models.excluir_momento(momento_id)
