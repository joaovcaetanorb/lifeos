"""Regras de negócio do módulo Hábitos. Port de modules/habitos/calculations.py
— verbatim (o original já não tinha dependência de Streamlit)."""

from datetime import date, timedelta

import pandas as pd

from . import repo as models
from . import utils


def buscar_habitos(somente_ativos: bool = True) -> pd.DataFrame:
    return models.listar_habitos(somente_ativos)


def buscar_registros_todos() -> pd.DataFrame:
    return models.listar_registros_todos()


def _habitos_ou_buscar(habitos: pd.DataFrame | None) -> pd.DataFrame:
    return models.listar_habitos() if habitos is None else habitos


def _registros_do_habito(habito_id: int, registros: pd.DataFrame | None) -> pd.DataFrame:
    if registros is None:
        return models.listar_registros(habito_id)
    if registros.empty:
        return registros
    return registros[registros["habito_id"] == habito_id]


def streak_atual(habito_id: int, hoje: date | None = None, registros: pd.DataFrame | None = None) -> int:
    hoje = hoje or date.today()
    do_habito = _registros_do_habito(habito_id, registros)
    if do_habito.empty:
        return 0
    datas_marcadas = set(do_habito["data"])

    cursor = hoje
    if hoje.isoformat() not in datas_marcadas:
        cursor = hoje - timedelta(days=1)

    streak = 0
    while cursor.isoformat() in datas_marcadas:
        streak += 1
        cursor -= timedelta(days=1)
    return streak


def percentual_cumprido(
    habito_id: int, dias: int = 30, hoje: date | None = None, registros: pd.DataFrame | None = None,
) -> float:
    if dias <= 0:
        return 0.0
    hoje = hoje or date.today()
    inicio = hoje - timedelta(days=dias - 1)
    do_habito = _registros_do_habito(habito_id, registros)
    if not do_habito.empty:
        do_habito = do_habito[do_habito["data"] >= inicio.isoformat()]
    return round(len(do_habito) / dias * 100, 1)


def esta_marcado_hoje(habito_id: int, hoje: date, registros: pd.DataFrame | None) -> bool:
    if registros is None:
        return models.esta_marcado(habito_id, hoje.isoformat())
    do_habito = _registros_do_habito(habito_id, registros)
    return hoje.isoformat() in set(do_habito["data"]) if not do_habito.empty else False


def resumo_habito(habito_id: int, hoje: date | None = None, registros: pd.DataFrame | None = None) -> dict:
    hoje = hoje or date.today()
    return {
        "streak": streak_atual(habito_id, hoje, registros),
        "percentual_30d": percentual_cumprido(habito_id, 30, hoje, registros),
        "feito_hoje": esta_marcado_hoje(habito_id, hoje, registros),
    }


def resumo_geral(
    hoje: date | None = None, registros: pd.DataFrame | None = None, habitos: pd.DataFrame | None = None,
) -> dict:
    hoje = hoje or date.today()
    habitos = _habitos_ou_buscar(habitos)
    if habitos.empty:
        return {"ativos": 0, "percentual_medio": None}

    percentuais = [percentual_cumprido(int(hid), 30, hoje, registros) for hid in habitos["id"]]
    return {
        "ativos": int(len(habitos)),
        "percentual_medio": round(sum(percentuais) / len(percentuais), 1),
    }


def progresso_por_habito(
    dias: int = 30, hoje: date | None = None,
    registros: pd.DataFrame | None = None, habitos: pd.DataFrame | None = None,
) -> pd.DataFrame:
    hoje = hoje or date.today()
    habitos = _habitos_ou_buscar(habitos)
    if habitos.empty:
        return pd.DataFrame(columns=["nome", "percentual"])

    linhas = [
        {"nome": h["nome"], "percentual": percentual_cumprido(int(h["id"]), dias, hoje, registros)}
        for _, h in habitos.iterrows()
    ]
    return pd.DataFrame(linhas).sort_values("percentual", ascending=True)


def percentual_periodo(
    habito_id: int, data_inicio: str, data_fim: str, registros: pd.DataFrame | None = None,
) -> float:
    total_dias = (date.fromisoformat(data_fim) - date.fromisoformat(data_inicio)).days + 1
    if total_dias <= 0:
        return 0.0
    do_habito = _registros_do_habito(habito_id, registros)
    if registros is None:
        do_habito = models.listar_registros(habito_id, data_inicio=data_inicio, data_fim=data_fim)
    elif not do_habito.empty:
        do_habito = do_habito[(do_habito["data"] >= data_inicio) & (do_habito["data"] <= data_fim)]
    return round(len(do_habito) / total_dias * 100, 1)


def progresso_por_habito_periodo(
    data_inicio: str, data_fim: str,
    registros: pd.DataFrame | None = None, habitos: pd.DataFrame | None = None,
) -> pd.DataFrame:
    habitos = _habitos_ou_buscar(habitos)
    if habitos.empty:
        return pd.DataFrame(columns=["nome", "percentual"])

    linhas = [
        {"nome": h["nome"], "percentual": percentual_periodo(int(h["id"]), data_inicio, data_fim, registros)}
        for _, h in habitos.iterrows()
    ]
    return pd.DataFrame(linhas).sort_values("percentual", ascending=True)


