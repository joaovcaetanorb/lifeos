"""Camada de acesso a dados (CRUD). Sem lógica de negócio — ver
calculations.py. Mesmo padrão de webapp/momentos/repo.py."""

import pandas as pd

from .db import get_connection, linha_para_dict


def obter_por_semana(semana_inicio: str) -> dict | None:
    conn = get_connection()
    cursor = conn.execute(
        "SELECT * FROM revisoes_semanais WHERE semana_inicio = ?", (semana_inicio,)
    )
    return linha_para_dict(cursor, cursor.fetchone())


def upsert_revisao(
    semana_inicio: str,
    semana_fim: str,
    o_que_funcionou: str,
    o_que_travou: str,
    ajuste_proxima_semana: str,
) -> dict:
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO revisoes_semanais
            (semana_inicio, semana_fim, o_que_funcionou, o_que_travou, ajuste_proxima_semana)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(semana_inicio) DO UPDATE SET
            semana_fim = excluded.semana_fim,
            o_que_funcionou = excluded.o_que_funcionou,
            o_que_travou = excluded.o_que_travou,
            ajuste_proxima_semana = excluded.ajuste_proxima_semana,
            updated_at = CURRENT_TIMESTAMP
        """,
        (semana_inicio, semana_fim, o_que_funcionou, o_que_travou, ajuste_proxima_semana),
    )
    conn.commit()
    return obter_por_semana(semana_inicio)


def listar_revisoes(limite: int = 12) -> pd.DataFrame:
    conn = get_connection()
    query = "SELECT * FROM revisoes_semanais ORDER BY semana_inicio DESC LIMIT ?"
    return pd.read_sql_query(query, conn, params=(limite,))
