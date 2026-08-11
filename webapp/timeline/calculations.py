"""Agregação somente-leitura dos eventos de todos os módulos, pra montar a
Life Timeline. Roda no mesmo processo FastAPI que os outros módulos (ver
webapp/main.py), então lê o `repo` de cada um direto — sem conexão cross-
módulo própria, sem banco novo (diferente de modules/dashboard_geral/,
que precisava disso porque cada página Streamlit rodava isolada).

Cada função eventos_* nunca deixa um módulo sem dado derrubar a timeline
inteira — DataFrame vazio vira lista vazia, igual ao
dashboard_geral/calculations.py original.

`spotify_historico` (plays brutos do Spotify) fica de fora de propósito:
é ruído de alto volume, e música é framed como diário de álbuns
(`escutas`), não scrobble log.
"""

from datetime import date, timedelta

import pandas as pd

from financeiro import repo as financeiro_repo
from habitos import repo as habitos_repo
from humor import repo as humor_repo
from livros import repo as livros_repo
from momentos import repo as momentos_repo
from musica import repo as musica_repo
from projetos import repo as projetos_repo

STATUS_LEITURA_VERBO = {
    "Lendo": "Começou a ler",
    "Concluído": "Concluiu a leitura de",
    "Abandonado": "Abandonou a leitura de",
}


def _moeda(v: float) -> str:
    return f"R$ {v:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")


def _filtrar_por_data(df: pd.DataFrame, coluna: str, data_inicio: str, data_fim: str) -> pd.DataFrame:
    if df.empty:
        return df
    return df[(df[coluna] >= data_inicio) & (df[coluna] <= data_fim)]


def eventos_habitos(data_inicio: str, data_fim: str) -> list[dict]:
    registros = habitos_repo.listar_registros_todos(data_inicio, data_fim)
    if registros.empty:
        return []
    return [
        {
            "data": r["data"], "hora": "", "modulo": "habitos", "icone": "✅",
            "texto": f"Hábito: {r['habito_nome']}", "href": "/habitos/habitos.html",
        }
        for _, r in registros.iterrows()
    ]


def eventos_humor(data_inicio: str, data_fim: str) -> list[dict]:
    registros = humor_repo.listar_registros(data_inicio, data_fim)
    if registros.empty:
        return []
    eventos = []
    for _, r in registros.iterrows():
        tags = [t for t in (r["tags"] or "").split(",") if t]
        texto = f"Humor {int(r['nota'])}/10"
        if tags:
            texto += f" ({', '.join(tags)})"
        eventos.append({
            "data": r["data"], "hora": r["hora"] or "", "modulo": "humor", "icone": "🙂",
            "texto": texto, "href": "/humor/humor.html",
        })
    return eventos


def eventos_financeiro(data_inicio: str, data_fim: str) -> list[dict]:
    eventos = []

    gastos = financeiro_repo.listar_gastos(data_inicio, data_fim)
    for _, r in gastos.iterrows():
        eventos.append({
            "data": r["data"], "hora": "", "modulo": "financeiro", "icone": "💰",
            "texto": f"Gasto: {r['descricao']} — {_moeda(r['valor'])}", "href": "/financeiro/gastos.html",
        })

    receitas = financeiro_repo.listar_receitas_extras(data_inicio, data_fim)
    for _, r in receitas.iterrows():
        eventos.append({
            "data": r["data"], "hora": "", "modulo": "financeiro", "icone": "💵",
            "texto": f"Renda extra: {r['descricao']} — {_moeda(r['valor'])}", "href": "/financeiro/receitas.html",
        })

    cofre = _filtrar_por_data(financeiro_repo.listar_movimentos_reserva(), "data", data_inicio, data_fim)
    for _, r in cofre.iterrows():
        eventos.append({
            "data": r["data"], "hora": "", "modulo": "financeiro", "icone": "🏦",
            "texto": f"Cofre — {r['tipo']}: {_moeda(r['valor'])}", "href": "/financeiro/cofre.html",
        })

    return eventos


