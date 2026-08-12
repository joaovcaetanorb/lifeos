"""Endpoints REST da Life Timeline (/api/timeline) — a listagem é só
leitura, cruzando todos os módulos (ver webapp/timeline/calculations.py);
/insight-dia chama o Groq pra comentar um dia específico."""

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from . import calculations as calc
from . import groq_service

router = APIRouter(prefix="/api/timeline", tags=["timeline"])


@router.get("")
def obter_timeline(inicio: Optional[str] = None, fim: Optional[str] = None):
    if not inicio or not fim:
        inicio_padrao, fim_padrao = calc.periodo_padrao()
        inicio = inicio or inicio_padrao
        fim = fim or fim_padrao
    return {"inicio": inicio, "fim": fim, "eventos": calc.timeline(inicio, fim)}


class InsightDiaIn(BaseModel):
    data: str


@router.post("/insight-dia")
def insight_dia(body: InsightDiaIn):
    if not groq_service.disponivel():
        raise HTTPException(503, "GROQ_API_KEY não configurada em webapp/.env.")
    contexto = calc.contexto_ia_dia(body.data)
    texto = groq_service.gerar_leitura_dia(contexto)
    if texto is None:
        raise HTTPException(502, "Não consegui gerar a leitura do dia agora. Tenta de novo em instantes.")
    return {"texto": texto}
