"""Agregações somente-leitura sobre os bancos dos demais módulos do LifeOS,
pra montar os gráficos cross-module e o contexto passado à IA. Nenhuma
escrita ocorre nos bancos alheios — cada módulo continua sendo o único
dono dos seus dados (mesmo princípio do Dashboard Geral).

Cada função abaixo devolve um valor "vazio" (DataFrame vazio, dict com
zeros, etc.) em caso de qualquer falha — credenciais não configuradas,
módulo nunca aberto/schema inexistente, erro de rede — em vez de derrubar
a página. Com Turso o banco sempre existe (foi criado manualmente), só a
tabela pode não existir ainda, e isso só aparece como exceção na query.
"""

from datetime import date, timedelta

import pandas as pd

import database
import utils


def _periodos_do_intervalo(data_inicio: str, data_fim: str) -> list[str]:
    inicio = date.fromisoformat(data_inicio)
    fim = date.fromisoformat(data_fim)
    periodos = []
    cursor = date(inicio.year, inicio.month, 1)
    while cursor <= fim:
        periodos.append(cursor.strftime("%Y-%m"))
        cursor = utils.somar_meses(cursor, 1)
    return periodos


# ---------------------------------------------------------------------------
# Financeiro
# ---------------------------------------------------------------------------

def financeiro_por_mes(data_inicio: str, data_fim: str) -> pd.DataFrame:
    """Total gasto por mês, dentro do período."""
    periodos = _periodos_do_intervalo(data_inicio, data_fim)
    vazio = pd.DataFrame({"periodo": periodos, "mes_nome": [utils.nome_mes_curto(p) for p in periodos], "valor": 0.0})

    conn = database.get_connection_modulo("financeiro")
    if conn is None:
        return vazio
    try:
        gastos = pd.read_sql_query("SELECT * FROM gastos", conn)
    except Exception:
        return vazio

    contagem = {}
    if not gastos.empty:
        gastos = gastos.copy()
        gastos["periodo"] = gastos["data"].str.slice(0, 7)
        contagem = gastos.groupby("periodo")["valor"].sum().to_dict()

    return pd.DataFrame({
        "periodo": periodos,
        "mes_nome": [utils.nome_mes_curto(p) for p in periodos],
        "valor": [round(float(contagem.get(p, 0.0)), 2) for p in periodos],
    })


def financeiro_resumo() -> dict | None:
    conn = database.get_connection_modulo("financeiro")
    if conn is None:
        return None
    try:
        cursor = conn.execute("SELECT * FROM config WHERE id = 1")
        config = database.linha_para_dict(cursor, cursor.fetchone())
        return {"salario": config["salario"], "dia_util_pagamento": config["dia_util_pagamento"]} if config else None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Projetos
# ---------------------------------------------------------------------------

def projetos_lista() -> pd.DataFrame:
    """Cada projeto com progresso financeiro (%) calculado."""
    vazio = pd.DataFrame(columns=["nome", "status", "progresso"])
    conn = database.get_connection_modulo("projetos")
    if conn is None:
        return vazio
    try:
        projetos = pd.read_sql_query("SELECT * FROM projetos", conn)
        if projetos.empty:
            return vazio
        aportes = pd.read_sql_query("SELECT * FROM projeto_aportes", conn)
    except Exception:
        return vazio

    linhas = []
    for _, projeto in projetos.iterrows():
        investido = aportes[aportes["projeto_id"] == projeto["id"]]["valor"].sum() if not aportes.empty else 0.0
        progresso = round(min(investido / projeto["orcamento"] * 100, 100), 1) if projeto["orcamento"] > 0 else None
        linhas.append({"nome": projeto["nome"], "status": projeto["status"], "progresso": progresso})
    return pd.DataFrame(linhas)


# ---------------------------------------------------------------------------
# Hábitos
# ---------------------------------------------------------------------------

