"""Agregações somente-leitura sobre os bancos dos demais módulos do LifeOS,
para montar os cards e gráficos do Dashboard Geral. Nenhuma escrita ocorre
aqui — cada módulo continua sendo o único dono dos seus dados.
"""

from datetime import date, timedelta

import pandas as pd

import database
import utils


# ---------------------------------------------------------------------------
# Financeiro
# ---------------------------------------------------------------------------

def _fatura_do_mes(conn, mes_referencia: str, dia_util: int) -> float:
    compras = pd.read_sql_query("SELECT * FROM cartao_compras", conn)
    total = 0.0
    for _, compra in compras.iterrows():
        data_compra = date.fromisoformat(compra["data_compra"])
        valor_parcela = compra["valor_total"] / compra["parcelas"]
        for k in range(int(compra["parcelas"])):
            data_parcela = utils.somar_meses(data_compra, k)
            if utils.mes_referencia(data_parcela, dia_util) == mes_referencia:
                total += valor_parcela
    return round(total, 2)


def resumo_financeiro(hoje: date | None = None) -> dict | None:
    """Saldo restante até o próximo pagamento + gasto do ciclo atual.

    None se o módulo Financeiro ainda nunca foi executado (banco inexistente).
    """
    hoje = hoje or date.today()
    conn = database.get_connection("financeiro")
    if conn is None:
        return None
    try:
        config = dict(conn.execute("SELECT * FROM config WHERE id = 1").fetchone())
        contas_fixas = conn.execute(
            "SELECT COALESCE(SUM(valor), 0) AS total FROM contas_fixas WHERE ativo = 1"
        ).fetchone()["total"]

        dia_util = config["dia_util_pagamento"]
        inicio_ciclo = utils.pagamento_anterior(hoje, dia_util)
        mes_ref = utils.mes_referencia(inicio_ciclo, dia_util)
        fatura = _fatura_do_mes(conn, mes_ref, dia_util)

        dinheiro_livre = config["salario"] - contas_fixas - fatura - config["reserva_aporte_padrao"]

        gastos_ciclo = pd.read_sql_query(
            "SELECT * FROM gastos WHERE data >= ? AND data <= ?",
            conn, params=[inicio_ciclo.isoformat(), hoje.isoformat()],
        )
        gasto_mes = gastos_ciclo["valor"].sum() if not gastos_ciclo.empty else 0.0
        gasto_impacta_livre = (
            gastos_ciclo[~gastos_ciclo["forma_pagamento"].isin(["Vale alimentação", "Crédito"])]["valor"].sum()
            if not gastos_ciclo.empty else 0.0
        )

        saldo_restante = dinheiro_livre - gasto_impacta_livre

        inicio_controle = config.get("inicio_controle") or ""
        controle_ativo = not inicio_controle or hoje >= date.fromisoformat(inicio_controle)
        if not controle_ativo:
            saldo_restante = 0.0

        proximo_pagamento = utils.proximo_pagamento(hoje, dia_util)
        dias_restantes = utils.dias_ate(proximo_pagamento, hoje)

        return {
            "saldo_restante": round(saldo_restante, 2),
            "gasto_mes": round(gasto_mes, 2),
            "dias_restantes": dias_restantes,
            "proximo_pagamento": proximo_pagamento,
            "controle_ativo": controle_ativo,
        }
    finally:
        conn.close()


def evolucao_gastos(n_meses: int = 6, hoje: date | None = None) -> pd.DataFrame:
    """Total gasto por ciclo de pagamento, últimos N meses."""
    hoje = hoje or date.today()
    conn = database.get_connection("financeiro")
    if conn is None:
        return pd.DataFrame(columns=["mes_nome", "valor"])
    try:
        config = dict(conn.execute("SELECT * FROM config WHERE id = 1").fetchone())
        dia_util = config["dia_util_pagamento"]
        gastos = pd.read_sql_query("SELECT * FROM gastos", conn)

        linhas = []
        for i in range(n_meses - 1, -1, -1):
            mes_alvo_data = utils.somar_meses(hoje, -i)
            inicio_ciclo = utils.pagamento_anterior(mes_alvo_data, dia_util)
            mes_ref = utils.mes_referencia(inicio_ciclo, dia_util)
            inicio, fim = utils.intervalo_mes(mes_ref, dia_util)
            if gastos.empty:
                valor = 0.0
            else:
                no_periodo = gastos[(gastos["data"] >= inicio) & (gastos["data"] <= fim)]
                valor = no_periodo["valor"].sum()
            linhas.append({"mes_nome": utils.nome_mes(mes_ref), "valor": round(valor, 2)})
        return pd.DataFrame(linhas)
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Projetos
# ---------------------------------------------------------------------------

