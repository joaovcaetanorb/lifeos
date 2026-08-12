"""Agregações somente-leitura cruzando os outros módulos do LifeOS — sem
banco próprio. Roda no mesmo processo FastAPI que os outros módulos (ver
webapp/main.py), então lê o repo/calculations de cada um direto, igual
webapp/timeline/calculations.py já faz — sem conexão cross-módulo própria,
sem banco novo (diferente de modules/analytics/, que precisava de uma
réplica Turso por módulo porque cada página Streamlit rodava isolada).

`_seguro()` engole RuntimeError (módulo sem TURSO_<MODULO>_* configurado)
igual à timeline: um módulo sem credencial não derruba a página inteira.
"""

import pandas as pd

from financeiro import calculations as financeiro_calc
from financeiro import repo as financeiro_repo
from habitos import calculations as habitos_calc
from habitos import repo as habitos_repo
from humor import calculations as humor_calc
from humor import repo as humor_repo
from livros import calculations as livros_calc
from livros import repo as livros_repo
from musica import calculations as musica_calc
from musica import repo as musica_repo
from projetos import repo as projetos_repo

_MIN_DIAS_POR_GRUPO = 7


def periodo_padrao() -> tuple[str, str]:
    return financeiro_calc.intervalo_mes(financeiro_calc.mes_atual())


def _seguro(fn, *args, default=None):
    try:
        return fn(*args)
    except RuntimeError:
        return default


# ---------------------------------------------------------------------------
# Cruzamentos — comparações reais (calculadas aqui, não pela IA) entre
# módulos, por dia. Porte de modules/analytics/calculations.py, trocando
# leitura cross-DB por chamada direta ao repo de cada módulo.
# ---------------------------------------------------------------------------

def _serie_diaria_humor(data_inicio: str, data_fim: str) -> pd.Series:
    registros = humor_repo.listar_registros(data_inicio, data_fim)
    if registros.empty:
        return pd.Series(dtype=float)
    serie = registros.groupby("data")["nota"].mean()
    serie.index = pd.to_datetime(serie.index).date
    return serie


def _dias_com_habito_cumprido(data_inicio: str, data_fim: str) -> set:
    registros = habitos_repo.listar_registros_todos(data_inicio, data_fim)
    if registros.empty:
        return set()
    return set(pd.to_datetime(registros["data"]).dt.date)


def _dias_gasto_por_data(data_inicio: str, data_fim: str) -> pd.Series:
    gastos = financeiro_repo.listar_gastos(data_inicio, data_fim)
    if gastos.empty:
        return pd.Series(dtype=float)
    serie = gastos.groupby("data")["valor"].sum()
    serie.index = pd.to_datetime(serie.index).date
    return serie


def _dias_com_atividade_cultural(data_inicio: str, data_fim: str) -> set:
    dias: set = set()
    leituras = livros_repo.listar_leituras_com_livro()
    if not leituras.empty:
        no_periodo = leituras[(leituras["data"] >= data_inicio) & (leituras["data"] <= data_fim)]
        dias |= set(pd.to_datetime(no_periodo["data"]).dt.date)
    escutas = musica_repo.listar_escutas_com_album()
    if not escutas.empty:
        no_periodo = escutas[(escutas["data"] >= data_inicio) & (escutas["data"] <= data_fim)]
        dias |= set(pd.to_datetime(no_periodo["data"]).dt.date)
    return dias


def _dias_com_atividade_projetos(data_inicio: str, data_fim: str) -> set:
    dias: set = set()
    aportes = projetos_repo.listar_aportes_todos(data_inicio, data_fim)
    if not aportes.empty:
        dias |= set(pd.to_datetime(aportes["data"]).dt.date)
    checklist = projetos_repo.listar_checklist_concluido(data_inicio, data_fim)
    if not checklist.empty:
        datas_concluido = checklist["concluido_em"].str.partition("T")[0]
        dias |= set(pd.to_datetime(datas_concluido).dt.date)
    return dias


def _split_por_mediana(serie_numerica: pd.Series) -> set:
    if serie_numerica.empty:
        return set()
    mediana = serie_numerica.median()
    return set(serie_numerica[serie_numerica > mediana].index)


def _comparar_grupos(
    serie_valor: pd.Series, dias_grupo_a: set, label_a: str, label_b: str,
    min_n: int = _MIN_DIAS_POR_GRUPO,
) -> dict | None:
    """Compara a média de `serie_valor` entre os dias em `dias_grupo_a` e os
    demais dias em que a série tem dado. Só retorna resultado se os dois
    grupos tiverem pelo menos `min_n` dias — caso contrário, `None` (sinal
    pra não mostrar nada em vez de um número baseado em amostra pequena
    demais pra significar algo)."""
    if serie_valor.empty:
        return None
    em_a = serie_valor.index.isin(dias_grupo_a)
    grupo_a = serie_valor[em_a]
    grupo_b = serie_valor[~em_a]
    if len(grupo_a) < min_n or len(grupo_b) < min_n:
        return None
    return {
        "label_a": label_a, "media_a": round(float(grupo_a.mean()), 1), "n_a": int(len(grupo_a)),
        "label_b": label_b, "media_b": round(float(grupo_b.mean()), 1), "n_b": int(len(grupo_b)),
    }


