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
CREATE TABLE IF NOT EXISTS config (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    salario REAL NOT NULL,
    vale_alimentacao REAL NOT NULL,
    dia_util_pagamento INTEGER NOT NULL DEFAULT 5,
    reserva_meta REAL NOT NULL DEFAULT 0,
    reserva_aporte_padrao REAL NOT NULL DEFAULT 0,
    inicio_controle TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS contas_fixas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    descricao TEXT NOT NULL,
    valor REAL NOT NULL,
    ativo INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS gastos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    data TEXT NOT NULL,
    descricao TEXT NOT NULL,
    valor REAL NOT NULL,
    categoria TEXT NOT NULL,
    forma_pagamento TEXT NOT NULL,
    hora TEXT DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS cartao_compras (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    descricao TEXT NOT NULL,
    data_compra TEXT NOT NULL,
    valor_total REAL NOT NULL,
    parcelas INTEGER NOT NULL DEFAULT 1,
    categoria TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS planejamento (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mes_referencia TEXT NOT NULL,
    categoria TEXT NOT NULL,
    valor_planejado REAL NOT NULL,
    UNIQUE(mes_referencia, categoria)
);

CREATE TABLE IF NOT EXISTS reserva_movimentos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    data TEXT NOT NULL,
    valor REAL NOT NULL,
    tipo TEXT NOT NULL CHECK (tipo IN ('Aporte', 'Retirada')),
    observacao TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


@st.cache_resource(show_spinner=False)
def _conexao_compartilhada():
    conn = libsql.connect(
        database=st.secrets["TURSO_FINANCEIRO_URL"],
        auth_token=st.secrets["TURSO_FINANCEIRO_TOKEN"],
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
    """Ajustes de schema em bancos já existentes (ALTER TABLE não é coberto
    pelo CREATE TABLE IF NOT EXISTS)."""
    colunas_gastos = {r[1] for r in conn.execute("PRAGMA table_info(gastos)").fetchall()}
    if "hora" not in colunas_gastos:
        conn.execute("ALTER TABLE gastos ADD COLUMN hora TEXT DEFAULT ''")

    colunas_config = {r[1] for r in conn.execute("PRAGMA table_info(config)").fetchall()}
    if "inicio_controle" not in colunas_config:
        conn.execute("ALTER TABLE config ADD COLUMN inicio_controle TEXT DEFAULT ''")

    conn.commit()


def init_db() -> None:
    """Cria as tabelas caso não existam e aplica migrações. Idempotente."""
    conn = get_connection()
    conn.executescript(SCHEMA)
    conn.commit()
    _migrar_schema(conn)


def banco_esta_vazio() -> bool:
    conn = get_connection()
    return conn.execute("SELECT COUNT(*) AS n FROM config").fetchone()[0] == 0


def seed_dados_iniciais() -> None:
    """Popula o banco na primeira execução.

    Config e contas fixas usam os valores reais informados (são a base
    real de uso do app, não dados de teste). Gastos, compras de cartão,
    planejamento e reserva recebem alguns lançamentos fictícios apenas
    para as telas e gráficos não nascerem vazios.
    """
    conn = get_connection()
    conn.execute(
        """INSERT INTO config
           (id, salario, vale_alimentacao, dia_util_pagamento, reserva_meta, reserva_aporte_padrao)
           VALUES (1, 2700, 700, 5, 3000, 150)"""
    )

    contas_fixas = [
        ("Casa", 230),
        ("Ajuda irmão 1", 125),
        ("Ajuda irmão 2", 150),
        ("Outra obrigação", 110),
        ("Psicóloga", 200),
    ]
    conn.executemany(
        "INSERT INTO contas_fixas (descricao, valor, ativo) VALUES (?, ?, 1)",
        contas_fixas,
    )

    hoje = date.today()
    gastos_ficticios = [
        (hoje - timedelta(days=1), "Almoço", 28.90, "Alimentação", "Débito"),
        (hoje - timedelta(days=2), "Uber", 18.50, "Transporte", "Pix"),
        (hoje - timedelta(days=3), "Cinema", 45.00, "Lazer", "Crédito"),
        (hoje - timedelta(days=5), "Mercado", 96.30, "Alimentação", "Vale alimentação"),
        (hoje - timedelta(days=7), "Farmácia", 32.00, "Saúde", "Débito"),
        (hoje - timedelta(days=10), "Netflix", 39.90, "Assinaturas", "Crédito"),
    ]
    conn.executemany(
        """INSERT INTO gastos (data, descricao, valor, categoria, forma_pagamento)
           VALUES (?, ?, ?, ?, ?)""",
        [(d.isoformat(), desc, valor, cat, forma) for d, desc, valor, cat, forma in gastos_ficticios],
    )

    conn.execute(
        """INSERT INTO cartao_compras (descricao, data_compra, valor_total, parcelas, categoria)
           VALUES (?, ?, ?, ?, ?)""",
        ("Notebook (exemplo)", (hoje - timedelta(days=20)).isoformat(), 2850.00, 6, "Compras pessoais"),
    )

    mes_ref = hoje.strftime("%Y-%m")
    planejamento_ficticio = [
        (mes_ref, "Transporte", 150.0),
        (mes_ref, "Lazer", 100.0),
        (mes_ref, "Compras pessoais", 100.0),
        (mes_ref, "Outros", 80.0),
    ]
    conn.executemany(
        """INSERT INTO planejamento (mes_referencia, categoria, valor_planejado)
           VALUES (?, ?, ?)""",
        planejamento_ficticio,
    )

    conn.execute(
        """INSERT INTO reserva_movimentos (data, valor, tipo, observacao)
           VALUES (?, ?, ?, ?)""",
        ((hoje - timedelta(days=15)).isoformat(), 150.0, "Aporte", "Aporte inicial (exemplo)"),
    )

    conn.commit()


def inicializar_banco() -> None:
    """Ponto único chamado por app.py: garante schema + dados iniciais."""
    init_db()
    if banco_esta_vazio():
        seed_dados_iniciais()
