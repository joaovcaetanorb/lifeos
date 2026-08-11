"""Endpoint REST da Life Timeline (/api/timeline) — só leitura, cruza todos
os módulos (ver webapp/timeline/calculations.py)."""

from typing import Optional

from fastapi import APIRouter

from . import calculations as calc

router = APIRouter(prefix="/api/timeline", tags=["timeline"])


@router.get("")
def obter_timeline(inicio: Optional[str] = None, fim: Optional[str] = None):
    if not inicio or not fim:
        inicio_padrao, fim_padrao = calc.periodo_padrao()
        inicio = inicio or inicio_padrao
        fim = fim or fim_padrao
    return {"inicio": inicio, "fim": fim, "eventos": calc.timeline(inicio, fim)}
