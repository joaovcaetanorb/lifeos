"""Camada de acesso a dados (CRUD). Sem regra de negócio.

Funções de listagem retornam pandas.DataFrame (facilita uso direto em
gráficos e nas páginas). Funções de escrita retornam None ou o id criado.
"""

import pandas as pd
from database import get_connection

# ---------------------------------------------------------------------------
# Projetos
# ---------------------------------------------------------------------------

def listar_projetos(status: str | None = None) -> pd.DataFrame:
    conn = get_connection()
    try:
        query = "SELECT * FROM projetos"
        params = []
        if status:
            query += " WHERE status = ?"
            params.append(status)
        query += " ORDER BY created_at DESC, id DESC"
        return pd.read_sql_query(query, conn, params=params)
    finally:
        conn.close()


def obter_projeto(projeto_id: int) -> dict | None:
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM projetos WHERE id = ?", (projeto_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def inserir_projeto(nome: str, descricao: str, orcamento: float, observacoes: str,
                     foto_path: str = "") -> int:
    conn = get_connection()
    try:
        cur = conn.execute(
            """INSERT INTO projetos (nome, descricao, orcamento, observacoes, foto_path)
               VALUES (?, ?, ?, ?, ?)""",
            (nome, descricao, orcamento, observacoes, foto_path),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def atualizar_projeto(projeto_id: int, nome: str, descricao: str, orcamento: float,
                       observacoes: str, status: str, foto_path: str | None = None) -> None:
    conn = get_connection()
    try:
        if foto_path is None:
            conn.execute(
                """UPDATE projetos SET nome = ?, descricao = ?, orcamento = ?,
                   observacoes = ?, status = ? WHERE id = ?""",
                (nome, descricao, orcamento, observacoes, status, projeto_id),
            )
        else:
            conn.execute(
                """UPDATE projetos SET nome = ?, descricao = ?, orcamento = ?,
                   observacoes = ?, status = ?, foto_path = ? WHERE id = ?""",
                (nome, descricao, orcamento, observacoes, status, foto_path, projeto_id),
            )
        conn.commit()
    finally:
        conn.close()


def excluir_projeto(projeto_id: int) -> None:
    conn = get_connection()
    try:
        conn.execute("DELETE FROM projetos WHERE id = ?", (projeto_id,))
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Checklist
# ---------------------------------------------------------------------------

def listar_checklist(projeto_id: int) -> pd.DataFrame:
    conn = get_connection()
    try:
        return pd.read_sql_query(
            "SELECT * FROM projeto_checklist WHERE projeto_id = ? ORDER BY ordem ASC, id ASC",
            conn, params=[projeto_id],
        )
    finally:
        conn.close()


def inserir_item_checklist(projeto_id: int, descricao: str) -> None:
    conn = get_connection()
    try:
        proxima_ordem = conn.execute(
            "SELECT COALESCE(MAX(ordem), -1) + 1 AS n FROM projeto_checklist WHERE projeto_id = ?",
            (projeto_id,),
        ).fetchone()["n"]
        conn.execute(
            "INSERT INTO projeto_checklist (projeto_id, descricao, ordem) VALUES (?, ?, ?)",
            (projeto_id, descricao, proxima_ordem),
        )
        conn.commit()
    finally:
        conn.close()


def marcar_item_checklist(item_id: int, concluido: bool) -> None:
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE projeto_checklist SET concluido = ? WHERE id = ?",
            (int(concluido), item_id),
        )
        conn.commit()
    finally:
        conn.close()


def excluir_item_checklist(item_id: int) -> None:
    conn = get_connection()
    try:
        conn.execute("DELETE FROM projeto_checklist WHERE id = ?", (item_id,))
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Aportes
# ---------------------------------------------------------------------------

def listar_aportes(projeto_id: int) -> pd.DataFrame:
    conn = get_connection()
    try:
        return pd.read_sql_query(
            "SELECT * FROM projeto_aportes WHERE projeto_id = ? ORDER BY data DESC, id DESC",
            conn, params=[projeto_id],
        )
    finally:
        conn.close()


def inserir_aporte(projeto_id: int, data: str, valor: float, observacao: str = "") -> None:
    conn = get_connection()
    try:
        conn.execute(
            """INSERT INTO projeto_aportes (projeto_id, data, valor, observacao)
               VALUES (?, ?, ?, ?)""",
            (projeto_id, data, valor, observacao),
        )
        conn.commit()
    finally:
        conn.close()


def excluir_aporte(aporte_id: int) -> None:
    conn = get_connection()
    try:
        conn.execute("DELETE FROM projeto_aportes WHERE id = ?", (aporte_id,))
        conn.commit()
    finally:
        conn.close()
