"""Camada de acesso ao SQLite: conexão, criação de schema e seed inicial.

Nenhuma regra de negócio aqui — só estrutura de dados e bootstrap.
"""

import sqlite3
from pathlib import Path
from datetime import date, timedelta

DB_DIR = Path(__file__).parent / "database"
DB_PATH = DB_DIR / "livros.db"
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


def get_connection() -> sqlite3.Connection:
    """Abre uma conexão nova com row_factory e foreign_keys configurados.

    SQLite + Streamlit: cada rerun pode acontecer em thread diferente,
    então não reaproveitamos uma conexão global — abrimos e fechamos
    por operação (custo desprezível para um app pessoal).
    """
    DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _migrar_schema(conn: sqlite3.Connection) -> None:
    """Garante uma linha em app_meta. Se o banco já existia (tinha livros)
    antes dessa tabela ser criada, marca como já semeado — sem isso, apagar
    o último livro faria o próximo carregamento recriar o exemplo."""
    row = conn.execute("SELECT seeded FROM app_meta WHERE id = 1").fetchone()
    if row is None:
        tinha_dados = conn.execute("SELECT COUNT(*) AS n FROM livros").fetchone()["n"] > 0
        conn.execute("INSERT INTO app_meta (id, seeded) VALUES (1, ?)", (1 if tinha_dados else 0,))
    conn.commit()


def init_db() -> None:
    """Cria as tabelas caso não existam e aplica migrações. Idempotente."""
    conn = get_connection()
    try:
        conn.executescript(SCHEMA)
        conn.commit()
        _migrar_schema(conn)
    finally:
        conn.close()


def banco_esta_vazio() -> bool:
    """True apenas se o app nunca foi semeado — não reflete se o usuário
    apagou todos os livros manualmente (isso é um estado válido)."""
    conn = get_connection()
    try:
        row = conn.execute("SELECT seeded FROM app_meta WHERE id = 1").fetchone()
        return row is None or row["seeded"] == 0
    finally:
        conn.close()


def seed_dados_iniciais() -> None:
    """Popula o banco com um livro fictício na primeira execução, só para
    a tela não nascer vazia — não são dados reais do usuário."""
    conn = get_connection()
    try:
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
    finally:
        conn.close()


def inicializar_banco() -> None:
    """Ponto único chamado por app.py: garante schema + dados iniciais."""
    init_db()
    if banco_esta_vazio():
        seed_dados_iniciais()
