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


def _migrar_schema(conn: sqlite3.Connection) -> None:
    """Garante uma linha em app_meta. Se o banco já existia (tinha projetos)
    antes dessa tabela ser criada, marca como já semeado — sem isso, apagar
    o último projeto faria o próximo carregamento recriar o exemplo.

    Também adiciona colunas de detalhe do checklist em bancos já existentes
    (ALTER TABLE não é coberto pelo CREATE TABLE IF NOT EXISTS)."""
    row = conn.execute("SELECT seeded FROM app_meta WHERE id = 1").fetchone()
    if row is None:
        tinha_projetos = conn.execute("SELECT COUNT(*) AS n FROM projetos").fetchone()["n"] > 0
        conn.execute("INSERT INTO app_meta (id, seeded) VALUES (1, ?)", (1 if tinha_projetos else 0,))

    colunas_checklist = {row["name"] for row in conn.execute("PRAGMA table_info(projeto_checklist)").fetchall()}
    for coluna in ("notas", "prazo", "link", "foto_path"):
        if coluna not in colunas_checklist:
            conn.execute(f"ALTER TABLE projeto_checklist ADD COLUMN {coluna} TEXT DEFAULT ''")

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
    apagou todos os projetos manualmente (isso é um estado válido)."""
    conn = get_connection()
    try:
        row = conn.execute("SELECT seeded FROM app_meta WHERE id = 1").fetchone()
        return row is None or row["seeded"] == 0
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

        conn.execute("UPDATE app_meta SET seeded = 1 WHERE id = 1")
        conn.commit()
    finally:
        conn.close()


def inicializar_banco() -> None:
    """Ponto único chamado por app.py: garante schema + dados iniciais."""
    init_db()
    if banco_esta_vazio():
        seed_dados_iniciais()
