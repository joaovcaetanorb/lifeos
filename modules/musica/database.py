"""Camada de acesso ao banco remoto (Turso/libSQL): conexão, criação de
schema e seed inicial.

Nenhuma regra de negócio aqui — só estrutura de dados e bootstrap.

Migrado de SQLite local pra Turso em 2026-07-29 (Streamlit Community Cloud
tem disco efêmero). O driver do Turso (`libsql`) imita o `sqlite3` em quase
tudo, MAS não suporta `conn.row_factory = sqlite3.Row` — as linhas voltam
como tupla simples. Por isso `linha_para_dict()` abaixo: sempre que o
código precisar acessar uma coluna pelo nome (não só por posição), usa essa
função em vez de `dict(row)` ou `row["coluna"]`. A conexão é compartilhada
(cache_resource) — nenhuma função em models.py chama `conn.close()`.

Capas de álbum (UPLOADS_DIR) continuam em disco local — só os dados SQL
migraram pro Turso.
"""

import os

import libsql
import streamlit as st
from pathlib import Path
from datetime import date, timedelta

DB_DIR = Path(__file__).parent / "database"
UPLOADS_DIR = DB_DIR / "uploads"

# 2026-07-30: trocado pra "embedded replica" (sync_url) — ver
# modules/financeiro/database.py pro detalhe completo da mudança.
_REPLICA_PATH = os.path.join(DB_DIR, "musica_replica.db")


class _ConexaoComSyncNoCommit:
    def __init__(self, conn):
        self._conn = conn

    def commit(self):
        self._conn.commit()
        self._conn.sync()

    def __getattr__(self, nome):
        return getattr(self._conn, nome)

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

-- Conta Spotify conectada (login de usuário via OAuth, separado das
-- credenciais de app usadas na busca de catálogo) — usada pra guardar o
-- token e o histórico bruto de faixas tocadas de verdade.
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
    tocado_em TEXT NOT NULL,
    duration_ms INTEGER NOT NULL DEFAULT 0,
    registrado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (track_spotify_id, tocado_em)
);
"""


@st.cache_resource(show_spinner=False)
def _conexao_compartilhada():
    os.makedirs(DB_DIR, exist_ok=True)
    conn = libsql.connect(
        database=_REPLICA_PATH,
        sync_url=st.secrets["TURSO_MUSICA_URL"],
        auth_token=st.secrets["TURSO_MUSICA_TOKEN"],
    )
    conn.sync()
    conn.execute("PRAGMA foreign_keys = ON")
    return _ConexaoComSyncNoCommit(conn)


def get_connection():
    """Conexão com o banco remoto no Turso, reaproveitada entre chamadas —
    quem chama NÃO deve fechá-la."""
    return _conexao_compartilhada()


def linha_para_dict(cursor, row: tuple | None) -> dict | None:
    """Converte uma linha (tupla) + cursor.description em dict — substitui
    `dict(row)`/`row["coluna"]`, que dependiam do row_factory do sqlite3
    local e não funcionam com o driver do Turso."""
    if row is None:
        return None
    colunas = [d[0] for d in cursor.description]
    return dict(zip(colunas, row))


def _migrar_schema(conn) -> None:
    """Garante uma linha em app_meta. Não basear "já foi semeado?" em
    tabelas que o usuário pode esvaziar (ver bug corrigido em Projetos) —
    apagar o último álbum não pode fazer o exemplo voltar sozinho."""
    row = conn.execute("SELECT seeded FROM app_meta WHERE id = 1").fetchone()
    if row is None:
        tinha_dados = conn.execute("SELECT COUNT(*) AS n FROM albuns").fetchone()[0] > 0
        conn.execute("INSERT INTO app_meta (id, seeded) VALUES (1, ?)", (1 if tinha_dados else 0,))

    colunas_albuns = {r[1] for r in conn.execute("PRAGMA table_info(albuns)").fetchall()}
    if "favorito" not in colunas_albuns:
        conn.execute("ALTER TABLE albuns ADD COLUMN favorito INTEGER NOT NULL DEFAULT 0")

    colunas_historico = {r[1] for r in conn.execute("PRAGMA table_info(spotify_historico)").fetchall()}
    if "duration_ms" not in colunas_historico:
        conn.execute("ALTER TABLE spotify_historico ADD COLUMN duration_ms INTEGER NOT NULL DEFAULT 0")

    conn.commit()


def init_db() -> None:
    """Cria as tabelas caso não existam e aplica migrações. Idempotente."""
    conn = get_connection()
    conn.executescript(SCHEMA)
    conn.commit()
    _migrar_schema(conn)


def banco_esta_vazio() -> bool:
    """True apenas se o app nunca foi semeado — não reflete se o usuário
    apagou todos os álbuns manualmente (isso é um estado válido)."""
    conn = get_connection()
    row = conn.execute("SELECT seeded FROM app_meta WHERE id = 1").fetchone()
    return row is None or row[0] == 0


def seed_dados_iniciais() -> None:
    """Popula o banco com um álbum fictício na primeira execução, só para
    a tela não nascer vazia — não são dados reais do usuário."""
    conn = get_connection()
    cur = conn.execute("INSERT INTO artistas (nome) VALUES (?)", ("Radiohead",))
    artista_id = cur.lastrowid

    cur = conn.execute(
        """INSERT INTO albuns (nome, artista_id, ano_lancamento, genero)
           VALUES (?, ?, ?, ?)""",
        ("OK Computer (exemplo)", artista_id, 1997, "rock alternativo"),
    )
    album_id = cur.lastrowid

    hoje = date.today()
    conn.execute(
        """INSERT INTO escutas (album_id, data, nota, review, faixa_favorita)
           VALUES (?, ?, ?, ?, ?)""",
        (
            album_id, (hoje - timedelta(days=30)).isoformat(), 4.5,
            "Primeira escuta completa, impressionante de cabo a rabo. (exemplo)",
            "Paranoid Android",
        ),
    )

    conn.execute("UPDATE app_meta SET seeded = 1 WHERE id = 1")
    conn.commit()


def inicializar_banco() -> None:
    """Ponto único chamado por app.py: garante schema + dados iniciais."""
    init_db()
    if banco_esta_vazio():
        seed_dados_iniciais()
