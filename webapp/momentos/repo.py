"""Camada de acesso a dados (CRUD). Sem calculations.py separado — este
módulo não tem lógica de negócio nenhuma, só registro e leitura."""

from datetime import datetime

import pandas as pd

from .db import get_connection, linha_para_dict

CATEGORIAS_MOMENTO = {
    "Social": "🎉",
    "Saúde": "🏃",
    "Lazer": "🎨",
    "Trabalho": "💼",
    "Família/Amigos": "👥",
    "Amor": "❤️",
    "Outro": "📝",
}


def listar_momentos(data_inicio: str | None = None, data_fim: str | None = None) -> pd.DataFrame:
    conn = get_connection()
    query = "SELECT * FROM momentos"
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


def obter_momento(momento_id: int) -> dict | None:
    conn = get_connection()
    cursor = conn.execute("SELECT * FROM momentos WHERE id = ?", (momento_id,))
    return linha_para_dict(cursor, cursor.fetchone())


def inserir_momento(texto: str, categoria: str, data: str | None = None, hora: str | None = None) -> int:
    agora = datetime.now()
    data = data or agora.strftime("%Y-%m-%d")
    hora = hora if hora is not None else agora.strftime("%H:%M")
    conn = get_connection()
    cur = conn.execute(
        "INSERT INTO momentos (data, hora, texto, categoria) VALUES (?, ?, ?, ?)",
        (data, hora, texto, categoria),
    )
    conn.commit()
    return cur.lastrowid


def excluir_momento(momento_id: int) -> None:
    conn = get_connection()
    conn.execute("DELETE FROM momentos WHERE id = ?", (momento_id,))
    conn.commit()
