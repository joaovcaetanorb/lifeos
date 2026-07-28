"""Camada de acesso a dados (CRUD). Sem regra de negócio.

Funções de listagem retornam pandas.DataFrame (facilita uso direto em
gráficos e nas páginas). Funções de escrita retornam None ou o id criado.
"""

import pandas as pd
from database import get_connection

# ---------------------------------------------------------------------------
# Artistas
# ---------------------------------------------------------------------------

def listar_artistas() -> pd.DataFrame:
    conn = get_connection()
    try:
        return pd.read_sql_query("SELECT * FROM artistas ORDER BY nome ASC", conn)
    finally:
        conn.close()


def obter_artista(artista_id: int) -> dict | None:
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM artistas WHERE id = ?", (artista_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def buscar_artista_por_nome(nome: str) -> dict | None:
    """Busca exata (case-insensitive) — usada pra evitar duplicar artista
    ao cadastrar um álbum novo."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM artistas WHERE nome = ? COLLATE NOCASE", (nome,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def inserir_artista(nome: str, spotify_id: str = "") -> int:
    conn = get_connection()
    try:
        cur = conn.execute(
            "INSERT INTO artistas (nome, spotify_id) VALUES (?, ?)", (nome, spotify_id)
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def obter_ou_criar_artista(nome: str, spotify_id: str = "") -> int:
    """Reaproveita o artista se já existir (mesmo nome), senão cria."""
    existente = buscar_artista_por_nome(nome)
    if existente:
        return int(existente["id"])
    return inserir_artista(nome, spotify_id)


# ---------------------------------------------------------------------------
# Álbuns
# ---------------------------------------------------------------------------

def listar_albuns() -> pd.DataFrame:
    """Álbuns com o nome do artista já resolvido (join), pra não precisar
    de N+1 consultas na tela de catálogo."""
    conn = get_connection()
    try:
        return pd.read_sql_query(
            """SELECT albuns.*, artistas.nome AS artista_nome
               FROM albuns
               JOIN artistas ON artistas.id = albuns.artista_id
               ORDER BY albuns.created_at DESC, albuns.id DESC""",
            conn,
        )
    finally:
        conn.close()


def obter_album(album_id: int) -> dict | None:
    conn = get_connection()
    try:
        row = conn.execute(
            """SELECT albuns.*, artistas.nome AS artista_nome
               FROM albuns JOIN artistas ON artistas.id = albuns.artista_id
               WHERE albuns.id = ?""",
            (album_id,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def inserir_album(nome: str, artista_id: int, ano_lancamento: int | None, genero: str = "",
                   capa_path: str = "", spotify_id: str = "", spotify_url: str = "") -> int:
    conn = get_connection()
    try:
        cur = conn.execute(
            """INSERT INTO albuns (nome, artista_id, ano_lancamento, genero, capa_path, spotify_id, spotify_url)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (nome, artista_id, ano_lancamento, genero, capa_path, spotify_id, spotify_url),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def atualizar_album(album_id: int, nome: str, ano_lancamento: int | None, genero: str,
                     capa_path: str | None = None) -> None:
    """capa_path=None mantém a capa atual (não a apaga)."""
    conn = get_connection()
    try:
        if capa_path is None:
            conn.execute(
                "UPDATE albuns SET nome = ?, ano_lancamento = ?, genero = ? WHERE id = ?",
                (nome, ano_lancamento, genero, album_id),
            )
        else:
            conn.execute(
                "UPDATE albuns SET nome = ?, ano_lancamento = ?, genero = ?, capa_path = ? WHERE id = ?",
                (nome, ano_lancamento, genero, capa_path, album_id),
            )
        conn.commit()
    finally:
        conn.close()


def buscar_album_por_nome(nome: str, artista_id: int) -> dict | None:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM albuns WHERE nome = ? COLLATE NOCASE AND artista_id = ?",
            (nome, artista_id),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def obter_ou_criar_album(nome: str, artista_id: int, ano_lancamento: int | None, genero: str = "",
                          spotify_id: str = "", spotify_url: str = "") -> int:
    """Reaproveita o álbum se já existir pra esse artista (evita duplicar
    catálogo se o usuário reenviar o formulário sem trocar a seleção)."""
    existente = buscar_album_por_nome(nome, artista_id)
    if existente:
        return int(existente["id"])
    return inserir_album(nome, artista_id, ano_lancamento, genero, spotify_id=spotify_id, spotify_url=spotify_url)


def excluir_album(album_id: int) -> None:
    conn = get_connection()
    try:
        conn.execute("DELETE FROM albuns WHERE id = ?", (album_id,))
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Escutas
# ---------------------------------------------------------------------------

def listar_escutas(album_id: int) -> pd.DataFrame:
    conn = get_connection()
    try:
        return pd.read_sql_query(
            "SELECT * FROM escutas WHERE album_id = ? ORDER BY data DESC, id DESC",
            conn, params=[album_id],
        )
    finally:
        conn.close()


def listar_escutas_com_album() -> pd.DataFrame:
    """Todas as escutas já com álbum e artista resolvidos (join) — usada
    pela timeline/diário, que não navega álbum por álbum."""
    conn = get_connection()
    try:
        return pd.read_sql_query(
            """SELECT escutas.*, albuns.nome AS album_nome, albuns.capa_path,
                      albuns.spotify_id AS album_spotify_id, artistas.nome AS artista_nome
               FROM escutas
               JOIN albuns ON albuns.id = escutas.album_id
               JOIN artistas ON artistas.id = albuns.artista_id
               ORDER BY escutas.data DESC, escutas.id DESC""",
            conn,
        )
    finally:
        conn.close()


def intervalo_datas_escutas() -> tuple[str, str] | None:
    """(data mais antiga, data mais recente) entre todas as escutas, ou
    None se não há nenhuma — usado pra resolver "todos os tempos" com
    datas reais em vez de sentinelas arbitrárias."""
    conn = get_connection()
    try:
        row = conn.execute("SELECT MIN(data) AS minima, MAX(data) AS maxima FROM escutas").fetchone()
        if row is None or row["minima"] is None:
            return None
        return row["minima"], row["maxima"]
    finally:
        conn.close()


def inserir_escuta(album_id: int, data: str, nota: float | None, review: str = "",
                    faixa_favorita: str = "") -> None:
    conn = get_connection()
    try:
        conn.execute(
            """INSERT INTO escutas (album_id, data, nota, review, faixa_favorita)
               VALUES (?, ?, ?, ?, ?)""",
            (album_id, data, nota, review, faixa_favorita),
        )
        conn.commit()
    finally:
        conn.close()


def atualizar_escuta(escuta_id: int, data: str, nota: float | None, review: str,
                      faixa_favorita: str) -> None:
    conn = get_connection()
    try:
        conn.execute(
            """UPDATE escutas SET data = ?, nota = ?, review = ?, faixa_favorita = ?
               WHERE id = ?""",
            (data, nota, review, faixa_favorita, escuta_id),
        )
        conn.commit()
    finally:
        conn.close()


def excluir_escuta(escuta_id: int) -> None:
    conn = get_connection()
    try:
        conn.execute("DELETE FROM escutas WHERE id = ?", (escuta_id,))
        conn.commit()
    finally:
        conn.close()
