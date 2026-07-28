"""Regras de negócio do módulo Projetos: progresso financeiro, progresso de
checklist e resumo geral. Sem acesso direto a SQL — usa models.py.
"""

from datetime import date

import pandas as pd

import models


def item_vencido(prazo_iso: str, concluido: bool) -> bool:
    """True se o item tem prazo definido, já passou, e ainda não foi concluído."""
    if not prazo_iso or concluido:
        return False
    return date.fromisoformat(prazo_iso) < date.today()


def valor_acumulado(projeto_id: int) -> float:
    aportes = models.listar_aportes(projeto_id)
    if aportes.empty:
        return 0.0
    return round(aportes["valor"].sum(), 2)


def progresso_financeiro(projeto_id: int, orcamento: float) -> float | None:
    """Percentual (0-100) do orçamento já acumulado. None se orçamento é 0
    (não há como calcular progresso sem meta)."""
    if orcamento <= 0:
        return None
    return min(valor_acumulado(projeto_id) / orcamento * 100, 100)


def progresso_checklist(projeto_id: int) -> float | None:
    """Percentual (0-100) de itens concluídos. None se não há itens."""
    itens = models.listar_checklist(projeto_id)
    if itens.empty:
        return None
    return round(itens["concluido"].sum() / len(itens) * 100, 1)


def evolucao_aportes(projeto_id: int) -> pd.DataFrame:
    """Saldo acumulado de aportes ao longo do tempo, pra gráfico de linha."""
    aportes = models.listar_aportes(projeto_id)
    if aportes.empty:
        return pd.DataFrame(columns=["data", "saldo_acumulado"])
    aportes = aportes.sort_values("data").copy()
    aportes["saldo_acumulado"] = aportes["valor"].cumsum()
    return aportes[["data", "saldo_acumulado"]]


def resumo_geral() -> dict:
    """Números curtos para o topo da página: quantos projetos ativos e
    quanto já foi investido no total (todos os projetos, qualquer status)."""
    projetos = models.listar_projetos()
    ativos = 0 if projetos.empty else (projetos["status"] == "Ativo").sum()

    total_investido = 0.0
    if not projetos.empty:
        total_investido = sum(valor_acumulado(int(pid)) for pid in projetos["id"])

    return {"projetos_ativos": int(ativos), "total_investido": round(total_investido, 2)}
