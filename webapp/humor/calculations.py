"""Regras de negócio do módulo humor: agregações sobre os registros. Port
~verbatim de modules/humor/calculations.py (já não usa streamlit)."""

from collections import Counter
from datetime import date, timedelta

import pandas as pd

from . import repo, utils


def resumo_geral(hoje: date | None = None) -> dict:
    """Números curtos pro topo da página: quantos registros, nota média
    geral e nota média dos últimos 7 dias."""
    hoje = hoje or date.today()
    registros = repo.listar_registros()
    if registros.empty:
        return {"total_registros": 0, "nota_media_geral": None, "nota_media_7d": None}

    inicio_7d = (hoje - timedelta(days=6)).isoformat()
    ultimos_7d = registros[registros["data"] >= inicio_7d]

    return {
        "total_registros": len(registros),
        "nota_media_geral": round(registros["nota"].mean(), 1),
        "nota_media_7d": round(ultimos_7d["nota"].mean(), 1) if not ultimos_7d.empty else None,
    }


def evolucao_diaria(dias: int = 60, hoje: date | None = None) -> pd.DataFrame:
    """Nota média por dia (todos os dias do período, mesmo sem registro) +
    média móvel de 7 dias."""
    hoje = hoje or date.today()
    inicio = hoje - timedelta(days=dias)
    todas_datas = pd.date_range(inicio, hoje, freq="D")

    registros = repo.listar_registros(data_inicio=inicio.isoformat())
    if registros.empty:
        diario = pd.DataFrame({"data": todas_datas, "nota": pd.NA})
    else:
        media_por_dia = registros.groupby("data")["nota"].mean()
        media_por_dia.index = pd.to_datetime(media_por_dia.index)
        diario = media_por_dia.reindex(todas_datas).rename_axis("data").reset_index(name="nota")

    diario["media_movel_7d"] = diario["nota"].rolling(7, min_periods=1).mean()
    return diario


def registros_periodo(data_inicio: str, data_fim: str) -> pd.DataFrame:
    """Registros individuais do período com um datetime combinado
    (data+hora), ordenados cronologicamente — preserva a granularidade
    intradiária (múltiplos registros no mesmo dia viram pontos separados)."""
    registros = repo.listar_registros(data_inicio, data_fim)
    if registros.empty:
        return pd.DataFrame(columns=["id", "datetime", "nota", "tags", "nota_livre"])

    registros = registros.copy()
    hora_valida = registros["hora"].where(registros["hora"].str.match(r"^\d{2}:\d{2}$"), "00:00")
    registros["datetime"] = pd.to_datetime(
        registros["data"] + " " + hora_valida, format="%Y-%m-%d %H:%M", errors="coerce",
    )
    registros["datetime"] = registros["datetime"].fillna(pd.to_datetime(registros["data"]))
    return registros.sort_values("datetime")[["id", "datetime", "nota", "tags", "nota_livre"]].reset_index(drop=True)


def resumo_periodo(data_inicio: str, data_fim: str) -> dict:
    """Números do período pro relatório: quantos registros, nota média e a
    tag mais frequente."""
    registros = repo.listar_registros(data_inicio, data_fim)
    if registros.empty:
        return {"total_registros": 0, "nota_media": None, "tag_destaque": None}

    tags = tags_mais_frequentes(data_inicio, data_fim)
    return {
        "total_registros": len(registros),
        "nota_media": round(registros["nota"].mean(), 1),
        "tag_destaque": tags.iloc[0]["tag"] if not tags.empty else None,
    }


def veredito_humor(nota_media: float | None) -> str:
    """Frase curta de fechamento pro relatório, na escala nativa 1-10."""
    if nota_media is None:
        return "Sem registros suficientes pra avaliar o período."
    if nota_media >= 8:
        return "Período muito positivo — humor consistentemente alto."
    if nota_media >= 6:
        return "Período bom, com humor estável na maior parte do tempo."
    if nota_media >= 4:
        return "Período misto — valeria olhar as tags mais frequentes pra entender o porquê."
    return "Período difícil — talvez valha conversar com alguém sobre o que pesou."


def tags_mais_frequentes(data_inicio: str | None = None, data_fim: str | None = None) -> pd.DataFrame:
    """Contagem de cada tag usada no período, ordenada da mais pra menos
    frequente."""
    registros = repo.listar_registros(data_inicio, data_fim)
    if registros.empty:
        return pd.DataFrame(columns=["tag", "total"])

    contador = Counter()
    for tags_texto in registros["tags"]:
        contador.update(utils.texto_para_tags(tags_texto))

    if not contador:
        return pd.DataFrame(columns=["tag", "total"])

    df = pd.DataFrame(contador.items(), columns=["tag", "total"])
    return df.sort_values("total", ascending=False).reset_index(drop=True)
