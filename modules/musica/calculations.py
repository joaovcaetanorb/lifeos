"""Regras de negócio do módulo Música: agregações sobre escutas e álbuns.
Sem acesso direto a SQL — usa models.py.
"""

import models


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
