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

Capas de livro (UPLOADS_DIR) continuam em disco local — só os dados SQL
migraram pro Turso.
"""

import libsql
import streamlit as st
from pathlib import Path
from datetime import date, timedelta

DB_DIR = Path(__file__).parent / "database"
UPLOADS_DIR = DB_DIR / "uploads"

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


@st.cache_resource(show_spinner=False)
def _conexao_compartilhada():
    conn = libsql.connect(
        database=st.secrets["TURSO_LIVROS_URL"],
        auth_token=st.secrets["TURSO_LIVROS_TOKEN"],
    )
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


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
    """Garante uma linha em app_meta. Se o banco já existia (tinha livros)
    antes dessa tabela ser criada, marca como já semeado — sem isso, apagar
    o último livro faria o próximo carregamento recriar o exemplo."""
    row = conn.execute("SELECT seeded FROM app_meta WHERE id = 1").fetchone()
    if row is None:
        tinha_dados = conn.execute("SELECT COUNT(*) AS n FROM livros").fetchone()[0] > 0
        conn.execute("INSERT INTO app_meta (id, seeded) VALUES (1, ?)", (1 if tinha_dados else 0,))

    colunas_livros = {r[1] for r in conn.execute("PRAGMA table_info(livros)").fetchall()}
    if "favorito" not in colunas_livros:
        conn.execute("ALTER TABLE livros ADD COLUMN favorito INTEGER NOT NULL DEFAULT 0")

    conn.commit()


def init_db() -> None:
    """Cria as tabelas caso não existam e aplica migrações. Idempotente."""
    conn = get_connection()
    conn.executescript(SCHEMA)
    conn.commit()
    _migrar_schema(conn)


def banco_esta_vazio() -> bool:
    """True apenas se o app nunca foi semeado — não reflete se o usuário
    apagou todos os livros manualmente (isso é um estado válido)."""
    conn = get_connection()
    row = conn.execute("SELECT seeded FROM app_meta WHERE id = 1").fetchone()
    return row is None or row[0] == 0


def seed_dados_iniciais() -> None:
    """Popula o banco com um livro fictício na primeira execução, só para
    a tela não nascer vazia — não são dados reais do usuário."""
    conn = get_connection()
    cur = conn.execute("INSERT INTO autores (nome) VALUES (?)", ("George Orwell",))
    autor_id = cur.lastrowid

    cur = conn.execute(
        """INSERT INTO livros (nome, autor_id, ano_publicacao, genero)
           VALUES (?, ?, ?, ?)""",
        ("1984 (exemplo)", autor_id, 1949, "distopia"),
    )
    livro_id = cur.lastrowid

    hoje = date.today()
    conn.execute(
        """INSERT INTO leituras (livro_id, data, status, nota, review)
           VALUES (?, ?, ?, ?, ?)""",
        (
            livro_id, (hoje - timedelta(days=20)).isoformat(), "Concluído", 5.0,
            "Perturbador do início ao fim. (exemplo)",
        ),
    )

    conn.execute("UPDATE app_meta SET seeded = 1 WHERE id = 1")
    conn.commit()


def inicializar_banco() -> None:
    """Ponto único chamado por app.py: garante schema + dados iniciais."""
    init_db()
    if banco_esta_vazio():
        seed_dados_iniciais()
