"""Conexões aos bancos remotos (Turso/libSQL) dos outros módulos do LifeOS,
mais um bancozinho PRÓPRIO só pra cache da saudação gerada por IA.

Cada card do Dashboard Geral lê o banco do módulo correspondente, mas
NUNCA escreve nele — cada módulo continua sendo o único dono (e
responsável por schema/migração) dos seus próprios dados. Diferente da
época do SQLite local (onde isso era garantido tecnicamente via
`mode=ro` na conexão), com Turso essa garantia agora é só por convenção
de código — ainda não configuramos tokens somente-leitura por módulo.
"""

import os

import libsql
import streamlit as st

# 2026-07-30: trocado pra "embedded replica" (sync_url) — conexão remota
# pura media ~275ms por query; ver modules/financeiro/database.py pro
# detalhe completo. As conexões cross-módulo abaixo são só leitura (por
# convenção, nunca escrevem), então usam embedded replica sem wrapper de
# sync-no-commit — só a conexão PRÓPRIA (que grava a saudação) precisa
# disso. Cada card usa seu próprio arquivo de replica local (nomeado por
# módulo) pra não colidir com o arquivo do módulo dono.
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
    os.makedirs(_REPLICA_DIR, exist_ok=True)
    conn = libsql.connect(
        database=os.path.join(_REPLICA_DIR, f"{modulo}_replica.db"),
        sync_url=url,
        auth_token=token,
    )
    conn.sync()
    return conn


def get_connection(modulo: str):
    """Conexão com o banco remoto do módulo indicado, reaproveitada entre
    chamadas (quem chama NÃO deve fechá-la).

    Retorna None se as credenciais desse módulo não estiverem
    configuradas em secrets.toml — nesse caso o card correspondente
    aparece como "sem dados ainda". Se o schema do módulo ainda não foi
    criado (módulo nunca aberto), a conexão é retornada normalmente, mas
    a query subsequente pode falhar — por isso todo `calculations.py`
    daqui envolve a leitura num try/except, não só no `is None`.

    Re-sincroniza a cada chamada (não só na criação): a conexão em si é
    cacheada (`st.cache_resource`, dura o container inteiro), mas sem
    ressincronizar aqui os cards ficariam presos no estado de quando o
    container ligou — visto na prática como "Hábitos ativos: 0" no
    Dashboard Geral mesmo depois do usuário cadastrar hábitos de verdade
    no módulo Hábitos. Um `sync()` incremental (sem mudança real) é
    barato perto do ganho de nunca mais mostrar dado cross-módulo velho.
    """
    conn = _conexao_modulo_compartilhada(modulo)
    if conn is not None:
        conn.sync()
    return conn


@st.cache_resource(show_spinner=False)
def _conexao_propria_compartilhada():
    replica_path = os.path.join(os.path.dirname(__file__), "database", "dashboard_geral_replica.db")
    os.makedirs(os.path.dirname(replica_path), exist_ok=True)
    conn = libsql.connect(
        database=replica_path,
        sync_url=st.secrets["TURSO_DASHBOARD_GERAL_URL"],
        auth_token=st.secrets["TURSO_DASHBOARD_GERAL_TOKEN"],
    )
    conn.sync()
    return _ConexaoComSyncNoCommit(conn)


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
