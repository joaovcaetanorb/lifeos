"""Camada de acesso ao banco remoto (Turso/libSQL): conexão, criação de
schema e seed inicial.

Nenhuma regra de negócio aqui — só estrutura de dados e bootstrap.

Migrado de SQLite local pra Turso em 2026-07-29 (Streamlit Community Cloud
tem disco efêmero — um arquivo .db local não sobrevive a um restart do
container). O driver do Turso (`libsql`) imita o `sqlite3` em quase tudo
(execute/fetchone/fetchall/executemany/lastrowid/PRAGMA/executescript todos
funcionam igual), MAS não suporta `conn.row_factory = sqlite3.Row` — as
linhas voltam como tupla simples. Por isso `linha_para_dict()` abaixo:
sempre que o código precisar acessar uma coluna pelo nome (não só por
posição), usa essa função em vez de `dict(row)` ou `row["coluna"]`.
"""

import libsql
import streamlit as st
from datetime import date, timedelta

# Diferente do sqlite3 local (abrir/fechar por operação era de graça), uma
# conexão remota tem custo real de handshake (~1s na primeira vez, medido
# contra o Turso) — reaproveitar uma única conexão via cache_resource evita
# pagar esse custo em toda chamada. Por isso models.py NÃO fecha mais a
# conexão depois de usar (fechar quebraria a próxima chamada da sessão).

SCHEMA = """
CREATE TABLE IF NOT EXISTS app_meta (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    seeded INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS habitos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    ativo INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS habito_registros (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    habito_id INTEGER NOT NULL REFERENCES habitos(id) ON DELETE CASCADE,
    data TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(habito_id, data)
);
"""


@st.cache_resource(show_spinner=False)
def _conexao_compartilhada():
    conn = libsql.connect(
        database=st.secrets["TURSO_HABITOS_URL"],
        auth_token=st.secrets["TURSO_HABITOS_TOKEN"],
    )
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def get_connection():
    """Conexão com o banco remoto no Turso, reaproveitada entre chamadas
    (ver nota de custo de handshake acima) — quem chama NÃO deve fechá-la."""
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
    """Garante uma linha em app_meta. Se o banco já existia (tinha hábitos)
    antes dessa tabela ser criada, marca como já semeado — sem isso, apagar
    o último hábito faria o próximo carregamento recriar o exemplo."""
    row = conn.execute("SELECT seeded FROM app_meta WHERE id = 1").fetchone()
    if row is None:
        tinha_dados = conn.execute("SELECT COUNT(*) AS n FROM habitos").fetchone()[0] > 0
        conn.execute("INSERT INTO app_meta (id, seeded) VALUES (1, ?)", (1 if tinha_dados else 0,))
    conn.commit()


def init_db() -> None:
    """Cria as tabelas caso não existam e aplica migrações. Idempotente."""
    conn = get_connection()
    conn.executescript(SCHEMA)
    conn.commit()
    _migrar_schema(conn)


def banco_esta_vazio() -> bool:
    """True apenas se o app nunca foi semeado — não reflete se o usuário
    apagou todos os hábitos manualmente (isso é um estado válido)."""
    conn = get_connection()
    row = conn.execute("SELECT seeded FROM app_meta WHERE id = 1").fetchone()
    return row is None or row[0] == 0


def seed_dados_iniciais() -> None:
    """Popula o banco com um hábito fictício e alguns dias marcados na
    primeira execução, só para a tela não nascer vazia — não são dados
    reais do usuário."""
    conn = get_connection()
    cur = conn.execute(
        "INSERT INTO habitos (nome, ativo) VALUES (?, 1)",
        ("Exercitar (exemplo)",),
    )
    habito_id = cur.lastrowid

    hoje = date.today()
    dias_marcados = [hoje - timedelta(days=i) for i in (1, 2, 3, 5, 6)]
    conn.executemany(
        "INSERT INTO habito_registros (habito_id, data) VALUES (?, ?)",
        [(habito_id, d.isoformat()) for d in dias_marcados],
    )

    conn.execute("UPDATE app_meta SET seeded = 1 WHERE id = 1")
    conn.commit()


def inicializar_banco() -> None:
    """Ponto único chamado por app.py: garante schema + dados iniciais."""
    init_db()
    if banco_esta_vazio():
        seed_dados_iniciais()
