"""Banco próprio do Analytics: só um cache de respostas geradas por IA
(nunca dados originais — esses continuam só nos módulos donos). Também
expõe conexões aos bancos remotos (Turso) dos outros módulos, mesmo padrão
do Dashboard Geral: nenhuma escrita nunca acontece nos bancos alheios (por
convenção de código — Turso ainda não tem token somente-leitura configurado
por módulo aqui).
"""

import os

import libsql
import streamlit as st

# 2026-07-30: trocado pra "embedded replica" (sync_url) — ver
# modules/financeiro/database.py pro detalhe completo. Conexões
# cross-módulo são só leitura (nunca escrevem), então usam embedded
# replica sem wrapper de sync-no-commit — só a conexão PRÓPRIA (que grava
# respostas/sugestões) precisa disso.
_REPLICA_DIR = os.path.join(os.path.dirname(__file__), "database", "replicas_cross_modulo")


class _ConexaoComSyncNoCommit:
    def __init__(self, conn):
        self._conn = conn

    def commit(self):
        self._conn.commit()
        self._conn.sync()

    def __getattr__(self, nome):
        return getattr(self._conn, nome)


DB_PATHS_SECRETS = {
    "financeiro": ("TURSO_FINANCEIRO_URL", "TURSO_FINANCEIRO_TOKEN"),
    "projetos": ("TURSO_PROJETOS_URL", "TURSO_PROJETOS_TOKEN"),
    "habitos": ("TURSO_HABITOS_URL", "TURSO_HABITOS_TOKEN"),
    "humor": ("TURSO_HUMOR_URL", "TURSO_HUMOR_TOKEN"),
    "livros": ("TURSO_LIVROS_URL", "TURSO_LIVROS_TOKEN"),
    "musica": ("TURSO_MUSICA_URL", "TURSO_MUSICA_TOKEN"),
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS respostas_perguntas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pergunta TEXT NOT NULL,
    resposta TEXT NOT NULL,
    gerado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sugestoes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    texto TEXT NOT NULL,
    gerado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


@st.cache_resource(show_spinner=False)
def _conexao_propria_compartilhada():
    replica_path = os.path.join(os.path.dirname(__file__), "database", "analytics_replica.db")
    os.makedirs(os.path.dirname(replica_path), exist_ok=True)
    conn = libsql.connect(
        database=replica_path,
        sync_url=st.secrets["TURSO_ANALYTICS_URL"],
        auth_token=st.secrets["TURSO_ANALYTICS_TOKEN"],
    )
    conn.sync()
    return _ConexaoComSyncNoCommit(conn)


def get_connection():
    """Conexão com o banco PRÓPRIO do analytics (só cache), reaproveitada
    entre chamadas — quem chama NÃO deve fechá-la."""
    return _conexao_propria_compartilhada()


@st.cache_resource(show_spinner=False)
def _conexao_modulo_compartilhada(modulo: str):
    chave_url, chave_token = DB_PATHS_SECRETS[modulo]
    try:
        url = st.secrets[chave_url]
        token = st.secrets[chave_token]
    except (KeyError, FileNotFoundError):
        return None
    os.makedirs(_REPLICA_DIR, exist_ok=True)
    conn = libsql.connect(
        database=os.path.join(_REPLICA_DIR, f"{modulo}_replica.db"),
        sync_url=url,
        auth_token=token,
    )
    conn.sync()
    return conn


def get_connection_modulo(modulo: str):
    """Conexão com o banco remoto de outro módulo do LifeOS, reaproveitada
    entre chamadas (quem chama NÃO deve fechá-la).

    Retorna None se as credenciais desse módulo não estiverem
    configuradas — nesse caso a agregação correspondente simplesmente não
    entra no contexto passado pra IA. Se o schema do módulo ainda não foi
    criado (nunca aberto), a conexão volta normalmente mas a query pode
    falhar — por isso `calculations.py` envolve cada leitura num
    try/except, não só no `is None`.
    """
    return _conexao_modulo_compartilhada(modulo)


def linha_para_dict(cursor, row: tuple | None) -> dict | None:
    """Converte uma linha (tupla) + cursor.description em dict — o driver
    do Turso não suporta row_factory tipo sqlite3.Row."""
    if row is None:
        return None
    colunas = [d[0] for d in cursor.description]
    return dict(zip(colunas, row))


def init_db() -> None:
    """Cria as tabelas do cache próprio caso não existam. Idempotente."""
    conn = get_connection()
    conn.executescript(SCHEMA)
    conn.commit()


def inicializar_banco() -> None:
    """Ponto único chamado por app.py."""
    init_db()
