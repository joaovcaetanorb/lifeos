"""Conexões somente-leitura aos bancos SQLite dos outros módulos do LifeOS.

Este módulo não tem banco próprio: cada card do Dashboard Geral lê direto
do banco do módulo correspondente, sem nunca escrever nele. Cada módulo
continua sendo o único dono (e responsável por schema/migração) dos seus
próprios dados.
"""

import sqlite3
from pathlib import Path

MODULES_DIR = Path(__file__).resolve().parent.parent

DB_PATHS = {
    "financeiro": MODULES_DIR / "financeiro" / "database" / "financeiro.db",
    "projetos": MODULES_DIR / "projetos" / "database" / "projetos.db",
    "habitos": MODULES_DIR / "habitos" / "database" / "habitos.db",
    "livros": MODULES_DIR / "livros" / "database" / "livros.db",
    "musica": MODULES_DIR / "musica" / "database" / "musica.db",
}


def get_connection(modulo: str) -> sqlite3.Connection | None:
    """Abre uma conexão somente-leitura com o banco do módulo indicado.

    Retorna None se o módulo ainda nunca foi executado (banco inexistente)
    — nesse caso o card correspondente aparece como "sem dados ainda".
    """
    caminho = DB_PATHS[modulo]
    if not caminho.exists():
        return None
    uri = f"file:{caminho.as_posix()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn
