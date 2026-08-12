"""Conexão com o banco remoto (Turso/libSQL) do módulo música — o MESMO
banco que o Streamlit usa em produção (ver modules/musica/database.py).

Port de modules/musica/database.py: mesmo schema, mesma lógica de migração
e o mesmo padrão de "embedded replica" (arquivo local sincronizado com o
Turso a cada commit). Duas diferenças deliberadas:

1. Credencial vem de variável de ambiente (core.config.settings), não de
   st.secrets.
2. O arquivo de réplica local fica em webapp/musica/data/, SEPARADO do
   arquivo que o processo Streamlit usa (modules/musica/database/) — os
   dois processos podem rodar ao mesmo tempo na mesma máquina sem disputar
   lock de arquivo. As CAPAS de álbum (UPLOADS_DIR) continuam apontando pro
   mesmo diretório do Streamlit: são arquivo de verdade do usuário, não faz
   sentido duplicar.

Sem @st.cache_resource: o processo FastAPI já é de longa duração, então um
singleton de módulo simples faz o mesmo papel (uma única conexão
reaproveitada entre requests).
"""

import os
from pathlib import Path

import libsql

from core.config import settings

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DB_DIR = _REPO_ROOT / "modules" / "musica" / "database"
UPLOADS_DIR = DB_DIR / "uploads"

_REPLICA_DIR = Path(__file__).resolve().parent / "data"
_REPLICA_PATH = _REPLICA_DIR / "musica_replica_webapp.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS app_meta (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    seeded INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS artistas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    spotify_id TEXT DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS albuns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    artista_id INTEGER NOT NULL REFERENCES artistas(id) ON DELETE CASCADE,
    ano_lancamento INTEGER,
    genero TEXT DEFAULT '',
    capa_path TEXT DEFAULT '',
    spotify_id TEXT DEFAULT '',
    spotify_url TEXT DEFAULT '',
    favorito INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS escutas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    album_id INTEGER NOT NULL REFERENCES albuns(id) ON DELETE CASCADE,
    data TEXT NOT NULL,
    nota REAL,
    review TEXT DEFAULT '',
    faixa_favorita TEXT DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS spotify_token (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    token_json TEXT NOT NULL,
    atualizado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS spotify_historico (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    faixa_nome TEXT NOT NULL,
    artista_nome TEXT NOT NULL,
    album_nome TEXT NOT NULL,
    capa_url TEXT DEFAULT '',
    track_spotify_id TEXT DEFAULT '',
    album_spotify_id TEXT DEFAULT '',
    artista_spotify_id TEXT DEFAULT '',
    tocado_em TEXT NOT NULL,
    duration_ms INTEGER NOT NULL DEFAULT 0,
    registrado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (track_spotify_id, tocado_em)
);
"""


class _ConexaoComSyncNoCommit:
    def __init__(self, conn):
        self._conn = conn

    def commit(self):
        self._conn.commit()
        self._conn.sync()

    def __getattr__(self, nome):
        return getattr(self._conn, nome)


_conn_singleton: _ConexaoComSyncNoCommit | None = None


def get_connection() -> _ConexaoComSyncNoCommit:
    """Conexão com o banco remoto, reaproveitada entre requests — quem
    chama NÃO deve fechá-la."""
    global _conn_singleton
    if _conn_singleton is not None:
        return _conn_singleton

    if not settings.turso_musica_url or not settings.turso_musica_token:
        raise RuntimeError(
            "TURSO_MUSICA_URL/TURSO_MUSICA_TOKEN não configurados. Copie "
            "webapp/.env.example para webapp/.env e preencha com os mesmos "
            "valores do secrets.toml do Streamlit Cloud."
        )

    os.makedirs(_REPLICA_DIR, exist_ok=True)
    os.makedirs(UPLOADS_DIR, exist_ok=True)

    conn = libsql.connect(
        database=str(_REPLICA_PATH),
        sync_url=settings.turso_musica_url,
        auth_token=settings.turso_musica_token,
    )
    conn.sync()
    conn.execute("PRAGMA foreign_keys = ON")
    _conn_singleton = _ConexaoComSyncNoCommit(conn)
    return _conn_singleton


def linha_para_dict(cursor, row: tuple | None) -> dict | None:
    """Converte uma linha (tupla) + cursor.description em dict — o driver
    do Turso não suporta row_factory, então cursor["coluna"] não existe."""
    if row is None:
        return None
    colunas = [d[0] for d in cursor.description]
    return dict(zip(colunas, row))


def _migrar_schema(conn) -> None:
    row = conn.execute("SELECT seeded FROM app_meta WHERE id = 1").fetchone()
    if row is None:
        tinha_dados = conn.execute("SELECT COUNT(*) AS n FROM albuns").fetchone()[0] > 0
        conn.execute("INSERT INTO app_meta (id, seeded) VALUES (1, ?)", (1 if tinha_dados else 0,))

    colunas_albuns = {r[1] for r in conn.execute("PRAGMA table_info(albuns)").fetchall()}
    if "favorito" not in colunas_albuns:
        conn.execute("ALTER TABLE albuns ADD COLUMN favorito INTEGER NOT NULL DEFAULT 0")
    if "capa_dados" not in colunas_albuns:
        conn.execute("ALTER TABLE albuns ADD COLUMN capa_dados BLOB")
    if "capa_mime" not in colunas_albuns:
        conn.execute("ALTER TABLE albuns ADD COLUMN capa_mime TEXT")

    colunas_historico = {r[1] for r in conn.execute("PRAGMA table_info(spotify_historico)").fetchall()}
    if "duration_ms" not in colunas_historico:
        conn.execute("ALTER TABLE spotify_historico ADD COLUMN duration_ms INTEGER NOT NULL DEFAULT 0")
    if "artista_spotify_id" not in colunas_historico:
        conn.execute("ALTER TABLE spotify_historico ADD COLUMN artista_spotify_id TEXT DEFAULT ''")

    conn.commit()


def init_db() -> None:
    """Cria as tabelas caso não existam e aplica migrações. Idempotente —
    seguro de chamar toda subida do processo, mesmo contra um banco já
    populado pelo Streamlit."""
    conn = get_connection()
    conn.executescript(SCHEMA)
    conn.commit()
    _migrar_schema(conn)


def inicializar_banco() -> None:
    """Ponto único chamado no startup do FastAPI: garante schema/migrações.

    Deliberadamente SEM seed de dados de exemplo (diferente do
    modules/musica/database.py original) — este backend aponta pro banco de
    produção, que já está seedado (ou tem dados reais); criar um álbum de
    exemplo aqui não faz sentido e seria uma escrita a mais num banco real
    logo na primeira subida."""
    init_db()