def habitos_por_mes(data_inicio: str, data_fim: str) -> pd.DataFrame:
    """% médio de cumprimento (entre hábitos ativos) por mês — mesma lógica
    de `habitos/calculations.py::cumprimento_por_mes`, reimplementada aqui
    porque módulos não se importam entre si (cada um lê seu próprio banco)."""
    inicio, fim = date.fromisoformat(data_inicio), date.fromisoformat(data_fim)
    periodos = _periodos_do_intervalo(data_inicio, data_fim)
    vazio = pd.DataFrame({"periodo": periodos, "mes_nome": [utils.nome_mes_curto(p) for p in periodos], "percentual": 0.0})

    conn = database.get_connection_modulo("habitos")
    if conn is None:
        return vazio
    try:
        habitos = pd.read_sql_query("SELECT * FROM habitos WHERE ativo = 1", conn)
        total_habitos = len(habitos)
        if total_habitos == 0:
            return vazio
        registros = pd.read_sql_query(
            "SELECT * FROM habito_registros WHERE data >= ? AND data <= ?", conn, params=[data_inicio, data_fim],
        )
    except Exception:
        return vazio

    linhas = []
    cursor = date(inicio.year, inicio.month, 1)
    while cursor <= fim:
        periodo = cursor.strftime("%Y-%m")
        mes_inicio = max(cursor, inicio)
        ultimo_dia_mes = utils.somar_meses(cursor, 1) - timedelta(days=1)
        mes_fim = min(ultimo_dia_mes, fim)
        dias_no_periodo = (mes_fim - mes_inicio).days + 1

        marcados = 0
        if not registros.empty:
            no_mes = registros[
                (registros["data"] >= mes_inicio.isoformat()) & (registros["data"] <= mes_fim.isoformat())
            ]
            marcados = len(no_mes)
        maximo = total_habitos * dias_no_periodo
        linhas.append({
            "periodo": periodo, "mes_nome": utils.nome_mes_curto(periodo),
            "percentual": round(marcados / maximo * 100, 1) if maximo else 0.0,
        })
        cursor = utils.somar_meses(cursor, 1)

    return pd.DataFrame(linhas)


def habitos_lista_percentual(dias: int = 30) -> pd.DataFrame:
    vazio = pd.DataFrame(columns=["nome", "percentual"])
    conn = database.get_connection_modulo("habitos")
    if conn is None:
        return vazio
    try:
        habitos = pd.read_sql_query("SELECT * FROM habitos WHERE ativo = 1", conn)
        if habitos.empty:
            return vazio
        hoje = date.today()
        inicio = (hoje - timedelta(days=dias - 1)).isoformat()
        registros = pd.read_sql_query(
            "SELECT * FROM habito_registros WHERE data >= ?", conn, params=[inicio],
        )
    except Exception:
        return vazio

    linhas = []
    for _, h in habitos.iterrows():
        total = len(registros[registros["habito_id"] == h["id"]]) if not registros.empty else 0
        linhas.append({"nome": h["nome"], "percentual": round(total / dias * 100, 1)})
    return pd.DataFrame(linhas)


# ---------------------------------------------------------------------------
# Humor
# ---------------------------------------------------------------------------

def humor_por_mes(data_inicio: str, data_fim: str) -> pd.DataFrame:
    periodos = _periodos_do_intervalo(data_inicio, data_fim)
    vazio = pd.DataFrame({"periodo": periodos, "mes_nome": [utils.nome_mes_curto(p) for p in periodos], "nota_media": None})

    conn = database.get_connection_modulo("humor")
    if conn is None:
        return vazio
    try:
        registros = pd.read_sql_query(
            "SELECT * FROM registros_humor WHERE data >= ? AND data <= ?", conn, params=[data_inicio, data_fim],
        )
    except Exception:
        return vazio

    medias = {}
    if not registros.empty:
        registros = registros.copy()
        registros["periodo"] = registros["data"].str.slice(0, 7)
        medias = registros.groupby("periodo")["nota"].mean().to_dict()

    return pd.DataFrame({
        "periodo": periodos,
        "mes_nome": [utils.nome_mes_curto(p) for p in periodos],
        "nota_media": [round(medias[p], 1) if p in medias else None for p in periodos],
    })


