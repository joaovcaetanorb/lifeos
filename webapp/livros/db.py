"""Conexão com o banco remoto (Turso/libSQL) do módulo livros — o MESMO
banco que o Streamlit usa em produção (ver modules/livros/database.py).

Port de modules/livros/database.py: mesmo schema/migração/réplica local,
mesmas duas diferenças deliberadas de webapp/musica/db.py (credencial via
.env, réplica local separada do processo Streamlit). Ver aquele arquivo
pros comentários completos — não repetidos aqui pra não duplicar.
"""

import os
from pathlib import Path

import libsql

from core.config import settings

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DB_DIR = _REPO_ROOT / "modules" / "livros" / "database"
UPLOADS_DIR = DB_DIR / "uploads"

_REPLICA_DIR = Path(__file__).resolve().parent / "data"
_REPLICA_PATH = _REPLICA_DIR / "livros_replica_webapp.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS app_meta (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    seeded INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS autores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS livros (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    autor_id INTEGER NOT NULL REFERENCES autores(id) ON DELETE CASCADE,
    ano_publicacao INTEGER,
    genero TEXT DEFAULT '',
    capa_path TEXT DEFAULT '',
    favorito INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS leituras (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    livro_id INTEGER NOT NULL REFERENCES livros(id) ON DELETE CASCADE,
    data TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'Lendo' CHECK (status IN ('Lendo', 'Concluído', 'Abandonado')),
    nota REAL,
    review TEXT DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
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
    global _conn_singleton
    if _conn_singleton is not None:
        return _conn_singleton

    if not settings.turso_livros_url or not settings.turso_livros_token:
        raise RuntimeError(
            "TURSO_LIVROS_URL/TURSO_LIVROS_TOKEN não configurados. Copie "
            "webapp/.env.example para webapp/.env e preencha com os mesmos "
            "valores do secrets.toml do Streamlit Cloud."
        )

    os.makedirs(_REPLICA_DIR, exist_ok=True)
    os.makedirs(UPLOADS_DIR, exist_ok=True)

    conn = libsql.connect(
        database=str(_REPLICA_PATH),
        sync_url=settings.turso_livros_url,
        auth_token=settings.turso_livros_token,
    )
    conn.sync()
    conn.execute("PRAGMA foreign_keys = ON")
    _conn_singleton = _ConexaoComSyncNoCommit(conn)
    return _conn_singleton


def linha_para_dict(cursor, row: tuple | None) -> dict | None:
    if row is None:
        return None
    colunas = [d[0] for d in cursor.description]
    return dict(zip(colunas, row))


def _migrar_schema(conn) -> None:
    row = conn.execute("SELECT seeded FROM app_meta WHERE id = 1").fetchone()
    if row is None:
        tinha_dados = conn.execute("SELECT COUNT(*) AS n FROM livros").fetchone()[0] > 0
        conn.execute("INSERT INTO app_meta (id, seeded) VALUES (1, ?)", (1 if tinha_dados else 0,))

    colunas_livros = {r[1] for r in conn.execute("PRAGMA table_info(livros)").fetchall()}
    if "favorito" not in colunas_livros:
        conn.execute("ALTER TABLE livros ADD COLUMN favorito INTEGER NOT NULL DEFAULT 0")
    if "capa_dados" not in colunas_livros:
        conn.execute("ALTER TABLE livros ADD COLUMN capa_dados BLOB")
    if "capa_mime" not in colunas_livros:
        conn.execute("ALTER TABLE livros ADD COLUMN capa_mime TEXT")

    conn.commit()


def init_db() -> None:
    conn = get_connection()
    conn.executescript(SCHEMA)
    conn.commit()
    _migrar_schema(conn)


def inicializar_banco() -> None:
    """Sem seed de dados de exemplo (diferente do modules/livros/database.py
    original) — mesma razão de webapp/musica/db.py: este backend aponta
    pro banco de produção, já populado."""
    init_db()
