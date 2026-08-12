"""Camada de acesso a dados (CRUD). Sem regra de negócio.

Port de modules/livros/models.py — mesmas queries, sem @st.cache_data (ver
webapp/musica/repo.py pro raciocínio completo, idêntico aqui).
"""

import pandas as pd

from .db import get_connection, linha_para_dict

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
    existente = buscar_autor_por_nome(nome)
    if existente:
        return int(existente["id"])
    return inserir_autor(nome)


# ---------------------------------------------------------------------------
# Livros
# ---------------------------------------------------------------------------

_COLUNAS_LIVRO = (
    "livros.id, livros.nome, livros.autor_id, livros.ano_publicacao, livros.genero, "
    "livros.capa_mime, livros.favorito, livros.created_at"
)


def listar_livros() -> pd.DataFrame:
    """Não traz `capa_dados` (BLOB) — ver obter_capa_livro() pra servir a
    capa sob demanda."""
    conn = get_connection()
    return pd.read_sql_query(
        f"""SELECT {_COLUNAS_LIVRO}, autores.nome AS autor_nome
           FROM livros
           JOIN autores ON autores.id = livros.autor_id
           ORDER BY livros.created_at DESC, livros.id DESC""",
        conn,
    )


def obter_livro(livro_id: int) -> dict | None:
    conn = get_connection()
    cursor = conn.execute(
        f"""SELECT {_COLUNAS_LIVRO}, autores.nome AS autor_nome
           FROM livros JOIN autores ON autores.id = livros.autor_id
           WHERE livros.id = ?""",
        (livro_id,),
    )
    return linha_para_dict(cursor, cursor.fetchone())


def obter_capa_livro(livro_id: int) -> tuple[bytes, str] | None:
    conn = get_connection()
    cursor = conn.execute("SELECT capa_dados, capa_mime FROM livros WHERE id = ?", (livro_id,))
    row = cursor.fetchone()
    if row is None or row[0] is None:
        return None
    return row[0], row[1] or "image/jpeg"


def favoritar_livro(livro_id: int, favorito: bool) -> None:
    conn = get_connection()
    conn.execute("UPDATE livros SET favorito = ? WHERE id = ?", (int(favorito), livro_id))
    conn.commit()


def buscar_livro_por_nome(nome: str, autor_id: int) -> dict | None:
    conn = get_connection()
    cursor = conn.execute(
        f"SELECT {_COLUNAS_LIVRO.replace('livros.', '')} FROM livros "
        "WHERE nome = ? COLLATE NOCASE AND autor_id = ?",
        (nome, autor_id),
    )
    return linha_para_dict(cursor, cursor.fetchone())


def inserir_livro(nome: str, autor_id: int, ano_publicacao: int | None, genero: str = "",
                   capa_dados: bytes | None = None, capa_mime: str | None = None) -> int:
    conn = get_connection()
    cur = conn.execute(
        """INSERT INTO livros (nome, autor_id, ano_publicacao, genero, capa_dados, capa_mime)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (nome, autor_id, ano_publicacao, genero, capa_dados, capa_mime),
    )
    conn.commit()
    return cur.lastrowid


def obter_ou_criar_livro(nome: str, autor_id: int, ano_publicacao: int | None, genero: str = "") -> int:
    existente = buscar_livro_por_nome(nome, autor_id)
    if existente:
        return int(existente["id"])
    return inserir_livro(nome, autor_id, ano_publicacao, genero)


def atualizar_livro(livro_id: int, nome: str, ano_publicacao: int | None, genero: str,
                     capa_dados: bytes | None = None, capa_mime: str | None = None) -> None:
    """capa_dados=None mantém a capa atual — mesmo sentinela de
    webapp/musica/repo.py::atualizar_album."""
    conn = get_connection()
    if capa_dados is None:
        conn.execute(
            "UPDATE livros SET nome = ?, ano_publicacao = ?, genero = ? WHERE id = ?",
            (nome, ano_publicacao, genero, livro_id),
        )
    else:
        conn.execute(
            "UPDATE livros SET nome = ?, ano_publicacao = ?, genero = ?, capa_dados = ?, capa_mime = ? WHERE id = ?",
            (nome, ano_publicacao, genero, capa_dados, capa_mime, livro_id),
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
    conn = get_connection()
    return pd.read_sql_query(
        """SELECT leituras.*, livros.nome AS livro_nome, livros.capa_mime,
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
    conn = get_connection()
    row = conn.execute("SELECT MIN(data) AS minima, MAX(data) AS maxima FROM leituras").fetchone()
    if row is None or row[0] is None:
        return None
    return row[0], row[1]
