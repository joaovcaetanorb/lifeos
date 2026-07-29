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

Fotos de capa (UPLOADS_DIR) continuam em disco local — só os dados SQL
migraram pro Turso (upload de arquivo é um problema à parte do disco
efêmero, não resolvido aqui).
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


@st.cache_resource(show_spinner=False)
def _conexao_compartilhada():
    conn = libsql.connect(
        database=st.secrets["TURSO_PROJETOS_URL"],
        auth_token=st.secrets["TURSO_PROJETOS_TOKEN"],
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
    """Garante uma linha em app_meta. Se o banco já existia (tinha projetos)
    antes dessa tabela ser criada, marca como já semeado — sem isso, apagar
    o último projeto faria o próximo carregamento recriar o exemplo.

    Também adiciona colunas de detalhe do checklist em bancos já existentes
    (ALTER TABLE não é coberto pelo CREATE TABLE IF NOT EXISTS)."""
    row = conn.execute("SELECT seeded FROM app_meta WHERE id = 1").fetchone()
    if row is None:
        tinha_projetos = conn.execute("SELECT COUNT(*) AS n FROM projetos").fetchone()[0] > 0
        conn.execute("INSERT INTO app_meta (id, seeded) VALUES (1, ?)", (1 if tinha_projetos else 0,))

    colunas_checklist = {r[1] for r in conn.execute("PRAGMA table_info(projeto_checklist)").fetchall()}
    for coluna in ("notas", "prazo", "link", "foto_path"):
        if coluna not in colunas_checklist:
            conn.execute(f"ALTER TABLE projeto_checklist ADD COLUMN {coluna} TEXT DEFAULT ''")

    conn.commit()


def init_db() -> None:
    """Cria as tabelas caso não existam e aplica migrações. Idempotente."""
    conn = get_connection()
    conn.executescript(SCHEMA)
    conn.commit()
    _migrar_schema(conn)


def banco_esta_vazio() -> bool:
    """True apenas se o app nunca foi semeado — não reflete se o usuário
    apagou todos os projetos manualmente (isso é um estado válido)."""
    conn = get_connection()
    row = conn.execute("SELECT seeded FROM app_meta WHERE id = 1").fetchone()
    return row is None or row[0] == 0


def seed_dados_iniciais() -> None:
    """Popula o banco com projetos fictícios na primeira execução, só para
    a tela não nascer vazia — não são dados reais do usuário."""
    conn = get_connection()
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


def inicializar_banco() -> None:
    """Ponto único chamado por app.py: garante schema + dados iniciais."""
    init_db()
    if banco_esta_vazio():
        seed_dados_iniciais()