def resumo_projetos() -> dict | None:
    conn = database.get_connection("projetos")
    if conn is None:
        return None
    try:
        projetos = pd.read_sql_query("SELECT * FROM projetos", conn)
        if projetos.empty:
            return {"ativos": 0, "total_investido": 0.0, "progresso_medio": None}

        ativos = projetos[projetos["status"] == "Ativo"]
        aportes = pd.read_sql_query("SELECT * FROM projeto_aportes", conn)

        def investido(pid: int) -> float:
            if aportes.empty:
                return 0.0
            return aportes[aportes["projeto_id"] == pid]["valor"].sum()

        total_investido = sum(investido(int(pid)) for pid in projetos["id"])

        progressos = []
        for _, projeto in ativos.iterrows():
            if projeto["orcamento"] > 0:
                progressos.append(min(investido(int(projeto["id"])) / projeto["orcamento"] * 100, 100))
        progresso_medio = round(sum(progressos) / len(progressos), 1) if progressos else None

        return {
            "ativos": int(len(ativos)),
            "total_investido": round(total_investido, 2),
            "progresso_medio": progresso_medio,
        }
    finally:
        conn.close()


def progresso_projetos_ativos() -> pd.DataFrame:
    """Progresso financeiro (%) de cada projeto ativo com orçamento definido."""
    conn = database.get_connection("projetos")
    if conn is None:
        return pd.DataFrame(columns=["nome", "progresso"])
    try:
        projetos = pd.read_sql_query("SELECT * FROM projetos WHERE status = 'Ativo'", conn)
        if projetos.empty:
            return pd.DataFrame(columns=["nome", "progresso"])
        aportes = pd.read_sql_query("SELECT * FROM projeto_aportes", conn)

        linhas = []
        for _, projeto in projetos.iterrows():
            if projeto["orcamento"] <= 0:
                continue
            investido = (
                aportes[aportes["projeto_id"] == projeto["id"]]["valor"].sum()
                if not aportes.empty else 0.0
            )
            progresso = min(investido / projeto["orcamento"] * 100, 100)
            linhas.append({"nome": projeto["nome"], "progresso": round(progresso, 1)})

        if not linhas:
            return pd.DataFrame(columns=["nome", "progresso"])
        return pd.DataFrame(linhas).sort_values("progresso", ascending=True)
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Hábitos
# ---------------------------------------------------------------------------

def resumo_habitos(hoje: date | None = None) -> dict | None:
    hoje = hoje or date.today()
    conn = database.get_connection("habitos")
    if conn is None:
        return None
    try:
        habitos = pd.read_sql_query("SELECT * FROM habitos WHERE ativo = 1", conn)
        if habitos.empty:
            return {"ativos": 0, "percentual_medio": None}

        inicio = (hoje - timedelta(days=29)).isoformat()
        registros = pd.read_sql_query(
            "SELECT * FROM habito_registros WHERE data >= ?", conn, params=[inicio],
        )

        percentuais = []
        for hid in habitos["id"]:
            total = len(registros[registros["habito_id"] == hid]) if not registros.empty else 0
            percentuais.append(total / 30 * 100)

        return {
            "ativos": int(len(habitos)),
            "percentual_medio": round(sum(percentuais) / len(percentuais), 1),
        }
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Livros
# ---------------------------------------------------------------------------

def resumo_livros() -> dict | None:
    conn = database.get_connection("livros")
    if conn is None:
        return None
    try:
        leituras = pd.read_sql_query(
            """SELECT leituras.*, livros.nome AS livro_nome
               FROM leituras JOIN livros ON livros.id = leituras.livro_id
               ORDER BY leituras.data DESC, leituras.id DESC""",
            conn,
        )
        if leituras.empty:
            return {"lendo_agora": 0, "titulos_lendo": [], "lidos_ano": 0}

        mais_recente_por_livro = leituras.sort_values(
            ["livro_id", "data"], ascending=[True, False]
        ).drop_duplicates("livro_id")
        lendo = mais_recente_por_livro[mais_recente_por_livro["status"] == "Lendo"]

        ano_atual = str(date.today().year)
        lidos_ano = leituras[
            (leituras["status"] == "Concluído") & (leituras["data"].str.slice(0, 4) == ano_atual)
        ]
        return {
            "lendo_agora": int(len(lendo)),
            "titulos_lendo": lendo["livro_nome"].tolist(),
            "lidos_ano": int(len(lidos_ano)),
        }
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Música
# ---------------------------------------------------------------------------

def resumo_musica() -> dict | None:
    conn = database.get_connection("musica")
    if conn is None:
        return None
    try:
        escutas = pd.read_sql_query(
            """SELECT escutas.*, albuns.nome AS album_nome, artistas.nome AS artista_nome
               FROM escutas
               JOIN albuns ON albuns.id = escutas.album_id
               JOIN artistas ON artistas.id = albuns.artista_id
               ORDER BY escutas.data DESC, escutas.id DESC""",
            conn,
        )
        if escutas.empty:
            return {"albuns_mes": 0, "ultimo_album": None}

        mes_ref = date.today().strftime("%Y-%m")
        escutas_mes = escutas[escutas["data"].str.slice(0, 7) == mes_ref]
        albuns_mes = escutas_mes["album_id"].nunique() if not escutas_mes.empty else 0
        ultima = escutas.iloc[0]

        return {
            "albuns_mes": int(albuns_mes),
            "ultimo_album": f"{ultima['album_nome']} — {ultima['artista_nome']}",
        }
    finally:
        conn.close()
