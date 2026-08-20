"""Regras de negócio do módulo Beat Forge. Sem SQL aqui — ver repo.py."""

from datetime import date, timedelta

import pandas as pd

from . import repo as models

STATUS_PIPELINE = ["Lixeira", "Loop Eterno", "Estrutura Montada", "Mixagem Crua", "Pronto para Master"]

TECNICAS_DISPONIVEIS = [
    "Micro-chopp", "Macro-chopp", "Pitch Shift", "Time Stretch",
    "Granular", "Reverse", "Sidechain Pumping", "Saturação Pesada",
]


def ultimo_passo_brutal(beat_id: int, sessoes: pd.DataFrame | None = None) -> str | None:
    """listar_sessoes() já vem ordenado por data DESC, id DESC — a primeira
    linha é a sessão mais recente desse beat."""
    if sessoes is None:
        sessoes = models.listar_sessoes(beat_id)
    if sessoes.empty:
        return None
    return sessoes.iloc[0]["proximo_passo_brutal"]


def tempo_total_investido(beat_id: int, sessoes: pd.DataFrame | None = None) -> int:
    if sessoes is None:
        sessoes = models.listar_sessoes(beat_id)
    if sessoes.empty:
        return 0
    return int(sessoes["duracao_minutos"].sum())


def tempo_total_investido_geral(mes: str | None = None, sessoes: pd.DataFrame | None = None) -> int:
    """`mes` no formato YYYY-MM, opcional."""
    if sessoes is None:
        sessoes = models.listar_sessoes_todas()
    if sessoes.empty:
        return 0
    if mes:
        sessoes = sessoes[sessoes["data"].str.startswith(mes)]
    if sessoes.empty:
        return 0
    return int(sessoes["duracao_minutos"].sum())


def dias_com_sessao(sessoes: pd.DataFrame | None = None) -> set[str]:
    if sessoes is None:
        sessoes = models.listar_sessoes_todas()
    if sessoes.empty:
        return set()
    return set(sessoes["data"])


def streak_atual(hoje: date | None = None, sessoes: pd.DataFrame | None = None) -> int:
    """Dias consecutivos com pelo menos uma sessão registrada, em qualquer
    beat — o sinal "beat-a-day". Mesma lógica de webapp/habitos/calculations.py::streak_atual."""
    hoje = hoje or date.today()
    datas_marcadas = dias_com_sessao(sessoes)
    if not datas_marcadas:
        return 0

    cursor = hoje
    if hoje.isoformat() not in datas_marcadas:
        cursor = hoje - timedelta(days=1)

    streak = 0
    while cursor.isoformat() in datas_marcadas:
        streak += 1
        cursor -= timedelta(days=1)
    return streak


def resumo_geral(hoje: date | None = None) -> dict:
    hoje = hoje or date.today()
    beats = models.listar_beats()
    sessoes = models.listar_sessoes_todas()
    crate_novos = models.listar_crate(status="novo")

    por_status = {status: 0 for status in STATUS_PIPELINE}
    if not beats.empty:
        for status, contagem in beats["status"].value_counts().items():
            por_status[status] = int(contagem)

    return {
        "total_beats": int(len(beats)),
        "por_status": por_status,
        "tempo_investido_mes_min": tempo_total_investido_geral(hoje.strftime("%Y-%m"), sessoes),
        "streak_dias": streak_atual(hoje, sessoes),
        "crate_novos": int(len(crate_novos)),
    }
