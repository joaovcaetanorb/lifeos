"""Endpoints REST do módulo hábitos (/api/habitos/...)."""

import math
from datetime import date
from typing import Optional

import pandas as pd
from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel

from . import calculations as calc
from . import relatorio
from . import repo as models

router = APIRouter(prefix="/api/habitos", tags=["habitos"])


def _limpar_nan(v):
    if isinstance(v, float) and math.isnan(v):
        return None
    return v


def _df_records(df: pd.DataFrame) -> list[dict]:
    if df.empty:
        return []
    return [{k: _limpar_nan(v) for k, v in r.items()} for r in df.to_dict("records")]


@router.get("/resumo")
def resumo():
    return calc.resumo_geral()


@router.get("/habitos")
def listar_habitos(somente_ativos: bool = True):
    hoje = date.today()
    habitos = models.listar_habitos(somente_ativos)
    registros = models.listar_registros_todos()
    if habitos.empty:
        return []
    saida = []
    for _, h in habitos.iterrows():
        hid = int(h["id"])
        r = calc.resumo_habito(hid, hoje, registros)
        saida.append({
            "id": hid, "nome": h["nome"], "ativo": bool(h["ativo"]),
            "streak": r["streak"], "percentual_30d": r["percentual_30d"], "feito_hoje": r["feito_hoje"],
        })
    return saida


class HabitoIn(BaseModel):
    nome: str


@router.post("/habitos", status_code=201)
def criar_habito(body: HabitoIn):
    if not body.nome.strip():
        raise HTTPException(400, "Informe um nome para o hábito.")
    hid = models.inserir_habito(body.nome.strip())
    return {"id": hid}


class HabitoUpdateIn(BaseModel):
    nome: str
    ativo: bool


@router.patch("/habitos/{habito_id}")
def atualizar_habito(habito_id: int, body: HabitoUpdateIn):
    if models.obter_habito(habito_id) is None:
        raise HTTPException(404, "Hábito não encontrado.")
    if not body.nome.strip():
        raise HTTPException(400, "Informe um nome para o hábito.")
    models.atualizar_habito(habito_id, body.nome.strip(), body.ativo)
    return {"ok": True}


@router.delete("/habitos/{habito_id}", status_code=204)
def excluir_habito(habito_id: int):
    if models.obter_habito(habito_id) is None:
        raise HTTPException(404, "Hábito não encontrado.")
    models.excluir_habito(habito_id)


class DataIn(BaseModel):
    data: str


@router.post("/habitos/{habito_id}/marcar")
def marcar(habito_id: int, body: DataIn):
    if models.obter_habito(habito_id) is None:
        raise HTTPException(404, "Hábito não encontrado.")
    models.marcar_dia(habito_id, body.data)
    return {"ok": True}


@router.post("/habitos/{habito_id}/desmarcar")
def desmarcar(habito_id: int, body: DataIn):
    models.desmarcar_dia(habito_id, body.data)
    return {"ok": True}


@router.get("/heatmap")
def heatmap(dias: int = 182):
    df = calc.heatmap_diario(dias)
    registros = df.to_dict("records")
    for r in registros:
        r["data"] = r["data"].strftime("%Y-%m-%d") if hasattr(r["data"], "strftime") else r["data"]
    return registros


def _periodo_query(inicio: Optional[str], fim: Optional[str]) -> tuple[str, str]:
    if inicio and fim:
        return inicio, fim
    intervalo = models.intervalo_datas_registros()
    hoje = date.today().isoformat()
    return intervalo if intervalo is not None else (hoje, hoje)


@router.get("/estatisticas")
def estatisticas(inicio: Optional[str] = None, fim: Optional[str] = None):
    data_inicio, data_fim = _periodo_query(inicio, fim)
    return {
        "periodo": {"inicio": data_inicio, "fim": data_fim},
        "progresso_por_habito": _df_records(calc.progresso_por_habito_periodo(data_inicio, data_fim)),
        "cumprimento_por_mes": _df_records(calc.cumprimento_por_mes(data_inicio, data_fim)),
    }


class RelatorioIn(BaseModel):
    dias: int = 30


@router.post("/relatorio-pdf")
def relatorio_pdf(body: RelatorioIn):
    if body.dias not in (7, 30, 90):
        raise HTTPException(400, "dias precisa ser 7, 30 ou 90.")
    pdf = relatorio.gerar_pdf_relatorio(body.dias)
    return Response(content=pdf, media_type="application/pdf", headers={
        "Content-Disposition": f'inline; filename="relatorio_habitos_{body.dias}d.pdf"',
    })
