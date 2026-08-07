"""Camada de acesso a dados (CRUD). Sem regra de negócio.

Funções de listagem retornam pandas.DataFrame (facilita uso direto em
gráficos e nas páginas). Funções de escrita retornam None ou o id criado.

A conexão (`get_connection()`) é compartilhada/cacheada (ver database.py) —
por isso nenhuma função aqui chama `conn.close()`.
"""

import pandas as pd
import streamlit as st
from database import get_connection, linha_para_dict


@st.cache_data(show_spinner=False)
def listar_registros(data_inicio: str | None = None, data_fim: str | None = None) -> pd.DataFrame:
    conn = get_connection()
    query = "SELECT * FROM registros_humor"
    condicoes, params = [], []
    if data_inicio:
        condicoes.append("data >= ?")
        params.append(data_inicio)
    if data_fim:
        condicoes.append("data <= ?")
        params.append(data_fim)
    if condicoes:
        query += " WHERE " + " AND ".join(condicoes)
    query += " ORDER BY data DESC, hora DESC, id DESC"
    return pd.read_sql_query(query, conn, params=params)


@st.cache_data(show_spinner=False)
def obter_registro(registro_id: int) -> dict | None:
    conn = get_connection()
    cursor = conn.execute("SELECT * FROM registros_humor WHERE id = ?", (registro_id,))
    return linha_para_dict(cursor, cursor.fetchone())


def inserir_registro(data: str, hora: str, nota: int, tags: str, nota_livre: str = "") -> int:
    conn = get_connection()
    cur = conn.execute(
        """INSERT INTO registros_humor (data, hora, nota, tags, nota_livre)
           VALUES (?, ?, ?, ?, ?)""",
        (data, hora, nota, tags, nota_livre),
    )
    conn.commit()
    st.cache_data.clear()
    return cur.lastrowid


def atualizar_registro(registro_id: int, data: str, hora: str, nota: int, tags: str, nota_livre: str) -> None:
    conn = get_connection()
    conn.execute(
        """UPDATE registros_humor SET data = ?, hora = ?, nota = ?, tags = ?, nota_livre = ?
           WHERE id = ?""",
        (data, hora, nota, tags, nota_livre, registro_id),
    )
    conn.commit()
    st.cache_data.clear()


def excluir_registro(registro_id: int) -> None:
    conn = get_connection()
    conn.execute("DELETE FROM registros_humor WHERE id = ?", (registro_id,))
    conn.commit()
    st.cache_data.clear()


@st.cache_data(show_spinner=False)
def intervalo_datas_registros() -> tuple[str, str] | None:
    """(data mais antiga, data mais recente) entre todos os registros, ou
    None se não há nenhum."""
    conn = get_connection()
    row = conn.execute("SELECT MIN(data) AS minima, MAX(data) AS maxima FROM registros_humor").fetchone()
    if row is None or row[0] is None:
        return None
    return row[0], row[1]