def eventos_livros(data_inicio: str, data_fim: str) -> list[dict]:
    leituras = _filtrar_por_data(livros_repo.listar_leituras_com_livro(), "data", data_inicio, data_fim)
    if leituras.empty:
        return []
    eventos = []
    for _, r in leituras.iterrows():
        verbo = STATUS_LEITURA_VERBO.get(r["status"], r["status"])
        texto = f"{verbo} '{r['livro_nome']}'"
        if pd.notna(r["nota"]):
            texto += f" — nota {r['nota']}"
        eventos.append({
            "data": r["data"], "hora": "", "modulo": "livros", "icone": "📚",
            "texto": texto, "href": "/livros/diario.html",
        })
    return eventos


def eventos_musica(data_inicio: str, data_fim: str) -> list[dict]:
    escutas = _filtrar_por_data(musica_repo.listar_escutas_com_album(), "data", data_inicio, data_fim)
    if escutas.empty:
        return []
    eventos = []
    for _, r in escutas.iterrows():
        texto = f"Ouviu '{r['album_nome']}' — {r['artista_nome']}"
        if pd.notna(r["nota"]):
            texto += f" — nota {r['nota']}"
        eventos.append({
            "data": r["data"], "hora": "", "modulo": "musica", "icone": "🎵",
            "texto": texto, "href": "/musica/diario.html",
        })
    return eventos


def eventos_projetos(data_inicio: str, data_fim: str) -> list[dict]:
    eventos = []

    aportes = projetos_repo.listar_aportes_todos(data_inicio, data_fim)
    for _, r in aportes.iterrows():
        eventos.append({
            "data": r["data"], "hora": "", "modulo": "projetos", "icone": "🎯",
            "texto": f"Aporte no projeto '{r['projeto_nome']}': {_moeda(r['valor'])}",
            "href": "/projetos/projetos.html",
        })

    checklist = projetos_repo.listar_checklist_concluido(data_inicio, data_fim)
    for _, r in checklist.iterrows():
        data_concluido, _, hora_concluido = r["concluido_em"].partition("T")
        eventos.append({
            "data": data_concluido, "hora": hora_concluido[:5], "modulo": "projetos", "icone": "☑️",
            "texto": f"Concluiu '{r['descricao']}' em {r['projeto_nome']}",
            "href": "/projetos/projetos.html",
        })

    return eventos


def eventos_momentos(data_inicio: str, data_fim: str) -> list[dict]:
    momentos = momentos_repo.listar_momentos(data_inicio, data_fim)
    if momentos.empty:
        return []
    return [
        {
            "id": int(r["id"]), "data": r["data"], "hora": r["hora"] or "", "modulo": "momentos",
            "icone": momentos_repo.CATEGORIAS_MOMENTO.get(r["categoria"], "📝"), "texto": r["texto"], "href": "",
        }
        for _, r in momentos.iterrows()
    ]


def _seguro(fn, data_inicio: str, data_fim: str) -> list[dict]:
    """Chama uma eventos_* isolando falha de módulo (ex.: TURSO_<MODULO>_*
    ainda não configurado) — um módulo sem credencial vira lista vazia,
    nunca derruba a timeline inteira."""
    try:
        return fn(data_inicio, data_fim)
    except RuntimeError:
        return []


def timeline(data_inicio: str, data_fim: str) -> list[dict]:
    eventos = [
        *_seguro(eventos_habitos, data_inicio, data_fim),
        *_seguro(eventos_humor, data_inicio, data_fim),
        *_seguro(eventos_financeiro, data_inicio, data_fim),
        *_seguro(eventos_livros, data_inicio, data_fim),
        *_seguro(eventos_musica, data_inicio, data_fim),
        *_seguro(eventos_projetos, data_inicio, data_fim),
        *_seguro(eventos_momentos, data_inicio, data_fim),
    ]
    eventos.sort(key=lambda e: (e["data"], e["hora"]), reverse=True)
    return eventos


def periodo_padrao() -> tuple[str, str]:
    hoje = date.today()
    return (hoje - timedelta(days=6)).isoformat(), hoje.isoformat()
