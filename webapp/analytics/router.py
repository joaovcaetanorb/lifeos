"""Endpoints REST do módulo Analytics (/api/analytics/...) — cruza todos os
outros módulos, sem banco próprio (ver webapp/analytics/calculations.py)."""

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from . import calculations as calc
from . import groq_service

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


def _periodo(inicio: Optional[str], fim: Optional[str]) -> tuple[str, str]:
    if inicio and fim:
        return inicio, fim
    inicio_padrao, fim_padrao = calc.periodo_padrao()
    return inicio or inicio_padrao, fim or fim_padrao


@router.get("/resumo")
def resumo(inicio: Optional[str] = None, fim: Optional[str] = None):
    data_inicio, data_fim = _periodo(inicio, fim)
    return {"periodo": {"inicio": data_inicio, "fim": data_fim}, **calc.resumo_modulos(data_inicio, data_fim)}


class PeriodoIn(BaseModel):
    inicio: str
    fim: str


@router.post("/leitura-periodo")
def leitura_periodo(body: PeriodoIn):
    if not groq_service.disponivel():
        raise HTTPException(503, "GROQ_API_KEY não configurada em webapp/.env.")
    contexto = calc.contexto_geral(body.inicio, body.fim)
    texto = groq_service.gerar_leitura_periodo(contexto)
    if texto is None:
        raise HTTPException(502, "Não consegui gerar a leitura agora. Tenta de novo em instantes.")
    return {"texto": texto}


@router.get("/correlacoes")
def correlacoes(inicio: Optional[str] = None, fim: Optional[str] = None):
    data_inicio, data_fim = _periodo(inicio, fim)
    return {
        "periodo": {"inicio": data_inicio, "fim": data_fim},
        "correlacoes": calc.correlacoes(data_inicio, data_fim),
    }


@router.post("/correlacoes/narrar")
def narrar_correlacoes(body: PeriodoIn):
    pares = calc.correlacoes(body.inicio, body.fim)
    if not pares:
        return {"texto": "Sem dados suficientes nesse período pra cruzar módulos (mínimo 7 dias por grupo)."}
    if not groq_service.disponivel():
        raise HTTPException(503, "GROQ_API_KEY não configurada em webapp/.env.")
    texto = groq_service.narrar_correlacoes(pares)
    if texto is None:
        raise HTTPException(502, "Não consegui narrar os cruzamentos agora. Tenta de novo em instantes.")
    return {"texto": texto}


class PerguntarIn(BaseModel):
    pergunta: str
    inicio: str
    fim: str


@router.post("/perguntar")
def perguntar(body: PerguntarIn):
    if not body.pergunta.strip():
        raise HTTPException(400, "Escreve uma pergunta.")
    if not groq_service.disponivel():
        raise HTTPException(503, "GROQ_API_KEY não configurada em webapp/.env.")
    contexto = calc.contexto_geral(body.inicio, body.fim)
    texto = groq_service.responder_pergunta(body.pergunta, contexto)
    if texto is None:
        raise HTTPException(502, "Não consegui responder agora. Tenta de novo em instantes.")
    return {"texto": texto}
