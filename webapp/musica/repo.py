"""Camada de acesso a dados (CRUD). Sem regra de negócio.

Port de modules/musica/models.py: mesmas funções, mesmas queries. Única
diferença é a ausência de @st.cache_data/st.cache_resource — o Streamlit
original cacheava por sessão de script e limpava TUDO (`st.cache_data.clear()`,
indiscriminado) a cada escrita; aqui cada request já é isolado e o custo de
round-trip pro Turso (embedded replica, leitura local) é baixo o bastante
pra não precisar de cache nesta fase.

Funções de listagem retornam pandas.DataFrame; funções de escrita retornam
None ou o id criado — mesmo contrato do original, pra facilitar comparar.
"""

import json

import pandas as pd

from .db import get_connection, linha_para_dict

# ---------------------------------------------------------------------------
# Artistas
# ---------------------------------------------------------------------------

def listar_artistas() -> pd.DataFrame:
    conn = get_connection()
    return pd.read_sql_query("SELECT * FROM artistas ORDER BY nome ASC", conn)


def obter_artista(artista_id: int) -> dict | None:
    conn = get_connection()
    cursor = conn.execute("SELECT * FROM artistas WHERE id = ?", (artista_id,))
    return linha_para_dict(cursor, cursor.fetchone())


def buscar_artista_por_nome(nome: str) -> dict | None:
    """Busca exata (case-insensitive) — usada pra evitar duplicar artista
    ao cadastrar um álbum novo."""
    conn = get_connection()
    cursor = conn.execute("SELECT * FROM artistas WHERE nome = ? COLLATE NOCASE", (nome,))
    return linha_para_dict(cursor, cursor.fetchone())


def inserir_artista(nome: str, spotify_id: str = "") -> int:
    conn = get_connection()
    cur = conn.execute(
        "INSERT INTO artistas (nome, spotify_id) VALUES (?, ?)", (nome, spotify_id)
    )
    conn.commit()
    return cur.lastrowid


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
    """Álbuns com o nome do artista já resolvido (join)."""
    conn = get_connection()
    return pd.read_sql_query(
        """SELECT albuns.*, artistas.nome AS artista_nome
           FROM albuns
           JOIN artistas ON artistas.id = albuns.artista_id
           ORDER BY albuns.created_at DESC, albuns.id DESC""",
        conn,
    )


def obter_album(album_id: int) -> dict | None:
    conn = get_connection()
    cursor = conn.execute(
        """SELECT albuns.*, artistas.nome AS artista_nome
           FROM albuns JOIN artistas ON artistas.id = albuns.artista_id
           WHERE albuns.id = ?""",
        (album_id,),
    )
    return linha_para_dict(cursor, cursor.fetchone())