def humor_tags_frequentes(data_inicio: str, data_fim: str, limite: int = 5) -> pd.DataFrame:
    vazio = pd.DataFrame(columns=["tag", "total"])
    conn = database.get_connection_modulo("humor")
    if conn is None:
        return vazio
    try:
        registros = pd.read_sql_query(
            "SELECT * FROM registros_humor WHERE data >= ? AND data <= ?", conn, params=[data_inicio, data_fim],
        )
    except Exception:
        return vazio
    if registros.empty:
        return vazio

    from collections import Counter
    contador = Counter()
    for tags_texto in registros["tags"]:
        contador.update(t for t in tags_texto.split(",") if t)
    if not contador:
        return vazio
    df = pd.DataFrame(contador.items(), columns=["tag", "total"])
    return df.sort_values("total", ascending=False).head(limite)


# ---------------------------------------------------------------------------
# Livros
# ---------------------------------------------------------------------------

def livros_resumo(data_inicio: str, data_fim: str) -> dict:
    vazio = {"concluidos": 0, "lendo_agora": 0, "nota_media": None}
    conn = database.get_connection_modulo("livros")
    if conn is None:
        return vazio
    try:
        leituras = pd.read_sql_query(
            """SELECT leituras.* FROM leituras
               WHERE leituras.data >= ? AND leituras.data <= ?""",
            conn, params=[data_inicio, data_fim],
        )
        todas = pd.read_sql_query("SELECT * FROM leituras ORDER BY data DESC", conn)
    except Exception:
        return vazio

    concluidos = len(leituras[leituras["status"] == "Concluído"]) if not leituras.empty else 0
    lendo_agora = 0
    if not todas.empty:
        mais_recente = todas.sort_values(["livro_id", "data"], ascending=[True, False]).drop_duplicates("livro_id")
        lendo_agora = int((mais_recente["status"] == "Lendo").sum())
    nota_media = round(leituras["nota"].dropna().mean(), 1) if not leituras.empty and not leituras["nota"].dropna().empty else None

    return {"concluidos": concluidos, "lendo_agora": lendo_agora, "nota_media": nota_media}


# ---------------------------------------------------------------------------
# Música
# ---------------------------------------------------------------------------

def musica_resumo(data_inicio: str, data_fim: str) -> dict:
    vazio = {"escutas": 0, "albuns_novos": 0, "top_artistas": []}
    conn = database.get_connection_modulo("musica")
    if conn is None:
        return vazio
    try:
        escutas = pd.read_sql_query(
            """SELECT escutas.*, artistas.nome AS artista_nome
               FROM escutas
               JOIN albuns ON albuns.id = escutas.album_id
               JOIN artistas ON artistas.id = albuns.artista_id
               WHERE escutas.data >= ? AND escutas.data <= ?""",
            conn, params=[data_inicio, data_fim],
        )
        albuns = pd.read_sql_query("SELECT * FROM albuns", conn)
    except Exception:
        return vazio

    albuns_novos = 0
    if not albuns.empty:
        criado_em = albuns["created_at"].str.slice(0, 10)
        albuns_novos = int(((criado_em >= data_inicio) & (criado_em <= data_fim)).sum())

    top_artistas = []
    if not escutas.empty:
        top = escutas.groupby("artista_nome").size().sort_values(ascending=False).head(3)
        top_artistas = list(top.index)

    return {"escutas": len(escutas), "albuns_novos": albuns_novos, "top_artistas": top_artistas}


# ---------------------------------------------------------------------------
# Cruzamentos — comparações reais (calculadas aqui, não pela IA) entre
# módulos, por dia. A IA (groq_client.narrar_correlacao) só traduz o
# resultado já calculado em uma frase — nunca inventa o número.
# ---------------------------------------------------------------------------

_MIN_DIAS_POR_GRUPO = 7


def _serie_diaria_humor(data_inicio: str, data_fim: str) -> pd.Series:
    """Nota média de humor por dia (index=date) — múltiplos registros no
    mesmo dia viram uma média, igual ao calendário do próprio módulo Humor."""
    conn = database.get_connection_modulo("humor")
    if conn is None:
        return pd.Series(dtype=float)
    try:
        registros = pd.read_sql_query(
            "SELECT data, nota FROM registros_humor WHERE data >= ? AND data <= ?",
            conn, params=[data_inicio, data_fim],
        )
    except Exception:
        return pd.Series(dtype=float)
    if registros.empty:
        return pd.Series(dtype=float)

    serie = registros.groupby("data")["nota"].mean()
    serie.index = pd.to_datetime(serie.index).date
    return serie


