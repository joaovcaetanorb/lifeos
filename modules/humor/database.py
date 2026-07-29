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
"""

import libsql
import streamlit as st
from datetime import date, timedelta

SCHEMA = """
CREATE TABLE IF NOT EXISTS app_meta (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    seeded INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS registros_humor (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    data TEXT NOT NULL,
    hora TEXT NOT NULL DEFAULT '',
    nota INTEGER NOT NULL CHECK (nota BETWEEN 1 AND 10),
    tags TEXT NOT NULL DEFAULT '',
    nota_livre TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


@st.cache_resource(show_spinner=False)
def _conexao_compartilhada():
    return libsql.connect(
        database=st.secrets["TURSO_HUMOR_URL"],
        auth_token=st.secrets["TURSO_HUMOR_TOKEN"],
    )


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
    """Garante uma linha em app_meta. Se o banco já existia (tinha registros)
    antes dessa tabela ser criada, marca como já semeado — sem isso, apagar
    o último registro faria o próximo carregamento recriar o exemplo."""
    row = conn.execute("SELECT seeded FROM app_meta WHERE id = 1").fetchone()
    if row is None:
        tinha_dados = conn.execute("SELECT COUNT(*) AS n FROM registros_humor").fetchone()[0] > 0
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
    apagou todos os registros manualmente (isso é um estado válido)."""
    conn = get_connection()
    row = conn.execute("SELECT seeded FROM app_meta WHERE id = 1").fetchone()
    return row is None or row[0] == 0


def seed_dados_iniciais() -> None:
    """Popula o banco com alguns registros fictícios na primeira execução,
    só para a tela não nascer vazia — não são dados reais do usuário."""
    conn = get_connection()
    hoje = date.today()
    exemplos = [
        (hoje - timedelta(days=4), "09:00", 6, "Cansado,Focado", ""),
        (hoje - timedelta(days=2), "20:30", 8, "Animado,Grato", "Registro de exemplo."),
        (hoje - timedelta(days=1), "13:00", 5, "Ansioso", ""),
    ]
    conn.executemany(
        """INSERT INTO registros_humor (data, hora, nota, tags, nota_livre)
           VALUES (?, ?, ?, ?, ?)""",
        [(d.isoformat(), h, n, t, o) for d, h, n, t, o in exemplos],
    )

    conn.execute("UPDATE app_meta SET seeded = 1 WHERE id = 1")
    conn.commit()


def inicializar_banco() -> None:
    """Ponto único chamado por app.py: garante schema + dados iniciais."""
    init_db()
    if banco_esta_vazio():
        seed_dados_iniciais()