def inserir_album(nome: str, artista_id: int, ano_lancamento: int | None, genero: str = "",
                   capa_path: str = "", spotify_id: str = "", spotify_url: str = "") -> int:
    conn = get_connection()
    cur = conn.execute(
        """INSERT INTO albuns (nome, artista_id, ano_lancamento, genero, capa_path, spotify_id, spotify_url)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (nome, artista_id, ano_lancamento, genero, capa_path, spotify_id, spotify_url),
    )
    conn.commit()
    return cur.lastrowid


def atualizar_album(album_id: int, nome: str, ano_lancamento: int | None, genero: str,
                     capa_path: str | None = None) -> None:
    """capa_path=None mantém a capa atual (não a apaga) — sentinela
    importante: o endpoint PATCH só deve passar capa_path quando um arquivo
    novo de verdade veio no request."""
    conn = get_connection()
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


def favoritar_album(album_id: int, favorito: bool) -> None:
    conn = get_connection()
    conn.execute("UPDATE albuns SET favorito = ? WHERE id = ?", (int(favorito), album_id))
    conn.commit()


def buscar_album_por_nome(nome: str, artista_id: int) -> dict | None:
    conn = get_connection()
    cursor = conn.execute(
        "SELECT * FROM albuns WHERE nome = ? COLLATE NOCASE AND artista_id = ?",
        (nome, artista_id),
    )
    return linha_para_dict(cursor, cursor.fetchone())


def obter_ou_criar_album(nome: str, artista_id: int, ano_lancamento: int | None, genero: str = "",
                          spotify_id: str = "", spotify_url: str = "") -> int:
    """Reaproveita o álbum se já existir pra esse artista."""
    existente = buscar_album_por_nome(nome, artista_id)
    if existente:
        return int(existente["id"])
    return inserir_album(nome, artista_id, ano_lancamento, genero, spotify_id=spotify_id, spotify_url=spotify_url)


def excluir_album(album_id: int) -> None:
    conn = get_connection()
    conn.execute("DELETE FROM albuns WHERE id = ?", (album_id,))
    conn.commit()


# ---------------------------------------------------------------------------
# Escutas
# ---------------------------------------------------------------------------

def listar_escutas(album_id: int) -> pd.DataFrame:
    conn = get_connection()
    return pd.read_sql_query(
        "SELECT * FROM escutas WHERE album_id = ? ORDER BY data DESC, id DESC",
        conn, params=[album_id],
    )


def listar_escutas_com_album() -> pd.DataFrame:
    """Todas as escutas já com álbum e artista resolvidos (join)."""
    conn = get_connection()
    return pd.read_sql_query(
        """SELECT escutas.*, albuns.nome AS album_nome, albuns.capa_path,
                  albuns.spotify_id AS album_spotify_id, albuns.ano_lancamento AS album_ano,
                  albuns.genero AS album_genero, artistas.nome AS artista_nome
           FROM escutas
           JOIN albuns ON albuns.id = escutas.album_id
           JOIN artistas ON artistas.id = albuns.artista_id
           ORDER BY escutas.data DESC, escutas.id DESC""",
        conn,
    )


def intervalo_datas_escutas() -> tuple[str, str] | None:
    conn = get_connection()
    row = conn.execute("SELECT MIN(data) AS minima, MAX(data) AS maxima FROM escutas").fetchone()
    if row is None or row[0] is None:
        return None
    return row[0], row[1]


def intervalo_datas_historico() -> tuple[str, str] | None:
    conn = get_connection()
    row = conn.execute(
        "SELECT MIN(substr(datetime(tocado_em, '-3 hours'), 1, 10)) AS minima, "
        "MAX(substr(datetime(tocado_em, '-3 hours'), 1, 10)) AS maxima "
        "FROM spotify_historico"
    ).fetchone()
    if row is None or row[0] is None:
        return None
    return row[0], row[1]


def inserir_escuta(album_id: int, data: str, nota: float | None, review: str = "",
                    faixa_favorita: str = "") -> None:
    conn = get_connection()
    conn.execute(
        """INSERT INTO escutas (album_id, data, nota, review, faixa_favorita)
           VALUES (?, ?, ?, ?, ?)""",
        (album_id, data, nota, review, faixa_favorita),
    )
    conn.commit()


def atualizar_escuta(escuta_id: int, data: str, nota: float | None, review: str,
                      faixa_favorita: str) -> None:
    conn = get_connection()
    conn.execute(
        """UPDATE escutas SET data = ?, nota = ?, review = ?, faixa_favorita = ?
           WHERE id = ?""",
        (data, nota, review, faixa_favorita, escuta_id),
    )
    conn.commit()


def excluir_escuta(escuta_id: int) -> None:
    conn = get_connection()
    conn.execute("DELETE FROM escutas WHERE id = ?", (escuta_id,))
    conn.commit()


# ---------------------------------------------------------------------------
# Conta Spotify (token OAuth + histórico bruto de faixas tocadas)
# ---------------------------------------------------------------------------

def obter_token_spotify() -> dict | None:
    conn = get_connection()
    row = conn.execute("SELECT token_json FROM spotify_token WHERE id = 1").fetchone()
    if row is None:
        return None
    return json.loads(row[0])


def salvar_token_spotify(token_info: dict) -> None:
    conn = get_connection()
    conn.execute(
        """INSERT INTO spotify_token (id, token_json, atualizado_em)
           VALUES (1, ?, CURRENT_TIMESTAMP)
           ON CONFLICT(id) DO UPDATE SET token_json = excluded.token_json,
               atualizado_em = excluded.atualizado_em""",
        (json.dumps(token_info),),
    )
    conn.commit()


def limpar_token_spotify() -> None:
    conn = get_connection()
    conn.execute("DELETE FROM spotify_token WHERE id = 1")
    conn.commit()


def inserir_historico_faixas(faixas: list[dict]) -> int:
    """Insere faixas do histórico (uma vez cada — o UNIQUE de
    track_spotify_id+tocado_em cuida de não duplicar). Retorna quantas eram
    realmente novas."""
    if not faixas:
        return 0
    conn = get_connection()
    novas = 0
    for f in faixas:
        cur = conn.execute(
            """INSERT OR IGNORE INTO spotify_historico
               (faixa_nome, artista_nome, album_nome, capa_url, track_spotify_id, album_spotify_id,
                artista_spotify_id, tocado_em, duration_ms)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                f["faixa_nome"], f["artista_nome"], f["album_nome"], f.get("capa_url", ""),
                f.get("track_spotify_id", ""), f.get("album_spotify_id", ""),
                f.get("artista_spotify_id", ""), f["tocado_em"], f.get("duration_ms", 0),
            ),
        )
        novas += cur.rowcount
    conn.commit()
    return novas


def listar_historico(limit: int = 50) -> pd.DataFrame:
    conn = get_connection()
    return pd.read_sql_query(
        "SELECT * FROM spotify_historico ORDER BY tocado_em DESC LIMIT ?", conn, params=[limit],
    )
