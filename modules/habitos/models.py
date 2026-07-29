"""Camada de acesso a dados (CRUD). Sem regra de negócio.

Funções de listagem retornam pandas.DataFrame (facilita uso direto em
gráficos e nas páginas). Funções de escrita retornam None ou o id criado.
"""

import pandas as pd
from database import get_connection

# ---------------------------------------------------------------------------
# Hábitos
# ---------------------------------------------------------------------------

def listar_habitos(somente_ativos: bool = True) -> pd.DataFrame:
    conn = get_connection()
    try:
        query = "SELECT * FROM habitos"
        if somente_ativos:
            query += " WHERE ativo = 1"
        query += " ORDER BY created_at ASC, id ASC"
        return pd.read_sql_query(query, conn)
    finally:
        conn.close()


def obter_habito(habito_id: int) -> dict | None:
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM habitos WHERE id = ?", (habito_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def inserir_habito(nome: str) -> int:
    conn = get_connection()
    try:
        cur = conn.execute("INSERT INTO habitos (nome, ativo) VALUES (?, 1)", (nome,))
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def atualizar_habito(habito_id: int, nome: str, ativo: bool) -> None:
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE habitos SET nome = ?, ativo = ? WHERE id = ?",
            (nome, int(ativo), habito_id),
        )
        conn.commit()
    finally:
        conn.close()


def excluir_habito(habito_id: int) -> None:
    conn = get_connection()
    try:
        conn.execute("DELETE FROM habitos WHERE id = ?", (habito_id,))
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Registros (dias marcados como cumpridos)
# ---------------------------------------------------------------------------

def esta_marcado(habito_id: int, data_iso: str) -> bool:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT 1 FROM habito_registros WHERE habito_id = ? AND data = ?",
            (habito_id, data_iso),
        ).fetchone()
        return row is not None
    finally:
        conn.close()


def marcar_dia(habito_id: int, data_iso: str) -> None:
    conn = get_connection()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO habito_registros (habito_id, data) VALUES (?, ?)",
            (habito_id, data_iso),
        )
        conn.commit()
    finally:
        conn.close()


def desmarcar_dia(habito_id: int, data_iso: str) -> None:
    conn = get_connection()
    try:
        conn.execute(
            "DELETE FROM habito_registros WHERE habito_id = ? AND data = ?",
            (habito_id, data_iso),
        )
        conn.commit()
    finally:
        conn.close()


def listar_registros(habito_id: int, data_inicio: str | None = None) -> pd.DataFrame:
    conn = get_connection()
    try:
        query = "SELECT * FROM habito_registros WHERE habito_id = ?"
        params = [habito_id]
        if data_inicio:
            query += " AND data >= ?"
            params.append(data_inicio)
        query += " ORDER BY data ASC"
        return pd.read_sql_query(query, conn, params=params)
    finally:
        conn.close()


def listar_registros_todos(data_inicio: str | None = None) -> pd.DataFrame:
    """Todos os registros já com o nome do hábito resolvido (join) — usada
    pelos cálculos que olham vários hábitos de uma vez."""
    conn = get_connection()
    try:
        query = """SELECT habito_registros.*, habitos.nome AS habito_nome
                   FROM habito_registros
                   JOIN habitos ON habitos.id = habito_registros.habito_id"""
        params = []
        if data_inicio:
            query += " WHERE habito_registros.data >= ?"
            params.append(data_inicio)
        query += " ORDER BY habito_registros.data ASC"
        return pd.read_sql_query(query, conn, params=params)
    finally:
        conn.close()
