"""Camada de acesso a dados (CRUD). Sem @st.cache_data (ver
webapp/musica/repo.py pro raciocínio completo)."""

import pandas as pd

from .db import get_connection, linha_para_dict

# ---------------------------------------------------------------------------
# Config (linha singleton id=1)
# ---------------------------------------------------------------------------

def get_config() -> dict:
    conn = get_connection()
    cursor = conn.execute("SELECT * FROM config WHERE id = 1")
    return linha_para_dict(cursor, cursor.fetchone())


def atualizar_config(salario: float, vale_alimentacao: float) -> None:
    conn = get_connection()
    conn.execute(
        "UPDATE config SET salario = ?, vale_alimentacao = ? WHERE id = 1",
        (salario, vale_alimentacao),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Contas fixas
# ---------------------------------------------------------------------------

def listar_contas_fixas(somente_ativas: bool = True) -> pd.DataFrame:
    conn = get_connection()
    query = "SELECT * FROM contas_fixas"
    if somente_ativas:
        query += " WHERE ativo = 1"
    query += " ORDER BY id ASC"
    return pd.read_sql_query(query, conn)


def obter_conta_fixa(conta_id: int) -> dict | None:
    conn = get_connection()
    cursor = conn.execute("SELECT * FROM contas_fixas WHERE id = ?", (conta_id,))
    return linha_para_dict(cursor, cursor.fetchone())


def inserir_conta_fixa(descricao: str, valor: float) -> int:
    conn = get_connection()
    cur = conn.execute(
        "INSERT INTO contas_fixas (descricao, valor, ativo) VALUES (?, ?, 1)", (descricao, valor),
    )
    conn.commit()
    return cur.lastrowid


def atualizar_conta_fixa(conta_id: int, descricao: str, valor: float, ativo: bool) -> None:
    conn = get_connection()
    conn.execute(
        "UPDATE contas_fixas SET descricao = ?, valor = ?, ativo = ? WHERE id = ?",
        (descricao, valor, int(ativo), conta_id),
    )
    conn.commit()


def excluir_conta_fixa(conta_id: int) -> None:
    conn = get_connection()
    conn.execute("DELETE FROM contas_fixas WHERE id = ?", (conta_id,))
    conn.commit()


# ---------------------------------------------------------------------------
# Gastos
# ---------------------------------------------------------------------------

def listar_gastos(data_inicio: str | None = None, data_fim: str | None = None) -> pd.DataFrame:
    conn = get_connection()
    query = "SELECT * FROM gastos"
    condicoes, params = [], []
    if data_inicio:
        condicoes.append("data >= ?")
        params.append(data_inicio)
    if data_fim:
        condicoes.append("data <= ?")
        params.append(data_fim)
    if condicoes:
        query += " WHERE " + " AND ".join(condicoes)
    query += " ORDER BY data DESC, id DESC"
    return pd.read_sql_query(query, conn, params=params)


def obter_gasto(gasto_id: int) -> dict | None:
    conn = get_connection()
    cursor = conn.execute("SELECT * FROM gastos WHERE id = ?", (gasto_id,))
    return linha_para_dict(cursor, cursor.fetchone())


def inserir_gasto(data: str, descricao: str, valor: float, categoria: str, forma_pagamento: str) -> int:
    conn = get_connection()
    cur = conn.execute(
        "INSERT INTO gastos (data, descricao, valor, categoria, forma_pagamento) VALUES (?, ?, ?, ?, ?)",
        (data, descricao, valor, categoria, forma_pagamento),
    )
    conn.commit()
    return cur.lastrowid


def excluir_gasto(gasto_id: int) -> None:
    conn = get_connection()
    conn.execute("DELETE FROM gastos WHERE id = ?", (gasto_id,))
    conn.commit()


# ---------------------------------------------------------------------------
# Receitas extras (freelance / renda ocasional)
# ---------------------------------------------------------------------------

def listar_receitas_extras(data_inicio: str | None = None, data_fim: str | None = None) -> pd.DataFrame:
    conn = get_connection()
    query = "SELECT * FROM receitas_extras"
    condicoes, params = [], []
    if data_inicio:
        condicoes.append("data >= ?")
        params.append(data_inicio)
    if data_fim:
        condicoes.append("data <= ?")
        params.append(data_fim)
    if condicoes:
        query += " WHERE " + " AND ".join(condicoes)
    query += " ORDER BY data DESC, id DESC"
    return pd.read_sql_query(query, conn, params=params)


def obter_receita_extra(receita_id: int) -> dict | None:
    conn = get_connection()
    cursor = conn.execute("SELECT * FROM receitas_extras WHERE id = ?", (receita_id,))
    return linha_para_dict(cursor, cursor.fetchone())


def inserir_receita_extra(data: str, descricao: str, valor: float) -> int:
    conn = get_connection()
    cur = conn.execute(
        "INSERT INTO receitas_extras (data, descricao, valor) VALUES (?, ?, ?)", (data, descricao, valor),
    )
    conn.commit()
    return cur.lastrowid


def excluir_receita_extra(receita_id: int) -> None:
    conn = get_connection()
    conn.execute("DELETE FROM receitas_extras WHERE id = ?", (receita_id,))
    conn.commit()


# ---------------------------------------------------------------------------
# Cofre (reserva_movimentos)
# ---------------------------------------------------------------------------

def listar_movimentos_reserva(data_inicio: str | None = None, data_fim: str | None = None) -> pd.DataFrame:
    conn = get_connection()
    query = "SELECT * FROM reserva_movimentos"
    condicoes, params = [], []
    if data_inicio:
        condicoes.append("data >= ?")
        params.append(data_inicio)
    if data_fim:
        condicoes.append("data <= ?")
        params.append(data_fim)
    if condicoes:
        query += " WHERE " + " AND ".join(condicoes)
    query += " ORDER BY data DESC, id DESC"
    return pd.read_sql_query(query, conn, params=params)


def obter_movimento_reserva(movimento_id: int) -> dict | None:
    conn = get_connection()
    cursor = conn.execute("SELECT * FROM reserva_movimentos WHERE id = ?", (movimento_id,))
    return linha_para_dict(cursor, cursor.fetchone())


def inserir_movimento_reserva(data: str, valor: float, tipo: str, observacao: str = "") -> int:
    conn = get_connection()
    cur = conn.execute(
        "INSERT INTO reserva_movimentos (data, valor, tipo, observacao) VALUES (?, ?, ?, ?)",
        (data, valor, tipo, observacao),
    )
    conn.commit()
    return cur.lastrowid


def excluir_movimento_reserva(movimento_id: int) -> None:
    conn = get_connection()
    conn.execute("DELETE FROM reserva_movimentos WHERE id = ?", (movimento_id,))
    conn.commit()
