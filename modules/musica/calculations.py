"""Regras de negócio do módulo Música: agregações sobre escutas e álbuns.
Sem acesso direto a SQL — usa models.py.
"""

from datetime import date

import pandas as pd

import models
import utils


def nota_media_album(album_id: int) -> float | None:
    """Média das notas registradas nas escutas desse álbum (ignora escutas
    sem nota). None se não há nenhuma nota ainda."""
    escutas = models.listar_escutas(album_id)
    notas = escutas["nota"].dropna()
    if notas.empty:
        return None
    return round(notas.mean(), 2)


def total_escutas_album(album_id: int) -> int:
    return len(models.listar_escutas(album_id))


def resumo_geral() -> dict:
    """Números curtos para o topo das páginas: quantos álbuns, quantas
    escutas ao todo, e a nota média geral."""
    albuns = models.listar_albuns()
    escutas = models.listar_escutas_com_album()

    nota_media_geral = None
    if not escutas.empty:
        notas = escutas["nota"].dropna()
        if not notas.empty:
            nota_media_geral = round(notas.mean(), 2)

    return {
        "total_albuns": len(albuns),
        "total_escutas": len(escutas),
        "nota_media_geral": nota_media_geral,
    }


def _filtrar_periodo(escutas: pd.DataFrame, data_inicio: str, data_fim: str) -> pd.DataFrame:
    if escutas.empty:
        return escutas
    return escutas[(escutas["data"] >= data_inicio) & (escutas["data"] <= data_fim)]


def escutas_por_mes(data_inicio: str, data_fim: str) -> pd.DataFrame:
    """Contagem de escutas por mês dentro do período — inclui meses sem
    nenhuma escuta (total 0), pra não sumir com o eixo do gráfico."""
    inicio = date.fromisoformat(data_inicio)
    fim = date.fromisoformat(data_fim)
    periodos = []
    cursor = date(inicio.year, inicio.month, 1)
    while cursor <= fim:
        periodos.append(cursor.strftime("%Y-%m"))
        cursor = utils.somar_meses(cursor, 1)

    escutas = _filtrar_periodo(models.listar_escutas_com_album(), data_inicio, data_fim)
    contagem_por_periodo = {}
    if not escutas.empty:
        periodo_da_escuta = escutas["data"].str.slice(0, 7)
        contagem_por_periodo = periodo_da_escuta.value_counts().to_dict()

    return pd.DataFrame({
        "periodo": periodos,
        "mes_nome": [utils.nome_mes_curto(p) for p in periodos],
        "total": [int(contagem_por_periodo.get(p, 0)) for p in periodos],
    })


def distribuicao_notas(data_inicio: str, data_fim: str) -> pd.DataFrame:
    """Quantas escutas caíram em cada nota possível (0.5 a 5.0), dentro do período."""
    escutas = _filtrar_periodo(models.listar_escutas_com_album(), data_inicio, data_fim)
    notas_validas = escutas["nota"].dropna() if not escutas.empty else pd.Series(dtype=float)
    contagem = notas_validas.value_counts().to_dict()

    return pd.DataFrame({
        "nota": utils.OPCOES_NOTA,
        "total": [int(contagem.get(n, 0)) for n in utils.OPCOES_NOTA],
    })


def top_artistas(data_inicio: str, data_fim: str, limit: int = 8) -> pd.DataFrame:
    """Artistas com mais escutas registradas dentro do período (não álbuns
    distintos — um artista ouvido muitas vezes no mesmo álbum ainda conta
    bastante)."""
    escutas = _filtrar_periodo(models.listar_escutas_com_album(), data_inicio, data_fim)
    if escutas.empty:
        return pd.DataFrame(columns=["artista_nome", "total"])
    contagem = escutas.groupby("artista_nome").size().reset_index(name="total")
    return contagem.sort_values("total", ascending=False).head(limit)


def top_albuns_periodo(data_inicio: str, data_fim: str, limite: int) -> pd.DataFrame:
    """Álbuns mais escutados no período [data_inicio, data_fim] (ISO,
    ambos inclusive), rankeados por número de escutas — pra colagem."""
    colunas = ["album_id", "album_nome", "artista_nome", "capa_path", "total"]
    escutas = _filtrar_periodo(models.listar_escutas_com_album(), data_inicio, data_fim)
    if escutas.empty:
        return pd.DataFrame(columns=colunas)

    agrupado = (
        escutas.groupby(["album_id", "album_nome", "artista_nome", "capa_path"])
        .size()
        .reset_index(name="total")
        .sort_values("total", ascending=False)
    )
    return agrupado.head(limite)


def resumo_periodo(data_inicio: str, data_fim: str) -> dict:
    """Números do período: álbuns novos no catálogo, escutas registradas,
    nota média e o artista mais escutado dentro dele."""
    escutas = _filtrar_periodo(models.listar_escutas_com_album(), data_inicio, data_fim)

    albuns = models.listar_albuns()
    albuns_periodo = pd.DataFrame()
    if not albuns.empty:
        criado_em = albuns["created_at"].str.slice(0, 10)
        albuns_periodo = albuns[(criado_em >= data_inicio) & (criado_em <= data_fim)]

    nota_media = None
    artista_destaque = None
    if not escutas.empty:
        notas = escutas["nota"].dropna()
        if not notas.empty:
            nota_media = round(notas.mean(), 2)
        top = escutas.groupby("artista_nome").size().sort_values(ascending=False)
        if not top.empty:
            artista_destaque = top.index[0]

    return {
        "albuns_novos": len(albuns_periodo),
        "escutas": len(escutas),
        "nota_media": nota_media,
        "artista_destaque": artista_destaque,
    }
