"""Camada de acesso a dados (CRUD). Sem regra de negócio.

Funções de listagem retornam pandas.DataFrame (facilita uso direto em
gráficos e nas páginas). Funções de escrita retornam None ou o id criado.

A conexão (`get_connection()`) é compartilhada/cacheada (ver database.py) —
por isso nenhuma função aqui chama `conn.close()`.
"""

import pandas as pd
from database import get_connection, linha_para_dict

# ---------------------------------------------------------------------------
# Projetos
# ---------------------------------------------------------------------------

def listar_projetos(status: str | None = None) -> pd.DataFrame:
    conn = get_connection()
    query = "SELECT * FROM projetos"
    params = []
    if status:
        query += " WHERE status = ?"
        params.append(status)
    query += " ORDER BY created_at DESC, id DESC"
    return pd.read_sql_query(query, conn, params=params)


def obter_projeto(projeto_id: int) -> dict | None:
    conn = get_connection()
    cursor = conn.execute("SELECT * FROM projetos WHERE id = ?", (projeto_id,))
    return linha_para_dict(cursor, cursor.fetchone())


def inserir_projeto(nome: str, descricao: str, orcamento: float, observacoes: str,
                     foto_path: str = "") -> int:
    conn = get_connection()
    cur = conn.execute(
        """INSERT INTO projetos (nome, descricao, orcamento, observacoes, foto_path)
           VALUES (?, ?, ?, ?, ?)""",
        (nome, descricao, orcamento, observacoes, foto_path),
    )
    conn.commit()
    return cur.lastrowid


def atualizar_projeto(projeto_id: int, nome: str, descricao: str, orcamento: float,
                       observacoes: str, status: str, foto_path: str | None = None) -> None:
    conn = get_connection()
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


def excluir_projeto(projeto_id: int) -> None:
    conn = get_connection()
    conn.execute("DELETE FROM projetos WHERE id = ?", (projeto_id,))
    conn.commit()


# ---------------------------------------------------------------------------
# Checklist
# ---------------------------------------------------------------------------

def listar_checklist(projeto_id: int) -> pd.DataFrame:
    conn = get_connection()
    return pd.read_sql_query(
        "SELECT * FROM projeto_checklist WHERE projeto_id = ? ORDER BY ordem ASC, id ASC",
        conn, params=[projeto_id],
    )


def inserir_item_checklist(projeto_id: int, descricao: str) -> None:
    conn = get_connection()
    proxima_ordem = conn.execute(
        "SELECT COALESCE(MAX(ordem), -1) + 1 AS n FROM projeto_checklist WHERE projeto_id = ?",
        (projeto_id,),
    ).fetchone()[0]
    conn.execute(
        "INSERT INTO projeto_checklist (projeto_id, descricao, ordem) VALUES (?, ?, ?)",
        (projeto_id, descricao, proxima_ordem),
    )
    conn.commit()


def marcar_item_checklist(item_id: int, concluido: bool) -> None:
    conn = get_connection()
    conn.execute(
        "UPDATE projeto_checklist SET concluido = ? WHERE id = ?",
        (int(concluido), item_id),
    )
    conn.commit()


def atualizar_detalhes_item_checklist(item_id: int, notas: str, prazo: str, link: str,
                                       foto_path: str | None = None) -> None:
    """foto_path=None mantém a foto atual (não a apaga); '' remove a foto."""
    conn = get_connection()
    if foto_path is None:
        conn.execute(
            "UPDATE projeto_checklist SET notas = ?, prazo = ?, link = ? WHERE id = ?",
            (notas, prazo, link, item_id),
        )
    else:
        conn.execute(
            "UPDATE projeto_checklist SET notas = ?, prazo = ?, link = ?, foto_path = ? WHERE id = ?",
            (notas, prazo, link, foto_path, item_id),
        )
    conn.commit()


def excluir_item_checklist(item_id: int) -> None:
    conn = get_connection()
    conn.execute("DELETE FROM projeto_checklist WHERE id = ?", (item_id,))
    conn.commit()


# ---------------------------------------------------------------------------
# Aportes
# ---------------------------------------------------------------------------

def listar_aportes(projeto_id: int) -> pd.DataFrame:
    conn = get_connection()
    return pd.read_sql_query(
        "SELECT * FROM projeto_aportes WHERE projeto_id = ? ORDER BY data DESC, id DESC",
        conn, params=[projeto_id],
    )


def inserir_aporte(projeto_id: int, data: str, valor: float, observacao: str = "") -> None:
    conn = get_connection()
    conn.execute(
        """INSERT INTO projeto_aportes (projeto_id, data, valor, observacao)
           VALUES (?, ?, ?, ?)""",
        (projeto_id, data, valor, observacao),
    )
    conn.commit()


def excluir_aporte(aporte_id: int) -> None:
    conn = get_connection()
    conn.execute("DELETE FROM projeto_aportes WHERE id = ?", (aporte_id,))
    conn.commit()
