"""Agregações somente-leitura sobre os bancos dos demais módulos do LifeOS,
para montar os cards e gráficos do Dashboard Geral. Nenhuma escrita ocorre
aqui — cada módulo continua sendo o único dono dos seus dados.

Cada função abaixo devolve None em caso de qualquer falha (credenciais não
configuradas, módulo nunca aberto/schema inexistente, erro de rede) — o
card correspondente vira "módulo ainda não usado" em vez de derrubar a
página inteira. Isso é mais importante agora do que era com SQLite local:
antes "banco inexistente" era o único jeito de faltar dado; com Turso o
banco sempre existe (foi criado manualmente), só a tabela pode não existir
ainda, e isso só aparece como exceção na hora da query, não antes.
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

    None se o módulo Financeiro ainda não tem dado disponível.
    """
    hoje = hoje or date.today()
    conn = database.get_connection("financeiro")
    if conn is None:
        return None
    try:
        cursor = conn.execute("SELECT * FROM config WHERE id = 1")
        config = database.linha_para_dict(cursor, cursor.fetchone())
        if config is None:
            return None
        contas_fixas = conn.execute(
            "SELECT COALESCE(SUM(valor), 0) AS total FROM contas_fixas WHERE ativo = 1"
        ).fetchone()[0]

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
        por_dia = round(saldo_restante / dias_restantes, 2) if dias_restantes else round(saldo_restante, 2)

        return {
            "saldo_restante": round(saldo_restante, 2),
            "gasto_mes": round(gasto_mes, 2),
            "dias_restantes": dias_restantes,
            "proximo_pagamento": proximo_pagamento,
            "controle_ativo": controle_ativo,
            "por_dia": por_dia,
        }
    except Exception:
        return None


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
    except Exception:
        return None


def proxima_tarefa_projeto() -> dict | None:
    """Primeiro item de checklist ainda não concluído, entre os projetos
    ativos — prioriza quem tem prazo mais próximo, depois ordem/criação.
    None se não há projeto ativo ou nenhum tem pendência."""
    conn = database.get_connection("projetos")
    if conn is None:
        return None
    try:
        pendentes = pd.read_sql_query(
            """SELECT projeto_checklist.*, projetos.nome AS projeto_nome
               FROM projeto_checklist
               JOIN projetos ON projetos.id = projeto_checklist.projeto_id
               WHERE projeto_checklist.concluido = 0 AND projetos.status = 'Ativo'""",
            conn,
        )
    except Exception:
        return None

    if pendentes.empty:
        return None

    com_prazo = pendentes[pendentes["prazo"] != ""].sort_values("prazo")
    escolhida = com_prazo.iloc[0] if not com_prazo.empty else pendentes.sort_values(["ordem", "id"]).iloc[0]
    return {
        "descricao": escolhida["descricao"],
        "projeto_nome": escolhida["projeto_nome"],
        "prazo": escolhida["prazo"] or None,
    }


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
    except Exception:
        return None


def habitos_faltantes_hoje(hoje: date | None = None) -> list[str] | None:
    """Nomes dos hábitos ativos ainda não marcados hoje. None se o módulo
    nunca foi usado OU não tem nenhum hábito ativo cadastrado — distinto de
    lista vazia, que significa 'tem hábito(s) e todos já foram cumpridos
    hoje'. Sem essa distinção, 0 hábitos cadastrados virava lista vazia
    igual a 'tudo cumprido', e a saudação gerada por IA (contexto_hoje())
    chegava a parabenizar o usuário por cumprir hábitos que nem existem."""
    hoje = hoje or date.today()
    conn = database.get_connection("habitos")
    if conn is None:
        return None
    try:
        habitos = pd.read_sql_query("SELECT * FROM habitos WHERE ativo = 1", conn)
        if habitos.empty:
            return None
        feitos_hoje = pd.read_sql_query(
            "SELECT habito_id FROM habito_registros WHERE data = ?", conn, params=[hoje.isoformat()],
        )
    except Exception:
        return None

    ids_feitos = set(feitos_hoje["habito_id"]) if not feitos_hoje.empty else set()
    return [h["nome"] for _, h in habitos.iterrows() if h["id"] not in ids_feitos]


# ---------------------------------------------------------------------------
# Livros
# ---------------------------------------------------------------------------

