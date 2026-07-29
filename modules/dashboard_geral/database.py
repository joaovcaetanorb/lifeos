"""Conexões aos bancos remotos (Turso/libSQL) dos outros módulos do LifeOS,
mais um bancozinho PRÓPRIO só pra cache da saudação gerada por IA.

Cada card do Dashboard Geral lê o banco do módulo correspondente, mas
NUNCA escreve nele — cada módulo continua sendo o único dono (e
responsável por schema/migração) dos seus próprios dados. Diferente da
época do SQLite local (onde isso era garantido tecnicamente via
`mode=ro` na conexão), com Turso essa garantia agora é só por convenção
de código — ainda não configuramos tokens somente-leitura por módulo.
"""

import libsql
import streamlit as st

DB_PATHS_SECRETS = {
    "financeiro": ("TURSO_FINANCEIRO_URL", "TURSO_FINANCEIRO_TOKEN"),
    "projetos": ("TURSO_PROJETOS_URL", "TURSO_PROJETOS_TOKEN"),
    "habitos": ("TURSO_HABITOS_URL", "TURSO_HABITOS_TOKEN"),
    "livros": ("TURSO_LIVROS_URL", "TURSO_LIVROS_TOKEN"),
    "musica": ("TURSO_MUSICA_URL", "TURSO_MUSICA_TOKEN"),
    "humor": ("TURSO_HUMOR_URL", "TURSO_HUMOR_TOKEN"),
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS saudacoes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    texto TEXT NOT NULL,
    gerado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


@st.cache_resource(show_spinner=False)
def _conexao_modulo_compartilhada(modulo: str):
    chave_url, chave_token = DB_PATHS_SECRETS[modulo]
    try:
        url = st.secrets[chave_url]
        token = st.secrets[chave_token]
    except (KeyError, FileNotFoundError):
        return None
    return libsql.connect(database=url, auth_token=token)


def get_connection(modulo: str):
    """Conexão com o banco remoto do módulo indicado, reaproveitada entre
    chamadas (quem chama NÃO deve fechá-la).

    Retorna None se as credenciais desse módulo não estiverem
    configuradas em secrets.toml — nesse caso o card correspondente
    aparece como "sem dados ainda". Se o schema do módulo ainda não foi
    criado (módulo nunca aberto), a conexão é retornada normalmente, mas
    a query subsequente pode falhar — por isso todo `calculations.py`
    daqui envolve a leitura num try/except, não só no `is None`.
    """
    return _conexao_modulo_compartilhada(modulo)


@st.cache_resource(show_spinner=False)
def _conexao_propria_compartilhada():
    return libsql.connect(
        database=st.secrets["TURSO_DASHBOARD_GERAL_URL"],
        auth_token=st.secrets["TURSO_DASHBOARD_GERAL_TOKEN"],
    )


def get_connection_propria():
    """Conexão com o banco PRÓPRIO do Dashboard Geral (só cache de
    saudação — nunca dados de outros módulos), reaproveitada entre
    chamadas — quem chama NÃO deve fechá-la."""
    return _conexao_propria_compartilhada()


def linha_para_dict(cursor, row: tuple | None) -> dict | None:
    """Converte uma linha (tupla) + cursor.description em dict — o driver
    do Turso não suporta row_factory tipo sqlite3.Row."""
    if row is None:
        return None
    colunas = [d[0] for d in cursor.description]
    return dict(zip(colunas, row))


def init_db() -> None:
    """Cria as tabelas do cache próprio caso não existam. Idempotente."""
    conn = get_connection_propria()
    conn.executescript(SCHEMA)
    conn.commit()


def inicializar_banco() -> None:
    """Ponto único chamado por app.py."""
    init_db()
