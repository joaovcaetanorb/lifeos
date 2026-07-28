"""Camada de acesso ao SQLite: conexão, criação de schema e seed inicial.

Nenhuma regra de negócio aqui — só estrutura de dados e bootstrap.
"""

import sqlite3
from pathlib import Path
from datetime import date, timedelta

DB_DIR = Path(__file__).parent / "database"
DB_PATH = DB_DIR / "projetos.db"
UPLOADS_DIR = DB_DIR / "uploads"

SCHEMA = """
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
    concluido INTEGER NOT NULL DEFAULT 0,
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


def init_db() -> None:
    """Cria as tabelas caso não existam. Idempotente."""
    conn = get_connection()
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()


def banco_esta_vazio() -> bool:
    conn = get_connection()
    try:
        cur = conn.execute("SELECT COUNT(*) AS n FROM projetos")
        return cur.fetchone()["n"] == 0
    finally:
        conn.close()


def seed_dados_iniciais() -> None:
    """Popula o banco com projetos fictícios na primeira execução, só para
    a tela não nascer vazia — não são dados reais do usuário."""
    conn = get_connection()
    try:
        hoje = date.today()

        cur = conn.execute(
            """INSERT INTO projetos (nome, descricao, orcamento, observacoes, status)
               VALUES (?, ?, ?, ?, ?)""",
            ("Viagem (exemplo)", "Viagem de fim de ano", 3000.0, "Ver datas de promoção de passagem.", "Ativo"),
        )
        projeto_id = cur.lastrowid

        conn.executemany(
            "INSERT INTO projeto_checklist (projeto_id, descricao, concluido, ordem) VALUES (?, ?, ?, ?)",
            [
                (projeto_id, "Definir destino", 1, 0),
                (projeto_id, "Comprar passagem", 0, 1),
                (projeto_id, "Reservar hospedagem", 0, 2),
            ],
        )

        conn.execute(
            "INSERT INTO projeto_aportes (projeto_id, data, valor, observacao) VALUES (?, ?, ?, ?)",
            (projeto_id, (hoje - timedelta(days=10)).isoformat(), 300.0, "Aporte inicial (exemplo)"),
        )

        conn.commit()
    finally:
        conn.close()


def inicializar_banco() -> None:
    """Ponto único chamado por app.py: garante schema + dados iniciais."""
    init_db()
    if banco_esta_vazio():
        seed_dados_iniciais()