def resumo_livros() -> dict | None:
    conn = database.get_connection("livros")
    if conn is None:
        return None
    try:
        leituras = pd.read_sql_query(
            """SELECT leituras.*, livros.nome AS livro_nome, livros.capa_path AS livro_capa_path,
                      livros.genero AS livro_genero, livros.ano_publicacao AS livro_ano,
                      autores.nome AS autor_nome
               FROM leituras
               JOIN livros ON livros.id = leituras.livro_id
               JOIN autores ON autores.id = livros.autor_id
               ORDER BY leituras.data DESC, leituras.id DESC""",
            conn,
        )
        if leituras.empty:
            return {"lendo_agora": 0, "livros_lendo": [], "lidos_ano": 0}

        mais_recente_por_livro = leituras.sort_values(
            ["livro_id", "data"], ascending=[True, False]
        ).drop_duplicates("livro_id")
        lendo = mais_recente_por_livro[mais_recente_por_livro["status"] == "Lendo"]

        ano_atual = str(date.today().year)
        lidos_ano = leituras[
            (leituras["status"] == "Concluído") & (leituras["data"].str.slice(0, 4) == ano_atual)
        ]
        livros_lendo = [
            {
                "nome": row["livro_nome"],
                "autor": row["autor_nome"],
                "genero": row["livro_genero"] or "",
                "ano": int(row["livro_ano"]) if pd.notna(row["livro_ano"]) else None,
                "capa_path": row["livro_capa_path"] or "",
            }
            for _, row in lendo.iterrows()
        ]
        return {
            "lendo_agora": int(len(lendo)),
            "livros_lendo": livros_lendo,
            "lidos_ano": int(len(lidos_ano)),
        }
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Humor
# ---------------------------------------------------------------------------

def resumo_humor(hoje: date | None = None) -> dict | None:
    hoje = hoje or date.today()
    conn = database.get_connection("humor")
    if conn is None:
        return None
    vazio = {
        "registrado_hoje": False, "nota_hoje": None, "tags_hoje": [],
        "nota_livre_hoje": "", "criado_em": None,
    }
    try:
        registros = pd.read_sql_query(
            "SELECT * FROM registros_humor ORDER BY data DESC, hora DESC, id DESC", conn,
        )
        if registros.empty:
            return vazio

        hoje_iso = hoje.isoformat()
        registros_hoje = registros[registros["data"] == hoje_iso]
        if registros_hoje.empty:
            return vazio

        ultimo = registros_hoje.iloc[0]
        tags = [t for t in ultimo["tags"].split(",") if t]
        return {
            "registrado_hoje": True,
            "nota_hoje": int(ultimo["nota"]),
            "tags_hoje": tags,
            "nota_livre_hoje": ultimo["nota_livre"] or "",
            "criado_em": ultimo["created_at"],
        }
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Música
# ---------------------------------------------------------------------------

def resumo_musica() -> dict | None:
    conn = database.get_connection("musica")
    if conn is None:
        return None
    try:
        escutas = pd.read_sql_query(
            """SELECT escutas.*, albuns.nome AS album_nome, albuns.capa_path AS album_capa_path,
                      albuns.genero AS album_genero, albuns.ano_lancamento AS album_ano,
                      artistas.nome AS artista_nome
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
            "ultimo_album": {
                "nome": ultima["album_nome"],
                "artista": ultima["artista_nome"],
                "genero": ultima["album_genero"] or "",
                "ano": int(ultima["album_ano"]) if pd.notna(ultima["album_ano"]) else None,
                "capa_path": ultima["album_capa_path"] or "",
            },
        }
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Contexto de hoje — o que vira a saudação por IA (nunca tendência/histórico,
# isso é trabalho do Analytics)
# ---------------------------------------------------------------------------

def contexto_hoje() -> str:
    """Resumo textual compacto só do AGORA — sem números agregados de meses
    passados. É isso que vira o contexto da saudação gerada por IA."""
    blocos = []

    fin = resumo_financeiro()
    if fin is not None:
        blocos.append(
            f"FINANCEIRO — pode gastar hoje: {utils.formatar_moeda(fin['por_dia'])}, "
            f"faltam {fin['dias_restantes']} dia(s) pro próximo pagamento."
        )

    tarefa = proxima_tarefa_projeto()
    if tarefa is not None:
        prazo_txt = f", prazo {tarefa['prazo']}" if tarefa["prazo"] else ""
        blocos.append(f"PROJETOS — próxima tarefa pendente: '{tarefa['descricao']}' ({tarefa['projeto_nome']}{prazo_txt}).")

    faltantes = habitos_faltantes_hoje()
    if faltantes is not None:
        txt = ", ".join(faltantes) if faltantes else "nenhum — todos cumpridos hoje"
        blocos.append(f"HÁBITOS — ainda faltam hoje: {txt}.")

    humor = resumo_humor()
    if humor is not None:
        if humor["registrado_hoje"]:
            tags_txt = ", ".join(humor["tags_hoje"]) if humor["tags_hoje"] else "sem tags"
            blocos.append(f"HUMOR — hoje: {humor['nota_hoje']}/10 ({tags_txt}).")
        else:
            blocos.append("HUMOR — ainda sem registro hoje.")

    livros = resumo_livros()
    if livros is not None and livros["lendo_agora"] > 0:
        nomes = ", ".join(l["nome"] for l in livros["livros_lendo"])
        blocos.append(f"LIVROS — lendo agora: {nomes}.")

    musica = resumo_musica()
    if musica is not None and musica["ultimo_album"]:
        album = musica["ultimo_album"]
        blocos.append(f"MÚSICA — último álbum ouvido: {album['nome']} — {album['artista']}.")

    if not blocos:
        return "Nenhum módulo tem dado suficiente ainda."
    return "\n".join(blocos)
