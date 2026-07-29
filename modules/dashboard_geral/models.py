"""Camada de acesso ao cache próprio (só a saudação gerada por IA). Sem
regra de negócio.

A conexão (`get_connection_propria()`) é compartilhada/cacheada — por isso
nenhuma função aqui chama `conn.close()`.
"""

from database import get_connection_propria, linha_para_dict


def obter_saudacao_mais_recente() -> dict | None:
    conn = get_connection_propria()
    cursor = conn.execute("SELECT * FROM saudacoes ORDER BY gerado_em DESC LIMIT 1")
    return linha_para_dict(cursor, cursor.fetchone())


def salvar_saudacao(texto: str) -> None:
    conn = get_connection_propria()
    conn.execute("INSERT INTO saudacoes (texto) VALUES (?)", (texto,))
    conn.commit()
