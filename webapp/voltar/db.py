"""Conexão com o banco remoto (Turso/libSQL) do módulo voltar — banco NOVO,
sem equivalente no Streamlit (dado 100% novo). Mesmo padrão de
webapp/momentos/db.py."""

import os
from pathlib import Path

import libsql

from core.config import settings

_REPLICA_DIR = Path(__file__).resolve().parent / "data"
_REPLICA_PATH = _REPLICA_DIR / "voltar_replica_webapp.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS app_meta (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    seeded INTEGER NOT NULL DEFAULT 0,
    data_inicio TEXT
);

CREATE TABLE IF NOT EXISTS registros_diarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    data TEXT NOT NULL UNIQUE,
    sono INTEGER,
    agua INTEGER,
    academia TEXT,
    leitura INTEGER,
    cigarros INTEGER,
    responsabilidades INTEGER,
    coisa_boa_texto TEXT,
    coisa_boa_categoria TEXT,
    dinheiro TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tags_coisa_boa (
    chave TEXT PRIMARY KEY,
    rotulo TEXT NOT NULL,
    ordem INTEGER NOT NULL DEFAULT 0
);
"""

_TAGS_COISA_BOA_PADRAO = [
    ("album", "🎵 Ouvir um álbum inteiro"), ("basquete", "🏀 Jogar basquete"), ("jogo", "🎮 Jogar sem culpa"),
    ("leitura", "📖 Ler algumas páginas"), ("caminhada", "🚶 Dar uma caminhada"),
    ("amor", "❤️ Fazer algo legal com quem você gosta"), ("quarto", "🧹 Arrumar seu quarto"),
    ("beat", "🎹 Fazer um beat"), ("cafe", "☕ Sair para tomar um café"), ("unhas", "🧼 Cuidar das unhas"),
    ("dormir", "😴 Dormir mais cedo"), ("filme", "🎬 Assistir um filme"), ("descansar", "🛋️ Simplesmente descansar"),
    ("cozinhar", "🍳 Cozinhar algo gostoso"), ("amigo", "📱 Mandar mensagem pra um amigo"),
    ("familia", "👨‍👩‍👧 Passar um tempo com a família"),
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

    if not settings.turso_voltar_url or not settings.turso_voltar_token:
        raise RuntimeError(
            "TURSO_VOLTAR_URL/TURSO_VOLTAR_TOKEN não configurados. Copie "
            "webapp/.env.example para webapp/.env e preencha com um banco Turso "
            "novo (não existe equivalente desse módulo no Streamlit)."
        )

    os.makedirs(_REPLICA_DIR, exist_ok=True)

    conn = libsql.connect(
        database=str(_REPLICA_PATH),
        sync_url=settings.turso_voltar_url,
        auth_token=settings.turso_voltar_token,
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
        from datetime import date
        tinha_dados = conn.execute("SELECT COUNT(*) AS n FROM registros_diarios").fetchone()[0] > 0
        conn.execute(
            "INSERT INTO app_meta (id, seeded, data_inicio) VALUES (1, ?, ?)",
            (1 if tinha_dados else 0, date.today().isoformat()),
        )

    # 2026-09-08: "sono" (sim/não) trocado por "hora_dormir" (que horas foi
    # deitar) — usuário apontou que perguntar "dormiu bem?" sobre HOJE não
    # fazia sentido (é sobre a noite anterior) e que queria trackear o
    # horário, não só um sim/não. Coluna `sono` fica órfã no schema (sem
    # DROP COLUMN — mesmo padrão de migração de todo módulo do projeto).
    colunas = {c[1] for c in conn.execute("PRAGMA table_info(registros_diarios)").fetchall()}
    if "hora_dormir" not in colunas:
        conn.execute("ALTER TABLE registros_diarios ADD COLUMN hora_dormir TEXT")
    # 2026-09-08: campo "maconha" adicionado a partir do projeto_90_dias.pdf
    # do usuário — mesma medida que ele já usa: "resolvi minhas obrigações
    # antes de usar?" (sim / não / não usei hoje), espelhando o padrão do
    # campo academia.
    if "maconha" not in colunas:
        conn.execute("ALTER TABLE registros_diarios ADD COLUMN maconha TEXT")
    # 2026-09-08: "coisa boa" virou tag multi-seleção (antes era 1 categoria
    # só) — coisa_boa_categoria fica órfã, novo campo guarda as chaves
    # selecionadas separadas por vírgula (mesmo padrão de tags-como-string
    # já usado em música/humor).
    if "coisa_boa_chaves" not in colunas:
        conn.execute("ALTER TABLE registros_diarios ADD COLUMN coisa_boa_chaves TEXT")

    tem_tags = conn.execute("SELECT COUNT(*) AS n FROM tags_coisa_boa").fetchone()[0] > 0
    if not tem_tags:
        for i, (chave, rotulo) in enumerate(_TAGS_COISA_BOA_PADRAO):
            conn.execute(
                "INSERT OR IGNORE INTO tags_coisa_boa (chave, rotulo, ordem) VALUES (?, ?, ?)",
                (chave, rotulo, i),
            )

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
