"""Conexão com o banco remoto (Turso/libSQL) do módulo Beat Forge — módulo
novo, sem equivalente no Streamlit legado (diferente de projetos/humor/etc,
não existe um `modules/beatforge/database.py` pra portar).

Mesmo padrão de webapp/humor/db.py: embedded replica + wrapper de
sync-on-commit (ver _ConexaoComSyncNoCommit)."""

import os
from pathlib import Path

import libsql

from core.config import settings

_REPLICA_DIR = Path(__file__).resolve().parent / "data"
_REPLICA_PATH = _REPLICA_DIR / "beatforge_replica_webapp.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS app_meta (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    seeded INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS beats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    data TEXT NOT NULL,
    bpm INTEGER,
    tonalidade TEXT DEFAULT '',
    duracao_alvo TEXT DEFAULT '',
    origem_tipo TEXT NOT NULL CHECK (origem_tipo IN ('sample', 'sintese')),
    origem_referencia TEXT DEFAULT '',
    origem_metodo TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'Loop Eterno'
        CHECK (status IN ('Lixeira', 'Loop Eterno', 'Estrutura Montada', 'Mixagem Crua', 'Pronto para Master')),
    tecnicas TEXT DEFAULT '',
    link_externo TEXT DEFAULT '',
    observacoes TEXT DEFAULT '',
    capa_dados BLOB,
    capa_mime TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS beat_sessoes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    beat_id INTEGER NOT NULL REFERENCES beats(id) ON DELETE CASCADE,
    data TEXT NOT NULL,
    duracao_minutos INTEGER NOT NULL,
    proximo_passo_brutal TEXT NOT NULL,
    estado_emocional_snapshot TEXT DEFAULT '',
    referencia_audicao_snapshot TEXT DEFAULT '',
    observacao TEXT DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS beat_dicas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    texto TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sample_crate (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    link TEXT NOT NULL,
    nome TEXT DEFAULT '',
    fonte TEXT DEFAULT '',
    tags TEXT DEFAULT '',
    status TEXT NOT NULL DEFAULT 'novo' CHECK (status IN ('novo', 'usado', 'descartado')),
    observacao TEXT DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""

_DICAS_SEMENTE = [
    "Restrição de sample, não de técnica: garimpa um gênero que você nunca "
    "usou (fado, gamelan, muzak, trilha de novela) numa sessão inteira.",
    "Groove sujo: desliga o snap-to-grid numa sessão inteira e ajusta o "
    "timing só no ouvido.",
    "Resample agressivo: bounça o beat, joga de volta como sample, "
    "distorce/pitcha/bitcrusher e usa só um pedaço como novo elemento.",
    "Beat curto, prazo curto: 1 loop, 8-16 bars, sem arranjo, um por dia "
    "por 2 semanas. Quantidade destrava mais que perfeição.",
    "Sample não-musical: grava 30s de áudio ambiente (rua, chuva, "
    "conversa) e usa como textura de fundo.",
    "Termina e solta (o lance do Conductor Williams): ele lança uma "
    "quantidade absurda de flips crus de soul/jazz sem entortar em cima. "
    "'Pronto' vence 'perfeito' — escolhe um beat pra ser o candidato do "
    "ano e empurra ele até Pronto para Master em vez de abrir mais um novo.",
]


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

    if not settings.turso_beatforge_url or not settings.turso_beatforge_token:
        raise RuntimeError(
            "TURSO_BEATFORGE_URL/TURSO_BEATFORGE_TOKEN não configurados. Copie "
            "webapp/.env.example para webapp/.env e preencha com os valores "
            "do banco Turso criado para o Beat Forge."
        )

    os.makedirs(_REPLICA_DIR, exist_ok=True)

    conn = libsql.connect(
        database=str(_REPLICA_PATH),
        sync_url=settings.turso_beatforge_url,
        auth_token=settings.turso_beatforge_token,
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


def _semear_dicas(conn) -> None:
    row = conn.execute("SELECT seeded FROM app_meta WHERE id = 1").fetchone()
    if row is not None:
        return
    for texto in _DICAS_SEMENTE:
        conn.execute("INSERT INTO beat_dicas (texto) VALUES (?)", (texto,))
    conn.execute("INSERT INTO app_meta (id, seeded) VALUES (1, 1)")
    conn.commit()


def init_db() -> None:
    conn = get_connection()
    conn.executescript(SCHEMA)
    conn.commit()
    _semear_dicas(conn)


def inicializar_banco() -> None:
    init_db()
