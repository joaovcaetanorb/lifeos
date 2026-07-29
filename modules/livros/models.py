"""Camada de acesso a dados (CRUD). Sem regra de negócio.

Funções de listagem retornam pandas.DataFrame (facilita uso direto em
gráficos e nas páginas). Funções de escrita retornam None ou o id criado.

A conexão (`get_connection()`) é compartilhada/cacheada (ver database.py) —
por isso nenhuma função aqui chama `conn.close()`.
"""

import pandas as pd
from database import get_connection, linha_para_dict

# ---------------------------------------------------------------------------
# Autores
# ---------------------------------------------------------------------------

def listar_autores() -> pd.DataFrame:
    conn = get_connection()
    return pd.read_sql_query("SELECT * FROM autores ORDER BY nome ASC", conn)


def obter_autor(autor_id: int) -> dict | None:
    conn = get_connection()
    cursor = conn.execute("SELECT * FROM autores WHERE id = ?", (autor_id,))
    return linha_para_dict(cursor, cursor.fetchone())


def buscar_autor_por_nome(nome: str) -> dict | None:
    conn = get_connection()
    cursor = conn.execute("SELECT * FROM autores WHERE nome = ? COLLATE NOCASE", (nome,))
    return linha_para_dict(cursor, cursor.fetchone())


def inserir_autor(nome: str) -> int:
    conn = get_connection()
    cur = conn.execute("INSERT INTO autores (nome) VALUES (?)", (nome,))
    conn.commit()
    return cur.lastrowid


def obter_ou_criar_autor(nome: str) -> int:
    """Reaproveita o autor se já existir (mesmo nome), senão cria."""
    existente = buscar_autor_por_nome(nome)
    if existente:
        return int(existente["id"])
    return inserir_autor(nome)


# ---------------------------------------------------------------------------
# Livros
# ---------------------------------------------------------------------------

def listar_livros() -> pd.DataFrame:
    """Livros com o nome do autor já resolvido (join), pra não precisar de
    N+1 consultas na tela de estante."""
    conn = get_connection()
    return pd.read_sql_query(
        """SELECT livros.*, autores.nome AS autor_nome
           FROM livros
           JOIN autores ON autores.id = livros.autor_id
           ORDER BY livros.created_at DESC, livros.id DESC""",
        conn,
    )


def obter_livro(livro_id: int) -> dict | None:
    conn = get_connection()
    cursor = conn.execute(
        """SELECT livros.*, autores.nome AS autor_nome
           FROM livros JOIN autores ON autores.id = livros.autor_id
           WHERE livros.id = ?""",
        (livro_id,),
    )
    return linha_para_dict(cursor, cursor.fetchone())


def favoritar_livro(livro_id: int, favorito: bool) -> None:
    conn = get_connection()
    conn.execute("UPDATE livros SET favorito = ? WHERE id = ?", (int(favorito), livro_id))
    conn.commit()


def buscar_livro_por_nome(nome: str, autor_id: int) -> dict | None:
    conn = get_connection()
    cursor = conn.execute(
        "SELECT * FROM livros WHERE nome = ? COLLATE NOCASE AND autor_id = ?",
        (nome, autor_id),
    )
    return linha_para_dict(cursor, cursor.fetchone())


def inserir_livro(nome: str, autor_id: int, ano_publicacao: int | None, genero: str = "",
                   capa_path: str = "") -> int:
    conn = get_connection()
    cur = conn.execute(
        """INSERT INTO livros (nome, autor_id, ano_publicacao, genero, capa_path)
           VALUES (?, ?, ?, ?, ?)""",
        (nome, autor_id, ano_publicacao, genero, capa_path),
    )
    conn.commit()
    return cur.lastrowid


def obter_ou_criar_livro(nome: str, autor_id: int, ano_publicacao: int | None, genero: str = "") -> int:
    """Reaproveita o livro se já existir pra esse autor (evita duplicar
    catálogo se o usuário reenviar o formulário sem trocar a seleção)."""
    existente = buscar_livro_por_nome(nome, autor_id)
    if existente:
        return int(existente["id"])
    return inserir_livro(nome, autor_id, ano_publicacao, genero)


def atualizar_livro(livro_id: int, nome: str, ano_publicacao: int | None, genero: str,
                     capa_path: str | None = None) -> None:
    """capa_path=None mantém a capa atual (não a apaga)."""
    conn = get_connection()
    if capa_path is None:
        conn.execute(
            "UPDATE livros SET nome = ?, ano_publicacao = ?, genero = ? WHERE id = ?",
            (nome, ano_publicacao, genero, livro_id),
        )
    else:
        conn.execute(
            "UPDATE livros SET nome = ?, ano_publicacao = ?, genero = ?, capa_path = ? WHERE id = ?",
            (nome, ano_publicacao, genero, capa_path, livro_id),
        )
    conn.commit()


def excluir_livro(livro_id: int) -> None:
    conn = get_connection()
    conn.execute("DELETE FROM livros WHERE id = ?", (livro_id,))
    conn.commit()


# ---------------------------------------------------------------------------
# Leituras
# ---------------------------------------------------------------------------

def listar_leituras(livro_id: int) -> pd.DataFrame:
    conn = get_connection()
    return pd.read_sql_query(
        "SELECT * FROM leituras WHERE livro_id = ? ORDER BY data DESC, id DESC",
        conn, params=[livro_id],
    )


def listar_leituras_com_livro() -> pd.DataFrame:
    """Todas as leituras já com livro e autor resolvidos (join) — usada
    pela timeline/diário, que não navega livro por livro."""
    conn = get_connection()
    return pd.read_sql_query(
        """SELECT leituras.*, livros.nome AS livro_nome, livros.capa_path,
                  autores.nome AS autor_nome
           FROM leituras
           JOIN livros ON livros.id = leituras.livro_id
           JOIN autores ON autores.id = livros.autor_id
           ORDER BY leituras.data DESC, leituras.id DESC""",
        conn,
    )


def inserir_leitura(livro_id: int, data: str, status: str, nota: float | None,
                     review: str = "") -> None:
    conn = get_connection()
    conn.execute(
        """INSERT INTO leituras (livro_id, data, status, nota, review)
           VALUES (?, ?, ?, ?, ?)""",
        (livro_id, data, status, nota, review),
    )
    conn.commit()


def atualizar_leitura(leitura_id: int, data: str, status: str, nota: float | None, review: str) -> None:
    conn = get_connection()
    conn.execute(
        "UPDATE leituras SET data = ?, status = ?, nota = ?, review = ? WHERE id = ?",
        (data, status, nota, review, leitura_id),
    )
    conn.commit()


def excluir_leitura(leitura_id: int) -> None:
    conn = get_connection()
    conn.execute("DELETE FROM leituras WHERE id = ?", (leitura_id,))
    conn.commit()


def intervalo_datas_leituras() -> tuple[str, str] | None:
    """(data mais antiga, data mais recente) entre todas as leituras, ou
    None se não há nenhuma."""
    conn = get_connection()
    row = conn.execute("SELECT MIN(data) AS minima, MAX(data) AS maxima FROM leituras").fetchone()
    if row is None or row[0] is None:
        return None
    return row[0], row[1]