def correlacoes(data_inicio: str, data_fim: str) -> list[dict]:
    """Roda os 5 cruzamentos — cada um só entra na lista se houver dado
    suficiente nos dois grupos (ver _comparar_grupos)."""
    serie_humor = _seguro(_serie_diaria_humor, data_inicio, data_fim, default=pd.Series(dtype=float))
    dias_habito = _seguro(_dias_com_habito_cumprido, data_inicio, data_fim, default=set())
    dias_gasto = _seguro(_dias_gasto_por_data, data_inicio, data_fim, default=pd.Series(dtype=float))
    dias_cultura = _seguro(_dias_com_atividade_cultural, data_inicio, data_fim, default=set())
    dias_projetos = _seguro(_dias_com_atividade_projetos, data_inicio, data_fim, default=set())

    resultados = []

    r = _comparar_grupos(serie_humor, dias_habito, "dias com hábito cumprido", "dias sem hábito cumprido")
    if r:
        resultados.append({"par": "humor_habitos", "titulo": "Humor × Hábitos", "metrica": "humor (1-10)", **r})

    r = _comparar_grupos(
        serie_humor, _split_por_mediana(dias_gasto),
        "dias de gasto acima da mediana", "dias de gasto na mediana ou abaixo",
    )
    if r:
        resultados.append({"par": "humor_financeiro", "titulo": "Humor × Financeiro", "metrica": "humor (1-10)", **r})

    r = _comparar_grupos(serie_humor, dias_cultura, "dias com leitura ou escuta musical", "dias sem atividade cultural")
    if r:
        resultados.append({"par": "humor_cultura", "titulo": "Humor × Livros/Música", "metrica": "humor (1-10)", **r})

    r = _comparar_grupos(dias_gasto, dias_habito, "dias com hábito cumprido", "dias sem hábito cumprido")
    if r:
        resultados.append({"par": "habitos_financeiro", "titulo": "Hábitos × Financeiro", "metrica": "gasto diário (R$)", **r})

    r = _comparar_grupos(serie_humor, dias_projetos, "dias com atividade em projetos", "dias sem atividade em projetos")
    if r:
        resultados.append({"par": "humor_projetos", "titulo": "Humor × Projetos", "metrica": "humor (1-10)", **r})

    return resultados


# ---------------------------------------------------------------------------
# Resumo por módulo — números crus (não texto), pra montar cards narrativos
# no frontend ("você leu X, ouviu Y, cumpriu Z% dos hábitos") em vez de
# gráfico solto por módulo.
# ---------------------------------------------------------------------------

def resumo_modulos(data_inicio: str, data_fim: str) -> dict:
    financeiro = None
    gastos = _seguro(financeiro_repo.listar_gastos, data_inicio, data_fim, default=pd.DataFrame())
    if not gastos.empty:
        top_categoria = gastos.groupby("categoria")["valor"].sum().sort_values(ascending=False)
        financeiro = {
            "total": round(float(gastos["valor"].sum()), 2), "lancamentos": int(len(gastos)),
            "categoria_destaque": top_categoria.index[0], "categoria_valor": round(float(top_categoria.iloc[0]), 2),
        }

    habitos = None
    habitos_df = _seguro(habitos_calc.progresso_por_habito_periodo, data_inicio, data_fim, default=pd.DataFrame())
    if not habitos_df.empty:
        melhor, pior = habitos_df.iloc[-1], habitos_df.iloc[0]
        habitos = {
            "media_percentual": round(float(habitos_df["percentual"].mean()), 1),
            "melhor_nome": melhor["nome"], "melhor_percentual": float(melhor["percentual"]),
            "pior_nome": pior["nome"], "pior_percentual": float(pior["percentual"]),
        }

    humor = _seguro(humor_calc.resumo_periodo, data_inicio, data_fim, default=None)
    if humor and not humor["total_registros"]:
        humor = None

    livros = _seguro(livros_calc.resumo_periodo, data_inicio, data_fim, default=None)
    if livros and not livros["leituras"]:
        livros = None

    musica = _seguro(musica_calc.resumo_periodo, data_inicio, data_fim, default=None)
    if musica and not musica["escutas"]:
        musica = None

    projetos = None
    aportes = _seguro(projetos_repo.listar_aportes_todos, data_inicio, data_fim, default=pd.DataFrame())
    checklist = _seguro(projetos_repo.listar_checklist_concluido, data_inicio, data_fim, default=pd.DataFrame())
    if not aportes.empty or not checklist.empty:
        projetos = {
            "total_aportado": round(float(aportes["valor"].sum()) if not aportes.empty else 0.0, 2),
            "itens_concluidos": int(len(checklist)),
        }

    return {
        "financeiro": financeiro, "habitos": habitos, "humor": humor,
        "livros": livros, "musica": musica, "projetos": projetos,
    }


