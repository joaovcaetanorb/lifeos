"""Regras de negócio do módulo revisão — sem SQL aqui (ver repo.py). A
comparação com a semana anterior reaproveita o motor de cruzamento do
Analytics em vez de duplicar lógica (mesmo padrão de import direto entre
módulos usado em webapp/beatforge/router.py)."""

from datetime import date, timedelta

from analytics import calculations as analytics_calc


def periodo_anterior(data_inicio: str, data_fim: str) -> tuple[str, str]:
    """Desloca o período pra trás pelo próprio tamanho dele, pra comparar
    semanas (ou qualquer intervalo) de tamanho igual lado a lado."""
    inicio = date.fromisoformat(data_inicio)
    fim = date.fromisoformat(data_fim)
    dias = (fim - inicio).days + 1
    inicio_anterior = inicio - timedelta(days=dias)
    fim_anterior = fim - timedelta(days=dias)
    return inicio_anterior.isoformat(), fim_anterior.isoformat()


def resumo_com_comparacao(data_inicio: str, data_fim: str) -> dict:
    inicio_anterior, fim_anterior = periodo_anterior(data_inicio, data_fim)
    return {
        "periodo": {"inicio": data_inicio, "fim": data_fim},
        "periodo_anterior": {"inicio": inicio_anterior, "fim": fim_anterior},
        "atual": analytics_calc.resumo_modulos(data_inicio, data_fim),
        "anterior": analytics_calc.resumo_modulos(inicio_anterior, fim_anterior),
        "correlacoes": analytics_calc.correlacoes(data_inicio, data_fim),
    }
