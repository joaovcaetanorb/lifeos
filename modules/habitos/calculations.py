"""Regras de negócio do módulo Hábitos: streak, percentual cumprido e
resumo geral. Sem acesso direto a SQL — usa models.py.
"""

from datetime import date, timedelta

import pandas as pd

import models


def streak_atual(habito_id: int, hoje: date | None = None) -> int:
    """Quantos dias seguidos (terminando hoje ou ontem) o hábito foi
    cumprido. Se hoje ainda não foi marcado, conta a partir de ontem — só
    quebra a streak à meia-noite, não no instante em que o dia começa."""
    hoje = hoje or date.today()
    registros = models.listar_registros(habito_id)
    if registros.empty:
        return 0
    datas_marcadas = set(registros["data"])

    cursor = hoje
    if hoje.isoformat() not in datas_marcadas:
        cursor = hoje - timedelta(days=1)

    streak = 0
    while cursor.isoformat() in datas_marcadas:
        streak += 1
        cursor -= timedelta(days=1)
    return streak


def percentual_cumprido(habito_id: int, dias: int = 30, hoje: date | None = None) -> float:
    """% de dias cumpridos nos últimos N dias (incluindo hoje)."""
    hoje = hoje or date.today()
    inicio = hoje - timedelta(days=dias - 1)
    registros = models.listar_registros(habito_id, data_inicio=inicio.isoformat())
    if dias <= 0:
        return 0.0
    return round(len(registros) / dias * 100, 1)


def resumo_habito(habito_id: int, hoje: date | None = None) -> dict:
    hoje = hoje or date.today()
    return {
        "streak": streak_atual(habito_id, hoje),
        "percentual_30d": percentual_cumprido(habito_id, 30, hoje),
        "feito_hoje": models.esta_marcado(habito_id, hoje.isoformat()),
    }


def resumo_geral(hoje: date | None = None) -> dict:
    """Números curtos para o topo da página: quantos hábitos ativos e a
    média de cumprimento (últimos 30 dias) entre eles."""
    hoje = hoje or date.today()
    habitos = models.listar_habitos()
    if habitos.empty:
        return {"ativos": 0, "percentual_medio": None}

    percentuais = [percentual_cumprido(int(hid), 30, hoje) for hid in habitos["id"]]
    return {
        "ativos": int(len(habitos)),
        "percentual_medio": round(sum(percentuais) / len(percentuais), 1),
    }


def progresso_por_habito(dias: int = 30, hoje: date | None = None) -> pd.DataFrame:
    """% cumprido (últimos N dias) de cada hábito ativo, para gráfico."""
    hoje = hoje or date.today()
    habitos = models.listar_habitos()
    if habitos.empty:
        return pd.DataFrame(columns=["nome", "percentual"])

    linhas = [
        {"nome": h["nome"], "percentual": percentual_cumprido(int(h["id"]), dias, hoje)}
        for _, h in habitos.iterrows()
    ]
    return pd.DataFrame(linhas).sort_values("percentual", ascending=True)


def evolucao_semanal(n_semanas: int = 8, hoje: date | None = None) -> pd.DataFrame:
    """% médio de cumprimento (entre todos os hábitos ativos) por semana,
    últimas N semanas — para gráfico de evolução."""
    hoje = hoje or date.today()
    habitos = models.listar_habitos()
    if habitos.empty:
        return pd.DataFrame(columns=["semana", "percentual"])

    registros = models.listar_registros_todos(
        data_inicio=(hoje - timedelta(weeks=n_semanas)).isoformat()
    )
    total_habitos = len(habitos)

    linhas = []
    for i in range(n_semanas - 1, -1, -1):
        fim_semana = hoje - timedelta(days=7 * i)
        inicio_semana = fim_semana - timedelta(days=6)
        if registros.empty:
            marcados = 0
        else:
            na_semana = registros[
                (registros["data"] >= inicio_semana.isoformat())
                & (registros["data"] <= fim_semana.isoformat())
            ]
            marcados = len(na_semana)
        maximo_possivel = total_habitos * 7
        percentual = round(marcados / maximo_possivel * 100, 1) if maximo_possivel else 0.0
        linhas.append({
            "semana": f"{inicio_semana.strftime('%d/%m')}",
            "percentual": percentual,
        })
    return pd.DataFrame(linhas)


# ---------------------------------------------------------------------------
# Nota do período (veredito para o relatório em PDF)
# ---------------------------------------------------------------------------

def melhor_streak_geral(hoje: date | None = None) -> tuple[str, int] | None:
    """Hábito ativo com a maior streak atual, e o valor dela. None se não
    há nenhum hábito cadastrado."""
    hoje = hoje or date.today()
    habitos = models.listar_habitos()
    if habitos.empty:
        return None
    streaks = [(h["nome"], streak_atual(int(h["id"]), hoje)) for _, h in habitos.iterrows()]
    return max(streaks, key=lambda item: item[1])


def nota_periodo(dias: int = 30, hoje: date | None = None) -> dict:
    """Nota de 0 a 10 pro período, com detalhamento transparente (nunca um
    número mágico sem explicação). Baseada no cumprimento médio entre os
    hábitos ativos nos últimos `dias` dias."""
    hoje = hoje or date.today()
    resumo = resumo_geral(hoje)

    if resumo["ativos"] == 0 or resumo["percentual_medio"] is None:
        return {"nota": 0.0, "veredito": "Cadastre um hábito pra começar a acompanhar.", "detalhes": []}

    nota = round(resumo["percentual_medio"] / 10, 1)
    detalhes = [f"Cumprimento médio de {resumo['percentual_medio']:.0f}% nos últimos {dias} dias."]

    df = progresso_por_habito(dias, hoje)
    if len(df) > 1:
        melhor, pior = df.iloc[-1], df.iloc[0]
        detalhes.append(f"Melhor: {melhor['nome']} ({melhor['percentual']:.0f}%).")
        detalhes.append(f"Precisa de atenção: {pior['nome']} ({pior['percentual']:.0f}%).")

    melhor_streak = melhor_streak_geral(hoje)
    if melhor_streak and melhor_streak[1] > 0:
        detalhes.append(f"Maior streak ativa: {melhor_streak[0]} ({melhor_streak[1]} dia(s)).")

    if nota >= 9:
        veredito = "Rotina exemplar — consistência quase perfeita."
    elif nota >= 7:
        veredito = "Rotina sob controle."
    elif nota >= 5:
        veredito = "Rotina ok, mas dá pra apertar em alguns hábitos."
    elif nota >= 3:
        veredito = "Rotina irregular — vale revisar o que está atrapalhando."
    else:
        veredito = "Rotina difícil no período — talvez seja hora de repensar quais hábitos valem o esforço agora."

    return {"nota": nota, "veredito": veredito, "detalhes": detalhes}
