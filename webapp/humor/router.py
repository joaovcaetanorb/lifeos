"""Endpoints REST do módulo humor (/api/humor/...)."""

import math
from datetime import date
from typing import Optional

import pandas as pd
from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel

from . import calculations as calc
from . import relatorio
from . import repo
from . import utils

router = APIRouter(prefix="/api/humor", tags=["humor"])


def _limpar_nan(v):
    if isinstance(v, float) and math.isnan(v):
        return None
    return v


def _df_records(df: pd.DataFrame) -> list[dict]:
    if df.empty:
        return []
    return [{k: _limpar_nan(v) for k, v in r.items()} for r in df.to_dict("records")]


@router.get("/tags")
def tags_disponiveis():
    return {"tags": utils.TAGS_HUMOR, "positivas": sorted(utils.TAGS_POSITIVAS)}


@router.get("/resumo")
def resumo():
    return calc.resumo_geral()


@router.get("/registros")
def listar_registros(inicio: Optional[str] = None, fim: Optional[str] = None, limite: int = 30):
    df = repo.listar_registros(inicio, fim)
    if df.empty:
        return []
    registros = _df_records(df)
    for r in registros:
        r["tags"] = utils.texto_para_tags(r["tags"])
    return registros[:limite] if limite else registros


class RegistroIn(BaseModel):
    data: str
    hora: str
    nota: int
    tags: list[str] = []
    nota_livre: str = ""


@router.post("/registros", status_code=201)
def criar_registro(body: RegistroIn):
    if not (1 <= body.nota <= 10):
        raise HTTPException(400, "Nota precisa estar entre 1 e 10.")
    rid = repo.inserir_registro(
        body.data, body.hora.strip(), body.nota, utils.tags_para_texto(body.tags), body.nota_livre.strip(),
    )
    return {"id": rid}


@router.put("/registros/{registro_id}")
def atualizar_registro(registro_id: int, body: RegistroIn):
    if repo.obter_registro(registro_id) is None:
        raise HTTPException(404, "Registro não encontrado.")
    if not (1 <= body.nota <= 10):
        raise HTTPException(400, "Nota precisa estar entre 1 e 10.")
    repo.atualizar_registro(
        registro_id, body.data, body.hora.strip(), body.nota, utils.tags_para_texto(body.tags), body.nota_livre.strip(),
    )
    return {"ok": True}


@router.delete("/registros/{registro_id}", status_code=204)
def excluir_registro(registro_id: int):
    if repo.obter_registro(registro_id) is None:
        raise HTTPException(404, "Registro não encontrado.")
    repo.excluir_registro(registro_id)


def _periodo_query(inicio: Optional[str], fim: Optional[str]) -> tuple[str, str]:
    if inicio and fim:
        return inicio, fim
    intervalo = repo.intervalo_datas_registros()
    hoje = date.today().isoformat()
    return intervalo if intervalo is not None else (hoje, hoje)


@router.get("/estatisticas/hora-dia")
def estatisticas_hora_dia(inicio: Optional[str] = None, fim: Optional[str] = None):
    data_inicio, data_fim = _periodo_query(inicio, fim)
    df = calc.registros_periodo(data_inicio, data_fim)
    if df.empty:
        return {"periodo": {"inicio": data_inicio, "fim": data_fim}, "registros": []}
    saida = [
        {
            "data": r["datetime"].strftime("%Y-%m-%d"),
            "hora_decimal": round(r["datetime"].hour + r["datetime"].minute / 60, 2),
            "nota": int(r["nota"]),
            "tags": utils.texto_para_tags(r["tags"]),
            "cor": utils.cor_nota(r["nota"]),
        }
        for _, r in df.iterrows()
    ]
    return {"periodo": {"inicio": data_inicio, "fim": data_fim}, "registros": saida}


@router.get("/estatisticas/tags")
def estatisticas_tags(inicio: Optional[str] = None, fim: Optional[str] = None):
    data_inicio, data_fim = _periodo_query(inicio, fim)
    df = calc.tags_mais_frequentes(data_inicio, data_fim)
    saida = _df_records(df)
    for item in saida:
        item["cor"] = utils.cor_tag(item["tag"])
        item["positiva"] = item["tag"] in utils.TAGS_POSITIVAS
    return {"periodo": {"inicio": data_inicio, "fim": data_fim}, "tags": saida}


@router.get("/meses-disponiveis")
def meses_disponiveis():
    hoje = date.today()
    intervalo = repo.intervalo_datas_registros()
    inicio = date.fromisoformat(intervalo[0]) if intervalo else hoje

    meses = []
    ano, mes = inicio.year, inicio.month
    while (ano, mes) <= (hoje.year, hoje.month):
        meses.append({"ano": ano, "mes": mes, "label": f"{utils.NOMES_MESES[mes - 1]} de {ano}"})
        ano, mes = (ano + 1, 1) if mes == 12 else (ano, mes + 1)
    return list(reversed(meses))


class RelatorioIn(BaseModel):
    dias: int = 30


@router.post("/relatorio-pdf")
def relatorio_pdf(body: RelatorioIn):
    if body.dias not in (7, 30, 90):
        raise HTTPException(400, "dias precisa ser 7, 30 ou 90.")
    pdf = relatorio.gerar_pdf_relatorio(body.dias)
    return Response(content=pdf, media_type="application/pdf", headers={
        "Content-Disposition": f'inline; filename="relatorio_humor_{body.dias}d.pdf"',
    })
