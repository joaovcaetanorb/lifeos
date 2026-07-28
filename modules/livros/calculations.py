"""Regras de negócio do módulo Livros: agregações sobre leituras e livros.
Sem acesso direto a SQL — usa models.py.
"""

import models


def nota_media_livro(livro_id: int) -> float | None:
    """Média das notas registradas nas leituras desse livro (ignora
    leituras sem nota). None se não há nenhuma nota ainda."""
    leituras = models.listar_leituras(livro_id)
    notas = leituras["nota"].dropna()
    if notas.empty:
        return None
    return round(notas.mean(), 2)


def total_leituras_livro(livro_id: int) -> int:
    return len(models.listar_leituras(livro_id))


def status_atual_livro(livro_id: int) -> str:
    """Status da leitura mais recente. 'Não iniciado' se não há nenhuma
    leitura registrada ainda (livro só cadastrado, na estante)."""
    leituras = models.listar_leituras(livro_id)
    if leituras.empty:
        return "Não iniciado"
    return leituras.iloc[0]["status"]


def resumo_geral() -> dict:
    """Números curtos para o topo das páginas: quantos livros, quantas
    leituras ao todo, e a nota média geral."""
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
