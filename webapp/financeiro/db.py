"""Conexão com o banco remoto (Turso/libSQL) do módulo financeiro — banco
NOVO, criado do zero pra essa versão simplificada (não é o mesmo banco do
financeiro no Streamlit, que carregava toda a complexidade de fatura de
cartão parcelada/planejamento/relatório). Mesmo padrão de webapp/habitos/db.py."""

import os
from pathlib import Path

import libsql

from core.config import settings

_REPLICA_DIR = Path(__file__).resolve().parent / "data"
_REPLICA_PATH = _REPLICA_DIR / "financeiro_replica_webapp.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS app_meta (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    seeded INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS config (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    salario REAL NOT NULL DEFAULT 0,
    vale_alimentacao REAL NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS contas_fixas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    descricao TEXT NOT NULL,
    valor REAL NOT NULL,
    ativo INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS gastos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    data TEXT NOT NULL,
    descricao TEXT NOT NULL,
    valor REAL NOT NULL,
    categoria TEXT NOT NULL,
    forma_pagamento TEXT NOT NULL
        CHECK (forma_pagamento IN ('Dinheiro','Vale-alimentação','Cartão de crédito')),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS receitas_extras (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    data TEXT NOT NULL,
    descricao TEXT NOT NULL,
    valor REAL NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS reserva_movimentos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    data TEXT NOT NULL,
    valor REAL NOT NULL,
    tipo TEXT NOT NULL CHECK (tipo IN ('Aporte', 'Retirada')),
    observacao TEXT,
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

    if not settings.turso_financeiro_url or not settings.turso_financeiro_token:
        raise RuntimeError(
            "TURSO_FINANCEIRO_URL/TURSO_FINANCEIRO_TOKEN não configurados. Copie "
            "webapp/.env.example para webapp/.env e preencha com um banco Turso "
            "novo (esse módulo não reaproveita o banco do financeiro no Streamlit)."
        )

    os.makedirs(_REPLICA_DIR, exist_ok=True)

    conn = libsql.connect(
        database=str(_REPLICA_PATH),
        sync_url=settings.turso_financeiro_url,
        auth_token=settings.turso_financeiro_token,
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
        tinha_dados = conn.execute("SELECT COUNT(*) AS n FROM gastos").fetchone()[0] > 0
        conn.execute("INSERT INTO app_meta (id, seeded) VALUES (1, ?)", (1 if tinha_dados else 0,))
    conn.execute(
        "INSERT OR IGNORE INTO config (id, salario, vale_alimentacao) VALUES (1, 0, 0)"
    )
    conn.commit()


def init_db() -> None:
    conn = get_connection()
    conn.executescript(SCHEMA)
    conn.commit()
    _migrar_schema(conn)


def inicializar_banco() -> None:
    """Sem seed de dados de exemplo — o usuário preenche salário/vale-
    alimentação/contas fixas reais na tela de configurações."""
    init_db()
