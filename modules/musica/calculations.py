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


def escutas_por_mes(meses: int = 12) -> pd.DataFrame:
    """Contagem de escutas por mês nos últimos N meses — inclui meses sem
    nenhuma escuta (com total 0), pra não sumir com o eixo do gráfico."""
    hoje = date.today()
    periodos = [utils.somar_meses(hoje, -i).strftime("%Y-%m") for i in range(meses - 1, -1, -1)]

    escutas = models.listar_escutas_com_album()
    contagem_por_periodo = {}
    if not escutas.empty:
        periodo_da_escuta = escutas["data"].str.slice(0, 7)
        contagem_por_periodo = periodo_da_escuta.value_counts().to_dict()

    return pd.DataFrame({
        "periodo": periodos,
        "mes_nome": [utils.nome_mes_curto(p) for p in periodos],
        "total": [int(contagem_por_periodo.get(p, 0)) for p in periodos],
    })


def distribuicao_notas() -> pd.DataFrame:
    """Quantas escutas caíram em cada nota possível (0.5 a 5.0)."""
    escutas = models.listar_escutas_com_album()
    notas_validas = escutas["nota"].dropna() if not escutas.empty else pd.Series(dtype=float)
    contagem = notas_validas.value_counts().to_dict()

    return pd.DataFrame({
        "nota": utils.OPCOES_NOTA,
        "total": [int(contagem.get(n, 0)) for n in utils.OPCOES_NOTA],
    })


def top_artistas(limit: int = 8) -> pd.DataFrame:
    """Artistas com mais escutas registradas (não álbuns distintos — um
    artista ouvido muitas vezes no mesmo álbum ainda conta bastante)."""
    escutas = models.listar_escutas_com_album()
    if escutas.empty:
        return pd.DataFrame(columns=["artista_nome", "total"])
    contagem = escutas.groupby("artista_nome").size().reset_index(name="total")
    return contagem.sort_values("total", ascending=False).head(limit)


def top_albuns_periodo(data_inicio: str, data_fim: str, limite: int) -> pd.DataFrame:
    """Álbuns mais escutados no período [data_inicio, data_fim] (ISO,
    ambos inclusive), rankeados por número de escutas — pra colagem."""
    colunas = ["album_id", "album_nome", "artista_nome", "capa_path", "total"]
    escutas = models.listar_escutas_com_album()
    if escutas.empty:
        return pd.DataFrame(columns=colunas)

    no_periodo = escutas[(escutas["data"] >= data_inicio) & (escutas["data"] <= data_fim)]
    if no_periodo.empty:
        return pd.DataFrame(columns=colunas)

    agrupado = (
        no_periodo.groupby(["album_id", "album_nome", "artista_nome", "capa_path"])
        .size()
        .reset_index(name="total")
        .sort_values("total", ascending=False)
    )
    return agrupado.head(limite)


def resumo_ano_atual(ano: int | None = None) -> dict:
    """Números do ano corrente: álbuns novos no catálogo, escutas
    registradas, nota média do ano e o artista mais escutado no período."""
    ano = ano or date.today().year
    prefixo = str(ano)

    escutas = models.listar_escutas_com_album()
    escutas_ano = escutas[escutas["data"].str.startswith(prefixo)] if not escutas.empty else escutas

    albuns = models.listar_albuns()
    albuns_ano = albuns[albuns["created_at"].str.startswith(prefixo)] if not albuns.empty else albuns

    nota_media_ano = None
    artista_destaque = None
    if not escutas_ano.empty:
        notas = escutas_ano["nota"].dropna()
        if not notas.empty:
            nota_media_ano = round(notas.mean(), 2)
        top = escutas_ano.groupby("artista_nome").size().sort_values(ascending=False)
        if not top.empty:
            artista_destaque = top.index[0]

    return {
        "ano": ano,
        "albuns_novos": len(albuns_ano),
        "escutas": len(escutas_ano),
        "nota_media": nota_media_ano,
        "artista_destaque": artista_destaque,
    }