def evolucao_semanal(
    n_semanas: int = 8, hoje: date | None = None,
    registros: pd.DataFrame | None = None, habitos: pd.DataFrame | None = None,
) -> pd.DataFrame:
    hoje = hoje or date.today()
    habitos = _habitos_ou_buscar(habitos)
    if habitos.empty:
        return pd.DataFrame(columns=["semana", "percentual"])
    total_habitos = len(habitos)

    inicio = (hoje - timedelta(weeks=n_semanas)).isoformat()
    if registros is None:
        registros = models.listar_registros_todos(data_inicio=inicio)
    elif not registros.empty:
        registros = registros[registros["data"] >= inicio]

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
        linhas.append({"semana": f"{inicio_semana.strftime('%d/%m')}", "percentual": percentual})
    return pd.DataFrame(linhas)


def heatmap_diario(
    dias: int = 182, hoje: date | None = None,
    registros: pd.DataFrame | None = None, habitos: pd.DataFrame | None = None,
) -> pd.DataFrame:
    hoje = hoje or date.today()
    inicio = hoje - timedelta(days=dias - 1)
    todas_datas = pd.date_range(inicio, hoje, freq="D")

    habitos = _habitos_ou_buscar(habitos)
    total_habitos = len(habitos)
    if total_habitos == 0:
        return pd.DataFrame({"data": todas_datas, "percentual": 0.0, "nomes": ""})

    if registros is None:
        registros = models.listar_registros_todos(data_inicio=inicio.isoformat())
    elif not registros.empty:
        registros = registros[registros["data"] >= inicio.isoformat()]

    if registros.empty:
        contagem_por_dia = pd.Series(dtype=int)
        nomes_por_dia = pd.Series(dtype=object)
    else:
        contagem_por_dia = registros.groupby("data").size()
        contagem_por_dia.index = pd.to_datetime(contagem_por_dia.index)
        nomes_por_dia = registros.groupby("data")["habito_nome"].apply(lambda s: ", ".join(s))
        nomes_por_dia.index = pd.to_datetime(nomes_por_dia.index)

    contagem = contagem_por_dia.reindex(todas_datas, fill_value=0)
    percentual = (contagem / total_habitos * 100).clip(upper=100)
    nomes = nomes_por_dia.reindex(todas_datas, fill_value="")
    return pd.DataFrame({"data": todas_datas, "percentual": percentual.values, "nomes": nomes.values})


def cumprimento_por_mes(
    data_inicio: str, data_fim: str,
    registros: pd.DataFrame | None = None, habitos: pd.DataFrame | None = None,
) -> pd.DataFrame:
    inicio = date.fromisoformat(data_inicio)
    fim = date.fromisoformat(data_fim)
    habitos = _habitos_ou_buscar(habitos)
    if habitos.empty:
        return pd.DataFrame(columns=["periodo", "mes_nome", "percentual"])
    total_habitos = len(habitos)

    if registros is None:
        registros = models.listar_registros_todos(data_inicio=data_inicio, data_fim=data_fim)
    elif not registros.empty:
        registros = registros[(registros["data"] >= data_inicio) & (registros["data"] <= data_fim)]

    linhas = []
    cursor = date(inicio.year, inicio.month, 1)
    while cursor <= fim:
        periodo = cursor.strftime("%Y-%m")
        mes_inicio = max(cursor, inicio)
        ultimo_dia_mes = utils.somar_meses(cursor, 1) - timedelta(days=1)
        mes_fim = min(ultimo_dia_mes, fim)
        dias_no_periodo = (mes_fim - mes_inicio).days + 1

        if registros.empty:
            marcados = 0
        else:
            no_mes = registros[
                (registros["data"] >= mes_inicio.isoformat()) & (registros["data"] <= mes_fim.isoformat())
            ]
            marcados = len(no_mes)
        maximo_possivel = total_habitos * dias_no_periodo
        percentual = round(marcados / maximo_possivel * 100, 1) if maximo_possivel else 0.0
        linhas.append({"periodo": periodo, "mes_nome": utils.nome_mes_curto(periodo), "percentual": percentual})
        cursor = utils.somar_meses(cursor, 1)

    return pd.DataFrame(linhas)


def melhor_streak_geral(
    hoje: date | None = None, registros: pd.DataFrame | None = None, habitos: pd.DataFrame | None = None,
) -> tuple[str, int] | None:
    hoje = hoje or date.today()
    habitos = _habitos_ou_buscar(habitos)
    if habitos.empty:
        return None
    streaks = [(h["nome"], streak_atual(int(h["id"]), hoje, registros)) for _, h in habitos.iterrows()]
    return max(streaks, key=lambda item: item[1])


def nota_periodo(
    dias: int = 30, hoje: date | None = None,
    registros: pd.DataFrame | None = None, habitos: pd.DataFrame | None = None,
) -> dict:
    hoje = hoje or date.today()
    if registros is None:
        registros = buscar_registros_todos()
    if habitos is None:
        habitos = buscar_habitos()
    resumo = resumo_geral(hoje, registros, habitos)

    if resumo["ativos"] == 0 or resumo["percentual_medio"] is None:
        return {"nota": 0.0, "veredito": "Cadastre um hábito pra começar a acompanhar.", "detalhes": []}

    nota = round(resumo["percentual_medio"] / 10, 1)
    detalhes = [f"Cumprimento médio de {resumo['percentual_medio']:.0f}% nos últimos {dias} dias."]

    df = progresso_por_habito(dias, hoje, registros, habitos)
    if len(df) > 1:
        melhor, pior = df.iloc[-1], df.iloc[0]
        detalhes.append(f"Melhor: {melhor['nome']} ({melhor['percentual']:.0f}%).")
        detalhes.append(f"Precisa de atenção: {pior['nome']} ({pior['percentual']:.0f}%).")

    melhor_streak = melhor_streak_geral(hoje, registros, habitos)
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
