"""Regras de negócio do módulo Livros: agregações sobre leituras e livros.

Port de modules/livros/calculations.py — verbatim (sem dependência de
Streamlit no original).
"""

from datetime import date

import pandas as pd

from . import repo as models
from . import utils


def nota_media_livro(livro_id: int) -> float | None:
    leituras = models.listar_leituras(livro_id)
    notas = leituras["nota"].dropna()
    if notas.empty:
        return None
    return round(notas.mean(), 2)


def total_leituras_livro(livro_id: int) -> int:
    return len(models.listar_leituras(livro_id))


def status_atual_livro(livro_id: int) -> str:
    leituras = models.listar_leituras(livro_id)
    if leituras.empty:
        return "Não iniciado"
    return leituras.iloc[0]["status"]


def status_por_livro() -> dict[int, str]:
    leituras = models.listar_leituras_com_livro()
    if leituras.empty:
        return {}
    mais_recente = leituras.sort_values(["livro_id", "data", "id"]).groupby("livro_id").tail(1)
    return dict(zip(mais_recente["livro_id"], mais_recente["status"]))


def resumo_geral() -> dict:
    livros = models.listar_livros()
    leituras = models.listar_leituras_com_livro()

    nota_media_geral = None
    if not leituras.empty:
        notas = leituras["nota"].dropna()
        if not notas.empty:
            nota_media_geral = round(notas.mean(), 2)

    return {
        "total_livros": len(livros),
        "total_leituras": len(leituras),
        "nota_media_geral": nota_media_geral,
    }


def _filtrar_periodo(leituras: pd.DataFrame, data_inicio: str, data_fim: str) -> pd.DataFrame:
    if leituras.empty:
        return leituras
    return leituras[(leituras["data"] >= data_inicio) & (leituras["data"] <= data_fim)]


def livros_concluidos_por_mes(data_inicio: str, data_fim: str) -> pd.DataFrame:
    inicio = date.fromisoformat(data_inicio)
    fim = date.fromisoformat(data_fim)
    periodos = []
    cursor = date(inicio.year, inicio.month, 1)
    while cursor <= fim:
        periodos.append(cursor.strftime("%Y-%m"))
        cursor = utils.somar_meses(cursor, 1)

    leituras = _filtrar_periodo(models.listar_leituras_com_livro(), data_inicio, data_fim)
    concluidos = leituras[leituras["status"] == "Concluído"] if not leituras.empty else leituras
    contagem_por_periodo = {}
    if not concluidos.empty:
        periodo_da_leitura = concluidos["data"].str.slice(0, 7)
        contagem_por_periodo = periodo_da_leitura.value_counts().to_dict()

    return pd.DataFrame({
        "periodo": periodos,
        "mes_nome": [utils.nome_mes_curto(p) for p in periodos],
        "total": [int(contagem_por_periodo.get(p, 0)) for p in periodos],
    })


def distribuicao_notas(data_inicio: str, data_fim: str) -> pd.DataFrame:
    leituras = _filtrar_periodo(models.listar_leituras_com_livro(), data_inicio, data_fim)
    notas_validas = leituras["nota"].dropna() if not leituras.empty else pd.Series(dtype=float)
    contagem = notas_validas.value_counts().to_dict()

    return pd.DataFrame({
        "nota": utils.OPCOES_NOTA,
        "total": [int(contagem.get(n, 0)) for n in utils.OPCOES_NOTA],
    })


def top_autores(data_inicio: str, data_fim: str, limit: int = 8) -> pd.DataFrame:
    leituras = _filtrar_periodo(models.listar_leituras_com_livro(), data_inicio, data_fim)
    if leituras.empty:
        return pd.DataFrame(columns=["autor_nome", "total"])
    contagem = leituras.groupby("autor_nome").size().reset_index(name="total")
    return contagem.sort_values("total", ascending=False).head(limit)


def resumo_periodo(data_inicio: str, data_fim: str) -> dict:
    leituras = _filtrar_periodo(models.listar_leituras_com_livro(), data_inicio, data_fim)
    concluidos = leituras[leituras["status"] == "Concluído"] if not leituras.empty else leituras

    nota_media = None
    autor_destaque = None
    if not leituras.empty:
        notas = leituras["nota"].dropna()
        if not notas.empty:
            nota_media = round(notas.mean(), 2)
        top = leituras.groupby("autor_nome").size().sort_values(ascending=False)
        if not top.empty:
            autor_destaque = top.index[0]

    return {
        "livros_concluidos": len(concluidos),
        "leituras": len(leituras),
        "nota_media": nota_media,
        "autor_destaque": autor_destaque,
    }
