"""Conexão com o banco remoto (Turso/libSQL) do módulo projetos — o MESMO
banco que o Streamlit usa em produção (ver modules/projetos/database.py).

Port de modules/projetos/database.py: mesmo schema/migração/réplica local,
mesmas duas diferenças deliberadas de webapp/livros/db.py (credencial via
.env, réplica local separada do processo Streamlit). Ver aquele arquivo
pros comentários completos — não repetidos aqui pra não duplicar.
"""

import os
from pathlib import Path

import libsql

from core.config import settings

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DB_DIR = _REPO_ROOT / "modules" / "projetos" / "database"
UPLOADS_DIR = DB_DIR / "uploads"

_REPLICA_DIR = Path(__file__).resolve().parent / "data"
_REPLICA_PATH = _REPLICA_DIR / "projetos_replica_webapp.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS app_meta (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    seeded INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS projetos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    descricao TEXT DEFAULT '',
    orcamento REAL NOT NULL DEFAULT 0,
    observacoes TEXT DEFAULT '',
    foto_path TEXT DEFAULT '',
    status TEXT NOT NULL DEFAULT 'Ativo' CHECK (status IN ('Ativo', 'Pausado', 'Concluído')),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS projeto_checklist (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    projeto_id INTEGER NOT NULL REFERENCES projetos(id) ON DELETE CASCADE,
    descricao TEXT NOT NULL,
    notas TEXT DEFAULT '',
    prazo TEXT DEFAULT '',
    link TEXT DEFAULT '',
    foto_path TEXT DEFAULT '',
    concluido INTEGER NOT NULL DEFAULT 0,
    concluido_em TEXT DEFAULT '',
    ordem INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS projeto_aportes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    projeto_id INTEGER NOT NULL REFERENCES projetos(id) ON DELETE CASCADE,
    data TEXT NOT NULL,
    valor REAL NOT NULL,
    observacao TEXT DEFAULT '',
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

    if not settings.turso_projetos_url or not settings.turso_projetos_token:
        raise RuntimeError(
            "TURSO_PROJETOS_URL/TURSO_PROJETOS_TOKEN não configurados. Copie "
            "webapp/.env.example para webapp/.env e preencha com os mesmos "
            "valores do secrets.toml do Streamlit Cloud."
        )

    os.makedirs(_REPLICA_DIR, exist_ok=True)
    os.makedirs(UPLOADS_DIR, exist_ok=True)

    conn = libsql.connect(
        database=str(_REPLICA_PATH),
        sync_url=settings.turso_projetos_url,
        auth_token=settings.turso_projetos_token,
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
        tinha_projetos = conn.execute("SELECT COUNT(*) AS n FROM projetos").fetchone()[0] > 0
        conn.execute("INSERT INTO app_meta (id, seeded) VALUES (1, ?)", (1 if tinha_projetos else 0,))

    colunas_checklist = {r[1] for r in conn.execute("PRAGMA table_info(projeto_checklist)").fetchall()}
    for coluna in ("notas", "prazo", "link", "foto_path", "concluido_em"):
        if coluna not in colunas_checklist:
            conn.execute(f"ALTER TABLE projeto_checklist ADD COLUMN {coluna} TEXT DEFAULT ''")

    conn.commit()


def init_db() -> None:
    conn = get_connection()
    conn.executescript(SCHEMA)
    conn.commit()
    _migrar_schema(conn)


def inicializar_banco() -> None:
    """Sem seed de dados de exemplo — este backend aponta pro banco de
    produção, já populado."""
    init_db()