def _dias_com_habito_cumprido(data_inicio: str, data_fim: str) -> set:
    """Dias (date) com pelo menos 1 hábito marcado como cumprido."""
    conn = database.get_connection_modulo("habitos")
    if conn is None:
        return set()
    try:
        registros = pd.read_sql_query(
            "SELECT DISTINCT data FROM habito_registros WHERE data >= ? AND data <= ?",
            conn, params=[data_inicio, data_fim],
        )
    except Exception:
        return set()
    if registros.empty:
        return set()
    return set(pd.to_datetime(registros["data"]).dt.date)


def _dias_gasto_por_data(data_inicio: str, data_fim: str) -> pd.Series:
    """Total gasto por dia (index=date)."""
    conn = database.get_connection_modulo("financeiro")
    if conn is None:
        return pd.Series(dtype=float)
    try:
        gastos = pd.read_sql_query(
            "SELECT data, valor FROM gastos WHERE data >= ? AND data <= ?",
            conn, params=[data_inicio, data_fim],
        )
    except Exception:
        return pd.Series(dtype=float)
    if gastos.empty:
        return pd.Series(dtype=float)

    serie = gastos.groupby("data")["valor"].sum()
    serie.index = pd.to_datetime(serie.index).date
    return serie


def _dias_com_atividade_cultural(data_inicio: str, data_fim: str) -> set:
    """Dias (date) com pelo menos 1 leitura (livros) ou 1 escuta (música)."""
    dias: set = set()

    conn_livros = database.get_connection_modulo("livros")
    if conn_livros is not None:
        try:
            leituras = pd.read_sql_query(
                "SELECT DISTINCT data FROM leituras WHERE data >= ? AND data <= ?",
                conn_livros, params=[data_inicio, data_fim],
            )
            if not leituras.empty:
                dias |= set(pd.to_datetime(leituras["data"]).dt.date)
        except Exception:
            pass

    conn_musica = database.get_connection_modulo("musica")
    if conn_musica is not None:
        try:
            escutas = pd.read_sql_query(
                "SELECT DISTINCT data FROM escutas WHERE data >= ? AND data <= ?",
                conn_musica, params=[data_inicio, data_fim],
            )
            if not escutas.empty:
                dias |= set(pd.to_datetime(escutas["data"]).dt.date)
        except Exception:
            pass

    return dias


def _split_por_mediana(serie_numerica: pd.Series) -> set:
    """Dias (date) cujo valor está acima da mediana da série — usado pra
    transformar uma métrica contínua (ex.: gasto do dia) em dois grupos
    comparáveis com _comparar_grupos."""
    if serie_numerica.empty:
        return set()
    mediana = serie_numerica.median()
    return set(serie_numerica[serie_numerica > mediana].index)


def _comparar_grupos(
    serie_humor: pd.Series, dias_grupo_a: set, label_a: str, label_b: str,
    min_n: int = _MIN_DIAS_POR_GRUPO,
) -> dict | None:
    """Compara a nota média de humor entre dias que estão em `dias_grupo_a`
    e os que não estão, dentro dos dias em que HÁ registro de humor. Só
    retorna resultado se os dois grupos tiverem pelo menos `min_n` dias —
    caso contrário, `None` (sinal pra não mostrar nada em vez de um número
    baseado em amostra pequena demais pra significar algo)."""
    if serie_humor.empty:
        return None

    em_a = serie_humor.index.isin(dias_grupo_a)
    grupo_a = serie_humor[em_a]
    grupo_b = serie_humor[~em_a]

    if len(grupo_a) < min_n or len(grupo_b) < min_n:
        return None

    return {
        "label_a": label_a, "media_a": round(grupo_a.mean(), 1), "n_a": len(grupo_a),
        "label_b": label_b, "media_b": round(grupo_b.mean(), 1), "n_b": len(grupo_b),
    }


