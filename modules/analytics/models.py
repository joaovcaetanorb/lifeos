"""Camada de acesso ao cache de respostas de IA. Sem regra de negócio.

Funções de listagem retornam pandas.DataFrame ou dict. Funções de escrita
retornam None ou o id criado.

A conexão (`get_connection()`) é compartilhada/cacheada — por isso nenhuma
função aqui chama `conn.close()`.
"""

import pandas as pd
from database import get_connection, linha_para_dict


def obter_resposta_cacheada(pergunta: str) -> dict | None:
    """Última resposta salva pra essa pergunta exata (perguntas
    pré-definidas repetem o mesmo texto, então reaproveitam o cache;
    perguntas livres só reaproveitam se digitadas de novo, idênticas)."""
    conn = get_connection()
    cursor = conn.execute(
        """SELECT * FROM respostas_perguntas WHERE pergunta = ?
           ORDER BY gerado_em DESC LIMIT 1""",
        (pergunta,),
    )
    return linha_para_dict(cursor, cursor.fetchone())


def salvar_resposta(pergunta: str, resposta: str) -> None:
    conn = get_connection()
    conn.execute(
        "INSERT INTO respostas_perguntas (pergunta, resposta) VALUES (?, ?)",
        (pergunta, resposta),
    )
    conn.commit()


def listar_perguntas_recentes(limite: int = 10) -> pd.DataFrame:
    conn = get_connection()
    return pd.read_sql_query(
        "SELECT * FROM respostas_perguntas ORDER BY gerado_em DESC LIMIT ?",
        conn, params=[limite],
    )


def obter_sugestao_mais_recente() -> dict | None:
    conn = get_connection()
    cursor = conn.execute("SELECT * FROM sugestoes ORDER BY gerado_em DESC LIMIT 1")
    return linha_para_dict(cursor, cursor.fetchone())


def salvar_sugestao(texto: str) -> None:
    conn = get_connection()
    conn.execute("INSERT INTO sugestoes (texto) VALUES (?)", (texto,))
    conn.commit()