# ---------------------------------------------------------------------------
# Contexto agregado — texto compacto pro Groq responder perguntas livres
# ---------------------------------------------------------------------------

def _moeda(v: float) -> str:
    return f"R$ {v:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")


def _contexto_financeiro(data_inicio: str, data_fim: str) -> str | None:
    gastos = financeiro_repo.listar_gastos(data_inicio, data_fim)
    if gastos.empty:
        return None
    top_categoria = gastos.groupby("categoria")["valor"].sum().sort_values(ascending=False)
    return (
        f"FINANCEIRO — total gasto no período: {_moeda(gastos['valor'].sum())} em {len(gastos)} lançamento(s). "
        f"Categoria com mais gasto: {top_categoria.index[0]} ({_moeda(top_categoria.iloc[0])})."
    )


def _contexto_habitos(data_inicio: str, data_fim: str) -> str | None:
    df = habitos_calc.progresso_por_habito_periodo(data_inicio, data_fim)
    if df.empty:
        return None
    linhas = "; ".join(f"{r['nome']}: {r['percentual']:.0f}%" for _, r in df.iterrows())
    return f"HÁBITOS — cumprimento no período, por hábito: {linhas}"


def _contexto_humor(data_inicio: str, data_fim: str) -> str | None:
    r = humor_calc.resumo_periodo(data_inicio, data_fim)
    if not r["total_registros"]:
        return None
    tag_txt = f", tag mais frequente: {r['tag_destaque']}" if r["tag_destaque"] else ""
    return f"HUMOR — {r['total_registros']} registro(s) no período, nota média {r['nota_media']}/10{tag_txt}."


def _contexto_livros(data_inicio: str, data_fim: str) -> str | None:
    r = livros_calc.resumo_periodo(data_inicio, data_fim)
    if not r["leituras"]:
        return None
    nota_txt = f", nota média {r['nota_media']}/5" if r["nota_media"] is not None else ""
    autor_txt = f", autor destaque: {r['autor_destaque']}" if r["autor_destaque"] else ""
    return f"LIVROS — {r['livros_concluidos']} concluído(s) no período, {r['leituras']} leitura(s) registrada(s){nota_txt}{autor_txt}."


def _contexto_musica(data_inicio: str, data_fim: str) -> str | None:
    r = musica_calc.resumo_periodo(data_inicio, data_fim)
    if not r["escutas"]:
        return None
    nota_txt = f", nota média {r['nota_media']}/5" if r["nota_media"] is not None else ""
    artista_txt = f", artista destaque: {r['artista_destaque']}" if r["artista_destaque"] else ""
    return f"MÚSICA — {r['escutas']} escuta(s) no período, {r['albuns_novos']} álbum/álbuns novo(s){nota_txt}{artista_txt}."


def _contexto_projetos(data_inicio: str, data_fim: str) -> str | None:
    aportes = projetos_repo.listar_aportes_todos(data_inicio, data_fim)
    checklist = projetos_repo.listar_checklist_concluido(data_inicio, data_fim)
    if aportes.empty and checklist.empty:
        return None
    total_aportado = float(aportes["valor"].sum()) if not aportes.empty else 0.0
    return f"PROJETOS — {_moeda(total_aportado)} aportado(s) no período, {len(checklist)} item(ns) de checklist concluído(s)."


def contexto_geral(data_inicio: str, data_fim: str) -> str:
    """Um parágrafo por módulo (só números agregados, nunca a lista bruta),
    o que vai pro Groq nas perguntas livres."""
    blocos = [
        _seguro(_contexto_financeiro, data_inicio, data_fim),
        _seguro(_contexto_habitos, data_inicio, data_fim),
        _seguro(_contexto_humor, data_inicio, data_fim),
        _seguro(_contexto_livros, data_inicio, data_fim),
        _seguro(_contexto_musica, data_inicio, data_fim),
        _seguro(_contexto_projetos, data_inicio, data_fim),
    ]
    blocos = [b for b in blocos if b]
    if not blocos:
        return "Nenhum dado suficiente ainda em nenhum módulo pra esse período."
    return "\n\n".join(blocos)