def correlacoes_humor(data_inicio: str, data_fim: str) -> list[dict]:
    """Roda os cruzamentos Humor×Hábitos, Humor×Financeiro e
    Humor×Livros/Música — cada um só entra na lista se houver dado
    suficiente (ver _comparar_grupos)."""
    serie_humor = _serie_diaria_humor(data_inicio, data_fim)
    resultados = []

    r = _comparar_grupos(
        serie_humor, _dias_com_habito_cumprido(data_inicio, data_fim),
        "dias com hábito cumprido", "dias sem hábito cumprido",
    )
    if r:
        resultados.append({"par": "humor_habitos", **r})

    dias_gasto = _dias_gasto_por_data(data_inicio, data_fim)
    r = _comparar_grupos(
        serie_humor, _split_por_mediana(dias_gasto),
        "dias de gasto acima da mediana", "dias de gasto na mediana ou abaixo",
    )
    if r:
        resultados.append({"par": "humor_financeiro", **r})

    r = _comparar_grupos(
        serie_humor, _dias_com_atividade_cultural(data_inicio, data_fim),
        "dias com leitura ou escuta musical", "dias sem atividade cultural",
    )
    if r:
        resultados.append({"par": "humor_cultura", **r})

    return resultados


# ---------------------------------------------------------------------------
# Contexto agregado — o que a IA recebe (perguntas e sugestões)
# ---------------------------------------------------------------------------

def contexto_geral(data_inicio: str, data_fim: str) -> str:
    """Monta um resumo textual compacto (não os dados brutos!) com o que
    cada módulo tem de mais relevante no período — é isso que vira o
    contexto passado ao Groq. Módulos nunca usados ficam de fora."""
    blocos = []

    fin = financeiro_por_mes(data_inicio, data_fim)
    if fin["valor"].sum() > 0:
        linhas = "; ".join(f"{r['mes_nome']}: {utils.formatar_moeda(r['valor'])}" for _, r in fin.iterrows())
        blocos.append(f"FINANCEIRO — gasto por mês: {linhas}")

    proj = projetos_lista()
    if not proj.empty:
        linhas = "; ".join(
            f"{r['nome']} ({r['status']}, {r['progresso']:.0f}% do orçamento)" if r["progresso"] is not None
            else f"{r['nome']} ({r['status']})"
            for _, r in proj.iterrows()
        )
        blocos.append(f"PROJETOS: {linhas}")

    hab_mes = habitos_por_mes(data_inicio, data_fim)
    hab_lista = habitos_lista_percentual()
    if hab_mes["percentual"].sum() > 0 or not hab_lista.empty:
        linhas_mes = "; ".join(f"{r['mes_nome']}: {r['percentual']:.0f}%" for _, r in hab_mes.iterrows())
        linhas_habitos = "; ".join(f"{r['nome']}: {r['percentual']:.0f}% (30d)" for _, r in hab_lista.iterrows())
        blocos.append(f"HÁBITOS — cumprimento médio por mês: {linhas_mes}. Por hábito (últimos 30 dias): {linhas_habitos}")

    hum_mes = humor_por_mes(data_inicio, data_fim)
    hum_tags = humor_tags_frequentes(data_inicio, data_fim)
    if hum_mes["nota_media"].notna().any():
        linhas = "; ".join(
            f"{r['mes_nome']}: {r['nota_media']:.1f}/10" for _, r in hum_mes.iterrows() if pd.notna(r["nota_media"])
        )
        tags_txt = ", ".join(f"{r['tag']} ({r['total']}x)" for _, r in hum_tags.iterrows()) if not hum_tags.empty else "nenhuma"
        blocos.append(f"HUMOR — nota média por mês: {linhas}. Tags mais frequentes: {tags_txt}")

    livros = livros_resumo(data_inicio, data_fim)
    if livros["concluidos"] or livros["lendo_agora"]:
        nota_txt = f", nota média {livros['nota_media']:.1f}/5" if livros["nota_media"] is not None else ""
        blocos.append(
            f"LIVROS — concluídos no período: {livros['concluidos']}, lendo agora: {livros['lendo_agora']}{nota_txt}"
        )

    musica = musica_resumo(data_inicio, data_fim)
    if musica["escutas"]:
        artistas_txt = ", ".join(musica["top_artistas"]) if musica["top_artistas"] else "nenhum"
        blocos.append(
            f"MÚSICA — escutas no período: {musica['escutas']}, álbuns novos: {musica['albuns_novos']}, "
            f"artistas mais ouvidos: {artistas_txt}"
        )

    if not blocos:
        return "Nenhum dado suficiente ainda em nenhum módulo pra esse período."
    return "\n\n".join(blocos)
