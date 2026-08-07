"""Camada de acesso a dados (CRUD). Sem regra de negócio.

Funções de listagem retornam pandas.DataFrame (facilita uso direto em
gráficos e nas páginas). Funções de escrita retornam None ou o id criado.

A conexão (`get_connection()`) é compartilhada/cacheada (ver database.py) —
por isso nenhuma função aqui chama `conn.close()`: fechar quebraria a
conexão pra todas as chamadas seguintes da mesma sessão.
"""

import pandas as pd
import streamlit as st
from database import get_connection, linha_para_dict

# ---------------------------------------------------------------------------
# Hábitos
# ---------------------------------------------------------------------------

@st.cache_data(show_spinner=False)
def listar_habitos(somente_ativos: bool = True) -> pd.DataFrame:
    conn = get_connection()
    query = "SELECT * FROM habitos"
    if somente_ativos:
        query += " WHERE ativo = 1"
    query += " ORDER BY created_at ASC, id ASC"
    return pd.read_sql_query(query, conn)


@st.cache_data(show_spinner=False)
def obter_habito(habito_id: int) -> dict | None:
    conn = get_connection()
    cursor = conn.execute("SELECT * FROM habitos WHERE id = ?", (habito_id,))
    return linha_para_dict(cursor, cursor.fetchone())


def inserir_habito(nome: str) -> int:
    conn = get_connection()
    cur = conn.execute("INSERT INTO habitos (nome, ativo) VALUES (?, 1)", (nome,))
    conn.commit()
    st.cache_data.clear()
    return cur.lastrowid


def atualizar_habito(habito_id: int, nome: str, ativo: bool) -> None:
    conn = get_connection()
    conn.execute(
        "UPDATE habitos SET nome = ?, ativo = ? WHERE id = ?",
        (nome, int(ativo), habito_id),
    )
    conn.commit()
    st.cache_data.clear()


def excluir_habito(habito_id: int) -> None:
    conn = get_connection()
    conn.execute("DELETE FROM habitos WHERE id = ?", (habito_id,))
    conn.commit()
    st.cache_data.clear()


# ---------------------------------------------------------------------------
# Registros (dias marcados como cumpridos)
# ---------------------------------------------------------------------------

@st.cache_data(show_spinner=False)
def esta_marcado(habito_id: int, data_iso: str) -> bool:
    conn = get_connection()
    row = conn.execute(
        "SELECT 1 FROM habito_registros WHERE habito_id = ? AND data = ?",
        (habito_id, data_iso),
    ).fetchone()
    return row is not None


def marcar_dia(habito_id: int, data_iso: str) -> None:
    conn = get_connection()
    conn.execute(
        "INSERT OR IGNORE INTO habito_registros (habito_id, data) VALUES (?, ?)",
        (habito_id, data_iso),
    )
    conn.commit()
    st.cache_data.clear()


def desmarcar_dia(habito_id: int, data_iso: str) -> None:
    conn = get_connection()
    conn.execute(
        "DELETE FROM habito_registros WHERE habito_id = ? AND data = ?",
        (habito_id, data_iso),
    )
    conn.commit()
    st.cache_data.clear()


@st.cache_data(show_spinner=False)
def listar_registros(habito_id: int, data_inicio: str | None = None, data_fim: str | None = None) -> pd.DataFrame:
    conn = get_connection()
    query = "SELECT * FROM habito_registros WHERE habito_id = ?"
    params = [habito_id]
    if data_inicio:
        query += " AND data >= ?"
        params.append(data_inicio)
    if data_fim:
        query += " AND data <= ?"
        params.append(data_fim)
    query += " ORDER BY data ASC"
    return pd.read_sql_query(query, conn, params=params)


@st.cache_data(show_spinner=False)
def listar_registros_todos(data_inicio: str | None = None, data_fim: str | None = None) -> pd.DataFrame:
    """Todos os registros já com o nome do hábito resolvido (join) — usada
    pelos cálculos que olham vários hábitos de uma vez."""
    conn = get_connection()
    query = """SELECT habito_registros.*, habitos.nome AS habito_nome
               FROM habito_registros
               JOIN habitos ON habitos.id = habito_registros.habito_id"""
    condicoes, params = [], []
    if data_inicio:
        condicoes.append("habito_registros.data >= ?")
        params.append(data_inicio)
    if data_fim:
        condicoes.append("habito_registros.data <= ?")
        params.append(data_fim)
    if condicoes:
        query += " WHERE " + " AND ".join(condicoes)
    query += " ORDER BY habito_registros.data ASC"
    return pd.read_sql_query(query, conn, params=params)


@st.cache_data(show_spinner=False)
def intervalo_datas_registros() -> tuple[str, str] | None:
    """(data mais antiga, data mais recente) entre todos os registros, ou
    None se não há nenhum."""
    conn = get_connection()
    row = conn.execute(
        "SELECT MIN(data) AS minima, MAX(data) AS maxima FROM habito_registros"
    ).fetchone()
    if row is None or row[0] is None:
        return None
    return row[0], row[1]
