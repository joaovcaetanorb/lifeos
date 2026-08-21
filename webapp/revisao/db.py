"""Conexão com o banco remoto (Turso/libSQL) do módulo revisão — banco
NOVO, sem equivalente no Streamlit (dado 100% novo). Mesmo padrão de
webapp/momentos/db.py."""

import os
from pathlib import Path

import libsql

from core.config import settings

_REPLICA_DIR = Path(__file__).resolve().parent / "data"
_REPLICA_PATH = _REPLICA_DIR / "revisao_replica_webapp.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS app_meta (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    seeded INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS revisoes_semanais (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    semana_inicio TEXT NOT NULL UNIQUE,
    semana_fim TEXT NOT NULL,
    o_que_funcionou TEXT NOT NULL DEFAULT '',
    o_que_travou TEXT NOT NULL DEFAULT '',
    ajuste_proxima_semana TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
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

    if not settings.turso_revisao_url or not settings.turso_revisao_token:
        raise RuntimeError(
            "TURSO_REVISAO_URL/TURSO_REVISAO_TOKEN não configurados. Copie "
            "webapp/.env.example para webapp/.env e preencha com um banco Turso "
            "novo (não existe equivalente desse módulo no Streamlit)."
        )

    os.makedirs(_REPLICA_DIR, exist_ok=True)

    conn = libsql.connect(
        database=str(_REPLICA_PATH),
        sync_url=settings.turso_revisao_url,
        auth_token=settings.turso_revisao_token,
    )
    conn.sync()
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
        tinha_dados = conn.execute("SELECT COUNT(*) AS n FROM revisoes_semanais").fetchone()[0] > 0
        conn.execute("INSERT INTO app_meta (id, seeded) VALUES (1, ?)", (1 if tinha_dados else 0,))
    conn.commit()


def init_db() -> None:
    conn = get_connection()
    conn.executescript(SCHEMA)
    conn.commit()
    _migrar_schema(conn)


def inicializar_banco() -> None:
    """Sem seed de dados de exemplo — mesmo raciocínio de todo módulo
    migrado (ver webapp/habitos/db.py)."""
    init_db()
